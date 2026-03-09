"""
Toolkit LLM Gateway - Metrics and Monitoring

Provides Prometheus-compatible metrics for monitoring.
"""

import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class MetricType(Enum):
    """Metric types"""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class Metric:
    """Base metric class"""

    name: str
    help_text: str
    metric_type: MetricType
    labels: Dict[str, str] = field(default_factory=dict)
    value: float = 0.0
    timestamp: float = field(default_factory=time.time)


class MetricsCollector:
    """Collects and exposes metrics"""

    def __init__(self):
        """Initialize metrics collector"""
        self.counters: Dict[str, float] = defaultdict(float)
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, list] = defaultdict(list)
        self.summaries: Dict[str, list] = defaultdict(list)

        # Initialize standard metrics
        self._init_standard_metrics()

    def _init_standard_metrics(self):
        """Initialize standard metrics"""
        # Request metrics
        self.counters["requests_total"] = 0
        self.counters["requests_success"] = 0
        self.counters["requests_error"] = 0

        # Cost metrics
        self.counters["total_cost"] = 0.0
        self.counters["total_tokens"] = 0

        # Latency metrics
        self.histograms["request_duration_seconds"] = []

        # Active connections
        self.gauges["active_connections"] = 0

    def increment_counter(
        self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None
    ):
        """Increment a counter metric"""
        key = self._make_key(name, labels)
        self.counters[key] += value

    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Set a gauge metric"""
        key = self._make_key(name, labels)
        self.gauges[key] = value

    def observe_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Observe a value in a histogram"""
        key = self._make_key(name, labels)
        self.histograms[key].append(value)

        # Keep only last 1000 observations
        if len(self.histograms[key]) > 1000:
            self.histograms[key] = self.histograms[key][-1000:]

    def observe_summary(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Observe a value in a summary"""
        key = self._make_key(name, labels)
        self.summaries[key].append(value)

        # Keep only last 1000 observations
        if len(self.summaries[key]) > 1000:
            self.summaries[key] = self.summaries[key][-1000:]

    def _make_key(self, name: str, labels: Optional[Dict[str, str]] = None) -> str:
        """Make a metric key with labels"""
        if not labels:
            return name

        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def get_metrics(self) -> Dict[str, Any]:
        """Get all metrics"""
        return {
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "histograms": {
                name: self._histogram_stats(values) for name, values in self.histograms.items()
            },
            "summaries": {
                name: self._summary_stats(values) for name, values in self.summaries.items()
            },
        }

    def _histogram_stats(self, values: list) -> Dict[str, float]:
        """Calculate histogram statistics"""
        if not values:
            return {"count": 0, "sum": 0, "min": 0, "max": 0, "avg": 0}

        return {
            "count": len(values),
            "sum": sum(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "p50": self._percentile(values, 0.5),
            "p95": self._percentile(values, 0.95),
            "p99": self._percentile(values, 0.99),
        }

    def _summary_stats(self, values: list) -> Dict[str, float]:
        """Calculate summary statistics"""
        return self._histogram_stats(values)

    def _percentile(self, values: list, p: float) -> float:
        """Calculate percentile"""
        if not values:
            return 0.0

        sorted_values = sorted(values)
        index = int(len(sorted_values) * p)
        return sorted_values[min(index, len(sorted_values) - 1)]

    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format"""
        lines = []

        # Export counters
        for name, value in self.counters.items():
            base_name = name.split("{")[0]
            lines.append(f"# TYPE {base_name} counter")
            lines.append(f"{name} {value}")

        # Export gauges
        for name, value in self.gauges.items():
            base_name = name.split("{")[0]
            lines.append(f"# TYPE {base_name} gauge")
            lines.append(f"{name} {value}")

        # Export histograms
        for name, values in self.histograms.items():
            if not values:
                continue

            base_name = name.split("{")[0]
            stats = self._histogram_stats(values)

            lines.append(f"# TYPE {base_name} histogram")
            lines.append(f"{name}_count {stats['count']}")
            lines.append(f"{name}_sum {stats['sum']}")
            lines.append(f'{name}_bucket{{le="0.1"}} {sum(1 for v in values if v <= 0.1)}')
            lines.append(f'{name}_bucket{{le="0.5"}} {sum(1 for v in values if v <= 0.5)}')
            lines.append(f'{name}_bucket{{le="1.0"}} {sum(1 for v in values if v <= 1.0)}')
            lines.append(f'{name}_bucket{{le="5.0"}} {sum(1 for v in values if v <= 5.0)}')
            lines.append(f'{name}_bucket{{le="+Inf"}} {len(values)}')

        return "\n".join(lines)


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create global metrics collector"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def track_request(
    duration: float, success: bool, model: str, provider: str, cost: float, tokens: int
):
    """Track a request with metrics"""
    collector = get_metrics_collector()

    # Increment counters
    collector.increment_counter("requests_total")
    if success:
        collector.increment_counter("requests_success")
    else:
        collector.increment_counter("requests_error")

    # Track by model and provider
    collector.increment_counter("requests_by_model", labels={"model": model})
    collector.increment_counter("requests_by_provider", labels={"provider": provider})

    # Track cost and tokens
    collector.increment_counter("total_cost", value=cost)
    collector.increment_counter("total_tokens", value=tokens)

    # Track latency
    collector.observe_histogram("request_duration_seconds", duration)
