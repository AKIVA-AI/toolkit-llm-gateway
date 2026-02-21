"""
Tests for alert webhook system
"""
import pytest
import json
from datetime import datetime
from unittest.mock import Mock, patch

from toolkit_extensions.database.connection import init_database, DatabaseConfig
from toolkit_extensions.alert_webhooks import (
    AlertWebhookManager, WebhookProvider,
    get_alert_webhook_manager
)
from toolkit_extensions.budget_manager import BudgetManager, BudgetPeriod
from toolkit_extensions.cost_tracker import CostTracker


@pytest.fixture
def db_manager():
    """Create test database manager"""
    import os
    import tempfile
    
    # Create temporary database file
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    config = DatabaseConfig(database_url=f"sqlite:///{db_path}")
    
    # Import webhook models to ensure tables are created
    from toolkit_extensions.alert_webhooks import WebhookConfig, WebhookDelivery
    
    manager = init_database(config)
    yield manager
    
    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def webhook_manager(db_manager):
    """Create webhook manager"""
    return AlertWebhookManager()


@pytest.fixture
def budget_manager(db_manager):
    """Create budget manager"""
    return BudgetManager()


@pytest.fixture
def cost_tracker(db_manager):
    """Create cost tracker"""
    return CostTracker(enabled=True)


def test_register_webhook(webhook_manager):
    """Test registering a webhook"""
    webhook_id = webhook_manager.register_webhook(
        name="Test Webhook",
        url="https://example.com/webhook",
        provider=WebhookProvider.GENERIC,
        secret="test_secret",
        alert_types=["threshold_warning", "budget_exceeded"],
        teams=["Engineering"],
        max_retries=3,
    )
    
    assert webhook_id is not None
    assert len(webhook_id) == 36  # UUID


def test_get_webhooks(webhook_manager):
    """Test getting webhooks"""
    # Register webhooks
    webhook_manager.register_webhook(
        name="Webhook 1",
        url="https://example.com/webhook1",
        enabled=True,
    )
    webhook_manager.register_webhook(
        name="Webhook 2",
        url="https://example.com/webhook2",
        enabled=False,
    )
    
    # Get enabled only
    webhooks = webhook_manager.get_webhooks(enabled_only=True)
    assert len(webhooks) == 1
    assert webhooks[0]["name"] == "Webhook 1"
    
    # Get all
    webhooks = webhook_manager.get_webhooks(enabled_only=False)
    assert len(webhooks) == 2


def test_update_webhook(webhook_manager):
    """Test updating a webhook"""
    webhook_id = webhook_manager.register_webhook(
        name="Test Webhook",
        url="https://example.com/webhook",
    )
    
    # Update
    success = webhook_manager.update_webhook(
        webhook_id,
        name="Updated Webhook",
        enabled=False,
    )
    assert success
    
    # Verify
    webhooks = webhook_manager.get_webhooks(enabled_only=False)
    webhook = [w for w in webhooks if w["id"] == webhook_id][0]
    assert webhook["name"] == "Updated Webhook"
    assert webhook["enabled"] is False


def test_delete_webhook(webhook_manager):
    """Test deleting a webhook"""
    webhook_id = webhook_manager.register_webhook(
        name="Test Webhook",
        url="https://example.com/webhook",
    )
    
    # Delete
    success = webhook_manager.delete_webhook(webhook_id)
    assert success
    
    # Verify
    webhooks = webhook_manager.get_webhooks(enabled_only=False)
    assert len(webhooks) == 0


def test_generic_payload(webhook_manager):
    """Test generic payload building"""
    alert = {
        "id": "test-alert-id",
        "alert_type": "threshold_warning",
        "current_spend": 85.0,
        "budget_limit": 100.0,
        "percentage_used": 85.0,
    }
    
    payload = webhook_manager._build_generic_payload(alert)
    
    assert "event" in payload
    assert payload["event"] == "budget_alert"
    assert "alert" in payload
    assert payload["alert"]["id"] == "test-alert-id"


def test_slack_payload(webhook_manager):
    """Test Slack payload building"""
    alert = {
        "id": "test-alert-id",
        "alert_type": "threshold_warning",
        "current_spend": 85.0,
        "budget_limit": 100.0,
        "percentage_used": 85.0,
    }
    
    payload = webhook_manager._build_slack_payload(alert)
    
    assert "attachments" in payload
    assert len(payload["attachments"]) == 1
    assert payload["attachments"][0]["color"] == "warning"
    assert len(payload["attachments"][0]["fields"]) == 3


def test_discord_payload(webhook_manager):
    """Test Discord payload building"""
    alert = {
        "id": "test-alert-id",
        "alert_type": "budget_exceeded",
        "current_spend": 120.0,
        "budget_limit": 100.0,
        "percentage_used": 120.0,
    }
    
    payload = webhook_manager._build_discord_payload(alert)
    
    assert "embeds" in payload
    assert len(payload["embeds"]) == 1
    assert payload["embeds"][0]["color"] == 0xFF0000  # Red for exceeded


def test_teams_payload(webhook_manager):
    """Test Microsoft Teams payload building"""
    alert = {
        "id": "test-alert-id",
        "alert_type": "threshold_warning",
        "current_spend": 85.0,
        "budget_limit": 100.0,
        "percentage_used": 85.0,
    }
    
    payload = webhook_manager._build_teams_payload(alert)
    
    assert "@type" in payload
    assert payload["@type"] == "MessageCard"
    assert "sections" in payload
    assert len(payload["sections"][0]["facts"]) == 3


def test_payload_signing(webhook_manager):
    """Test HMAC payload signing"""
    payload = {"test": "data"}
    secret = "test_secret"
    
    signature = webhook_manager._sign_payload(payload, secret)
    
    assert signature is not None
    assert len(signature) == 64  # SHA256 hex digest


@patch("httpx.post")
def test_deliver_to_webhook_success(mock_post, webhook_manager, budget_manager, cost_tracker):
    """Test successful webhook delivery"""
    # Mock successful response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = "OK"
    mock_post.return_value = mock_response
    
    # Create budget and alert
    budget_manager.create_budget(
        period=BudgetPeriod.DAILY,
        limit_amount=100.0,
        user_email="user@test.com",
    )
    
    cost_tracker.track_request(
        model="gpt-4",
        provider="openai",
        prompt_tokens=100,
        completion_tokens=50,
        total_cost=85.0,
        user_email="user@test.com",
    )
    
    budget_manager.generate_alerts()
    alerts = budget_manager.get_unsent_alerts()
    
    # Register webhook
    webhook_id = webhook_manager.register_webhook(
        name="Test Webhook",
        url="https://example.com/webhook",
    )
    
    webhooks = webhook_manager.get_webhooks()
    
    # Deliver
    success = webhook_manager._deliver_to_webhook(webhooks[0], alerts[0])
    
    assert success
    assert mock_post.called


@patch("httpx.post")
def test_deliver_to_webhook_failure(mock_post, webhook_manager, budget_manager, cost_tracker):
    """Test webhook delivery failure"""
    # Mock failed response
    mock_response = Mock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_post.return_value = mock_response
    
    # Create budget and alert
    budget_manager.create_budget(
        period=BudgetPeriod.DAILY,
        limit_amount=100.0,
        user_email="user@test.com",
    )
    
    cost_tracker.track_request(
        model="gpt-4",
        provider="openai",
        prompt_tokens=100,
        completion_tokens=50,
        total_cost=85.0,
        user_email="user@test.com",
    )
    
    budget_manager.generate_alerts()
    alerts = budget_manager.get_unsent_alerts()
    
    # Register webhook
    webhook_id = webhook_manager.register_webhook(
        name="Test Webhook",
        url="https://example.com/webhook",
    )
    
    webhooks = webhook_manager.get_webhooks()
    
    # Deliver
    success = webhook_manager._deliver_to_webhook(webhooks[0], alerts[0])
    
    assert not success
    assert mock_post.called


@patch("httpx.post")
def test_deliver_pending_alerts(mock_post, webhook_manager, budget_manager, cost_tracker):
    """Test delivering all pending alerts"""
    # Mock successful response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = "OK"
    mock_post.return_value = mock_response
    
    # Register webhook
    webhook_manager.register_webhook(
        name="Test Webhook",
        url="https://example.com/webhook",
    )
    
    # Create multiple budgets and alerts
    for i in range(3):
        budget_manager.create_budget(
            period=BudgetPeriod.DAILY,
            limit_amount=100.0,
            user_email=f"user{i}@test.com",
        )
        
        cost_tracker.track_request(
            model="gpt-4",
            provider="openai",
            prompt_tokens=100,
            completion_tokens=50,
            total_cost=85.0,
            user_email=f"user{i}@test.com",
        )
    
    budget_manager.generate_alerts()
    
    # Deliver
    result = webhook_manager.deliver_pending_alerts()
    
    assert result["alerts_processed"] == 3
    assert result["success_count"] == 3
    assert result["failure_count"] == 0


def test_webhook_filtering(webhook_manager):
    """Test webhook filtering by alert type"""
    # Register webhook with filter
    webhook_id = webhook_manager.register_webhook(
        name="Threshold Webhook",
        url="https://example.com/webhook",
        alert_types=["threshold_warning"],
    )
    
    webhooks = webhook_manager.get_webhooks()
    
    # Test matching alert
    alert1 = {"alert_type": "threshold_warning"}
    matching = webhook_manager._filter_webhooks_for_alert(webhooks, alert1)
    assert len(matching) == 1
    
    # Test non-matching alert
    alert2 = {"alert_type": "budget_exceeded"}
    matching = webhook_manager._filter_webhooks_for_alert(webhooks, alert2)
    assert len(matching) == 0


def test_get_delivery_stats(webhook_manager):
    """Test getting delivery statistics"""
    webhook_id = webhook_manager.register_webhook(
        name="Test Webhook",
        url="https://example.com/webhook",
    )
    
    # Update stats manually
    webhook_manager._update_webhook_stats(webhook_id, True)
    webhook_manager._update_webhook_stats(webhook_id, True)
    webhook_manager._update_webhook_stats(webhook_id, False)
    
    # Get stats
    stats = webhook_manager.get_delivery_stats(webhook_id)
    
    assert stats["total_deliveries"] == 3
    assert stats["success_count"] == 2
    assert stats["failure_count"] == 1
    assert stats["success_rate"] == pytest.approx(66.67, rel=0.1)


def test_global_instance():
    """Test global webhook manager instance"""
    manager1 = get_alert_webhook_manager()
    manager2 = get_alert_webhook_manager()
    
    assert manager1 is manager2  # Same instance

