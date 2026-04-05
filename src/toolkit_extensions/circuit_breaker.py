"""
Toolkit LLM Gateway - Circuit Breaker

Three-state (CLOSED/OPEN/HALF_OPEN) circuit breaker for per-provider
fault isolation per LLM Gateway Standard v1.2 Section 7.

When a provider fails consecutively beyond the threshold, the circuit
opens and requests fail fast. After a recovery timeout the circuit
enters half-open state and allows a single probe request through.
"""

import logging
import threading
import time
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Per-provider circuit breaker.

    Args:
        provider: Provider name (e.g. "openai", "anthropic").
        failure_threshold: Consecutive failures before opening. Default 5.
        recovery_timeout: Seconds to wait before probing. Default 60.
    """

    def __init__(
        self,
        provider: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
    ) -> None:
        self.provider = provider
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._lock = threading.Lock()

    # -- public API -----------------------------------------------------------

    @property
    def state(self) -> CircuitState:
        """Current state, accounting for recovery timeout."""
        with self._lock:
            if (
                self._state == CircuitState.OPEN
                and self._last_failure_time is not None
                and time.time() - self._last_failure_time >= self.recovery_timeout
            ):
                self._transition(CircuitState.HALF_OPEN)
            return self._state

    def allow_request(self) -> bool:
        """Return True if a request may be attempted."""
        current = self.state  # triggers timeout check
        if current == CircuitState.CLOSED:
            return True
        if current == CircuitState.HALF_OPEN:
            return True  # allow probe
        return False  # OPEN

    def record_success(self) -> None:
        """Record a successful request."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._transition(CircuitState.CLOSED)
            self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed request."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                self._transition(CircuitState.OPEN)
            elif (
                self._state == CircuitState.CLOSED and self._failure_count >= self.failure_threshold
            ):
                self._transition(CircuitState.OPEN)

    def reset(self) -> None:
        """Force-reset the breaker to CLOSED (e.g. manual recovery)."""
        with self._lock:
            self._transition(CircuitState.CLOSED)
            self._failure_count = 0
            self._last_failure_time = None

    def get_status(self) -> Dict[str, Any]:
        """Return a JSON-serialisable status dict."""
        return {
            "provider": self.provider,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure_time": self._last_failure_time,
        }

    # -- internal -------------------------------------------------------------

    def _transition(self, new_state: CircuitState) -> None:
        """Transition state and log the event."""
        old = self._state
        self._state = new_state
        if old != new_state:
            logger.warning(
                "Circuit breaker %s: %s -> %s (failures=%d)",
                self.provider,
                old.value,
                new_state.value,
                self._failure_count,
            )


class CircuitBreakerRegistry:
    """Manages per-provider circuit breakers.

    Usage::

        registry = CircuitBreakerRegistry(failure_threshold=5, recovery_timeout=60)
        cb = registry.get("openai")
        if cb.allow_request():
            try:
                result = call_provider("openai", ...)
                cb.record_success()
            except ProviderError:
                cb.record_failure()
        else:
            # use fallback chain
            ...
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()

    def get(self, provider: str) -> CircuitBreaker:
        """Get or create a breaker for *provider*."""
        with self._lock:
            if provider not in self._breakers:
                self._breakers[provider] = CircuitBreaker(
                    provider=provider,
                    failure_threshold=self.failure_threshold,
                    recovery_timeout=self.recovery_timeout,
                )
            return self._breakers[provider]

    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """Return status for every known provider."""
        with self._lock:
            return {name: cb.get_status() for name, cb in self._breakers.items()}

    def reset_all(self) -> None:
        """Reset all breakers to CLOSED."""
        with self._lock:
            for cb in self._breakers.values():
                cb.reset()


# -- module-level singleton ---------------------------------------------------

_registry: Optional[CircuitBreakerRegistry] = None


def get_circuit_breaker_registry(
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
) -> CircuitBreakerRegistry:
    """Return (or create) the global circuit breaker registry."""
    global _registry
    if _registry is None:
        _registry = CircuitBreakerRegistry(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
        )
    return _registry
