"""
Tests for toolkit-llm-gateway control_plane adapter.

Coverage:
  - contracts: PermissionScope ordinal, AuthorityBoundary helpers
  - config: build_config_hierarchy (platform defaults, overrides, CLI)
  - tool_specs: TOOLKIT_TOOL_SPECS covers all 4 commands, get_tool_spec lookup
  - Optional framework import: _HAS_EXECUTION_CONTRACTS flag is a bool (no crash)
"""
from __future__ import annotations

from toolkit_extensions.control_plane.contracts import (
    ApprovalPolicy,
    AuthorityBoundary,
    PermissionScope,
    ToolSpec,
    _HAS_EXECUTION_CONTRACTS,
)
from toolkit_extensions.control_plane.config import (
    CONFIG_LEVELS,
    ToolkitConfigContract,
    build_config_hierarchy,
)
from toolkit_extensions.control_plane.tool_specs import (
    TOOLKIT_TOOL_SPECS,
    get_tool_spec,
)


# -- contracts ----------------------------------------------------------------


class TestPermissionScope:
    def test_values_are_strings(self) -> None:
        assert PermissionScope.READ_ONLY.value == "read_only"
        assert PermissionScope.WORKSPACE_WRITE.value == "workspace_write"
        assert PermissionScope.FULL_ACCESS.value == "full_access"

    def test_ordinal_ascending(self) -> None:
        boundary = AuthorityBoundary(scope=PermissionScope.FULL_ACCESS, approval=ApprovalPolicy.AUTO)
        assert boundary.scope_allows(PermissionScope.READ_ONLY)

    def test_lower_does_not_satisfy_higher(self) -> None:
        boundary = AuthorityBoundary(scope=PermissionScope.READ_ONLY, approval=ApprovalPolicy.AUTO)
        assert not boundary.scope_allows(PermissionScope.WORKSPACE_WRITE)
        assert not boundary.scope_allows(PermissionScope.FULL_ACCESS)


class TestApprovalPolicy:
    def test_values_are_strings(self) -> None:
        assert ApprovalPolicy.AUTO.value == "auto"
        assert ApprovalPolicy.REQUIRE_APPROVAL.value == "require_approval"
        assert ApprovalPolicy.DENY.value == "deny"


class TestAuthorityBoundary:
    def test_is_denied(self) -> None:
        b = AuthorityBoundary(scope=PermissionScope.READ_ONLY, approval=ApprovalPolicy.DENY)
        assert b.is_denied()
        assert not b.needs_approval()

    def test_needs_approval(self) -> None:
        b = AuthorityBoundary(scope=PermissionScope.FULL_ACCESS, approval=ApprovalPolicy.REQUIRE_APPROVAL)
        assert b.needs_approval()
        assert not b.is_denied()

    def test_auto_neither(self) -> None:
        b = AuthorityBoundary(scope=PermissionScope.WORKSPACE_WRITE, approval=ApprovalPolicy.AUTO)
        assert not b.is_denied()
        assert not b.needs_approval()

    def test_sandbox_defaults_none(self) -> None:
        b = AuthorityBoundary(scope=PermissionScope.READ_ONLY, approval=ApprovalPolicy.AUTO)
        assert b.sandbox is None


class TestToolSpec:
    def test_construction(self) -> None:
        spec = ToolSpec(
            name="validate_config",
            description="test",
            category="tool",
            version="1.1.0",
            owner="toolkit-llm-gateway",
            permission_scope=PermissionScope.READ_ONLY,
        )
        assert spec.name == "validate_config"
        assert spec.permission_scope == PermissionScope.READ_ONLY
        assert spec.input_schema is None
        assert spec.aliases is None

    def test_repr_contains_name(self) -> None:
        spec = ToolSpec(
            name="start",
            description="test",
            category="tool",
            version="1.1.0",
            owner="o",
            permission_scope=PermissionScope.FULL_ACCESS,
        )
        assert "start" in repr(spec)


class TestFrameworkFlag:
    def test_flag_is_bool(self) -> None:
        assert isinstance(_HAS_EXECUTION_CONTRACTS, bool)


# -- config -------------------------------------------------------------------


class TestConfigLevels:
    def test_ordering(self) -> None:
        assert CONFIG_LEVELS["platform_default"] < CONFIG_LEVELS["toolkit_config"]
        assert CONFIG_LEVELS["toolkit_config"] < CONFIG_LEVELS["cli_override"]


class TestBuildConfigHierarchy:
    def test_defaults(self) -> None:
        cfg = build_config_hierarchy()
        assert cfg.toolkit_id == "TK-GW"
        assert cfg.toolkit_name == "toolkit-llm-gateway"
        assert cfg.log_format == "json"
        assert cfg.structured_logging is True
        assert cfg.port == 4000
        assert cfg.cost_tracking_enabled is True

    def test_toolkit_config_overrides_defaults(self) -> None:
        cfg = build_config_hierarchy(toolkit_config={"port": 8080, "log_format": "text"})
        assert cfg.port == 8080
        assert cfg.log_format == "text"
        assert cfg.toolkit_id == "TK-GW"

    def test_cli_overrides_toolkit_config(self) -> None:
        cfg = build_config_hierarchy(
            toolkit_config={"port": 8080},
            cli_overrides={"port": 9090},
        )
        assert cfg.port == 9090

    def test_unknown_keys_go_to_extra(self) -> None:
        cfg = build_config_hierarchy(toolkit_config={"custom_flag": True})
        assert cfg.extra.get("custom_flag") is True

    def test_cli_unknown_keys_go_to_extra(self) -> None:
        cfg = build_config_hierarchy(cli_overrides={"verbose": True})
        assert cfg.extra.get("verbose") is True

    def test_returns_toolkit_config_contract(self) -> None:
        cfg = build_config_hierarchy()
        assert isinstance(cfg, ToolkitConfigContract)


# -- tool_specs ---------------------------------------------------------------


class TestToolkitToolSpecs:
    def test_all_four_commands_present(self) -> None:
        expected = {"start", "validate-config", "health-check", "version"}
        assert set(TOOLKIT_TOOL_SPECS.keys()) == expected

    def test_start_is_full_access(self) -> None:
        spec = TOOLKIT_TOOL_SPECS["start"]
        assert spec.spec.permission_scope == PermissionScope.FULL_ACCESS
        assert spec.boundary.approval == ApprovalPolicy.REQUIRE_APPROVAL

    def test_read_only_commands_are_auto(self) -> None:
        for cmd in ("validate-config", "health-check", "version"):
            s = TOOLKIT_TOOL_SPECS[cmd]
            assert s.spec.permission_scope == PermissionScope.READ_ONLY
            assert s.boundary.approval == ApprovalPolicy.AUTO

    def test_boundary_scope_matches_spec_scope(self) -> None:
        for name, cmd_spec in TOOLKIT_TOOL_SPECS.items():
            assert cmd_spec.boundary.scope == cmd_spec.spec.permission_scope, name

    def test_no_sandbox_required(self) -> None:
        for name, cmd_spec in TOOLKIT_TOOL_SPECS.items():
            assert cmd_spec.spec.sandbox_requirement is None, name

    def test_validate_config_has_input_schema(self) -> None:
        schema = TOOLKIT_TOOL_SPECS["validate-config"].spec.input_schema
        assert schema is not None
        assert "config" in schema.get("required", [])

    def test_command_name_matches_key(self) -> None:
        for key, cmd_spec in TOOLKIT_TOOL_SPECS.items():
            assert cmd_spec.command == key

    def test_owner_is_toolkit(self) -> None:
        for cmd_spec in TOOLKIT_TOOL_SPECS.values():
            assert cmd_spec.spec.owner == "toolkit-llm-gateway"


class TestGetToolSpec:
    def test_returns_spec_for_known_command(self) -> None:
        spec = get_tool_spec("start")
        assert spec is not None
        assert spec.command == "start"

    def test_returns_none_for_unknown_command(self) -> None:
        assert get_tool_spec("nonexistent") is None

    def test_returns_none_for_empty_string(self) -> None:
        assert get_tool_spec("") is None
