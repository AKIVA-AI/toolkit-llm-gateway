"""
Proactive budget monitoring system for Toolkit LLM Gateway

Runs a background thread that periodically:
1. Scans all active budgets for threshold crossings
2. Generates BudgetAlert records
3. Delivers alerts via configured webhooks

This bridges the reactive BudgetManager + AlertWebhookManager into
an autonomous, always-on alerting pipeline.
"""

import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from toolkit_extensions.alert_webhooks import AlertWebhookManager, get_alert_webhook_manager
from toolkit_extensions.budget_manager import BudgetManager, get_budget_manager

logger = logging.getLogger(__name__)


@dataclass
class MonitorStats:
    """Runtime statistics for the budget monitor."""

    checks_performed: int = 0
    alerts_generated: int = 0
    alerts_delivered: int = 0
    delivery_failures: int = 0
    last_check_at: Optional[float] = None
    last_error: Optional[str] = None
    is_running: bool = False


class BudgetMonitor:
    """
    Background monitor that proactively checks budgets and delivers alerts.

    Usage:
        monitor = BudgetMonitor(interval_seconds=60)
        monitor.start()
        # ... runs in background ...
        monitor.stop()
    """

    def __init__(
        self,
        interval_seconds: int = 60,
        budget_manager: Optional[BudgetManager] = None,
        webhook_manager: Optional[AlertWebhookManager] = None,
        on_alert_generated: Optional[Callable[[List[str]], None]] = None,
        on_delivery_complete: Optional[Callable[[Dict], None]] = None,
    ):
        """
        Initialize monitor.

        Args:
            interval_seconds: Seconds between budget checks (default 60)
            budget_manager: BudgetManager instance (default: global singleton)
            webhook_manager: AlertWebhookManager instance (default: global singleton)
            on_alert_generated: Optional callback when alerts are generated
            on_delivery_complete: Optional callback when deliveries finish
        """
        self.interval_seconds = max(5, interval_seconds)
        self.budget_manager = budget_manager or get_budget_manager()
        self.webhook_manager = webhook_manager or get_alert_webhook_manager()
        self.on_alert_generated = on_alert_generated
        self.on_delivery_complete = on_delivery_complete

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self.stats = MonitorStats()

    # -- Lifecycle -----------------------------------------------------------

    def start(self) -> None:
        """Start the background monitoring thread."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                logger.warning("BudgetMonitor already running")
                return

            self._stop_event.clear()
            self.stats.is_running = True
            self._thread = threading.Thread(
                target=self._run_loop,
                name="BudgetMonitor",
                daemon=True,
            )
            self._thread.start()
            logger.info(
                "BudgetMonitor started (interval=%ds)", self.interval_seconds
            )

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the background monitoring thread gracefully."""
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                logger.warning("BudgetMonitor not running")
                return

            self._stop_event.set()
            self.stats.is_running = False

        self._thread.join(timeout=timeout)
        if self._thread.is_alive():
            logger.warning("BudgetMonitor thread did not stop within timeout")
        else:
            logger.info("BudgetMonitor stopped")

    def is_running(self) -> bool:
        """Check if the monitor thread is currently running."""
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    # -- Core Loop -----------------------------------------------------------

    def _run_loop(self) -> None:
        """Main monitoring loop."""
        while not self._stop_event.is_set():
            try:
                self._perform_check()
            except Exception as e:
                logger.error("BudgetMonitor check failed: %s", e, exc_info=True)
                self.stats.last_error = str(e)

            # Wait for interval or until stopped
            self._stop_event.wait(self.interval_seconds)

    def _perform_check(self) -> None:
        """Single check cycle: generate alerts then deliver them."""
        self.stats.checks_performed += 1
        self.stats.last_check_at = time.time()

        # 1. Generate alerts for budgets crossing thresholds
        alert_ids = self.budget_manager.generate_alerts()
        if alert_ids:
            self.stats.alerts_generated += len(alert_ids)
            logger.info("Generated %d budget alert(s)", len(alert_ids))
            if self.on_alert_generated:
                try:
                    self.on_alert_generated(alert_ids)
                except Exception:
                    logger.exception("on_alert_generated callback failed")

        # 2. Deliver pending alerts via webhooks
        delivery_result = self.webhook_manager.deliver_pending_alerts()
        self.stats.alerts_delivered += delivery_result.get("success_count", 0)
        self.stats.delivery_failures += delivery_result.get("failure_count", 0)

        if delivery_result.get("alerts_processed", 0) > 0:
            logger.info(
                "Delivered %d/%d alerts (success=%d, failure=%d)",
                delivery_result.get("alerts_processed", 0),
                delivery_result.get("alerts_processed", 0),
                delivery_result.get("success_count", 0),
                delivery_result.get("failure_count", 0),
            )
            if self.on_delivery_complete:
                try:
                    self.on_delivery_complete(delivery_result)
                except Exception:
                    logger.exception("on_delivery_complete callback failed")

    # -- Manual Trigger ------------------------------------------------------

    def check_now(self) -> Dict[str, any]:
        """
        Manually trigger a single check cycle (blocking).

        Returns:
            Dict with alerts_generated, delivery_result
        """
        try:
            self._perform_check()
        except Exception as e:
            logger.error("BudgetMonitor manual check failed: %s", e, exc_info=True)
            self.stats.last_error = str(e)

        return {
            "alerts_generated": self.stats.alerts_generated,
            "alert_ids": [],  # Not tracked at this granularity
            "delivery": {
                "success_count": self.stats.alerts_delivered,
                "failure_count": self.stats.delivery_failures,
            },
        }

    # -- Stats ---------------------------------------------------------------

    def get_stats(self) -> Dict[str, any]:
        """Get current monitor statistics."""
        with self._lock:
            return {
                "is_running": self.stats.is_running,
                "checks_performed": self.stats.checks_performed,
                "alerts_generated": self.stats.alerts_generated,
                "alerts_delivered": self.stats.alerts_delivered,
                "delivery_failures": self.stats.delivery_failures,
                "last_check_at": self.stats.last_check_at,
                "last_error": self.stats.last_error,
                "interval_seconds": self.interval_seconds,
            }

    def reset_stats(self) -> None:
        """Reset runtime statistics."""
        with self._lock:
            self.stats = MonitorStats(is_running=self.stats.is_running)


# Global singleton instance
_monitor_instance: Optional[BudgetMonitor] = None
_monitor_lock = threading.Lock()


def get_budget_monitor(
    interval_seconds: int = 60,
    budget_manager: Optional[BudgetManager] = None,
    webhook_manager: Optional[AlertWebhookManager] = None,
) -> BudgetMonitor:
    """Get or create global BudgetMonitor singleton."""
    global _monitor_instance
    with _monitor_lock:
        if _monitor_instance is None:
            _monitor_instance = BudgetMonitor(
                interval_seconds=interval_seconds,
                budget_manager=budget_manager,
                webhook_manager=webhook_manager,
            )
        return _monitor_instance


def start_budget_monitor(interval_seconds: int = 60) -> BudgetMonitor:
    """Convenience: create and start the global monitor."""
    monitor = get_budget_monitor(interval_seconds=interval_seconds)
    monitor.start()
    return monitor


def stop_budget_monitor() -> None:
    """Convenience: stop the global monitor."""
    global _monitor_instance
    with _monitor_lock:
        if _monitor_instance is not None:
            _monitor_instance.stop()
