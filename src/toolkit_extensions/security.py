"""
Toolkit LLM Gateway - Security Module

Provides security features including:
- Input validation and sanitization
- Rate limiting (sliding window)
- API key management and rotation
- Request/response logging with PII redaction
- Secrets management (environment variable validation)
- CORS configuration
- Security headers
"""

import hashlib
import hmac
import logging
import os
import re
import secrets
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limit configuration"""

    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    requests_per_day: int = 10000
    burst_size: int = 10


@dataclass
class RateLimitState:
    """Rate limit state for a client"""

    minute_requests: List[float] = field(default_factory=list)
    hour_requests: List[float] = field(default_factory=list)
    day_requests: List[float] = field(default_factory=list)


class InputValidator:
    """Validates and sanitizes user input"""

    # Patterns for validation
    EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    API_KEY_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{32,}$")
    UUID_PATTERN = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
    )

    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r"(\bUNION\b.*\bSELECT\b)",
        r"(\bDROP\b.*\bTABLE\b)",
        r"(\bINSERT\b.*\bINTO\b)",
        r"(\bDELETE\b.*\bFROM\b)",
        r"(--)",
        r"(;.*--)",
        r"(\bOR\b.*=.*)",
        r"(\bAND\b.*=.*)",
    ]

    @classmethod
    def validate_email(cls, email: str) -> bool:
        """Validate email format"""
        if not email or len(email) > 255:
            return False
        return bool(cls.EMAIL_PATTERN.match(email))

    @classmethod
    def validate_api_key(cls, api_key: str) -> bool:
        """Validate API key format"""
        if not api_key:
            return False
        return bool(cls.API_KEY_PATTERN.match(api_key))

    @classmethod
    def validate_uuid(cls, uuid_str: str) -> bool:
        """Validate UUID format"""
        if not uuid_str:
            return False
        return bool(cls.UUID_PATTERN.match(uuid_str))

    @classmethod
    def sanitize_string(cls, value: str, max_length: int = 1000) -> str:
        """Sanitize string input"""
        if not isinstance(value, str):
            return ""

        # Truncate to max length
        value = value[:max_length]

        # Remove null bytes
        value = value.replace("\x00", "")

        # Strip whitespace
        value = value.strip()

        return value

    @classmethod
    def check_sql_injection(cls, value: str) -> bool:
        """Check for SQL injection patterns"""
        if not isinstance(value, str):
            return False

        value_upper = value.upper()
        for pattern in cls.SQL_INJECTION_PATTERNS:
            if re.search(pattern, value_upper, re.IGNORECASE):
                return True

        return False

    @classmethod
    def validate_model_name(cls, model: str) -> bool:
        """Validate model name"""
        if not model or len(model) > 100:
            return False

        # Allow alphanumeric, hyphens, underscores, dots, slashes
        pattern = re.compile(r"^[a-zA-Z0-9._/-]+$")
        return bool(pattern.match(model))

    @classmethod
    def validate_numeric_range(
        cls, value: float, min_val: float = 0, max_val: float = float("inf")
    ) -> bool:
        """Validate numeric value is in range"""
        try:
            return min_val <= float(value) <= max_val
        except (ValueError, TypeError):
            return False


class RateLimiter:
    """Rate limiter with sliding window"""

    def __init__(self, config: Optional[RateLimitConfig] = None):
        """Initialize rate limiter"""
        self.config = config or RateLimitConfig()
        self.clients: Dict[str, RateLimitState] = defaultdict(RateLimitState)

    def check_rate_limit(self, client_id: str) -> Dict[str, Any]:
        """
        Check if client is within rate limits

        Returns:
            Dict with 'allowed' (bool) and 'retry_after' (int seconds)
        """
        now = time.time()
        state = self.clients[client_id]

        # Clean old requests
        self._clean_old_requests(state, now)

        # Check limits
        if len(state.minute_requests) >= self.config.requests_per_minute:
            retry_after = int(60 - (now - state.minute_requests[0]))
            return {"allowed": False, "retry_after": retry_after, "reason": "minute_limit"}

        if len(state.hour_requests) >= self.config.requests_per_hour:
            retry_after = int(3600 - (now - state.hour_requests[0]))
            return {"allowed": False, "retry_after": retry_after, "reason": "hour_limit"}

        if len(state.day_requests) >= self.config.requests_per_day:
            retry_after = int(86400 - (now - state.day_requests[0]))
            return {"allowed": False, "retry_after": retry_after, "reason": "day_limit"}

        # Record request
        state.minute_requests.append(now)
        state.hour_requests.append(now)
        state.day_requests.append(now)

        return {"allowed": True, "retry_after": 0}

    def _clean_old_requests(self, state: RateLimitState, now: float):
        """Remove requests outside the time windows"""
        # Keep only last minute
        state.minute_requests = [t for t in state.minute_requests if now - t < 60]

        # Keep only last hour
        state.hour_requests = [t for t in state.hour_requests if now - t < 3600]

        # Keep only last day
        state.day_requests = [t for t in state.day_requests if now - t < 86400]


class APIKeyManager:
    """Manages API key generation, validation, and rotation"""

    @staticmethod
    def generate_api_key(prefix: str = "ak") -> str:
        """Generate a secure API key"""
        random_part = secrets.token_urlsafe(32)
        return f"{prefix}_{random_part}"

    @staticmethod
    def hash_api_key(api_key: str) -> str:
        """Hash API key for storage"""
        return hashlib.sha256(api_key.encode()).hexdigest()

    @staticmethod
    def verify_api_key(api_key: str, key_hash: str) -> bool:
        """Verify API key against stored hash using constant-time comparison."""
        computed = APIKeyManager.hash_api_key(api_key)
        return hmac.compare_digest(computed, key_hash)

    @staticmethod
    def generate_rotation_pair(prefix: str = "ak") -> Dict[str, str]:
        """
        Generate a new API key and its hash for key rotation.

        Returns a dict with 'key' (plaintext, show once) and 'key_hash' (for storage).
        """
        key = APIKeyManager.generate_api_key(prefix=prefix)
        key_hash = APIKeyManager.hash_api_key(key)
        return {"key": key, "key_hash": key_hash, "prefix": key[:12]}

    @staticmethod
    def check_key_strength(api_key: str) -> Dict[str, Any]:
        """
        Evaluate the strength of an API key.

        Returns dict with 'strong' (bool) and 'issues' (list of strings).
        """
        issues: List[str] = []
        if len(api_key) < 32:
            issues.append("Key is shorter than 32 characters")
        if api_key == api_key.lower() or api_key == api_key.upper():
            if not any(c in api_key for c in "-_"):
                issues.append("Key lacks character diversity")
        if re.search(r"(.)\1{4,}", api_key):
            issues.append("Key contains repeated character sequences")
        return {"strong": len(issues) == 0, "issues": issues}


# ---------------------------------------------------------------------------
# PII Redaction
# ---------------------------------------------------------------------------


class PIIRedactor:
    """Redacts personally identifiable information from log messages and payloads."""

    # Patterns for common PII types
    EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
    PHONE_RE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
    SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    CREDIT_CARD_RE = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")
    API_KEY_RE = re.compile(
        r"\b(?:sk-[a-zA-Z0-9]{20,}|sk-ant-[a-zA-Z0-9]{20,}|ak_[a-zA-Z0-9_-]{20,})\b"
    )

    # Keys in dicts that likely contain sensitive data
    SENSITIVE_KEYS: Set[str] = frozenset(
        {
            "password",
            "secret",
            "token",
            "api_key",
            "apikey",
            "authorization",
            "auth",
            "credential",
            "private_key",
            "access_token",
            "refresh_token",
            "ssn",
            "credit_card",
        }
    )

    @classmethod
    def redact_text(cls, text: str) -> str:
        """Redact PII patterns from a string."""
        if not isinstance(text, str):
            return text
        text = cls.SSN_RE.sub("[SSN_REDACTED]", text)
        text = cls.CREDIT_CARD_RE.sub("[CARD_REDACTED]", text)
        text = cls.API_KEY_RE.sub("[KEY_REDACTED]", text)
        text = cls.EMAIL_RE.sub("[EMAIL_REDACTED]", text)
        text = cls.PHONE_RE.sub("[PHONE_REDACTED]", text)
        return text

    @classmethod
    def redact_dict(cls, data: Dict[str, Any], depth: int = 0) -> Dict[str, Any]:
        """
        Recursively redact sensitive values in a dictionary.

        Keys matching SENSITIVE_KEYS are fully masked.
        String values are scanned for PII patterns.
        """
        if depth > 10:
            return data  # prevent infinite recursion
        redacted: Dict[str, Any] = {}
        for key, value in data.items():
            key_lower = key.lower()
            if key_lower in cls.SENSITIVE_KEYS:
                redacted[key] = "[REDACTED]"
            elif isinstance(value, dict):
                redacted[key] = cls.redact_dict(value, depth + 1)
            elif isinstance(value, str):
                redacted[key] = cls.redact_text(value)
            elif isinstance(value, list):
                redacted[key] = [
                    (
                        cls.redact_dict(item, depth + 1)
                        if isinstance(item, dict)
                        else cls.redact_text(item) if isinstance(item, str) else item
                    )
                    for item in value
                ]
            else:
                redacted[key] = value
        return redacted


# ---------------------------------------------------------------------------
# Secrets Management
# ---------------------------------------------------------------------------


class SecretsManager:
    """
    Validates that required secrets are present in the environment
    and that no hardcoded credentials exist in configuration.
    """

    # Patterns that suggest hardcoded credentials
    HARDCODED_PATTERNS = [
        re.compile(r"^password$", re.IGNORECASE),
        re.compile(r"^changeme$", re.IGNORECASE),
        re.compile(r"^secret$", re.IGNORECASE),
        re.compile(r"^default$", re.IGNORECASE),
        re.compile(r"^your[-_]?.*[-_]?here$", re.IGNORECASE),
        re.compile(r"^xxx+$", re.IGNORECASE),
        re.compile(r"^test[-_]?key$", re.IGNORECASE),
    ]

    # Minimum lengths for secret values
    MIN_SECRET_LENGTH = 16

    @classmethod
    def validate_env_secrets(
        cls,
        required_vars: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Validate that required environment secrets are set and not hardcoded defaults.

        Args:
            required_vars: List of env var names to check.
                           Defaults to standard security vars.

        Returns:
            Dict with 'valid' (bool), 'errors' (list), and 'warnings' (list).
        """
        if required_vars is None:
            required_vars = ["SECRET_KEY", "DATABASE_URL"]

        errors: List[str] = []
        warnings: List[str] = []

        for var_name in required_vars:
            value = os.environ.get(var_name)
            if value is None or value.strip() == "":
                errors.append(f"{var_name} is not set")
                continue

            # Check for hardcoded defaults
            if cls._is_hardcoded(value):
                errors.append(f"{var_name} appears to use a hardcoded default value")

            # Check minimum length for secret-like vars
            secret_indicators = {"key", "secret", "token", "password"}
            if any(ind in var_name.lower() for ind in secret_indicators):
                if len(value) < cls.MIN_SECRET_LENGTH:
                    warnings.append(
                        f"{var_name} is shorter than {cls.MIN_SECRET_LENGTH} characters"
                    )

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }

    @classmethod
    def _is_hardcoded(cls, value: str) -> bool:
        """Check if a value looks like a hardcoded default."""
        for pattern in cls.HARDCODED_PATTERNS:
            if pattern.match(value.strip()):
                return True
        return False

    @classmethod
    def mask_value(cls, value: str, visible_chars: int = 4) -> str:
        """
        Mask a secret value for safe logging, showing only the last N characters.

        Example: 'sk-abc123xyz' -> '***xyz'
        """
        if not value or len(value) <= visible_chars:
            return "***"
        return "***" + value[-visible_chars:]


# ---------------------------------------------------------------------------
# Security Headers
# ---------------------------------------------------------------------------

# Standard security headers for HTTP responses
SECURITY_HEADERS: Dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Cache-Control": "no-store, no-cache, must-revalidate",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def get_security_headers(
    include_hsts: bool = True,
    custom_overrides: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """
    Return a copy of security headers with optional overrides.

    Args:
        include_hsts: Whether to include Strict-Transport-Security
                      (disable for non-HTTPS dev environments).
        custom_overrides: Dict of header name -> value to override defaults.

    Returns:
        Dict of header name -> value.
    """
    headers = dict(SECURITY_HEADERS)
    if not include_hsts:
        headers.pop("Strict-Transport-Security", None)
    if custom_overrides:
        headers.update(custom_overrides)
    return headers


# ---------------------------------------------------------------------------
# CORS Configuration
# ---------------------------------------------------------------------------


@dataclass
class CORSConfig:
    """CORS configuration loaded from environment variables."""

    allowed_origins: List[str] = field(default_factory=list)
    allow_credentials: bool = False
    allowed_methods: List[str] = field(
        default_factory=lambda: ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    )
    allowed_headers: List[str] = field(
        default_factory=lambda: ["Authorization", "Content-Type", "X-API-Key"]
    )
    max_age: int = 3600

    @classmethod
    def from_env(cls) -> "CORSConfig":
        """
        Build CORS config from environment variables.

        Reads:
            CORS_ORIGINS - comma-separated origins (default: none / restrictive)
            CORS_ALLOW_CREDENTIALS - 'true' or 'false'
            CORS_MAX_AGE - integer seconds
        """
        origins_str = os.environ.get("CORS_ORIGINS", "")
        origins = [o.strip() for o in origins_str.split(",") if o.strip()] if origins_str else []

        allow_creds = os.environ.get("CORS_ALLOW_CREDENTIALS", "false").lower() == "true"
        max_age = int(os.environ.get("CORS_MAX_AGE", "3600"))

        return cls(
            allowed_origins=origins,
            allow_credentials=allow_creds,
            max_age=max_age,
        )

    def is_origin_allowed(self, origin: str) -> bool:
        """Check if an origin is in the allowed list."""
        if not self.allowed_origins:
            return False
        if "*" in self.allowed_origins:
            return True
        return origin in self.allowed_origins


# ---------------------------------------------------------------------------
# Request Payload Validator (LLM-specific)
# ---------------------------------------------------------------------------


class RequestPayloadValidator:
    """
    Validates LLM completion request payloads.

    Enforces limits on prompt size, message count, and parameter ranges
    to prevent abuse and resource exhaustion.
    """

    DEFAULT_MAX_PROMPT_LENGTH = 100_000  # characters
    DEFAULT_MAX_MESSAGES = 200
    DEFAULT_MAX_TOKENS_LIMIT = 128_000
    VALID_CONTENT_TYPES = frozenset(
        {
            "application/json",
            "application/json; charset=utf-8",
            "application/json;charset=utf-8",
        }
    )

    @classmethod
    def validate_completion_request(
        cls,
        payload: Dict[str, Any],
        max_prompt_length: int = DEFAULT_MAX_PROMPT_LENGTH,
        max_messages: int = DEFAULT_MAX_MESSAGES,
    ) -> Dict[str, Any]:
        """
        Validate a chat/completion request payload.

        Returns dict with 'valid' (bool) and 'errors' (list of strings).
        """
        errors: List[str] = []

        # Model is required
        model = payload.get("model")
        if not model:
            errors.append("'model' is required")
        elif not InputValidator.validate_model_name(str(model)):
            errors.append("'model' contains invalid characters")

        # Messages validation
        messages = payload.get("messages")
        if messages is not None:
            if not isinstance(messages, list):
                errors.append("'messages' must be a list")
            elif len(messages) > max_messages:
                errors.append(f"'messages' count ({len(messages)}) exceeds limit ({max_messages})")
            else:
                total_length = 0
                for i, msg in enumerate(messages):
                    if not isinstance(msg, dict):
                        errors.append(f"messages[{i}] must be a dict")
                        continue
                    role = msg.get("role", "")
                    if role not in ("system", "user", "assistant", "tool", "function"):
                        errors.append(f"messages[{i}] has invalid role: '{role}'")
                    content = msg.get("content", "")
                    if isinstance(content, str):
                        total_length += len(content)

                if total_length > max_prompt_length:
                    errors.append(
                        f"Total prompt length ({total_length}) exceeds "
                        f"limit ({max_prompt_length})"
                    )

        # Temperature range
        temperature = payload.get("temperature")
        if temperature is not None:
            if not InputValidator.validate_numeric_range(temperature, 0.0, 2.0):
                errors.append("'temperature' must be between 0.0 and 2.0")

        # Max tokens
        max_tokens = payload.get("max_tokens")
        if max_tokens is not None:
            if not isinstance(max_tokens, int) or max_tokens < 1:
                errors.append("'max_tokens' must be a positive integer")
            elif max_tokens > cls.DEFAULT_MAX_TOKENS_LIMIT:
                errors.append(
                    f"'max_tokens' ({max_tokens}) exceeds limit "
                    f"({cls.DEFAULT_MAX_TOKENS_LIMIT})"
                )

        # top_p range
        top_p = payload.get("top_p")
        if top_p is not None:
            if not InputValidator.validate_numeric_range(top_p, 0.0, 1.0):
                errors.append("'top_p' must be between 0.0 and 1.0")

        return {"valid": len(errors) == 0, "errors": errors}

    @classmethod
    def validate_content_type(cls, content_type: str) -> bool:
        """Validate that the Content-Type header is acceptable JSON."""
        if not content_type:
            return False
        return content_type.lower().strip() in cls.VALID_CONTENT_TYPES
