"""
Tests for database models
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from toolkit_extensions.database.models import (
    APIKey,
    Base,
    Budget,
    BudgetAlert,
    CostAggregate,
    LLMRequest,
    Project,
    Team,
    User,
)


@pytest.fixture
def engine():
    """Create in-memory SQLite database for testing"""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """Create database session"""
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


def test_create_team(session):
    """Test creating a team"""
    team = Team(name="Engineering", description="Engineering team", cost_center="CC-100")
    session.add(team)
    session.commit()

    assert team.id is not None
    assert team.name == "Engineering"
    assert team.status == "active"


def test_create_user(session):
    """Test creating a user"""
    team = Team(name="Engineering")
    session.add(team)
    session.commit()

    user = User(email="alice@company.com", name="Alice Smith", team_id=team.id)
    session.add(user)
    session.commit()

    assert user.id is not None
    assert user.email == "alice@company.com"
    assert user.team_id == team.id


def test_create_project(session):
    """Test creating a project"""
    team = Team(name="Engineering")
    user = User(email="alice@company.com", team_id=team.id)
    session.add_all([team, user])
    session.commit()

    project = Project(
        name="Chatbot v2", description="Customer support chatbot", team_id=team.id, owner_id=user.id
    )
    session.add(project)
    session.commit()

    assert project.id is not None
    assert project.name == "Chatbot v2"
    assert project.team_id == team.id
    assert project.owner_id == user.id


def test_create_llm_request(session):
    """Test creating an LLM request"""
    user = User(email="alice@company.com")
    session.add(user)
    session.commit()

    request = LLMRequest(
        model="gpt-4",
        provider="openai",
        user_id=user.id,
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        prompt_cost=Decimal("0.003"),
        completion_cost=Decimal("0.003"),
        total_cost=Decimal("0.006"),
        latency_ms=500,
        status="success",
    )
    session.add(request)
    session.commit()

    assert request.id is not None
    assert request.model == "gpt-4"
    assert request.total_cost == Decimal("0.006")
    assert request.total_tokens == 150


def test_create_budget(session):
    """Test creating a budget"""
    user = User(email="alice@company.com")
    session.add(user)
    session.commit()

    budget = Budget(
        user_id=user.id,
        period="daily",
        limit_amount=Decimal("100.00"),
        alert_threshold=Decimal("0.8"),
        start_date=datetime.utcnow(),
    )
    session.add(budget)
    session.commit()

    assert budget.id is not None
    assert budget.period == "daily"
    assert budget.limit_amount == Decimal("100.00")
    assert budget.enabled is True


def test_budget_constraint(session):
    """Test budget attribution constraint"""
    user = User(email="alice@company.com")
    team = Team(name="Engineering")
    session.add_all([user, team])
    session.commit()

    # This should fail - can't have both user_id and team_id
    with pytest.raises(Exception):
        budget = Budget(
            user_id=user.id,
            team_id=team.id,
            period="daily",
            limit_amount=Decimal("100.00"),
            start_date=datetime.utcnow(),
        )
        session.add(budget)
        session.commit()


def test_create_budget_alert(session):
    """Test creating a budget alert"""
    user = User(email="alice@company.com")
    session.add(user)
    session.commit()

    budget = Budget(
        user_id=user.id,
        period="daily",
        limit_amount=Decimal("100.00"),
        start_date=datetime.utcnow(),
    )
    session.add(budget)
    session.commit()

    alert = BudgetAlert(
        budget_id=budget.id,
        alert_type="threshold_warning",
        current_spend=Decimal("85.00"),
        budget_limit=Decimal("100.00"),
        percentage_used=Decimal("85.00"),
        notification_sent=True,
        notification_channels={"email": True, "slack": False},
    )
    session.add(alert)
    session.commit()

    assert alert.id is not None
    assert alert.alert_type == "threshold_warning"
    assert alert.percentage_used == Decimal("85.00")


def test_create_api_key(session):
    """Test creating an API key"""
    user = User(email="alice@company.com")
    session.add(user)
    session.commit()

    api_key = APIKey(
        key_hash="hashed_key_12345",
        key_prefix="ak_12345",
        user_id=user.id,
        name="Development Key",
        rate_limit_rpm=100,
        rate_limit_tpm=100000,
    )
    session.add(api_key)
    session.commit()

    assert api_key.id is not None
    assert api_key.key_prefix == "ak_12345"
    assert api_key.status == "active"


def test_create_cost_aggregate(session):
    """Test creating a cost aggregate"""
    aggregate = CostAggregate(
        dimension_type="user",
        dimension_id="user-123",
        period_type="day",
        period_start=datetime.utcnow(),
        period_end=datetime.utcnow() + timedelta(days=1),
        total_requests=100,
        total_tokens=50000,
        total_cost=Decimal("25.50"),
        avg_latency_ms=500,
        cache_hit_rate=Decimal("0.35"),
        error_rate=Decimal("0.02"),
    )
    session.add(aggregate)
    session.commit()

    assert aggregate.id is not None
    assert aggregate.dimension_type == "user"
    assert aggregate.total_cost == Decimal("25.50")


def test_user_team_relationship(session):
    """Test user-team relationship"""
    team = Team(name="Engineering")
    user = User(email="alice@company.com", team=team)
    session.add(user)
    session.commit()

    assert user.team.name == "Engineering"
    assert user in team.users


def test_project_relationships(session):
    """Test project relationships"""
    team = Team(name="Engineering")
    user = User(email="alice@company.com", team=team)
    project = Project(name="Chatbot", team=team, owner=user)
    session.add(project)
    session.commit()

    assert project.team.name == "Engineering"
    assert project.owner.email == "alice@company.com"
    assert project in team.projects
    assert project in user.projects


def test_llm_request_relationships(session):
    """Test LLM request relationships"""
    user = User(email="alice@company.com")
    team = Team(name="Engineering")
    project = Project(name="Chatbot", team=team, owner=user)
    request = LLMRequest(
        model="gpt-4",
        provider="openai",
        user=user,
        team=team,
        project=project,
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        total_cost=Decimal("0.006"),
    )
    session.add(request)
    session.commit()

    assert request.user.email == "alice@company.com"
    assert request.team.name == "Engineering"
    assert request.project.name == "Chatbot"
    assert request in user.requests
    assert request in team.requests
    assert request in project.requests
