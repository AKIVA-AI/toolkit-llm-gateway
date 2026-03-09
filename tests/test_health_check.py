"""
Tests for health check module
"""

import os
import tempfile
from unittest.mock import Mock

import pytest

from toolkit_extensions import __version__
from toolkit_extensions.database.connection import DatabaseConfig, init_database
from toolkit_extensions.health_check import HealthChecker, create_health_checker


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


def test_basic_health_check(db_manager):
    """Test basic health check without details."""
    checker = HealthChecker(db_manager=db_manager)
    result = checker.check_health(detailed=False)

    assert result["status"] == "healthy"
    assert result["version"] == __version__
    assert "uptime_seconds" in result
    assert "timestamp" in result
    assert "checks" not in result


def test_detailed_health_check(db_manager):
    """Test detailed health check includes dependency status."""
    checker = HealthChecker(db_manager=db_manager)
    result = checker.check_health(detailed=True)

    assert result["status"] in ("healthy", "degraded")
    assert "checks" in result
    assert "database" in result["checks"]
    assert result["checks"]["database"]["healthy"] is True
    assert result["checks"]["database"]["response_time_ms"] is not None
    assert "providers" in result["checks"]


def test_health_check_no_db():
    """Test health check when database is not configured."""
    checker = HealthChecker(db_manager=None)
    result = checker.check_health(detailed=True)

    assert result["status"] == "unhealthy"
    assert result["checks"]["database"]["healthy"] is False
    assert "not initialized" in result["checks"]["database"]["error"]


def test_health_check_with_redis():
    """Test health check with Redis."""
    mock_redis = Mock()
    mock_redis.ping.return_value = True

    checker = HealthChecker(redis_client=mock_redis)
    result = checker.check_health(detailed=True)

    assert "redis" in result["checks"]
    assert result["checks"]["redis"]["healthy"] is True


def test_health_check_redis_failure():
    """Test health check with Redis failure."""
    mock_redis = Mock()
    mock_redis.ping.side_effect = ConnectionError("Connection refused")

    checker = HealthChecker(redis_client=mock_redis)
    result = checker.check_health(detailed=True)

    assert result["checks"]["redis"]["healthy"] is False
    assert "Connection refused" in result["checks"]["redis"]["error"]
    assert result["status"] == "degraded"


def test_readiness_check_ready(db_manager, monkeypatch):
    """Test readiness check when everything is up."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    checker = HealthChecker(db_manager=db_manager)
    result = checker.check_readiness()

    assert result["ready"] is True


def test_readiness_check_no_db():
    """Test readiness check fails without database."""
    checker = HealthChecker(db_manager=None)
    result = checker.check_readiness()

    assert result["ready"] is False
    assert "Database" in result["reason"]


def test_readiness_check_no_providers(db_manager, monkeypatch):
    """Test readiness check fails without providers."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    checker = HealthChecker(db_manager=db_manager)
    result = checker.check_readiness()

    assert result["ready"] is False
    assert "providers" in result["reason"].lower()


def test_create_health_checker_factory(db_manager):
    """Test factory function creates checker."""
    checker = create_health_checker(db_manager=db_manager)
    assert isinstance(checker, HealthChecker)


def test_version_in_health():
    """Test that version is included in health response."""
    checker = HealthChecker()
    result = checker.check_health()
    assert result["version"] == __version__
