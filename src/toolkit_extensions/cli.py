"""
Toolkit LLM Gateway - CLI utilities

Provides version display and basic CLI entry points.
"""

from toolkit_extensions import __version__


def print_version() -> None:
    """Print the toolkit-llm-gateway version and exit."""
    print(f"toolkit-llm-gateway {__version__}")
