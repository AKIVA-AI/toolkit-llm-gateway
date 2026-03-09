"""
Tests for configuration validator module
"""

import os

import pytest

from toolkit_extensions.config_validator import (
    ConfigLevel,
    ConfigValidator,
    ConfigVar,
    validate_config,
)


def test_validate_required_missing(monkeypatch):
    """Test that missing REQUIRED var produces error."""
    monkeypatch.delenv("DATABASE_URL", raising=False)

    validator = ConfigValidator(strict=False)
    is_valid, messages = validator.validate()

    assert not is_valid
    assert any("DATABASE_URL" in e for e in messages["errors"])


def test_validate_required_present(monkeypatch):
    """Test that present REQUIRED var passes."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")

    validator = ConfigValidator(strict=False)
    is_valid, messages = validator.validate()

    assert is_valid


def test_validate_recommended_missing(monkeypatch):
    """Test that missing RECOMMENDED var produces warning."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    validator = ConfigValidator(strict=False)
    is_valid, messages = validator.validate()

    # Should be valid (recommended is not required in non-strict)
    assert is_valid
    assert any("OPENAI_API_KEY" in w for w in messages["warnings"])


def test_validate_strict_mode(monkeypatch):
    """Test that strict mode treats RECOMMENDED as REQUIRED."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)

    validator = ConfigValidator(strict=True)
    is_valid, messages = validator.validate()

    assert not is_valid


def test_validate_invalid_value(monkeypatch):
    """Test that invalid value produces error."""
    monkeypatch.setenv("DATABASE_URL", "not-a-valid-url")

    validator = ConfigValidator(strict=False)
    is_valid, messages = validator.validate()

    assert not is_valid
    assert any("DATABASE_URL" in e for e in messages["errors"])


def test_validate_port_validation(monkeypatch):
    """Test PORT validator."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")
    monkeypatch.setenv("PORT", "99999")

    validator = ConfigValidator(strict=False)
    is_valid, messages = validator.validate()

    assert any("PORT" in e for e in messages["errors"])


def test_validate_port_valid(monkeypatch):
    """Test PORT validator with valid port."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")
    monkeypatch.setenv("PORT", "8080")

    validator = ConfigValidator(strict=False)
    is_valid, messages = validator.validate()

    # PORT error should not appear
    assert not any("PORT" in e for e in messages["errors"])


def test_validate_log_level(monkeypatch):
    """Test LOG_LEVEL validator."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")
    monkeypatch.setenv("LOG_LEVEL", "INVALID")

    validator = ConfigValidator(strict=False)
    is_valid, messages = validator.validate()

    assert any("LOG_LEVEL" in e for e in messages["errors"])


def test_print_report(monkeypatch, capsys):
    """Test print_report outputs something."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")

    validator = ConfigValidator(strict=False)
    _, messages = validator.validate()
    validator.print_report(messages)

    captured = capsys.readouterr()
    assert "Configuration Validation Report" in captured.out


def test_validate_config_no_exit(monkeypatch):
    """Test validate_config with exit_on_error=False."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")

    result = validate_config(strict=False, exit_on_error=False)
    assert isinstance(result, bool)


def test_optional_missing_produces_info(monkeypatch):
    """Test that missing OPTIONAL var produces info."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")
    monkeypatch.delenv("REDIS_URL", raising=False)

    validator = ConfigValidator(strict=False)
    _, messages = validator.validate()

    assert any("REDIS_URL" in i for i in messages["info"])
