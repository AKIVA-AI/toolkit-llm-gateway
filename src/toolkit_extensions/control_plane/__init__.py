"""
Control-plane adapter for toolkit-llm-gateway.

Language-portability proof (2026-04-03):
These Python contracts are structurally equivalent to the TypeScript interfaces
in BIOS / ADII / HubZone control-plane-types.ts.  Field shapes, enum values,
and helper-function semantics are preserved across languages.

Toolkit-llm-gateway is an Archetype 9 CLI tool (TK-GW).  The control-plane
contract here covers:
  - Config hierarchy (global defaults -> toolkit config -> CLI overrides)
  - CLI command -> ToolSpec mapping for start, validate-config, health-check, version
  - Optional import from akiva_execution_contracts / akiva_policy_runtime
    (graceful no-op when the framework is not installed)
"""

from .config import ToolkitConfigContract, build_config_hierarchy
from .tool_specs import (
    TOOLKIT_TOOL_SPECS,
    get_tool_spec,
    ToolkitCommandSpec,
)
from .contracts import (
    PermissionScope,
    ApprovalPolicy,
    AuthorityBoundary,
    ToolSpec as CPToolSpec,
    _HAS_EXECUTION_CONTRACTS,
)

__all__ = [
    # config
    "ToolkitConfigContract",
    "build_config_hierarchy",
    # tool specs
    "TOOLKIT_TOOL_SPECS",
    "get_tool_spec",
    "ToolkitCommandSpec",
    # contracts
    "PermissionScope",
    "ApprovalPolicy",
    "AuthorityBoundary",
    "CPToolSpec",
    "_HAS_EXECUTION_CONTRACTS",
]
