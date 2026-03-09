"""
Tests for async webhook delivery
"""

import asyncio
import os
import tempfile
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from toolkit_extensions.alert_webhooks import AlertWebhookManager, WebhookProvider
from toolkit_extensions.budget_manager import BudgetManager, BudgetPeriod
from toolkit_extensions.cost_tracker import CostTracker
from toolkit_extensions.database.connection import DatabaseConfig, init_database


@pytest.fixture
def db_manager():
    """Create test database manager"""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    config = DatabaseConfig(database_url=f"sqlite:///{db_path}")
    manager = init_database(config)
    yield manager

    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def webhook_manager(db_manager):
    return AlertWebhookManager()


@pytest.fixture
def budget_manager(db_manager):
    return BudgetManager()


@pytest.fixture
def cost_tracker(db_manager):
    return CostTracker(enabled=True)


def _create_alert(budget_manager, cost_tracker):
    """Helper to create a budget alert."""
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
    return budget_manager.get_unsent_alerts()


@pytest.mark.asyncio
async def test_async_deliver_success(webhook_manager, budget_manager, cost_tracker):
    """Test async delivery succeeds."""
    alerts = _create_alert(budget_manager, cost_tracker)
    webhook_id = webhook_manager.register_webhook(
        name="Test",
        url="https://example.com/webhook",
    )
    webhooks = webhook_manager.get_webhooks()

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = "OK"

    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client

        result = await webhook_manager._async_deliver_to_webhook(webhooks[0], alerts[0])

    assert result is True
    mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_async_deliver_retry_on_failure(webhook_manager, budget_manager, cost_tracker):
    """Test async delivery retries on 500 error."""
    alerts = _create_alert(budget_manager, cost_tracker)
    webhook_manager.register_webhook(
        name="Test",
        url="https://example.com/webhook",
        max_retries=2,
    )
    webhooks = webhook_manager.get_webhooks()

    # First call fails, second succeeds
    fail_response = Mock()
    fail_response.status_code = 500
    fail_response.text = "Error"

    success_response = Mock()
    success_response.status_code = 200
    success_response.text = "OK"

    call_count = 0

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return fail_response
        return success_response

    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.post = mock_post
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client

        # Patch asyncio.sleep to avoid actual delays
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await webhook_manager._async_deliver_to_webhook(webhooks[0], alerts[0])

    assert result is True
    assert call_count == 2


@pytest.mark.asyncio
async def test_async_deliver_exception_retry(webhook_manager, budget_manager, cost_tracker):
    """Test async delivery retries on network exception."""
    alerts = _create_alert(budget_manager, cost_tracker)
    webhook_manager.register_webhook(
        name="Test",
        url="https://example.com/webhook",
        max_retries=2,
    )
    webhooks = webhook_manager.get_webhooks()

    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.ConnectError("Connection refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await webhook_manager._async_deliver_to_webhook(webhooks[0], alerts[0])

    assert result is False


def test_sync_wrapper_calls_async(webhook_manager, budget_manager, cost_tracker):
    """Test that _deliver_to_webhook sync wrapper works."""
    alerts = _create_alert(budget_manager, cost_tracker)
    webhook_manager.register_webhook(
        name="Test",
        url="https://example.com/webhook",
    )
    webhooks = webhook_manager.get_webhooks()

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.text = "OK"

    with patch("httpx.AsyncClient") as MockClient:
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client

        result = webhook_manager._deliver_to_webhook(webhooks[0], alerts[0])

    assert result is True
