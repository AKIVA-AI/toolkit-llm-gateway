"""
Tests for cost tracking
"""
import pytest
from decimal import Decimal
from unittest.mock import Mock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from toolkit_extensions.database.models import Base, User, Team, Project, LLMRequest
from toolkit_extensions.database.connection import DatabaseManager, DatabaseConfig, init_database
from toolkit_extensions.cost_tracker import CostTracker, CostTrackingMiddleware


@pytest.fixture(scope="module")
def db_manager():
    """Create test database manager (shared across module)"""
    config = DatabaseConfig(database_url="sqlite:///./test_gateway.db")
    # Initialize global database manager for tests
    manager = init_database(config)
    yield manager
    # Cleanup
    import os
    if os.path.exists("./test_gateway.db"):
        os.remove("./test_gateway.db")


@pytest.fixture
def cost_tracker(db_manager):
    """Create cost tracker"""
    return CostTracker(enabled=True)


def test_track_basic_request(db_manager, cost_tracker):
    """Test tracking a basic request"""
    request_id = cost_tracker.track_request(
        model="gpt-4",
        provider="openai",
        prompt_tokens=100,
        completion_tokens=50,
        total_cost=0.006,
    )
    
    assert request_id is not None
    
    # Verify in database
    with db_manager.session() as session:
        request = session.query(LLMRequest).filter_by(id=request_id).first()
        assert request is not None
        assert request.model == "gpt-4"
        assert request.provider == "openai"
        assert request.total_tokens == 150
        assert request.total_cost == Decimal("0.006")


def test_track_request_with_user(db_manager, cost_tracker):
    """Test tracking a request with user attribution"""
    request_id = cost_tracker.track_request(
        model="gpt-4",
        provider="openai",
        prompt_tokens=100,
        completion_tokens=50,
        total_cost=0.006,
        user_email="alice@company.com",
    )
    
    assert request_id is not None
    
    # Verify user was created and linked
    with db_manager.session() as session:
        request = session.query(LLMRequest).filter_by(id=request_id).first()
        assert request.user is not None
        assert request.user.email == "alice@company.com"


def test_track_request_with_team(db_manager, cost_tracker):
    """Test tracking a request with team attribution"""
    request_id = cost_tracker.track_request(
        model="gpt-4",
        provider="openai",
        prompt_tokens=100,
        completion_tokens=50,
        total_cost=0.006,
        team_name="Engineering",
    )
    
    assert request_id is not None
    
    # Verify team was created and linked
    with db_manager.session() as session:
        request = session.query(LLMRequest).filter_by(id=request_id).first()
        assert request.team is not None
        assert request.team.name == "Engineering"


def test_track_request_with_project(db_manager, cost_tracker):
    """Test tracking a request with project attribution"""
    request_id = cost_tracker.track_request(
        model="gpt-4",
        provider="openai",
        prompt_tokens=100,
        completion_tokens=50,
        total_cost=0.006,
        project_name="Chatbot v2",
    )
    
    assert request_id is not None
    
    # Verify project was created and linked
    with db_manager.session() as session:
        request = session.query(LLMRequest).filter_by(id=request_id).first()
        assert request.project is not None
        assert request.project.name == "Chatbot v2"


def test_track_request_with_all_attribution(db_manager, cost_tracker):
    """Test tracking a request with full attribution"""
    request_id = cost_tracker.track_request(
        model="gpt-4",
        provider="openai",
        prompt_tokens=100,
        completion_tokens=50,
        total_cost=0.006,
        user_email="alice@company.com",
        team_name="Engineering",
        project_name="Chatbot v2",
    )
    
    assert request_id is not None
    
    # Verify all attribution
    with db_manager.session() as session:
        request = session.query(LLMRequest).filter_by(id=request_id).first()
        assert request.user.email == "alice@company.com"
        assert request.team.name == "Engineering"
        assert request.project.name == "Chatbot v2"


def test_track_request_with_performance_metrics(db_manager, cost_tracker):
    """Test tracking with performance metrics"""
    request_id = cost_tracker.track_request(
        model="gpt-4",
        provider="openai",
        prompt_tokens=100,
        completion_tokens=50,
        total_cost=0.006,
        latency_ms=500,
        cache_hit=True,
    )
    
    assert request_id is not None
    
    # Verify metrics
    with db_manager.session() as session:
        request = session.query(LLMRequest).filter_by(id=request_id).first()
        assert request.latency_ms == 500
        assert request.cache_hit is True


def test_track_error_request(db_manager, cost_tracker):
    """Test tracking an error request"""
    request_id = cost_tracker.track_request(
        model="gpt-4",
        provider="openai",
        prompt_tokens=100,
        completion_tokens=0,
        total_cost=0.0,
        status="error",
        error_message="API rate limit exceeded",
    )
    
    assert request_id is not None
    
    # Verify error info
    with db_manager.session() as session:
        request = session.query(LLMRequest).filter_by(id=request_id).first()
        assert request.status == "error"
        assert request.error_message == "API rate limit exceeded"


def test_track_request_with_metadata(db_manager, cost_tracker):
    """Test tracking with custom metadata"""
    request_id = cost_tracker.track_request(
        model="gpt-4",
        provider="openai",
        prompt_tokens=100,
        completion_tokens=50,
        total_cost=0.006,
        metadata={
            "session_id": "abc123",
            "endpoint": "/v1/chat/completions",
            "custom_field": "value"
        }
    )
    
    assert request_id is not None
    
    # Verify metadata
    with db_manager.session() as session:
        request = session.query(LLMRequest).filter_by(id=request_id).first()
        assert request.extra_metadata["session_id"] == "abc123"
        assert request.extra_metadata["custom_field"] == "value"


def test_disabled_tracking(db_manager):
    """Test that disabled tracking doesn't store anything"""
    # Get current count
    with db_manager.session() as session:
        initial_count = session.query(LLMRequest).count()
    
    tracker = CostTracker(enabled=False)
    
    request_id = tracker.track_request(
        model="gpt-4",
        provider="openai",
        prompt_tokens=100,
        completion_tokens=50,
        total_cost=0.006,
    )
    
    assert request_id is None
    
    # Verify no NEW records added
    with db_manager.session() as session:
        final_count = session.query(LLMRequest).count()
        assert final_count == initial_count


def test_middleware_track_completion(db_manager):
    """Test middleware tracking a completion"""
    middleware = CostTrackingMiddleware(enabled=True)
    
    # Mock LiteLLM response
    response = Mock()
    response.model = "gpt-4"
    response.usage = Mock()
    response.usage.prompt_tokens = 100
    response.usage.completion_tokens = 50
    response._hidden_params = {
        "response_cost": 0.006,
        "custom_llm_provider": "openai",
        "cache_hit": False
    }
    
    request_id = middleware.track_completion(
        response=response,
        start_time=None,
        metadata={
            "user": "alice@company.com",
            "team": "Engineering",
            "project": "Chatbot v2"
        }
    )
    
    assert request_id is not None
    
    # Verify in database
    with db_manager.session() as session:
        request = session.query(LLMRequest).filter_by(id=request_id).first()
        assert request.model == "gpt-4"
        assert request.user.email == "alice@company.com"
        assert request.team.name == "Engineering"
        assert request.project.name == "Chatbot v2"


def test_middleware_track_error(db_manager):
    """Test middleware tracking an error"""
    middleware = CostTrackingMiddleware(enabled=True)
    
    request_id = middleware.track_error(
        model="gpt-4",
        provider="openai",
        error_message="API timeout",
        metadata={
            "user": "alice@company.com",
        }
    )
    
    assert request_id is not None
    
    # Verify in database
    with db_manager.session() as session:
        request = session.query(LLMRequest).filter_by(id=request_id).first()
        assert request.status == "error"
        assert request.error_message == "API timeout"
        assert request.total_cost == Decimal("0")


def test_reuse_existing_user(db_manager, cost_tracker):
    """Test that existing users are reused"""
    # Use unique email for this test
    test_email = "alice_unique_test@company.com"
    
    # Create first request
    cost_tracker.track_request(
        model="gpt-4",
        provider="openai",
        prompt_tokens=100,
        completion_tokens=50,
        total_cost=0.006,
        user_email=test_email,
    )
    
    # Create second request with same user
    cost_tracker.track_request(
        model="gpt-3.5-turbo",
        provider="openai",
        prompt_tokens=50,
        completion_tokens=25,
        total_cost=0.001,
        user_email=test_email,
    )
    
    # Verify only one user was created
    with db_manager.session() as session:
        user_count = session.query(User).filter_by(email=test_email).count()
        assert user_count == 1
        
        # Verify both requests linked to same user
        requests = session.query(LLMRequest).join(User).filter(
            User.email == test_email
        ).all()
        assert len(requests) == 2


