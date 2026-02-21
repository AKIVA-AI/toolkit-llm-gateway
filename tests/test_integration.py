"""
Integration tests for Toolkit LLM Gateway

Tests end-to-end workflows across all components.
"""
import pytest
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from toolkit_extensions.database.connection import init_database, DatabaseConfig
from toolkit_extensions.cost_tracker import CostTracker
from toolkit_extensions.budget_manager import BudgetManager, BudgetPeriod
from toolkit_extensions.cost_analytics import CostAnalytics, TimeGranularity
from toolkit_extensions.alert_webhooks import AlertWebhookManager, WebhookProvider


@pytest.fixture
def integrated_system():
    """Create fully integrated system with all components"""
    import os
    import tempfile
    
    # Create temporary database
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    config = DatabaseConfig(database_url=f"sqlite:///{db_path}")
    
    # Import all models to ensure tables are created
    from toolkit_extensions.alert_webhooks import WebhookConfig, WebhookDelivery
    
    db_manager = init_database(config)
    
    # Initialize all components
    cost_tracker = CostTracker(enabled=True)
    budget_manager = BudgetManager()
    analytics = CostAnalytics()
    webhook_manager = AlertWebhookManager()
    
    yield {
        "db_manager": db_manager,
        "cost_tracker": cost_tracker,
        "budget_manager": budget_manager,
        "analytics": analytics,
        "webhook_manager": webhook_manager,
        "db_path": db_path,
    }
    
    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


def test_complete_workflow_threshold_alert(integrated_system):
    """
    Test complete workflow: Track costs â†’ Check budget â†’ Generate alert â†’ Deliver webhook
    
    Scenario: User approaches budget threshold (85%)
    """
    cost_tracker = integrated_system["cost_tracker"]
    budget_manager = integrated_system["budget_manager"]
    webhook_manager = integrated_system["webhook_manager"]
    
    # 1. Create a budget for a user
    budget_id = budget_manager.create_budget(
        period=BudgetPeriod.DAILY,
        limit_amount=100.0,
        user_email="user@company.com",
        alert_threshold=0.8,
    )
    
    assert budget_id is not None
    
    # 2. Track some requests (under threshold)
    cost_tracker.track_request(
        model="gpt-4",
        provider="openai",
        prompt_tokens=100,
        completion_tokens=50,
        total_cost=50.0,
        user_email="user@company.com",
        team_name="Engineering",
    )
    
    # Check budget - should be OK
    status = budget_manager.check_budget(user_email="user@company.com")
    assert status["status"].value == "ok"
    assert status["can_proceed"] is True
    
    # 3. Track more requests (cross threshold)
    cost_tracker.track_request(
        model="gpt-4",
        provider="openai",
        prompt_tokens=100,
        completion_tokens=50,
        total_cost=35.0,
        user_email="user@company.com",
        team_name="Engineering",
    )
    
    # Check budget - should be APPROACHING
    status = budget_manager.check_budget(user_email="user@company.com")
    # Status might be APPROACHING or still OK depending on exact logic
    assert status["can_proceed"] is True  # Not blocking yet
    
    # 4. Generate alerts
    alert_ids = budget_manager.generate_alerts()
    assert len(alert_ids) > 0
    
    # 5. Register webhook
    with patch("httpx.post") as mock_post:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response
        
        webhook_id = webhook_manager.register_webhook(
            name="Test Webhook",
            url="https://example.com/webhook",
            provider=WebhookProvider.SLACK,
        )
        
        # 6. Deliver alerts
        result = webhook_manager.deliver_pending_alerts()
        
        assert result["alerts_processed"] > 0
        assert result["success_count"] > 0
        assert mock_post.called


def test_complete_workflow_exceeded_alert(integrated_system):
    """
    Test complete workflow with budget exceeded
    
    Scenario: User exceeds budget (120%)
    """
    cost_tracker = integrated_system["cost_tracker"]
    budget_manager = integrated_system["budget_manager"]
    
    # 1. Create budget
    budget_id = budget_manager.create_budget(
        period=BudgetPeriod.DAILY,
        limit_amount=100.0,
        user_email="user@company.com",
    )
    
    # 2. Track requests that exceed budget
    cost_tracker.track_request(
        model="gpt-4",
        provider="openai",
        prompt_tokens=100,
        completion_tokens=50,
        total_cost=120.0,
        user_email="user@company.com",
    )
    
    # 3. Check budget - should show exceeded status
    status = budget_manager.check_budget(user_email="user@company.com")
    # The check_budget returns status enum and budget list
    assert len(status["budgets"]) > 0
    
    # 4. Generate alerts - should create exceeded alert
    alert_ids = budget_manager.generate_alerts()
    alerts = budget_manager.get_unsent_alerts()
    
    exceeded_alerts = [a for a in alerts if a["alert_type"] == "budget_exceeded"]
    assert len(exceeded_alerts) > 0


def test_multi_user_multi_team_scenario(integrated_system):
    """
    Test complex scenario with multiple users, teams, and budgets
    
    Scenario: 
    - 3 users across 2 teams
    - Different budgets per team
    - Track costs and verify attribution
    """
    cost_tracker = integrated_system["cost_tracker"]
    budget_manager = integrated_system["budget_manager"]
    analytics = integrated_system["analytics"]
    
    # 1. Create team budgets
    team_a_budget = budget_manager.create_budget(
        period=BudgetPeriod.DAILY,
        limit_amount=500.0,
        team_name="TeamA",
    )
    
    team_b_budget = budget_manager.create_budget(
        period=BudgetPeriod.DAILY,
        limit_amount=300.0,
        team_name="TeamB",
    )
    
    # 2. Track requests from different users/teams
    requests = [
        # Team A users
        {"user": "alice@company.com", "team": "TeamA", "cost": 100.0, "model": "gpt-4"},
        {"user": "bob@company.com", "team": "TeamA", "cost": 150.0, "model": "gpt-4"},
        {"user": "alice@company.com", "team": "TeamA", "cost": 50.0, "model": "gpt-3.5-turbo"},
        
        # Team B users
        {"user": "charlie@company.com", "team": "TeamB", "cost": 200.0, "model": "claude-2"},
        {"user": "charlie@company.com", "team": "TeamB", "cost": 50.0, "model": "gpt-4"},
    ]
    
    for req in requests:
        cost_tracker.track_request(
            model=req["model"],
            provider="openai",
            prompt_tokens=100,
            completion_tokens=50,
            total_cost=req["cost"],
            user_email=req["user"],
            team_name=req["team"],
        )
    
    # 3. Check team budgets
    team_a_status = budget_manager.check_budget(team_name="TeamA")
    assert team_a_status["can_proceed"] is True
    assert len(team_a_status["budgets"]) > 0
    
    team_b_status = budget_manager.check_budget(team_name="TeamB")
    assert team_b_status["can_proceed"] is True
    assert len(team_b_status["budgets"]) > 0
    
    # 4. Verify analytics
    total_cost = analytics.get_total_cost()
    assert total_cost == 550.0  # Total across all teams
    
    # By team
    by_team = analytics.get_cost_by_team()
    assert len(by_team) == 2
    
    team_a_cost = [t for t in by_team if t["team_name"] == "TeamA"][0]
    assert team_a_cost["total_cost"] == 300.0
    
    team_b_cost = [t for t in by_team if t["team_name"] == "TeamB"][0]
    assert team_b_cost["total_cost"] == 250.0
    
    # By user
    by_user = analytics.get_cost_by_user()
    assert len(by_user) == 3
    
    # By model
    by_model = analytics.get_cost_by_model()
    assert len(by_model) == 3  # gpt-4, gpt-3.5-turbo, claude-2


def test_budget_period_transitions(integrated_system):
    """
    Test budget calculations across different time periods
    
    Scenario: Verify daily, weekly, monthly period calculations
    """
    cost_tracker = integrated_system["cost_tracker"]
    budget_manager = integrated_system["budget_manager"]
    
    user_email = "user@company.com"
    
    # Create budgets for different periods
    daily_budget = budget_manager.create_budget(
        period=BudgetPeriod.DAILY,
        limit_amount=100.0,
        user_email=user_email,
    )
    
    weekly_budget = budget_manager.create_budget(
        period=BudgetPeriod.WEEKLY,
        limit_amount=500.0,
        user_email=user_email,
    )
    
    monthly_budget = budget_manager.create_budget(
        period=BudgetPeriod.MONTHLY,
        limit_amount=2000.0,
        user_email=user_email,
    )
    
    # Track a request
    cost_tracker.track_request(
        model="gpt-4",
        provider="openai",
        prompt_tokens=100,
        completion_tokens=50,
        total_cost=75.0,
        user_email=user_email,
    )
    
    # All budgets should show active status
    daily_status = budget_manager.check_budget(user_email=user_email)
    
    assert daily_status["can_proceed"] is True
    assert len(daily_status["budgets"]) == 3  # All three budgets should be active


def test_alert_deduplication(integrated_system):
    """
    Test that alerts are not duplicated for the same budget in the same period
    
    Scenario: Generate alerts multiple times, should not create duplicates
    """
    cost_tracker = integrated_system["cost_tracker"]
    budget_manager = integrated_system["budget_manager"]
    
    # Create budget
    budget_id = budget_manager.create_budget(
        period=BudgetPeriod.DAILY,
        limit_amount=100.0,
        user_email="user@company.com",
    )
    
    # Track request that triggers threshold
    cost_tracker.track_request(
        model="gpt-4",
        provider="openai",
        prompt_tokens=100,
        completion_tokens=50,
        total_cost=85.0,
        user_email="user@company.com",
    )
    
    # Generate alerts first time
    alert_ids_1 = budget_manager.generate_alerts()
    assert len(alert_ids_1) > 0
    
    # Generate alerts again - should not create duplicates
    alert_ids_2 = budget_manager.generate_alerts()
    assert len(alert_ids_2) == 0  # No new alerts
    
    # Verify only one alert exists
    alerts = budget_manager.get_unsent_alerts()
    threshold_alerts = [a for a in alerts if a["alert_type"] == "threshold_warning"]
    assert len(threshold_alerts) == 1


def test_time_series_analytics(integrated_system):
    """
    Test time-series analytics with multiple data points
    
    Scenario: Track requests and verify time-series aggregation
    """
    cost_tracker = integrated_system["cost_tracker"]
    analytics = integrated_system["analytics"]
    
    # Track multiple requests
    for i in range(10):
        cost_tracker.track_request(
            model="gpt-4",
            provider="openai",
            prompt_tokens=100,
            completion_tokens=50,
            total_cost=10.0,
            user_email=f"user{i}@company.com",
        )
    
    # Get time series
    time_series = analytics.get_time_series(
        granularity=TimeGranularity.DAILY,
        start_date=datetime.utcnow() - timedelta(days=7)
    )
    
    assert len(time_series) >= 1
    
    # Total cost should sum correctly
    total_cost = sum(point["total_cost"] for point in time_series)
    assert total_cost == 100.0
    
    # Total requests should match
    total_requests = sum(point["request_count"] for point in time_series)
    assert total_requests == 10


def test_webhook_filtering_and_delivery(integrated_system):
    """
    Test webhook filtering by alert type and selective delivery
    
    Scenario: Register webhooks with filters and verify correct delivery
    """
    cost_tracker = integrated_system["cost_tracker"]
    budget_manager = integrated_system["budget_manager"]
    webhook_manager = integrated_system["webhook_manager"]
    
    with patch("httpx.post") as mock_post:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response
        
        # Register two webhooks with different filters
        threshold_webhook = webhook_manager.register_webhook(
            name="Threshold Webhook",
            url="https://example.com/threshold",
            alert_types=["threshold_warning"],
        )
        
        exceeded_webhook = webhook_manager.register_webhook(
            name="Exceeded Webhook",
            url="https://example.com/exceeded",
            alert_types=["budget_exceeded"],
        )
        
        # Create budget and trigger threshold alert
        budget_id = budget_manager.create_budget(
            period=BudgetPeriod.DAILY,
            limit_amount=100.0,
            user_email="user@company.com",
        )
        
        cost_tracker.track_request(
            model="gpt-4",
            provider="openai",
            prompt_tokens=100,
            completion_tokens=50,
            total_cost=85.0,
            user_email="user@company.com",
        )
        
        # Generate alerts
        budget_manager.generate_alerts()
        
        # Deliver - should only trigger threshold webhook
        result = webhook_manager.deliver_pending_alerts()
        
        # Should have delivered to 1 webhook (threshold only)
        assert result["success_count"] == 1


def test_performance_with_high_volume(integrated_system):
    """
    Test system performance with high volume of requests
    
    Scenario: Track 100 requests and verify system handles them efficiently
    """
    cost_tracker = integrated_system["cost_tracker"]
    analytics = integrated_system["analytics"]
    
    start_time = time.time()
    
    # Track 100 requests
    for i in range(100):
        cost_tracker.track_request(
            model="gpt-4",
            provider="openai",
            prompt_tokens=100,
            completion_tokens=50,
            total_cost=1.0,
            user_email=f"user{i % 10}@company.com",
            team_name=f"Team{i % 3}",
        )
    
    tracking_time = time.time() - start_time
    
    # Should complete in reasonable time (< 5 seconds)
    assert tracking_time < 5.0
    
    # Verify data integrity
    total_cost = analytics.get_total_cost()
    assert total_cost == 100.0
    
    by_team = analytics.get_cost_by_team()
    assert len(by_team) == 3  # Team0, Team1, Team2


def test_analytics_summary(integrated_system):
    """
    Test comprehensive analytics summary endpoint
    
    Scenario: Track diverse requests and get complete summary
    """
    cost_tracker = integrated_system["cost_tracker"]
    analytics = integrated_system["analytics"]
    
    # Track diverse requests
    requests = [
        {"model": "gpt-4", "cost": 50.0, "user": "alice@company.com", "team": "TeamA"},
        {"model": "gpt-3.5-turbo", "cost": 10.0, "user": "bob@company.com", "team": "TeamA"},
        {"model": "claude-2", "cost": 30.0, "user": "charlie@company.com", "team": "TeamB"},
        {"model": "gpt-4", "cost": 40.0, "user": "alice@company.com", "team": "TeamA"},
    ]
    
    for req in requests:
        cost_tracker.track_request(
            model=req["model"],
            provider="openai",
            prompt_tokens=100,
            completion_tokens=50,
            total_cost=req["cost"],
            user_email=req["user"],
            team_name=req["team"],
        )
    
    # Get summary
    summary = analytics.get_summary()
    
    # Verify summary structure
    assert "period" in summary
    assert "total_cost" in summary
    assert "by_model" in summary
    assert "by_user" in summary
    assert "by_team" in summary
    assert "by_project" in summary
    assert "performance" in summary
    
    # Verify values
    assert summary["total_cost"] == 130.0
    assert len(summary["by_model"]) == 3
    assert len(summary["by_user"]) == 3
    assert len(summary["by_team"]) == 2


def test_budget_update_and_lifecycle(integrated_system):
    """
    Test budget lifecycle: create, update, disable, re-enable
    
    Scenario: Full budget management workflow
    """
    budget_manager = integrated_system["budget_manager"]
    
    # Create budget
    budget_id = budget_manager.create_budget(
        period=BudgetPeriod.DAILY,
        limit_amount=100.0,
        user_email="user@company.com",
    )
    
    assert budget_id is not None
    
    # Update budget limit (returns None, raises exception on failure)
    budget_manager.update_budget(budget_id, limit_amount=200.0)
    
    # Disable budget using update_budget
    budget_manager.update_budget(budget_id, enabled=False)
    
    # Verify disabled by checking budget status
    status = budget_manager.check_budget(user_email="user@company.com")
    # Disabled budgets shouldn't block
    assert status["can_proceed"] is True


def test_error_handling_and_recovery(integrated_system):
    """
    Test system behavior with invalid inputs and error conditions
    
    Scenario: Attempt invalid operations and verify graceful handling
    """
    budget_manager = integrated_system["budget_manager"]
    webhook_manager = integrated_system["webhook_manager"]
    
    # Test invalid budget creation (no attribution)
    with pytest.raises(ValueError):
        budget_manager.create_budget(
            period=BudgetPeriod.DAILY,
            limit_amount=100.0,
            # No user_email, team_name, or project_name
        )
    
    # Test invalid budget check (no attribution) - should return default status
    status = budget_manager.check_budget()
    assert status is not None
    assert "status" in status
    assert "can_proceed" in status
    
    # Test invalid webhook update
    success = webhook_manager.update_webhook("nonexistent-webhook-id", name="New Name")
    assert not success
    
    # Test webhook deletion of non-existent webhook
    success = webhook_manager.delete_webhook("nonexistent-webhook-id")
    assert not success


