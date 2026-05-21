"""
Tests for token-bucket rate limiter
"""

import time

import pytest

from toolkit_extensions.rate_limiter import (
    RateLimitExceeded,
    TokenBucket,
    TokenBucketRateLimiter,
)


class TestTokenBucket:
    """Test TokenBucket dataclass"""

    def test_initial_state(self):
        """Bucket starts full"""
        bucket = TokenBucket(rpm_limit=10, tpm_limit=100)
        assert bucket.rpm_tokens == 10.0
        assert bucket.tpm_tokens == 100.0
        assert bucket.rpm_limit == 10
        assert bucket.tpm_limit == 100

    def test_post_init_defaults(self):
        """Defaults are applied correctly"""
        bucket = TokenBucket(rpm_limit=5, tpm_limit=50)
        assert bucket.rpm_tokens == 5.0
        assert bucket.tpm_tokens == 50.0


class TestTokenBucketRateLimiter:
    """Test TokenBucketRateLimiter"""

    def test_default_limits(self):
        """Default limits are applied when no per-key override"""
        limiter = TokenBucketRateLimiter(default_rpm=10, default_tpm=100)
        result = limiter.check_and_consume("key1")
        assert result["allowed"]
        assert result["rpm_remaining"] == 9
        assert result["tpm_remaining"] == 100

    def test_per_key_rpm_limit(self):
        """Per-key RPM override is respected"""
        limiter = TokenBucketRateLimiter(default_rpm=100)
        # key with custom limit of 2
        result = limiter.check_and_consume("key2", rpm_limit=2)
        assert result["allowed"]
        assert result["rpm_remaining"] == 1

        result = limiter.check_and_consume("key2")
        assert result["allowed"]
        assert result["rpm_remaining"] == 0

        result = limiter.check_and_consume("key2")
        assert not result["allowed"]
        assert result["reason"] == "rpm_limit"
        assert result["retry_after"] > 0

    def test_per_key_tpm_limit(self):
        """Per-key TPM override is respected"""
        limiter = TokenBucketRateLimiter(default_tpm=100)
        result = limiter.check_and_consume("key3", tokens=50, tpm_limit=100)
        assert result["allowed"]
        assert result["tpm_remaining"] == 50

        result = limiter.check_and_consume("key3", tokens=60)
        assert not result["allowed"]
        assert result["reason"] == "tpm_limit"

    def test_rpm_refill_over_time(self):
        """Tokens refill after elapsed time"""
        limiter = TokenBucketRateLimiter(default_rpm=60)  # 1 per second
        # Consume all tokens
        for _ in range(60):
            limiter.check_and_consume("key4")

        result = limiter.check_and_consume("key4")
        assert not result["allowed"]

        # Wait for refill
        time.sleep(1.1)
        result = limiter.check_and_consume("key4")
        assert result["allowed"]

    def test_tpm_refill_over_time(self):
        """TPM tokens refill after elapsed time"""
        limiter = TokenBucketRateLimiter(default_tpm=60)  # 1 per second
        result = limiter.check_and_consume("key5", tokens=60)
        assert result["allowed"]

        result = limiter.check_and_consume("key5", tokens=1)
        assert not result["allowed"]

        time.sleep(1.1)
        result = limiter.check_and_consume("key5", tokens=1)
        assert result["allowed"]

    def test_different_keys_isolated(self):
        """Rate limits are isolated per key"""
        limiter = TokenBucketRateLimiter(default_rpm=2)
        limiter.check_and_consume("keyA")
        limiter.check_and_consume("keyA")

        # keyA is exhausted
        assert not limiter.check_and_consume("keyA")["allowed"]

        # keyB is still fresh
        assert limiter.check_and_consume("keyB")["allowed"]
        assert limiter.check_and_consume("keyB")["allowed"]
        assert not limiter.check_and_consume("keyB")["allowed"]

    def test_zero_tokens_allowed(self):
        """Request with 0 tokens only checks RPM"""
        limiter = TokenBucketRateLimiter(default_rpm=1, default_tpm=0)
        result = limiter.check_and_consume("key6", tokens=0)
        assert result["allowed"]
        assert result["rpm_remaining"] == 0

    def test_negative_limits_clamped(self):
        """Negative limits are clamped to 1"""
        limiter = TokenBucketRateLimiter(default_rpm=-5, default_tpm=-10)
        result = limiter.check_and_consume("key7")
        assert result["allowed"]
        # Should have been clamped to 1
        assert result["rpm_remaining"] == 0

    def test_get_status(self):
        """Status query returns current bucket state"""
        limiter = TokenBucketRateLimiter(default_rpm=10, default_tpm=100)
        limiter.check_and_consume("key8", tokens=20)
        status = limiter.get_status("key8")
        assert status is not None
        assert status["rpm_limit"] == 10
        assert status["tpm_limit"] == 100
        assert status["rpm_remaining"] == 9
        assert status["tpm_remaining"] == 80

    def test_get_status_unknown_key(self):
        """Status for unknown key returns None"""
        limiter = TokenBucketRateLimiter()
        assert limiter.get_status("unknown") is None

    def test_reset_key(self):
        """Resetting a key clears its bucket"""
        limiter = TokenBucketRateLimiter(default_rpm=1)
        limiter.check_and_consume("key9")
        assert not limiter.check_and_consume("key9")["allowed"]

        limiter.reset_key("key9")
        result = limiter.check_and_consume("key9")
        assert result["allowed"]

    def test_reset_all(self):
        """Resetting all clears every bucket"""
        limiter = TokenBucketRateLimiter(default_rpm=1)
        limiter.check_and_consume("key10")
        limiter.check_and_consume("key11")

        limiter.reset_all()
        assert limiter.check_and_consume("key10")["allowed"]
        assert limiter.check_and_consume("key11")["allowed"]

    def test_thread_safety_race(self):
        """Concurrent consumption does not overdraw"""
        import threading

        limiter = TokenBucketRateLimiter(default_rpm=100)
        results = []

        def consume():
            r = limiter.check_and_consume("race_key")
            results.append(r["allowed"])

        threads = [threading.Thread(target=consume) for _ in range(200)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        allowed_count = sum(results)
        # Should never exceed limit + 1 (possible race at boundary)
        assert allowed_count <= 101

    def test_retry_after_calculation(self):
        """Retry-after is computed correctly"""
        limiter = TokenBucketRateLimiter(default_rpm=60)  # 1 per second
        # Exhaust bucket
        for _ in range(60):
            limiter.check_and_consume("key12")

        result = limiter.check_and_consume("key12")
        assert not result["allowed"]
        # Should be roughly 1 second (a bit less because of elapsed time during loop)
        assert 0 < result["retry_after"] <= 2
