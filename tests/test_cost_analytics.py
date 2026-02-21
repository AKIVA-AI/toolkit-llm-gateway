"""
Tests for cost analytics
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from toolkit_extensions.database.connection import init_database, DatabaseConfig
from toolkit_extensions.cost_analytics import CostAnalytics, TimeGranularity
from toolkit_extensions.cost_tracker import CostTracker


@pytest.fixture
def db_manager():
    """Create test database manager (new DB per test)"""
    import os
    import tempfile
    
    # Create temporary database file
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    config = DatabaseConfig(database_url=f"sqlite:///{db_path}")
    manager = init_database(config)
    yield manager
    
    # Cleanup
    if os.path.exists(db_path):
        os.remove(db_path)


@pytest.fixture
def analytics(db_manager):
    """Create analytics instance"""
    return CostAnalytics()


@pytest.fixture
def cost_tracker(db_manager):
    """Create cost tracker"""
    return CostTracker(enabled=True)


@pytest.fixture
def sample_data(cost_tracker):
    """Create sample cost data for testing"""
    # Create requests for multiple users, teams, models
    requests = [
        # User 1, Team A, GPT-4
        {"model": "gpt-4", "provider": "openai", "prompt_tokens": 100, "completion_tokens": 50, 
         "total_cost": 10.0, "user_email": "user1@company.com", "team_name": "TeamA", "project_name": "Project1"},
        {"model": "gpt-4", "provider": "openai", "prompt_tokens": 200, "completion_tokens": 100, 
         "total_cost": 20.0, "user_email": "user1@company.com", "team_name": "TeamA", "project_name": "Project1"},
        
        # User 2, Team A, GPT-3.5
        {"model": "gpt-3.5-turbo", "provider": "openai", "prompt_tokens": 500, "completion_tokens": 250, 
         "total_cost": 5.0, "user_email": "user2@company.com", "team_name": "TeamA", "project_name": "Project2"},
        
        # User 3, Team B, Claude
        {"model": "claude-2", "provider": "anthropic", "prompt_tokens": 300, "completion_tokens": 150, 
         "total_cost": 15.0, "user_email": "user3@company.com", "team_name": "TeamB", "project_name": "Project3"},
    ]
    
    for req in requests:
        cost_tracker.track_request(**req)
    
    return requests


def test_get_total_cost(analytics, sample_data):
    """Test getting total cost"""
    total = analytics.get_total_cost()
    assert total == Decimal("50.0")


def test_get_total_cost_with_date_filter(analytics, sample_data):
    """Test total cost with date filtering"""
    # Get cost for yesterday (should be 0)
    yesterday = datetime.utcnow() - timedelta(days=1)
    today = datetime.utcnow()
    
    total = analytics.get_total_cost(start_date=yesterday, end_date=yesterday)
    assert total == Decimal("0")
    
    # Get cost for today
    total = analytics.get_total_cost(start_date=today - timedelta(hours=1))
    assert total == Decimal("50.0")


def test_get_cost_by_model(analytics, sample_data):
    """Test cost breakdown by model"""
    by_model = analytics.get_cost_by_model()
    
    # Should have 3 models
    assert len(by_model) == 3
    
    # Sort by cost
    by_model_sorted = sorted(by_model, key=lambda x: x["total_cost"], reverse=True)
    
    # GPT-4 should be most expensive (30.0)
    assert by_model_sorted[0]["model"] == "gpt-4"
    assert by_model_sorted[0]["total_cost"] == 30.0
    assert by_model_sorted[0]["request_count"] == 2
    
    # Claude should be second (15.0)
    assert by_model_sorted[1]["model"] == "claude-2"
    assert by_model_sorted[1]["total_cost"] == 15.0
    
    # GPT-3.5 should be cheapest (5.0)
    assert by_model_sorted[2]["model"] == "gpt-3.5-turbo"
    assert by_model_sorted[2]["total_cost"] == 5.0


def test_get_cost_by_user(analytics, sample_data):
    """Test cost breakdown by user"""
    by_user = analytics.get_cost_by_user()
    
    # Should have 3 users
    assert len(by_user) == 3
    
    # Should be sorted by cost descending
    assert by_user[0]["total_cost"] >= by_user[1]["total_cost"]
    assert by_user[1]["total_cost"] >= by_user[2]["total_cost"]
    
    # User1 should be most expensive (30.0)
    assert by_user[0]["user_email"] == "user1@company.com"
    assert by_user[0]["total_cost"] == 30.0


def test_get_cost_by_team(analytics, sample_data):
    """Test cost breakdown by team"""
    by_team = analytics.get_cost_by_team()
    
    # Should have 2 teams
    assert len(by_team) == 2
    
    # TeamA should be more expensive (35.0 = 30 + 5)
    team_a = [t for t in by_team if t["team_name"] == "TeamA"][0]
    assert team_a["total_cost"] == 35.0
    assert team_a["request_count"] == 3
    
    # TeamB should be less (15.0)
    team_b = [t for t in by_team if t["team_name"] == "TeamB"][0]
    assert team_b["total_cost"] == 15.0
    assert team_b["request_count"] == 1


def test_get_cost_by_project(analytics, sample_data):
    """Test cost breakdown by project"""
    by_project = analytics.get_cost_by_project()
    
    # Should have 3 projects
    assert len(by_project) == 3
    
    # Should be sorted by cost descending
    assert by_project[0]["total_cost"] >= by_project[1]["total_cost"]
    assert by_project[1]["total_cost"] >= by_project[2]["total_cost"]


def test_get_time_series_daily(analytics, sample_data):
    """Test time series data with daily granularity"""
    time_series = analytics.get_time_series(
        granularity=TimeGranularity.DAILY,
        start_date=datetime.utcnow() - timedelta(days=7)
    )
    
    # Should have at least one data point (today)
    assert len(time_series) >= 1
    
    # Total cost should sum to 50.0
    total_cost = sum(point["total_cost"] for point in time_series)
    assert total_cost == 50.0


def test_get_performance_stats(analytics, sample_data):
    """Test performance statistics"""
    stats = analytics.get_performance_stats()
    
    assert "avg_latency_ms" in stats
    assert "cache_hit_rate" in stats
    assert "error_rate" in stats
    assert "total_requests" in stats
    
    assert stats["total_requests"] == 4


def test_get_summary(analytics, sample_data):
    """Test comprehensive summary"""
    summary = analytics.get_summary()
    
    assert "period" in summary
    assert "total_cost" in summary
    assert "by_model" in summary
    assert "by_user" in summary
    assert "by_team" in summary
    assert "by_project" in summary
    assert "performance" in summary
    
    assert summary["total_cost"] == 50.0
    assert len(summary["by_model"]) == 3
    assert len(summary["by_user"]) == 3
    assert len(summary["by_team"]) == 2


def test_filter_by_user(analytics, sample_data):
    """Test filtering by user"""
    total = analytics.get_total_cost(user_email="user1@company.com")
    assert total == Decimal("30.0")
    
    by_model = analytics.get_cost_by_model(user_email="user1@company.com")
    assert len(by_model) == 1  # Only GPT-4
    assert by_model[0]["model"] == "gpt-4"


def test_filter_by_team(analytics, sample_data):
    """Test filtering by team"""
    total = analytics.get_total_cost(team_name="TeamA")
    assert total == Decimal("35.0")
    
    by_model = analytics.get_cost_by_model(team_name="TeamA")
    assert len(by_model) == 2  # GPT-4 and GPT-3.5


def test_filter_by_project(analytics, sample_data):
    """Test filtering by project"""
    total = analytics.get_total_cost(project_name="Project1")
    assert total == Decimal("30.0")


def test_filter_by_model(analytics, sample_data):
    """Test filtering by model"""
    total = analytics.get_total_cost(model="gpt-4")
    assert total == Decimal("30.0")
    
    stats = analytics.get_performance_stats(model="gpt-4")
    assert stats["total_requests"] == 2


def test_empty_results(analytics):
    """Test analytics with no data"""
    total = analytics.get_total_cost(user_email="nonexistent@company.com")
    assert total == Decimal("0")
    
    by_model = analytics.get_cost_by_model(user_email="nonexistent@company.com")
    assert len(by_model) == 0
    
    stats = analytics.get_performance_stats(user_email="nonexistent@company.com")
    assert stats["total_requests"] == 0

