"""
Tests for metrics module
"""

from toolkit_extensions.metrics import (
    MetricsCollector,
    get_metrics_collector,
    track_request,
)


def test_increment_counter():
    """Test counter increment."""
    collector = MetricsCollector()
    collector.increment_counter("test_counter")
    collector.increment_counter("test_counter", value=5.0)

    metrics = collector.get_metrics()
    assert metrics["counters"]["test_counter"] == 6.0


def test_increment_counter_with_labels():
    """Test counter with labels."""
    collector = MetricsCollector()
    collector.increment_counter("requests", labels={"model": "gpt-4"})
    collector.increment_counter("requests", labels={"model": "gpt-4"})
    collector.increment_counter("requests", labels={"model": "claude"})

    metrics = collector.get_metrics()
    assert metrics["counters"]["requests{model=gpt-4}"] == 2.0
    assert metrics["counters"]["requests{model=claude}"] == 1.0


def test_set_gauge():
    """Test gauge set."""
    collector = MetricsCollector()
    collector.set_gauge("active_connections", 42)

    metrics = collector.get_metrics()
    assert metrics["gauges"]["active_connections"] == 42


def test_observe_histogram():
    """Test histogram observation."""
    collector = MetricsCollector()
    for v in [0.1, 0.5, 1.0, 2.0, 5.0]:
        collector.observe_histogram("request_duration", v)

    metrics = collector.get_metrics()
    hist = metrics["histograms"]["request_duration"]
    assert hist["count"] == 5
    assert hist["min"] == 0.1
    assert hist["max"] == 5.0
    assert hist["avg"] > 0


def test_histogram_cap_1000():
    """Test histogram caps at 1000 observations."""
    collector = MetricsCollector()
    for i in range(1200):
        collector.observe_histogram("big_hist", float(i))

    assert len(collector.histograms["big_hist"]) == 1000


def test_observe_summary():
    """Test summary observation."""
    collector = MetricsCollector()
    for v in [10, 20, 30]:
        collector.observe_summary("latency", float(v))

    metrics = collector.get_metrics()
    assert metrics["summaries"]["latency"]["count"] == 3


def test_export_prometheus():
    """Test Prometheus format export."""
    collector = MetricsCollector()
    collector.increment_counter("requests_total", value=100)
    collector.set_gauge("active_connections", 5)
    collector.observe_histogram("request_duration_seconds", 0.25)

    output = collector.export_prometheus()
    assert "# TYPE requests_total counter" in output
    assert "requests_total 100" in output
    assert "# TYPE active_connections gauge" in output
    assert "active_connections 5" in output
    assert "request_duration_seconds_count 1" in output


def test_track_request_function():
    """Test convenience track_request function."""
    track_request(
        duration=0.5,
        success=True,
        model="gpt-4",
        provider="openai",
        cost=0.03,
        tokens=500,
    )

    collector = get_metrics_collector()
    metrics = collector.get_metrics()
    assert metrics["counters"]["requests_total"] > 0
    assert metrics["counters"]["requests_success"] > 0


def test_empty_histogram_stats():
    """Test histogram stats with no data."""
    collector = MetricsCollector()
    stats = collector._histogram_stats([])
    assert stats["count"] == 0
    assert stats["sum"] == 0


def test_percentile_calculation():
    """Test percentile calculation."""
    collector = MetricsCollector()
    values = list(range(1, 101))
    p50 = collector._percentile(values, 0.5)
    p99 = collector._percentile(values, 0.99)

    # _percentile uses int(len*p) as index into sorted 0-based list
    # For 100 elements: int(100*0.5)=50 -> values[50]=51
    assert p50 == 51
    assert p99 == 100


def test_global_metrics_collector():
    """Test global singleton."""
    c1 = get_metrics_collector()
    c2 = get_metrics_collector()
    assert c1 is c2
