"""
Tests for budget manager
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from toolkit_extensions.database.connection import init_database, DatabaseConfig
from toolkit_extensions.database.models import User, Team, Project
from toolkit_extensions.budget_manager import BudgetManager, BudgetPeriod, BudgetStatus
from toolkit_extensions.cost_tracker import CostTracker


@pytest.fixture(scope="module")
def db_manager():
    """Create test database manager (shared across module)"""
    config = DatabaseConfig(database_url="sqlite:///./test_budget.db")
    manager = init_database(config)
    yield manager
    # Cleanup
    import os
    if os.path.exists("./test_budget.db"):
        os.remove("./test_budget.db")


@pytest.fixture
def budget_manager(db_manager):
    """Create budget manager"""
    return BudgetManager(block_on_exceeded=False)


@pytest.fixture
def cost_tracker(db_manager):
    """Create cost tracker"""
    return CostTracker(enabled=True)


def test_create_user_budget(db_manager, budget_manager):
    """Test creating a user budget"""
    budget_id = budget_manager.create_budget(
        period=BudgetPeriod.DAILY,
        limit_amount=100.0,
        user_email="test1@company.com",
        alert_threshold=0.8,
    )
    
    assert budget_id is not None


def test_create_team_budget(db_manager, budget_manager):
    """Test creating a team budget"""
    budget_id = budget_manager.create_budget(
        period=BudgetPeriod.MONTHLY,
        limit_amount=5000.0,
        team_name="Engineering",
        alert_threshold=0.9,
    )
    
    assert budget_id is not None


def test_create_project_budget(db_manager, budget_manager):
    """Test creating a project budget"""
    budget_id = budget_manager.create_budget(
        period=BudgetPeriod.WEEKLY,
        limit_amount=500.0,
        project_name="Chatbot v2",
        alert_threshold=0.75,
    )
    
    assert budget_id is not None


def test_budget_attribution_validation(db_manager, budget_manager):
    """Test that exactly one attribution is required"""
    # No attribution
    with pytest.raises(ValueError, match="exactly one"):
        budget_manager.create_budget(
            period=BudgetPeriod.DAILY,
            limit_amount=100.0,
        )
    
    # Multiple attributions
    with pytest.raises(ValueError, match="exactly one"):
        budget_manager.create_budget(
            period=BudgetPeriod.DAILY,
            limit_amount=100.0,
            user_email="test@company.com",
            team_name="Engineering",
        )


def test_duplicate_budget_prevention(db_manager, budget_manager):
    """Test that duplicate budgets are prevented"""
    # Create first budget
    budget_manager.create_budget(
        period=BudgetPeriod.DAILY,
        limit_amount=100.0,
        user_email="duplicate_test@company.com",
    )
    
    # Try to create duplicate
    with pytest.raises(ValueError, match="already exists"):
        budget_manager.create_budget(
            period=BudgetPeriod.DAILY,
            limit_amount=200.0,
            user_email="duplicate_test@company.com",
        )


def test_check_budget_no_spend(db_manager, budget_manager):
    """Test checking budget with no spend"""
    budget_manager.create_budget(
        period=BudgetPeriod.DAILY,
        limit_amount=100.0,
        user_email="no_spend@company.com",
    )
    
    status = budget_manager.check_budget(user_email="no_spend@company.com")
    
    assert status["status"] == BudgetStatus.OK
    assert status["can_proceed"] is True
    assert len(status["budgets"]) == 1
    assert status["budgets"][0]["current_spend"] == 0.0


def test_check_budget_with_spend(db_manager, budget_manager, cost_tracker):
    """Test checking budget with some spend"""
    user_email = "with_spend@company.com"
    
    # Create budget
    budget_manager.create_budget(
        period=BudgetPeriod.DAILY,
        limit_amount=100.0,
        user_email=user_email,
        alert_threshold=0.8,
    )
    
    # Add some spend (below threshold)
    cost_tracker.track_request(
        model="gpt-4",
        provider="openai",
        prompt_tokens=100,
        completion_tokens=50,
        total_cost=50.0,
        user_email=user_email,
    )
    
    status = budget_manager.check_budget(user_email=user_email)
    
    assert status["status"] == BudgetStatus.OK
    assert status["can_proceed"] is True
    assert status["budgets"][0]["current_spend"] == 50.0
    assert status["budgets"][0]["percentage_used"] == 50.0


def test_check_budget_approaching(db_manager, budget_manager, cost_tracker):
    """Test budget approaching threshold"""
    user_email = "approaching@company.com"
    
    # Create budget with 80% threshold
    budget_manager.create_budget(
        period=BudgetPeriod.DAILY,
        limit_amount=100.0,
        user_email=user_email,
        alert_threshold=0.8,
    )
    
    # Add spend at 85% of limit
    cost_tracker.track_request(
        model="gpt-4",
        provider="openai",
        prompt_tokens=100,
        completion_tokens=50,
        total_cost=85.0,
        user_email=user_email,
    )
    
    status = budget_manager.check_budget(user_email=user_email)
    
    assert status["status"] == BudgetStatus.APPROACHING
    assert status["can_proceed"] is True
    assert status["budgets"][0]["percentage_used"] == 85.0


def test_check_budget_exceeded(db_manager, budget_manager, cost_tracker):
    """Test budget exceeded"""
    user_email = "exceeded@company.com"
    
    # Create budget
    budget_manager.create_budget(
        period=BudgetPeriod.DAILY,
        limit_amount=100.0,
        user_email=user_email,
    )
    
    # Add spend over limit
    cost_tracker.track_request(
        model="gpt-4",
        provider="openai",
        prompt_tokens=100,
        completion_tokens=50,
        total_cost=150.0,
        user_email=user_email,
    )
    
    status = budget_manager.check_budget(user_email=user_email)
    
    assert status["status"] == BudgetStatus.EXCEEDED
    # Should still allow by default (block_on_exceeded=False)
    assert status["can_proceed"] is True
    assert status["budgets"][0]["percentage_used"] == 150.0


def test_block_on_exceeded(db_manager, cost_tracker):
    """Test blocking when budget exceeded"""
    user_email = "blocked@company.com"
    
    # Create budget manager with blocking enabled
    blocking_manager = BudgetManager(block_on_exceeded=True)
    
    # Create budget
    blocking_manager.create_budget(
        period=BudgetPeriod.DAILY,
        limit_amount=100.0,
        user_email=user_email,
    )
    
    # Add spend over limit
    cost_tracker.track_request(
        model="gpt-4",
        provider="openai",
        prompt_tokens=100,
        completion_tokens=50,
        total_cost=150.0,
        user_email=user_email,
    )
    
    status = blocking_manager.check_budget(user_email=user_email)
    
    assert status["status"] == BudgetStatus.EXCEEDED
    # Should block when enabled
    assert status["can_proceed"] is False


def test_update_budget(db_manager, budget_manager):
    """Test updating a budget"""
    user_email = "update_test@company.com"
    
    # Create budget
    budget_id = budget_manager.create_budget(
        period=BudgetPeriod.DAILY,
        limit_amount=100.0,
        user_email=user_email,
        alert_threshold=0.8,
    )
    
    # Update budget
    budget_manager.update_budget(
        budget_id=budget_id,
        limit_amount=200.0,
        alert_threshold=0.9,
    )
    
    # Check updated values
    status = budget_manager.check_budget(user_email=user_email)
    assert status["budgets"][0]["limit"] == 200.0


def test_disable_budget(db_manager, budget_manager):
    """Test disabling a budget"""
    user_email = "disable_test@company.com"
    
    # Create budget
    budget_id = budget_manager.create_budget(
        period=BudgetPeriod.DAILY,
        limit_amount=100.0,
        user_email=user_email,
    )
    
    # Disable budget
    budget_manager.update_budget(budget_id=budget_id, enabled=False)
    
    # Check that budget is disabled
    status = budget_manager.check_budget(user_email=user_email)
    assert len(status["budgets"]) == 0  # Disabled budgets not returned


def test_generate_threshold_alert(db_manager, budget_manager, cost_tracker):
    """Test generating alert when threshold crossed"""
    user_email = "alert_threshold@company.com"
    
    # Create budget
    budget_manager.create_budget(
        period=BudgetPeriod.DAILY,
        limit_amount=100.0,
        user_email=user_email,
        alert_threshold=0.8,
    )
    
    # Add spend over threshold
    cost_tracker.track_request(
        model="gpt-4",
        provider="openai",
        prompt_tokens=100,
        completion_tokens=50,
        total_cost=90.0,
        user_email=user_email,
    )
    
    # Generate alerts
    alert_ids = budget_manager.generate_alerts()
    
    assert len(alert_ids) > 0
    
    # Check alert details
    unsent = budget_manager.get_unsent_alerts()
    assert len(unsent) > 0
    
    # Find the alert for this test (filter by percentage to ensure we get the right one)
    alert = next((a for a in unsent if a["id"] in alert_ids and a["percentage_used"] == 90.0), None)
    assert alert is not None
    assert alert["alert_type"] == "threshold_warning"


def test_generate_exceeded_alert(db_manager, budget_manager, cost_tracker):
    """Test generating alert when budget exceeded"""
    user_email = "alert_exceeded@company.com"
    
    # Create budget
    budget_manager.create_budget(
        period=BudgetPeriod.DAILY,
        limit_amount=100.0,
        user_email=user_email,
    )
    
    # Add spend over limit
    cost_tracker.track_request(
        model="gpt-4",
        provider="openai",
        prompt_tokens=100,
        completion_tokens=50,
        total_cost=150.0,
        user_email=user_email,
    )
    
    # Generate alerts
    alert_ids = budget_manager.generate_alerts()
    
    assert len(alert_ids) > 0
    
    # Check alert details
    unsent = budget_manager.get_unsent_alerts()
    alert = [a for a in unsent if a["alert_type"] == "budget_exceeded"]
    assert len(alert) > 0
    assert alert[0]["percentage_used"] == 150.0


def test_mark_alert_sent(db_manager, budget_manager, cost_tracker):
    """Test marking alert as sent"""
    user_email = "alert_sent@company.com"
    
    # Create budget and spend
    budget_manager.create_budget(
        period=BudgetPeriod.DAILY,
        limit_amount=100.0,
        user_email=user_email,
        alert_threshold=0.8,
    )
    
    cost_tracker.track_request(
        model="gpt-4",
        provider="openai",
        prompt_tokens=100,
        completion_tokens=50,
        total_cost=90.0,
        user_email=user_email,
    )
    
    # Generate and mark alert as sent
    alert_ids = budget_manager.generate_alerts()
    assert len(alert_ids) > 0
    
    budget_manager.mark_alert_sent(
        alert_id=alert_ids[0],
        channels={"email": True, "slack": False}
    )
    
    # Check that alert is no longer in unsent
    unsent = budget_manager.get_unsent_alerts()
    unsent_ids = [a["id"] for a in unsent]
    assert alert_ids[0] not in unsent_ids


def test_no_duplicate_alerts(db_manager, budget_manager, cost_tracker):
    """Test that duplicate alerts aren't created for same period"""
    user_email = "no_dup_alerts@company.com"
    
    # Create budget
    budget_manager.create_budget(
        period=BudgetPeriod.DAILY,
        limit_amount=100.0,
        user_email=user_email,
        alert_threshold=0.8,
    )
    
    # Add spend
    cost_tracker.track_request(
        model="gpt-4",
        provider="openai",
        prompt_tokens=100,
        completion_tokens=50,
        total_cost=90.0,
        user_email=user_email,
    )
    
    # Generate alerts twice
    alert_ids_1 = budget_manager.generate_alerts()
    alert_ids_2 = budget_manager.generate_alerts()
    
    # Should only create one alert
    assert len(alert_ids_1) > 0
    assert len(alert_ids_2) == 0


def test_monthly_budget_period(db_manager, budget_manager, cost_tracker):
    """Test monthly budget period calculations"""
    user_email = "monthly@company.com"
    
    budget_manager.create_budget(
        period=BudgetPeriod.MONTHLY,
        limit_amount=1000.0,
        user_email=user_email,
    )
    
    cost_tracker.track_request(
        model="gpt-4",
        provider="openai",
        prompt_tokens=100,
        completion_tokens=50,
        total_cost=250.0,
        user_email=user_email,
    )
    
    status = budget_manager.check_budget(user_email=user_email)
    
    assert status["budgets"][0]["period"] == "monthly"
    assert status["budgets"][0]["current_spend"] == 250.0
    assert status["budgets"][0]["percentage_used"] == 25.0

