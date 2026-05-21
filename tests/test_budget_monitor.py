"""
Tests for proactive budget monitor
"""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from toolkit_extensions.budget_manager import BudgetManager, BudgetPeriod
from toolkit_extensions.budget_monitor import BudgetMonitor, get_budget_monitor
from toolkit_extensions.cost_tracker import CostTracker
from toolkit_extensions.database.connection import DatabaseConfig, init_database


@pytest.fixture
def db_manager():
    """Create test database manager"""
    import os
    import tempfile

    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    config = DatabaseConfig(database_url=f"sqlite:///{db_path}")
    manager = init_database(config)
    yield manager

    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def budget_manager(db_manager):
    """Create budget manager"""
    return BudgetManager(block_on_exceeded=False)


@pytest.fixture
def cost_tracker(db_manager):
    """Create cost tracker"""
    return CostTracker(enabled=True)


@pytest.fixture
def monitor(budget_manager):
    """Create budget monitor with fast interval for testing"""
    # Patch webhook manager to avoid real HTTP calls
    with patch("toolkit_extensions.budget_monitor.get_alert_webhook_manager") as mock_get:
        mock_wm = MagicMock()
        mock_wm.deliver_pending_alerts.return_value = {
            "success_count": 0,
            "failure_count": 0,
            "alerts_processed": 0,
        }
        mock_get.return_value = mock_wm
        monitor = BudgetMonitor(
            interval_seconds=1,
            budget_manager=budget_manager,
            webhook_manager=mock_wm,
        )
        yield monitor
        monitor.stop()


# ── Lifecycle Tests ──────────────────────────────────────────────────────


def test_monitor_start_stop(monitor):
    """Monitor starts and stops correctly"""
    assert not monitor.is_running()
    monitor.start()
    assert monitor.is_running()
    monitor.stop()
    assert not monitor.is_running()


def test_monitor_double_start(monitor):
    """Double start is a no-op"""
    monitor.start()
    t1 = monitor._thread
    monitor.start()  # should not spawn second thread
    assert monitor._thread is t1
    monitor.stop()


def test_monitor_stop_when_not_running(monitor):
    """Stopping an idle monitor is safe"""
    monitor.stop()  # should not raise
    assert not monitor.is_running()


def test_monitor_thread_is_daemon(monitor):
    """Monitor thread is daemon so it won't block process exit"""
    monitor.start()
    assert monitor._thread.daemon
    monitor.stop()


# ── Check Cycle Tests ────────────────────────────────────────────────────


def test_check_now_generates_alerts(monitor, budget_manager, cost_tracker):
    """Manual check generates alerts when budget threshold is crossed"""
    # Create budget with low limit
    budget_manager.create_budget(
        period=BudgetPeriod.DAILY,
        limit_amount=10.0,
        user_email="monitor_test@example.com",
        alert_threshold=0.5,
    )

    # Spend enough to cross threshold
    cost_tracker.track_request(
        model="gpt-4",
        provider="openai",
        prompt_tokens=1000,
        completion_tokens=500,
        total_cost=6.0,
        user_email="monitor_test@example.com",
    )

    result = monitor.check_now()
    assert monitor.stats.alerts_generated >= 1


def test_check_now_no_alerts_when_budget_ok(monitor, budget_manager):
    """Manual check generates no alerts when budget is fine"""
    budget_manager.create_budget(
        period=BudgetPeriod.DAILY,
        limit_amount=1000.0,
        user_email="ok_test@example.com",
        alert_threshold=0.9,
    )

    result = monitor.check_now()
    assert result["alerts_generated"] == 0


def test_check_now_delivers_alerts(monitor, budget_manager, cost_tracker):
    """Manual check delivers generated alerts via webhooks"""
    budget_manager.create_budget(
        period=BudgetPeriod.DAILY,
        limit_amount=10.0,
        user_email="delivery_test@example.com",
        alert_threshold=0.5,
    )

    cost_tracker.track_request(
        model="gpt-4",
        provider="openai",
        prompt_tokens=1000,
        completion_tokens=500,
        total_cost=6.0,
        user_email="delivery_test@example.com",
    )

    # Configure mock to report delivery
    monitor.webhook_manager.deliver_pending_alerts.return_value = {
        "success_count": 1,
        "failure_count": 0,
        "alerts_processed": 1,
    }

    result = monitor.check_now()
    assert result["alerts_generated"] >= 1
    assert result["delivery"]["success_count"] == 1


# ── Background Loop Tests ──────────────────────────────────────────────────


def test_background_loop_generates_alerts(monitor, budget_manager, cost_tracker):
    """Background thread generates alerts over time"""
    budget_manager.create_budget(
        period=BudgetPeriod.DAILY,
        limit_amount=10.0,
        user_email="bg_test@example.com",
        alert_threshold=0.5,
    )

    cost_tracker.track_request(
        model="gpt-4",
        provider="openai",
        prompt_tokens=1000,
        completion_tokens=500,
        total_cost=6.0,
        user_email="bg_test@example.com",
    )

    monitor.start()
    time.sleep(5.0)  # Generous wait for multiple cycles
    monitor.stop()

    assert monitor.stats.alerts_generated >= 1
    assert monitor.stats.checks_performed >= 1


def test_background_loop_stops_gracefully(monitor):
    """Background thread stops within timeout"""
    monitor.start()
    time.sleep(0.5)
    monitor.stop(timeout=2.0)
    assert not monitor.is_running()


# ── Stats Tests ────────────────────────────────────────────────────────────


def test_get_stats_initial(monitor):
    """Initial stats are zeroed"""
    stats = monitor.get_stats()
    assert stats["checks_performed"] == 0
    assert stats["alerts_generated"] == 0
    assert stats["alerts_delivered"] == 0
    assert stats["delivery_failures"] == 0
    assert stats["is_running"] is False
    assert stats["last_error"] is None


def test_get_stats_after_check(monitor, budget_manager, cost_tracker):
    """Stats update after check cycle"""
    budget_manager.create_budget(
        period=BudgetPeriod.DAILY,
        limit_amount=10.0,
        user_email="stats_test@example.com",
        alert_threshold=0.5,
    )

    cost_tracker.track_request(
        model="gpt-4",
        provider="openai",
        prompt_tokens=1000,
        completion_tokens=500,
        total_cost=6.0,
        user_email="stats_test@example.com",
    )

    monitor.check_now()
    stats = monitor.get_stats()
    assert stats["checks_performed"] == 1
    assert stats["alerts_generated"] >= 1
    assert stats["last_check_at"] is not None


def test_reset_stats(monitor, budget_manager, cost_tracker):
    """Reset clears stats but preserves running state"""
    budget_manager.create_budget(
        period=BudgetPeriod.DAILY,
        limit_amount=10.0,
        user_email="reset_test@example.com",
        alert_threshold=0.5,
    )

    cost_tracker.track_request(
        model="gpt-4",
        provider="openai",
        prompt_tokens=1000,
        completion_tokens=500,
        total_cost=6.0,
        user_email="reset_test@example.com",
    )

    monitor.check_now()
    assert monitor.stats.checks_performed > 0

    monitor.reset_stats()
    stats = monitor.get_stats()
    assert stats["checks_performed"] == 0
    assert stats["alerts_generated"] == 0


# ── Callback Tests ─────────────────────────────────────────────────────────


def test_on_alert_generated_callback(monitor, budget_manager, cost_tracker):
    """Callback fires when alerts are generated"""
    cb_alerts = []

    def callback(alert_ids):
        cb_alerts.extend(alert_ids)

    monitor.on_alert_generated = callback

    budget_manager.create_budget(
        period=BudgetPeriod.DAILY,
        limit_amount=10.0,
        user_email="cb_test@example.com",
        alert_threshold=0.5,
    )

    cost_tracker.track_request(
        model="gpt-4",
        provider="openai",
        prompt_tokens=1000,
        completion_tokens=500,
        total_cost=6.0,
        user_email="cb_test@example.com",
    )

    monitor.check_now()
    assert len(cb_alerts) >= 1


def test_on_delivery_complete_callback(monitor, budget_manager, cost_tracker):
    """Callback fires when deliveries complete"""
    cb_result = None

    def callback(result):
        nonlocal cb_result
        cb_result = result

    monitor.on_delivery_complete = callback
    monitor.webhook_manager.deliver_pending_alerts.return_value = {
        "success_count": 1,
        "failure_count": 0,
        "alerts_processed": 1,
    }

    budget_manager.create_budget(
        period=BudgetPeriod.DAILY,
        limit_amount=10.0,
        user_email="cb2_test@example.com",
        alert_threshold=0.5,
    )

    cost_tracker.track_request(
        model="gpt-4",
        provider="openai",
        prompt_tokens=1000,
        completion_tokens=500,
        total_cost=6.0,
        user_email="cb2_test@example.com",
    )

    monitor.check_now()
    assert cb_result is not None
    assert cb_result["success_count"] == 1


def test_callback_exception_isolated(monitor, budget_manager, cost_tracker):
    """Exception in callback does not break the check cycle"""
    def bad_callback(_):
        raise RuntimeError("callback failure")

    monitor.on_alert_generated = bad_callback

    budget_manager.create_budget(
        period=BudgetPeriod.DAILY,
        limit_amount=10.0,
        user_email="cb_bad@example.com",
        alert_threshold=0.5,
    )

    cost_tracker.track_request(
        model="gpt-4",
        provider="openai",
        prompt_tokens=1000,
        completion_tokens=500,
        total_cost=6.0,
        user_email="cb_bad@example.com",
    )

    # Should not raise
    result = monitor.check_now()
    assert result["alerts_generated"] >= 1


# ── Error Handling Tests ─────────────────────────────────────────────────


def test_check_cycle_exception_caught(monitor):
    """Exceptions in check cycle are caught and logged"""
    # Break budget_manager to force exception
    monitor.budget_manager = MagicMock()
    monitor.budget_manager.generate_alerts.side_effect = RuntimeError("boom")

    monitor.start()
    time.sleep(1.5)
    monitor.stop()

    assert monitor.stats.last_error is not None
    assert "boom" in monitor.stats.last_error


# ── Singleton Tests ────────────────────────────────────────────────────────


def test_get_budget_monitor_singleton():
    """get_budget_monitor returns same instance"""
    m1 = get_budget_monitor(interval_seconds=30)
    m2 = get_budget_monitor(interval_seconds=30)
    assert m1 is m2


def test_get_budget_monitor_respects_interval():
    """First call's interval is preserved"""
    # Reset singleton to ensure fresh instance
    import toolkit_extensions.budget_monitor as bm_module
    with bm_module._monitor_lock:
        bm_module._monitor_instance = None
    m1 = get_budget_monitor(interval_seconds=45)
    assert m1.interval_seconds == 45
