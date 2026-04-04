"""
CLI command -> ToolSpec mapping for toolkit-llm-gateway.

Maps the key CLI commands (start, validate-config, health-check, version)
to ToolSpec contracts with appropriate permission scope and approval policy.

'start' requires FULL_ACCESS + REQUIRE_APPROVAL (starts a long-running proxy
server that binds a port and proxies external API calls).
Read-only / diagnostic commands (validate-config, health-check, version) are
READ_ONLY + AUTO.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import ApprovalPolicy, AuthorityBoundary, PermissionScope, ToolSpec


@dataclass
class ToolkitCommandSpec:
    """Maps a CLI subcommand name to its ToolSpec and authority boundary."""

    command: str
    spec: ToolSpec
    boundary: AuthorityBoundary


def _make_spec(
    name: str,
    description: str,
    scope: PermissionScope = PermissionScope.READ_ONLY,
    input_schema: dict[str, Any] | None = None,
) -> ToolSpec:
    """Create a ToolSpec for a CLI command."""
    return ToolSpec(
        name=name,
        description=description,
        category="tool",
        version="1.1.0",
        owner="toolkit-llm-gateway",
        permission_scope=scope,
        input_schema=input_schema,
        output_schema=None,
        sandbox_requirement=None,
        aliases=None,
    )


_READ_ONLY_AUTO = AuthorityBoundary(
    scope=PermissionScope.READ_ONLY,
    approval=ApprovalPolicy.AUTO,
)

_FULL_APPROVE = AuthorityBoundary(
    scope=PermissionScope.FULL_ACCESS,
    approval=ApprovalPolicy.REQUIRE_APPROVAL,
)

# -- Per-command specs ---------------------------------------------------------

TOOLKIT_TOOL_SPECS: dict[str, ToolkitCommandSpec] = {
    "start": ToolkitCommandSpec(
        command="start",
        spec=_make_spec(
            name="start",
            description=(
                "Start the LLM proxy gateway server (binds port, proxies external "
                "API calls). Requires explicit approval before execution."
            ),
            scope=PermissionScope.FULL_ACCESS,
            input_schema={
                "type": "object",
                "properties": {
                    "host": {"type": "string", "description": "Bind host"},
                    "port": {"type": "integer", "description": "Bind port (default 4000)"},
                    "num_workers": {"type": "integer"},
                    "config": {"type": "string", "description": "Path to config YAML"},
                },
            },
        ),
        boundary=_FULL_APPROVE,
    ),
    "validate-config": ToolkitCommandSpec(
        command="validate-config",
        spec=_make_spec(
            name="validate_config",
            description=(
                "Validate a gateway config file. Read-only; reports errors to stdout."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "config": {"type": "string", "description": "Path to config YAML"},
                    "format": {"type": "string", "enum": ["json", "text"]},
                },
                "required": ["config"],
            },
        ),
        boundary=_READ_ONLY_AUTO,
    ),
    "health-check": ToolkitCommandSpec(
        command="health-check",
        spec=_make_spec(
            name="health_check",
            description=(
                "Check the health of a running gateway instance. Read-only."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "host": {"type": "string"},
                    "port": {"type": "integer"},
                },
            },
        ),
        boundary=_READ_ONLY_AUTO,
    ),
    "version": ToolkitCommandSpec(
        command="version",
        spec=_make_spec(
            name="version",
            description="Print the toolkit-llm-gateway version string.",
        ),
        boundary=_READ_ONLY_AUTO,
    ),
}


def get_tool_spec(command: str) -> ToolkitCommandSpec | None:
    """Return the ToolkitCommandSpec for a CLI subcommand, or None if unknown."""
    return TOOLKIT_TOOL_SPECS.get(command)


__all__ = ["TOOLKIT_TOOL_SPECS", "ToolkitCommandSpec", "get_tool_spec"]
