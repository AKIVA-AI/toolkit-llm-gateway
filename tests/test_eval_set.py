"""
Eval set for toolkit-llm-gateway.

Golden test cases that verify the gateway's core domain logic:
cost tracking accuracy, budget enforcement, circuit breaker behaviour,
analytics correctness, and webhook payload construction.

These are regression tests — they assert concrete expected outputs
and must be updated deliberately when business rules change.
"""

import pytest

from toolkit_extensions.budget_manager import BudgetManager, BudgetPeriod, BudgetStatus
from toolkit_extensions.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerRegistry,
    CircuitState,
)
from toolkit_extensions.metrics import MetricsCollector

# ---------------------------------------------------------------------------
# EVAL-1: Cost attribution accuracy
# ---------------------------------------------------------------------------


class TestCostAttributionEval:
    """Golden set: cost values must match expected outputs exactly."""

    def test_total_cost_sums_correctly(self):
        """3 requests with known costs should sum to exact total."""
        collector = MetricsCollector()
        costs = [0.0012, 0.0045, 0.0003]
        for cost in costs:
            collector.increment_counter("total_cost", value=cost)
        assert abs(collector.counters["total_cost"] - 0.006) < 1e-9

    def test_token_count_sums_correctly(self):
        """Token counts from multiple requests sum precisely."""
        collector = MetricsCollector()
        tokens = [150, 200, 350]
        for t in tokens:
            collector.increment_counter("total_tokens", value=t)
        assert collector.counters["total_tokens"] == 700

    def test_per_model_cost_isolation(self):
        """Costs attributed to model A don't leak to model B."""
        collector = MetricsCollector()
        collector.increment_counter("cost_by_model", value=0.01, labels={"model": "gpt-4"})
        collector.increment_counter("cost_by_model", value=0.002, labels={"model": "claude-3"})
        assert collector.counters["cost_by_model{model=gpt-4}"] == 0.01
        assert collector.counters["cost_by_model{model=claude-3}"] == 0.002


# ---------------------------------------------------------------------------
# EVAL-2: Budget enforcement logic
# ---------------------------------------------------------------------------


class TestBudgetEnforcementEval:
    """Golden set: budget threshold logic matches expected classification."""

    def test_budget_period_types(self):
        """All 5 period types must be valid BudgetPeriod enums."""
        periods = ["daily", "weekly", "monthly", "yearly", "lifetime"]
        for p in periods:
            assert BudgetPeriod(p).value == p

    def test_budget_status_types(self):
        """All 4 status types must be valid BudgetStatus enums."""
        statuses = ["ok", "approaching", "exceeded", "disabled"]
        for s in statuses:
            assert BudgetStatus(s).value == s

    def test_single_attribution_constraint(self):
        """Budget creation must reject zero or multiple attributions."""
        manager = BudgetManager(block_on_exceeded=False)

        # Zero attributions
        with pytest.raises(ValueError, match="exactly one"):
            manager.create_budget(period=BudgetPeriod.MONTHLY, limit_amount=100.0)

        # Multiple attributions
        with pytest.raises(ValueError, match="exactly one"):
            manager.create_budget(
                period=BudgetPeriod.MONTHLY,
                limit_amount=100.0,
                user_email="a@b.com",
                team_name="team-x",
            )

    def test_alert_threshold_bounds(self):
        """Alert threshold must be in [0.0, 1.0]."""
        manager = BudgetManager(block_on_exceeded=False)

        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            manager.create_budget(
                period=BudgetPeriod.MONTHLY,
                limit_amount=100.0,
                user_email="a@b.com",
                alert_threshold=1.5,
            )


# ---------------------------------------------------------------------------
# EVAL-3: Circuit breaker state machine
# ---------------------------------------------------------------------------


class TestCircuitBreakerEval:
    """Golden set: exact state transitions per LLM Gateway Standard v1.2 s7."""

    def test_exact_threshold_transition(self):
        """5th consecutive failure opens the circuit (not 4th, not 6th)."""
        cb = CircuitBreaker("eval-provider", failure_threshold=5)
        for i in range(4):
            cb.record_failure()
            assert cb.state == CircuitState.CLOSED, f"Opened too early at failure {i + 1}"
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_provider_isolation_under_load(self):
        """10 providers: one failing hard, others unaffected."""
        registry = CircuitBreakerRegistry(failure_threshold=3)
        providers = [f"provider-{i}" for i in range(10)]

        # Fail provider-0 hard
        for _ in range(5):
            registry.get("provider-0").record_failure()

        # All others remain closed
        for name in providers[1:]:
            assert registry.get(name).state == CircuitState.CLOSED

    def test_fallback_chain_activation(self):
        """When primary is open, fallback must be reachable."""
        registry = CircuitBreakerRegistry(failure_threshold=1)
        primary = registry.get("primary")
        fallback = registry.get("fallback")

        primary.record_failure()
        assert not primary.allow_request()
        assert fallback.allow_request()


# ---------------------------------------------------------------------------
# EVAL-4: Metrics Prometheus export format
# ---------------------------------------------------------------------------


class TestMetricsExportEval:
    """Golden set: Prometheus export lines match expected format."""

    def test_counter_export_format(self):
        collector = MetricsCollector()
        collector.increment_counter("requests_total", value=42)
        output = collector.export_prometheus()
        assert "# TYPE requests_total counter" in output
        assert "requests_total 42" in output

    def test_histogram_export_includes_buckets(self):
        collector = MetricsCollector()
        for v in [0.05, 0.2, 0.8, 2.0, 10.0]:
            collector.observe_histogram("request_duration_seconds", v)
        output = collector.export_prometheus()
        assert 'request_duration_seconds_bucket{le="0.1"} 1' in output
        assert 'request_duration_seconds_bucket{le="0.5"} 2' in output
        assert 'request_duration_seconds_bucket{le="1.0"} 3' in output
        assert 'request_duration_seconds_bucket{le="+Inf"} 5' in output

    def test_percentile_accuracy(self):
        collector = MetricsCollector()
        # 100 values from 1 to 100
        for v in range(1, 101):
            collector.observe_histogram("latency", float(v))
        stats = collector._histogram_stats(collector.histograms["latency"])
        # Implementation uses int(len*p) index into sorted list
        # For 100 items: p50 -> index 50 -> value 51, p95 -> index 95 -> 96, p99 -> index 99 -> 100
        assert stats["p50"] == 51
        assert stats["p95"] == 96
        assert stats["p99"] == 100
