"""
Tests for security module
"""

from toolkit_extensions.security import (
    APIKeyManager,
    InputValidator,
    RateLimitConfig,
    RateLimiter,
)


class TestInputValidator:
    """Test input validation"""

    def test_validate_email(self):
        """Test email validation"""
        assert InputValidator.validate_email("user@example.com")
        assert InputValidator.validate_email("test.user+tag@company.co.uk")
        assert not InputValidator.validate_email("invalid")
        assert not InputValidator.validate_email("@example.com")
        assert not InputValidator.validate_email("user@")
        assert not InputValidator.validate_email("")

    def test_validate_api_key(self):
        """Test API key validation"""
        assert InputValidator.validate_api_key("a" * 32)
        assert InputValidator.validate_api_key("abc123_-" * 4)
        assert not InputValidator.validate_api_key("short")
        assert not InputValidator.validate_api_key("")
        assert not InputValidator.validate_api_key("has spaces")

    def test_validate_uuid(self):
        """Test UUID validation"""
        assert InputValidator.validate_uuid("550e8400-e29b-41d4-a716-446655440000")
        assert InputValidator.validate_uuid("550E8400-E29B-41D4-A716-446655440000")
        assert not InputValidator.validate_uuid("invalid-uuid")
        assert not InputValidator.validate_uuid("550e8400-e29b-41d4-a716")
        assert not InputValidator.validate_uuid("")

    def test_sanitize_string(self):
        """Test string sanitization"""
        assert InputValidator.sanitize_string("  hello  ") == "hello"
        assert InputValidator.sanitize_string("test\x00null") == "testnull"
        assert len(InputValidator.sanitize_string("a" * 2000, max_length=100)) == 100
        assert InputValidator.sanitize_string(123) == ""

    def test_check_sql_injection(self):
        """Test SQL injection detection"""
        assert InputValidator.check_sql_injection("SELECT * FROM users WHERE id=1 OR 1=1")
        assert InputValidator.check_sql_injection("'; DROP TABLE users; --")
        assert InputValidator.check_sql_injection("UNION SELECT password FROM users")
        assert not InputValidator.check_sql_injection("normal text")
        assert not InputValidator.check_sql_injection("user@example.com")

    def test_validate_model_name(self):
        """Test model name validation"""
        assert InputValidator.validate_model_name("gpt-4")
        assert InputValidator.validate_model_name("claude-3.5-sonnet")
        assert InputValidator.validate_model_name("openai/gpt-4")
        assert not InputValidator.validate_model_name("")
        assert not InputValidator.validate_model_name("model with spaces")
        assert not InputValidator.validate_model_name("a" * 101)

    def test_validate_numeric_range(self):
        """Test numeric range validation"""
        assert InputValidator.validate_numeric_range(5, 0, 10)
        assert InputValidator.validate_numeric_range(0, 0, 10)
        assert InputValidator.validate_numeric_range(10, 0, 10)
        assert not InputValidator.validate_numeric_range(-1, 0, 10)
        assert not InputValidator.validate_numeric_range(11, 0, 10)
        assert not InputValidator.validate_numeric_range("invalid", 0, 10)


class TestRateLimiter:
    """Test rate limiting"""

    def test_rate_limit_minute(self):
        """Test per-minute rate limiting"""
        config = RateLimitConfig(requests_per_minute=3)
        limiter = RateLimiter(config)

        # First 3 requests should succeed
        for i in range(3):
            result = limiter.check_rate_limit("client1")
            assert result["allowed"], f"Request {i + 1} should be allowed"

        # 4th request should be blocked
        result = limiter.check_rate_limit("client1")
        assert not result["allowed"]
        assert result["retry_after"] > 0
        assert result["reason"] == "minute_limit"

    def test_rate_limit_different_clients(self):
        """Test rate limiting for different clients"""
        config = RateLimitConfig(requests_per_minute=2)
        limiter = RateLimiter(config)

        # Client 1 makes 2 requests
        assert limiter.check_rate_limit("client1")["allowed"]
        assert limiter.check_rate_limit("client1")["allowed"]
        assert not limiter.check_rate_limit("client1")["allowed"]

        # Client 2 should still be allowed
        assert limiter.check_rate_limit("client2")["allowed"]
        assert limiter.check_rate_limit("client2")["allowed"]

    def test_rate_limit_window_sliding(self):
        """Test sliding window behavior"""
        config = RateLimitConfig(requests_per_minute=2)
        limiter = RateLimiter(config)

        # Make 2 requests
        assert limiter.check_rate_limit("client1")["allowed"]
        assert limiter.check_rate_limit("client1")["allowed"]

        # 3rd should be blocked
        assert not limiter.check_rate_limit("client1")["allowed"]

        # Wait a bit and try again (in real scenario, would wait 60s)
        # For testing, we just verify the state is tracked correctly
        state = limiter.clients["client1"]
        assert len(state.minute_requests) == 2


class TestAPIKeyManager:
    """Test API key management"""

    def test_generate_api_key(self):
        """Test API key generation"""
        key1 = APIKeyManager.generate_api_key()
        key2 = APIKeyManager.generate_api_key()

        assert key1.startswith("ak_")
        assert key2.startswith("ak_")
        assert key1 != key2
        assert len(key1) > 32

    def test_generate_api_key_custom_prefix(self):
        """Test API key generation with custom prefix"""
        key = APIKeyManager.generate_api_key(prefix="test")
        assert key.startswith("test_")

    def test_hash_api_key(self):
        """Test API key hashing"""
        key = "test_api_key_12345"
        hash1 = APIKeyManager.hash_api_key(key)
        hash2 = APIKeyManager.hash_api_key(key)

        assert hash1 == hash2
        assert hash1 != key
        assert len(hash1) == 64  # SHA256 hex digest

    def test_verify_api_key(self):
        """Test API key verification"""
        key = "test_api_key_12345"
        key_hash = APIKeyManager.hash_api_key(key)

        assert APIKeyManager.verify_api_key(key, key_hash)
        assert not APIKeyManager.verify_api_key("wrong_key", key_hash)
