"""
Tests for version and CLI utilities
"""

from toolkit_extensions import __version__
from toolkit_extensions.cli import print_version


def test_version_is_set():
    """Test that __version__ is a non-empty string."""
    assert __version__
    assert isinstance(__version__, str)
    assert "." in __version__


def test_version_is_1_1_0():
    """Test that version was bumped correctly."""
    assert __version__ == "1.1.0"


def test_print_version(capsys):
    """Test that print_version outputs the version."""
    print_version()
    captured = capsys.readouterr()
    assert "toolkit-llm-gateway" in captured.out
    assert __version__ in captured.out
