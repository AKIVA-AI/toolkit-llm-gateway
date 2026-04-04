"""
Config hierarchy contract for toolkit-llm-gateway.

Three-tier hierarchy (mirrors Akiva platform pattern):
  Level 0 -- Platform defaults (global Akiva CLI conventions)
  Level 1 -- Toolkit config (pyproject.toml / config file)
  Level 2 -- CLI overrides (argv flags)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolkitConfigContract:
    """
    Resolved configuration contract for toolkit-llm-gateway.

    All fields represent resolved values after applying the three-tier
    hierarchy (platform defaults -> toolkit config -> CLI overrides).
    """

    # -- Identity --------------------------------------------------------------
    toolkit_id: str = "TK-GW"
    toolkit_name: str = "toolkit-llm-gateway"
    version: str = "1.1.0"

    # -- Runtime behaviour -----------------------------------------------------
    log_format: str = "json"          # 'json' | 'text'
    structured_logging: bool = True
    output_format: str = "json"       # 'json' | 'text'

    # -- Proxy / gateway -------------------------------------------------------
    host: str = "0.0.0.0"
    port: int = 4000
    num_workers: int = 1

    # -- Cost / budget ---------------------------------------------------------
    cost_tracking_enabled: bool = True
    default_budget_limit: float = 100.0   # USD

    # -- Extension -------------------------------------------------------------
    extra: dict[str, Any] = field(default_factory=dict)


# Config hierarchy levels -- mirrors the TypeScript CONFIG_HIERARCHY_LEVELS pattern
# used in HubZone and Website adapters.
CONFIG_LEVELS = {
    "platform_default": 0,
    "toolkit_config": 1,
    "cli_override": 2,
}


def build_config_hierarchy(
    toolkit_config: dict[str, Any] | None = None,
    cli_overrides: dict[str, Any] | None = None,
) -> ToolkitConfigContract:
    """
    Merge config tiers into a resolved ToolkitConfigContract.

    Priority: CLI overrides > toolkit config > platform defaults.

    Parameters
    ----------
    toolkit_config:
        Values loaded from pyproject.toml [tool.toolkit-llm-gateway]
        or equivalent config file.
    cli_overrides:
        Values parsed from CLI argv (e.g. ``--port 8080``).

    Returns
    -------
    ToolkitConfigContract
        Fully resolved configuration contract.
    """
    # Start with platform defaults
    resolved: dict[str, Any] = {
        "toolkit_id": "TK-GW",
        "toolkit_name": "toolkit-llm-gateway",
        "version": "1.1.0",
        "log_format": "json",
        "structured_logging": True,
        "output_format": "json",
        "host": "0.0.0.0",
        "port": 4000,
        "num_workers": 1,
        "cost_tracking_enabled": True,
        "default_budget_limit": 100.0,
        "extra": {},
    }

    # Layer 1: toolkit config
    if toolkit_config:
        for k, v in toolkit_config.items():
            if k in resolved:
                resolved[k] = v
            else:
                resolved["extra"][k] = v

    # Layer 2: CLI overrides (highest priority)
    if cli_overrides:
        for k, v in cli_overrides.items():
            if k in resolved:
                resolved[k] = v
            else:
                resolved["extra"][k] = v

    return ToolkitConfigContract(**{k: v for k, v in resolved.items()})


__all__ = ["ToolkitConfigContract", "CONFIG_LEVELS", "build_config_hierarchy"]
