"""
Tests for circuit breaker module.

Covers: 3-state machine, per-provider isolation, recovery timeout,
registry, and status reporting.
"""

import time
from unittest.mock import patch

from toolkit_extensions.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerRegistry,
    CircuitState,
    get_circuit_breaker_registry,
)

# ---------------------------------------------------------------------------
# CircuitBreaker unit tests
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    def test_initial_state_is_closed(self):
        cb = CircuitBreaker("openai")
        assert cb.state == CircuitState.CLOSED

    def test_allows_requests_when_closed(self):
        cb = CircuitBreaker("openai")
        assert cb.allow_request() is True

    def test_stays_closed_below_threshold(self):
        cb = CircuitBreaker("openai", failure_threshold=5)
        for _ in range(4):
            cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        assert cb.allow_request() is True

    def test_opens_at_failure_threshold(self):
        cb = CircuitBreaker("openai", failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.allow_request() is False

    def test_blocks_requests_when_open(self):
        cb = CircuitBreaker("openai", failure_threshold=1)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.allow_request() is False

    def test_transitions_to_half_open_after_timeout(self):
        cb = CircuitBreaker("openai", failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.allow_request() is True

    def test_closes_on_half_open_success(self):
        cb = CircuitBreaker("openai", failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb._failure_count == 0

    def test_reopens_on_half_open_failure(self):
        cb = CircuitBreaker("openai", failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker("openai", failure_threshold=5)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb._failure_count == 0
        # Should need 5 more failures to open
        for _ in range(4):
            cb.record_failure()
        assert cb.state == CircuitState.CLOSED

    def test_manual_reset(self):
        cb = CircuitBreaker("openai", failure_threshold=1)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb._failure_count == 0

    def test_get_status(self):
        cb = CircuitBreaker("anthropic", failure_threshold=3, recovery_timeout=30)
        cb.record_failure()
        status = cb.get_status()
        assert status["provider"] == "anthropic"
        assert status["state"] == "closed"
        assert status["failure_count"] == 1
        assert status["failure_threshold"] == 3
        assert status["recovery_timeout"] == 30
        assert status["last_failure_time"] is not None

    def test_state_transition_logging(self):
        cb = CircuitBreaker("openai", failure_threshold=1)
        with patch("toolkit_extensions.circuit_breaker.logger") as mock_logger:
            cb.record_failure()
            mock_logger.warning.assert_called_once()
            args = mock_logger.warning.call_args[0]
            assert "openai" in args[1]
            assert "closed" in args[2]
            assert "open" in args[3]


# ---------------------------------------------------------------------------
# CircuitBreakerRegistry tests
# ---------------------------------------------------------------------------


class TestCircuitBreakerRegistry:
    def test_creates_breaker_on_first_get(self):
        registry = CircuitBreakerRegistry()
        cb = registry.get("openai")
        assert isinstance(cb, CircuitBreaker)
        assert cb.provider == "openai"

    def test_returns_same_breaker_for_same_provider(self):
        registry = CircuitBreakerRegistry()
        cb1 = registry.get("openai")
        cb2 = registry.get("openai")
        assert cb1 is cb2

    def test_different_breakers_for_different_providers(self):
        registry = CircuitBreakerRegistry()
        cb1 = registry.get("openai")
        cb2 = registry.get("anthropic")
        assert cb1 is not cb2

    def test_per_provider_isolation(self):
        """Single provider outage does not degrade entire LLM layer."""
        registry = CircuitBreakerRegistry(failure_threshold=2)
        openai = registry.get("openai")
        anthropic = registry.get("anthropic")

        # Openai fails
        openai.record_failure()
        openai.record_failure()
        assert openai.state == CircuitState.OPEN

        # Anthropic is unaffected
        assert anthropic.state == CircuitState.CLOSED
        assert anthropic.allow_request() is True

    def test_get_all_status(self):
        registry = CircuitBreakerRegistry()
        registry.get("openai").record_failure()
        registry.get("anthropic")
        status = registry.get_all_status()
        assert "openai" in status
        assert "anthropic" in status
        assert status["openai"]["failure_count"] == 1
        assert status["anthropic"]["failure_count"] == 0

    def test_reset_all(self):
        registry = CircuitBreakerRegistry(failure_threshold=1)
        registry.get("openai").record_failure()
        registry.get("anthropic").record_failure()
        assert registry.get("openai").state == CircuitState.OPEN
        assert registry.get("anthropic").state == CircuitState.OPEN
        registry.reset_all()
        assert registry.get("openai").state == CircuitState.CLOSED
        assert registry.get("anthropic").state == CircuitState.CLOSED

    def test_custom_thresholds(self):
        registry = CircuitBreakerRegistry(failure_threshold=10, recovery_timeout=120)
        cb = registry.get("openai")
        assert cb.failure_threshold == 10
        assert cb.recovery_timeout == 120


# ---------------------------------------------------------------------------
# Global singleton test
# ---------------------------------------------------------------------------


class TestGlobalRegistry:
    def test_get_circuit_breaker_registry_returns_singleton(self):
        import toolkit_extensions.circuit_breaker as mod

        mod._registry = None  # reset
        r1 = get_circuit_breaker_registry()
        r2 = get_circuit_breaker_registry()
        assert r1 is r2
        mod._registry = None  # cleanup

    def test_get_circuit_breaker_registry_custom_params(self):
        import toolkit_extensions.circuit_breaker as mod

        mod._registry = None
        r = get_circuit_breaker_registry(failure_threshold=10, recovery_timeout=120)
        assert r.failure_threshold == 10
        assert r.recovery_timeout == 120
        mod._registry = None
