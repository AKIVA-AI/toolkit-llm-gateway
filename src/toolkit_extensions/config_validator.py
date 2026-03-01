"""
Toolkit LLM Gateway - Configuration Validator

Validates all required environment variables and configuration on startup.
Provides clear error messages for missing or invalid configuration.
"""

import os
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple


class ConfigLevel(Enum):
    """Configuration requirement levels"""

    REQUIRED = "required"  # Must be set for basic operation
    RECOMMENDED = "recommended"  # Should be set for production
    OPTIONAL = "optional"  # Nice to have


@dataclass
class ConfigVar:
    """Configuration variable definition"""

    name: str
    level: ConfigLevel
    description: str
    default: Optional[str] = None
    validator: Optional[callable] = None


class ConfigValidator:
    """Validates environment configuration for Toolkit LLM Gateway"""

    # Define all configuration variables
    CONFIG_VARS = [
        # Database Configuration (REQUIRED)
        ConfigVar(
            name="DATABASE_URL",
            level=ConfigLevel.REQUIRED,
            description="PostgreSQL connection string (e.g., postgresql://user:pass@localhost:5432/dbname)",
            validator=lambda v: v.startswith(("postgresql://", "sqlite://", "mysql://")),
        ),
        # Server Configuration (RECOMMENDED)
        ConfigVar(
            name="HOST",
            level=ConfigLevel.RECOMMENDED,
            description="Server host address",
            default="0.0.0.0",
        ),
        ConfigVar(
            name="PORT",
            level=ConfigLevel.RECOMMENDED,
            description="Server port number",
            default="12000",
            validator=lambda v: v.isdigit() and 1 <= int(v) <= 65535,
        ),
        # LLM Provider API Keys (RECOMMENDED)
        ConfigVar(
            name="OPENAI_API_KEY",
            level=ConfigLevel.RECOMMENDED,
            description="OpenAI API key for GPT models",
        ),
        ConfigVar(
            name="ANTHROPIC_API_KEY",
            level=ConfigLevel.RECOMMENDED,
            description="Anthropic API key for Claude models",
        ),
        # Cost Tracking (RECOMMENDED)
        ConfigVar(
            name="ENABLE_COST_TRACKING",
            level=ConfigLevel.RECOMMENDED,
            description="Enable cost tracking features",
            default="true",
            validator=lambda v: v.lower() in ("true", "false", "1", "0"),
        ),
        # Security (RECOMMENDED)
        ConfigVar(
            name="SECRET_KEY",
            level=ConfigLevel.RECOMMENDED,
            description="Secret key for signing webhooks and sessions",
        ),
        # Dashboard Security (RECOMMENDED)
        ConfigVar(
            name="DASHBOARD_API_KEY",
            level=ConfigLevel.RECOMMENDED,
            description="API key for authenticating dashboard /api/* requests. If unset, dashboard runs without auth.",
        ),
        # Optional Features
        ConfigVar(
            name="REDIS_URL",
            level=ConfigLevel.OPTIONAL,
            description="Redis connection string for caching",
        ),
        ConfigVar(
            name="LOG_LEVEL",
            level=ConfigLevel.OPTIONAL,
            description="Logging level (DEBUG, INFO, WARNING, ERROR)",
            default="INFO",
            validator=lambda v: v.upper() in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        ),
    ]

    def __init__(self, strict: bool = False):
        """
        Initialize validator

        Args:
            strict: If True, treat RECOMMENDED as REQUIRED
        """
        self.strict = strict
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []

    def validate(self) -> Tuple[bool, Dict[str, List[str]]]:
        """
        Validate all configuration variables

        Returns:
            Tuple of (is_valid, messages_dict)
        """
        self.errors = []
        self.warnings = []
        self.info = []

        for config_var in self.CONFIG_VARS:
            self._validate_var(config_var)

        is_valid = len(self.errors) == 0

        messages = {"errors": self.errors, "warnings": self.warnings, "info": self.info}

        return is_valid, messages

    def _validate_var(self, config_var: ConfigVar):
        """Validate a single configuration variable"""
        value = os.getenv(config_var.name)

        # Check if variable is set
        if value is None or value.strip() == "":
            if config_var.level == ConfigLevel.REQUIRED or (
                self.strict and config_var.level == ConfigLevel.RECOMMENDED
            ):
                self.errors.append(
                    f"âŒ {config_var.name} is {config_var.level.value} but not set. "
                    f"{config_var.description}"
                )
            elif config_var.level == ConfigLevel.RECOMMENDED:
                self.warnings.append(
                    f"âš ï¸  {config_var.name} is recommended but not set. "
                    f"{config_var.description}"
                )
            else:
                self.info.append(
                    f"â„¹ï¸  {config_var.name} is optional and not set. "
                    f"Default: {config_var.default or 'None'}"
                )
            return

        # Validate value if validator provided
        if config_var.validator:
            try:
                if not config_var.validator(value):
                    self.errors.append(
                        f"âŒ {config_var.name} has invalid value: '{value}'. "
                        f"{config_var.description}"
                    )
            except Exception as e:
                self.errors.append(f"âŒ {config_var.name} validation failed: {str(e)}")

    def print_report(self, messages: Dict[str, List[str]]):
        """Print validation report to console"""
        print("\n" + "=" * 70)
        print("ðŸ” Toolkit LLM Gateway - Configuration Validation Report")
        print("=" * 70 + "\n")

        if messages["errors"]:
            print("âŒ ERRORS (Must Fix):")
            for error in messages["errors"]:
                print(f"  {error}")
            print()

        if messages["warnings"]:
            print("âš ï¸  WARNINGS (Recommended):")
            for warning in messages["warnings"]:
                print(f"  {warning}")
            print()

        if messages["info"]:
            print("â„¹ï¸  INFO:")
            for info in messages["info"]:
                print(f"  {info}")
            print()

        print("=" * 70 + "\n")


def validate_config(strict: bool = False, exit_on_error: bool = True) -> bool:
    """
    Validate configuration and optionally exit on error

    Args:
        strict: Treat RECOMMENDED as REQUIRED
        exit_on_error: Exit with code 1 if validation fails

    Returns:
        True if valid, False otherwise
    """
    validator = ConfigValidator(strict=strict)
    is_valid, messages = validator.validate()
    validator.print_report(messages)

    if not is_valid and exit_on_error:
        print("âŒ Configuration validation failed. Please fix the errors above.")
        sys.exit(1)

    return is_valid


if __name__ == "__main__":
    # Run validation when executed directly
    import argparse

    parser = argparse.ArgumentParser(description="Validate Toolkit LLM Gateway configuration")
    parser.add_argument("--strict", action="store_true", help="Treat recommended as required")
    parser.add_argument("--no-exit", action="store_true", help="Don't exit on error")

    args = parser.parse_args()

    validate_config(strict=args.strict, exit_on_error=not args.no_exit)
