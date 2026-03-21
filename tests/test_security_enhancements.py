"""
Tests for security hardening enhancements:
- PII redaction
- Secrets management
- Security headers
- CORS configuration
- Request payload validation
- API key rotation support
- Key strength checking
"""

from __future__ import annotations

import os
from unittest import mock

from toolkit_extensions.security import (
    SECURITY_HEADERS,
    APIKeyManager,
    CORSConfig,
    PIIRedactor,
    RequestPayloadValidator,
    SecretsManager,
    get_security_headers,
)

# ---------------------------------------------------------------------------
# PIIRedactor Tests
# ---------------------------------------------------------------------------


class TestPIIRedactorText:
    """Test PII redaction in plain text."""

    def test_redact_email(self) -> None:
        text = "Contact john.doe@example.com for help"
        result = PIIRedactor.redact_text(text)
        assert "john.doe@example.com" not in result
        assert "[EMAIL_REDACTED]" in result

    def test_redact_multiple_emails(self) -> None:
        text = "From alice@test.com to bob@test.org"
        result = PIIRedactor.redact_text(text)
        assert result.count("[EMAIL_REDACTED]") == 2

    def test_redact_phone_us(self) -> None:
        text = "Call me at 555-123-4567"
        result = PIIRedactor.redact_text(text)
        assert "555-123-4567" not in result
        assert "[PHONE_REDACTED]" in result

    def test_redact_phone_with_parens(self) -> None:
        text = "Phone: (555) 123-4567"
        result = PIIRedactor.redact_text(text)
        assert "[PHONE_REDACTED]" in result

    def test_redact_ssn(self) -> None:
        text = "SSN: 123-45-6789"
        result = PIIRedactor.redact_text(text)
        assert "123-45-6789" not in result
        assert "[SSN_REDACTED]" in result

    def test_redact_credit_card(self) -> None:
        text = "Card: 4111-1111-1111-1111"
        result = PIIRedactor.redact_text(text)
        assert "4111" not in result
        assert "[CARD_REDACTED]" in result

    def test_redact_api_key_openai(self) -> None:
        text = "Using key sk-abcdefghijklmnopqrstuvwx"
        result = PIIRedactor.redact_text(text)
        assert "sk-abcdefghijklmnopqrstuvwx" not in result
        assert "[KEY_REDACTED]" in result

    def test_redact_api_key_anthropic(self) -> None:
        text = "Key: sk-ant-abcdefghijklmnopqrstuvwx"
        result = PIIRedactor.redact_text(text)
        assert "[KEY_REDACTED]" in result

    def test_redact_api_key_toolkit(self) -> None:
        text = "Key: ak_abcdefghijklmnopqrstuvwx"
        result = PIIRedactor.redact_text(text)
        assert "[KEY_REDACTED]" in result

    def test_no_false_positive_normal_text(self) -> None:
        text = "The model performed well on the benchmark"
        result = PIIRedactor.redact_text(text)
        assert result == text

    def test_non_string_passthrough(self) -> None:
        assert PIIRedactor.redact_text(42) == 42  # type: ignore[arg-type]

    def test_empty_string(self) -> None:
        assert PIIRedactor.redact_text("") == ""


class TestPIIRedactorDict:
    """Test PII redaction in dictionaries."""

    def test_redact_sensitive_key(self) -> None:
        data = {"username": "alice", "password": "hunter2"}
        result = PIIRedactor.redact_dict(data)
        assert result["password"] == "[REDACTED]"
        assert result["username"] == "alice"

    def test_redact_nested_sensitive_key(self) -> None:
        data = {"config": {"api_key": "sk-secret", "model": "gpt-4"}}
        result = PIIRedactor.redact_dict(data)
        assert result["config"]["api_key"] == "[REDACTED]"
        assert result["config"]["model"] == "gpt-4"

    def test_redact_email_in_value(self) -> None:
        data = {"message": "Send to user@example.com"}
        result = PIIRedactor.redact_dict(data)
        assert "[EMAIL_REDACTED]" in result["message"]

    def test_redact_list_values(self) -> None:
        data = {"emails": ["alice@test.com", "bob@test.com"]}
        result = PIIRedactor.redact_dict(data)
        assert all("[EMAIL_REDACTED]" == v for v in result["emails"])

    def test_redact_list_of_dicts(self) -> None:
        data = {"users": [{"token": "secret123"}]}
        result = PIIRedactor.redact_dict(data)
        assert result["users"][0]["token"] == "[REDACTED]"

    def test_depth_limit(self) -> None:
        # Build deeply nested dict (> 10 levels)
        inner: dict = {"secret": "value"}
        current = inner
        for _ in range(12):
            current = {"nested": current}
        result = PIIRedactor.redact_dict(current)
        # Should still return without error
        assert isinstance(result, dict)

    def test_numeric_values_preserved(self) -> None:
        data = {"cost": 1.23, "count": 42}
        result = PIIRedactor.redact_dict(data)
        assert result["cost"] == 1.23
        assert result["count"] == 42

    def test_sensitive_key_variants(self) -> None:
        data = {
            "authorization": "Bearer xyz",
            "access_token": "tok_123",
            "refresh_token": "ref_456",
            "credential": "cred_789",
        }
        result = PIIRedactor.redact_dict(data)
        for key in data:
            assert result[key] == "[REDACTED]"


# ---------------------------------------------------------------------------
# SecretsManager Tests
# ---------------------------------------------------------------------------


class TestSecretsManager:
    """Test secrets management and validation."""

    def test_validate_missing_var(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            result = SecretsManager.validate_env_secrets(["SECRET_KEY"])
        assert not result["valid"]
        assert any("SECRET_KEY" in e and "not set" in e for e in result["errors"])

    def test_validate_empty_var(self) -> None:
        with mock.patch.dict(os.environ, {"SECRET_KEY": ""}, clear=True):
            result = SecretsManager.validate_env_secrets(["SECRET_KEY"])
        assert not result["valid"]

    def test_validate_hardcoded_password(self) -> None:
        with mock.patch.dict(os.environ, {"SECRET_KEY": "changeme"}, clear=True):
            result = SecretsManager.validate_env_secrets(["SECRET_KEY"])
        assert not result["valid"]
        assert any("hardcoded" in e for e in result["errors"])

    def test_validate_hardcoded_default(self) -> None:
        with mock.patch.dict(os.environ, {"SECRET_KEY": "your-secret-here"}, clear=True):
            result = SecretsManager.validate_env_secrets(["SECRET_KEY"])
        assert not result["valid"]

    def test_validate_hardcoded_password_word(self) -> None:
        with mock.patch.dict(os.environ, {"SECRET_KEY": "password"}, clear=True):
            result = SecretsManager.validate_env_secrets(["SECRET_KEY"])
        assert not result["valid"]

    def test_validate_good_secret(self) -> None:
        good_secret = "a_reasonably_long_secret_value_here_123"
        with mock.patch.dict(os.environ, {"SECRET_KEY": good_secret}, clear=True):
            result = SecretsManager.validate_env_secrets(["SECRET_KEY"])
        assert result["valid"]

    def test_warn_short_secret(self) -> None:
        with mock.patch.dict(os.environ, {"SECRET_KEY": "short_but_ok"}, clear=True):
            result = SecretsManager.validate_env_secrets(["SECRET_KEY"])
        # Short but not hardcoded -> valid with warning
        assert result["valid"]
        assert len(result["warnings"]) > 0

    def test_non_secret_var_no_length_warning(self) -> None:
        with mock.patch.dict(os.environ, {"DATABASE_URL": "postgresql://localhost/db"}, clear=True):
            result = SecretsManager.validate_env_secrets(["DATABASE_URL"])
        assert result["valid"]
        assert len(result["warnings"]) == 0

    def test_mask_value(self) -> None:
        assert SecretsManager.mask_value("sk-abc123xyz") == "***3xyz"

    def test_mask_short_value(self) -> None:
        assert SecretsManager.mask_value("ab") == "***"

    def test_mask_empty_value(self) -> None:
        assert SecretsManager.mask_value("") == "***"

    def test_mask_custom_visible(self) -> None:
        assert SecretsManager.mask_value("abcdefgh", visible_chars=2) == "***gh"


# ---------------------------------------------------------------------------
# Security Headers Tests
# ---------------------------------------------------------------------------


class TestSecurityHeaders:
    """Test security header configuration."""

    def test_default_headers_present(self) -> None:
        headers = get_security_headers()
        assert "X-Content-Type-Options" in headers
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert "X-Frame-Options" in headers
        assert headers["X-Frame-Options"] == "DENY"
        assert "X-XSS-Protection" in headers
        assert "Strict-Transport-Security" in headers
        assert "Referrer-Policy" in headers
        assert "Cache-Control" in headers
        assert "Permissions-Policy" in headers

    def test_hsts_excluded(self) -> None:
        headers = get_security_headers(include_hsts=False)
        assert "Strict-Transport-Security" not in headers
        # Other headers should still be present
        assert "X-Frame-Options" in headers

    def test_custom_overrides(self) -> None:
        headers = get_security_headers(
            custom_overrides={"X-Frame-Options": "SAMEORIGIN", "X-Custom": "value"}
        )
        assert headers["X-Frame-Options"] == "SAMEORIGIN"
        assert headers["X-Custom"] == "value"

    def test_returns_copy(self) -> None:
        headers1 = get_security_headers()
        headers2 = get_security_headers()
        headers1["X-Frame-Options"] = "CHANGED"
        assert headers2["X-Frame-Options"] == "DENY"
        # Also verify the module-level constant is untouched
        assert SECURITY_HEADERS["X-Frame-Options"] == "DENY"


# ---------------------------------------------------------------------------
# CORSConfig Tests
# ---------------------------------------------------------------------------


class TestCORSConfig:
    """Test CORS configuration."""

    def test_default_config(self) -> None:
        config = CORSConfig()
        assert config.allowed_origins == []
        assert config.allow_credentials is False
        assert "GET" in config.allowed_methods
        assert "POST" in config.allowed_methods
        assert config.max_age == 3600

    def test_from_env_with_origins(self) -> None:
        env = {"CORS_ORIGINS": "https://app.example.com,https://admin.example.com"}
        with mock.patch.dict(os.environ, env, clear=True):
            config = CORSConfig.from_env()
        assert len(config.allowed_origins) == 2
        assert "https://app.example.com" in config.allowed_origins

    def test_from_env_empty_origins(self) -> None:
        with mock.patch.dict(os.environ, {"CORS_ORIGINS": ""}, clear=True):
            config = CORSConfig.from_env()
        assert config.allowed_origins == []

    def test_from_env_no_origins_var(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            config = CORSConfig.from_env()
        assert config.allowed_origins == []

    def test_from_env_credentials(self) -> None:
        env = {"CORS_ALLOW_CREDENTIALS": "true"}
        with mock.patch.dict(os.environ, env, clear=True):
            config = CORSConfig.from_env()
        assert config.allow_credentials is True

    def test_from_env_max_age(self) -> None:
        env = {"CORS_MAX_AGE": "7200"}
        with mock.patch.dict(os.environ, env, clear=True):
            config = CORSConfig.from_env()
        assert config.max_age == 7200

    def test_is_origin_allowed_match(self) -> None:
        config = CORSConfig(allowed_origins=["https://app.example.com"])
        assert config.is_origin_allowed("https://app.example.com")

    def test_is_origin_allowed_no_match(self) -> None:
        config = CORSConfig(allowed_origins=["https://app.example.com"])
        assert not config.is_origin_allowed("https://evil.com")

    def test_is_origin_allowed_wildcard(self) -> None:
        config = CORSConfig(allowed_origins=["*"])
        assert config.is_origin_allowed("https://anything.com")

    def test_is_origin_allowed_empty(self) -> None:
        config = CORSConfig(allowed_origins=[])
        assert not config.is_origin_allowed("https://anything.com")


# ---------------------------------------------------------------------------
# RequestPayloadValidator Tests
# ---------------------------------------------------------------------------


class TestRequestPayloadValidator:
    """Test LLM request payload validation."""

    def test_valid_completion_request(self) -> None:
        payload = {
            "model": "gpt-4",
            "messages": [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Hello"},
            ],
            "temperature": 0.7,
            "max_tokens": 1000,
        }
        result = RequestPayloadValidator.validate_completion_request(payload)
        assert result["valid"]
        assert result["errors"] == []

    def test_missing_model(self) -> None:
        payload = {"messages": [{"role": "user", "content": "Hi"}]}
        result = RequestPayloadValidator.validate_completion_request(payload)
        assert not result["valid"]
        assert any("model" in e for e in result["errors"])

    def test_invalid_model_name(self) -> None:
        payload = {"model": "invalid model name with spaces"}
        result = RequestPayloadValidator.validate_completion_request(payload)
        assert not result["valid"]

    def test_messages_not_a_list(self) -> None:
        payload = {"model": "gpt-4", "messages": "not a list"}
        result = RequestPayloadValidator.validate_completion_request(payload)
        assert not result["valid"]
        assert any("list" in e for e in result["errors"])

    def test_too_many_messages(self) -> None:
        messages = [{"role": "user", "content": "hi"}] * 201
        payload = {"model": "gpt-4", "messages": messages}
        result = RequestPayloadValidator.validate_completion_request(payload)
        assert not result["valid"]
        assert any("exceeds limit" in e for e in result["errors"])

    def test_custom_max_messages(self) -> None:
        messages = [{"role": "user", "content": "hi"}] * 5
        payload = {"model": "gpt-4", "messages": messages}
        result = RequestPayloadValidator.validate_completion_request(payload, max_messages=3)
        assert not result["valid"]

    def test_invalid_role(self) -> None:
        payload = {
            "model": "gpt-4",
            "messages": [{"role": "hacker", "content": "hi"}],
        }
        result = RequestPayloadValidator.validate_completion_request(payload)
        assert not result["valid"]
        assert any("invalid role" in e for e in result["errors"])

    def test_valid_roles(self) -> None:
        for role in ("system", "user", "assistant", "tool", "function"):
            payload = {
                "model": "gpt-4",
                "messages": [{"role": role, "content": "test"}],
            }
            result = RequestPayloadValidator.validate_completion_request(payload)
            assert result["valid"], f"Role '{role}' should be valid"

    def test_prompt_too_long(self) -> None:
        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "x" * 200_000}],
        }
        result = RequestPayloadValidator.validate_completion_request(payload)
        assert not result["valid"]
        assert any("prompt length" in e.lower() for e in result["errors"])

    def test_temperature_out_of_range(self) -> None:
        payload = {"model": "gpt-4", "temperature": 3.0}
        result = RequestPayloadValidator.validate_completion_request(payload)
        assert not result["valid"]

    def test_temperature_negative(self) -> None:
        payload = {"model": "gpt-4", "temperature": -0.1}
        result = RequestPayloadValidator.validate_completion_request(payload)
        assert not result["valid"]

    def test_max_tokens_negative(self) -> None:
        payload = {"model": "gpt-4", "max_tokens": -1}
        result = RequestPayloadValidator.validate_completion_request(payload)
        assert not result["valid"]

    def test_max_tokens_too_large(self) -> None:
        payload = {"model": "gpt-4", "max_tokens": 999_999}
        result = RequestPayloadValidator.validate_completion_request(payload)
        assert not result["valid"]

    def test_top_p_out_of_range(self) -> None:
        payload = {"model": "gpt-4", "top_p": 1.5}
        result = RequestPayloadValidator.validate_completion_request(payload)
        assert not result["valid"]

    def test_message_item_not_dict(self) -> None:
        payload = {"model": "gpt-4", "messages": ["not a dict"]}
        result = RequestPayloadValidator.validate_completion_request(payload)
        assert not result["valid"]
        assert any("dict" in e for e in result["errors"])

    def test_no_messages_is_ok(self) -> None:
        """Some APIs allow prompt-only (no messages)."""
        payload = {"model": "gpt-4"}
        result = RequestPayloadValidator.validate_completion_request(payload)
        assert result["valid"]

    def test_validate_content_type_json(self) -> None:
        assert RequestPayloadValidator.validate_content_type("application/json")

    def test_validate_content_type_json_charset(self) -> None:
        assert RequestPayloadValidator.validate_content_type(
            "application/json; charset=utf-8"
        )

    def test_validate_content_type_text_plain(self) -> None:
        assert not RequestPayloadValidator.validate_content_type("text/plain")

    def test_validate_content_type_empty(self) -> None:
        assert not RequestPayloadValidator.validate_content_type("")

    def test_validate_content_type_case_insensitive(self) -> None:
        assert RequestPayloadValidator.validate_content_type("Application/JSON")


# ---------------------------------------------------------------------------
# APIKeyManager Enhancement Tests
# ---------------------------------------------------------------------------


class TestAPIKeyRotation:
    """Test API key rotation and strength checking."""

    def test_generate_rotation_pair(self) -> None:
        pair = APIKeyManager.generate_rotation_pair()
        assert "key" in pair
        assert "key_hash" in pair
        assert "prefix" in pair
        assert pair["key"].startswith("ak_")
        assert len(pair["key_hash"]) == 64
        # Verify the hash matches
        assert APIKeyManager.verify_api_key(pair["key"], pair["key_hash"])

    def test_generate_rotation_pair_custom_prefix(self) -> None:
        pair = APIKeyManager.generate_rotation_pair(prefix="prod")
        assert pair["key"].startswith("prod_")

    def test_check_key_strength_strong(self) -> None:
        key = APIKeyManager.generate_api_key()
        result = APIKeyManager.check_key_strength(key)
        assert result["strong"]
        assert result["issues"] == []

    def test_check_key_strength_too_short(self) -> None:
        result = APIKeyManager.check_key_strength("short")
        assert not result["strong"]
        assert any("shorter" in issue for issue in result["issues"])

    def test_check_key_strength_repeated(self) -> None:
        result = APIKeyManager.check_key_strength("a" * 40)
        assert not result["strong"]
        assert any("repeated" in issue for issue in result["issues"])
