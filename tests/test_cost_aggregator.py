"""
Tests for cost aggregate materialization
"""

import os
import tempfile
from datetime import datetime, timedelta

import pytest

from toolkit_extensions.cost_aggregator import CostAggregator, get_cost_aggregator
from toolkit_extensions.cost_tracker import CostTracker
from toolkit_extensions.database.connection import DatabaseConfig, get_session, init_database
from toolkit_extensions.database.models import CostAggregate


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
def cost_tracker(db_manager):
    """Create cost tracker"""
    return CostTracker(enabled=True)


@pytest.fixture
def aggregator(db_manager):
    """Create cost aggregator"""
    return CostAggregator()


def _seed_requests(cost_tracker, count=5):
    """Seed some LLM requests for aggregation."""
    for i in range(count):
        cost_tracker.track_request(
            model="gpt-4",
            provider="openai",
            prompt_tokens=100 + i,
            completion_tokens=50 + i,
            total_cost=0.05 * (i + 1),
            latency_ms=200 + i * 10,
            user_email="alice@example.com",
            team_name="engineering",
            project_name="chatbot",
        )


def test_materialize_daily(aggregator, cost_tracker):
    """Test daily materialization creates aggregates."""
    _seed_requests(cost_tracker)

    # Materialize for today
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    count = aggregator.materialize(period_type="daily", target_date=today)

    assert count > 0

    with get_session() as session:
        aggs = session.query(CostAggregate).all()
        assert len(aggs) > 0

        # Should have aggregates for model, provider, user, team, project
        dim_types = {a.dimension_type for a in aggs}
        assert "model" in dim_types
        assert "provider" in dim_types


def test_materialize_hourly(aggregator, cost_tracker):
    """Test hourly materialization."""
    _seed_requests(cost_tracker)

    now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    count = aggregator.materialize(period_type="hourly", target_date=now)

    assert count > 0


def test_materialize_invalid_period(aggregator):
    """Test invalid period type raises ValueError."""
    with pytest.raises(ValueError, match="period_type must be"):
        aggregator.materialize(period_type="yearly")


def test_materialize_no_data(aggregator, db_manager):
    """Test materialization with no request data returns 0."""
    yesterday = datetime.utcnow() - timedelta(days=1)
    count = aggregator.materialize(period_type="daily", target_date=yesterday)
    assert count == 0


def test_materialize_idempotent(aggregator, cost_tracker):
    """Test that re-materializing same period replaces old data."""
    _seed_requests(cost_tracker)

    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    count1 = aggregator.materialize(period_type="daily", target_date=today)
    count2 = aggregator.materialize(period_type="daily", target_date=today)

    assert count1 == count2

    with get_session() as session:
        aggs = session.query(CostAggregate).all()
        # No duplicates
        seen = set()
        for a in aggs:
            key = (a.dimension_type, a.dimension_id, a.period_type, str(a.period_start))
            assert key not in seen, f"Duplicate aggregate: {key}"
            seen.add(key)


def test_aggregate_values_correct(aggregator, cost_tracker):
    """Test that aggregate values are computed correctly."""
    _seed_requests(cost_tracker, count=3)

    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    aggregator.materialize(period_type="daily", target_date=today)

    with get_session() as session:
        model_agg = (
            session.query(CostAggregate)
            .filter_by(dimension_type="model", dimension_id="gpt-4")
            .first()
        )
        assert model_agg is not None
        assert model_agg.total_requests == 3
        assert float(model_agg.total_cost) > 0
        assert model_agg.total_tokens > 0


def test_global_aggregator():
    """Test global singleton."""
    a1 = get_cost_aggregator()
    a2 = get_cost_aggregator()
    assert a1 is a2
