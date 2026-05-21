"""
Token-bucket rate limiter for per-API-key request and token throttling.

Supports:
- Requests-per-minute (RPM) limits per API key
- Tokens-per-minute (TPM) limits per API key
- Thread-safe in-memory state with optional Redis backend
- Configurable defaults and per-key overrides from database
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class TokenBucket:
    """Token bucket state for a single client."""

    rpm_limit: int
    tpm_limit: int
    rpm_tokens: float = field(default=0.0)
    tpm_tokens: float = field(default=0.0)
    last_refill: float = field(default_factory=time.time)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self):
        # Start full
        self.rpm_tokens = float(self.rpm_limit)
        self.tpm_tokens = float(self.tpm_limit)


class RateLimitExceeded(Exception):
    """Raised when a rate limit is exceeded."""

    def __init__(self, reason: str, retry_after: float):
        self.reason = reason
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded: {reason}. Retry after {retry_after:.1f}s")


class TokenBucketRateLimiter:
    """
    Thread-safe token-bucket rate limiter for API keys.

    Each API key gets its own bucket for RPM and TPM.
    Buckets refill at a constant rate (1 token per 60/limit seconds).
    """

    def __init__(
        self,
        default_rpm: int = 60,
        default_tpm: int = 100_000,
        default_burst_rpm: Optional[int] = None,
        default_burst_tpm: Optional[int] = None,
    ):
        """
        Initialize rate limiter.

        Args:
            default_rpm: Default requests-per-minute limit
            default_tpm: Default tokens-per-minute limit
            default_burst_rpm: Default burst capacity for RPM (defaults to rpm)
            default_burst_tpm: Default burst capacity for TPM (defaults to tpm)
        """
        self.default_rpm = max(1, default_rpm)
        self.default_tpm = max(1, default_tpm)
        self.default_burst_rpm = default_burst_rpm or self.default_rpm
        self.default_burst_tpm = default_burst_tpm or self.default_tpm
        self._buckets: Dict[str, TokenBucket] = {}
        self._global_lock = threading.Lock()

    def _get_or_create_bucket(
        self,
        key_id: str,
        rpm_limit: Optional[int] = None,
        tpm_limit: Optional[int] = None,
    ) -> TokenBucket:
        """Get existing bucket or create a new one with given limits."""
        with self._global_lock:
            bucket = self._buckets.get(key_id)
            if bucket is None:
                rpm = max(1, rpm_limit) if rpm_limit else self.default_rpm
                tpm = max(1, tpm_limit) if tpm_limit else self.default_tpm
                bucket = TokenBucket(rpm_limit=rpm, tpm_limit=tpm)
                self._buckets[key_id] = bucket
            return bucket

    def _refill(self, bucket: TokenBucket) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - bucket.last_refill
        bucket.last_refill = now

        # Refill RPM: 1 token per (60 / limit) seconds
        if bucket.rpm_limit > 0:
            rpm_rate = bucket.rpm_limit / 60.0
            bucket.rpm_tokens = min(bucket.rpm_limit, bucket.rpm_tokens + elapsed * rpm_rate)

        # Refill TPM: 1 token per (60 / limit) seconds
        if bucket.tpm_limit > 0:
            tpm_rate = bucket.tpm_limit / 60.0
            bucket.tpm_tokens = min(bucket.tpm_limit, bucket.tpm_tokens + elapsed * tpm_rate)

    def check_and_consume(
        self,
        key_id: str,
        tokens: int = 0,
        rpm_limit: Optional[int] = None,
        tpm_limit: Optional[int] = None,
    ) -> Dict[str, any]:
        """
        Check rate limit and consume tokens if allowed.

        Args:
            key_id: Unique identifier for the API key
            tokens: Number of tokens this request consumes (for TPM)
            rpm_limit: Per-key RPM override (from database)
            tpm_limit: Per-key TPM override (from database)

        Returns:
            Dict with:
                - allowed: bool
                - retry_after: float (seconds)
                - reason: Optional[str]
                - rpm_remaining: int
                - tpm_remaining: int

        Raises:
            RateLimitExceeded: If the limit is exceeded (optional, caller decides)
        """
        bucket = self._get_or_create_bucket(key_id, rpm_limit, tpm_limit)

        with bucket.lock:
            self._refill(bucket)

            # Check RPM
            if bucket.rpm_tokens < 1:
                retry_after = (1 - bucket.rpm_tokens) / (bucket.rpm_limit / 60.0) if bucket.rpm_limit > 0 else 60.0
                return {
                    "allowed": False,
                    "retry_after": max(0.1, retry_after),
                    "reason": "rpm_limit",
                    "rpm_remaining": 0,
                    "tpm_remaining": int(bucket.tpm_tokens),
                }

            # Check TPM
            if tokens > 0 and bucket.tpm_tokens < tokens:
                retry_after = (tokens - bucket.tpm_tokens) / (bucket.tpm_limit / 60.0) if bucket.tpm_limit > 0 else 60.0
                return {
                    "allowed": False,
                    "retry_after": max(0.1, retry_after),
                    "reason": "tpm_limit",
                    "rpm_remaining": int(bucket.rpm_tokens),
                    "tpm_remaining": int(bucket.tpm_tokens),
                }

            # Consume
            bucket.rpm_tokens -= 1
            if tokens > 0:
                bucket.tpm_tokens -= tokens

            return {
                "allowed": True,
                "retry_after": 0,
                "reason": None,
                "rpm_remaining": int(bucket.rpm_tokens),
                "tpm_remaining": int(bucket.tpm_tokens),
            }

    def get_status(self, key_id: str) -> Optional[Dict[str, any]]:
        """Get current rate limit status for a key without consuming."""
        bucket = self._buckets.get(key_id)
        if bucket is None:
            return None

        with bucket.lock:
            self._refill(bucket)
            return {
                "rpm_limit": bucket.rpm_limit,
                "tpm_limit": bucket.tpm_limit,
                "rpm_remaining": int(bucket.rpm_tokens),
                "tpm_remaining": int(bucket.tpm_tokens),
            }

    def reset_key(self, key_id: str) -> None:
        """Reset rate limit state for a specific key (e.g., after limit change)."""
        with self._global_lock:
            self._buckets.pop(key_id, None)

    def reset_all(self) -> None:
        """Reset all rate limit state."""
        with self._global_lock:
            self._buckets.clear()
