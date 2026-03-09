"""
Tests for API key authentication middleware
"""

import os
import tempfile
from datetime import datetime, timedelta

import pytest

from toolkit_extensions.auth_middleware import (
    ALL_SCOPES,
    SCOPE_ADMIN,
    SCOPE_ANALYTICS,
    SCOPE_COMPLETIONS,
    SCOPE_READ,
    SCOPE_WRITE,
    APIKeyAuthenticator,
    AuthResult,
    get_authenticator,
)
from toolkit_extensions.database.connection import DatabaseConfig, init_database
from toolkit_extensions.database.models import APIKey, User
from toolkit_extensions.security import APIKeyManager


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
def authenticator(db_manager):
    """Create authenticator with test DB"""
    return APIKeyAuthenticator()


@pytest.fixture
def active_key_data(db_manager):
    """Create an active API key in the database and return (raw_key, db_key)."""
    from toolkit_extensions.database.connection import get_session

    raw_key = APIKeyManager.generate_api_key(prefix="ak")
    key_hash = APIKeyManager.hash_api_key(raw_key)

    with get_session() as session:
        user = User(email="test@example.com")
        session.add(user)
        session.flush()

        db_key = APIKey(
            key_hash=key_hash,
            key_prefix="ak",
            user_id=user.id,
            name="test-key",
            scopes=["read", "completions"],
            status="active",
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        session.add(db_key)
        session.commit()
        key_id = str(db_key.id)

    return raw_key, key_id


def test_auth_result_has_scope():
    """Test AuthResult.has_scope logic"""
    result = AuthResult(authenticated=True, scopes=["read", "completions"])
    assert result.has_scope("read")
    assert result.has_scope("completions")
    assert not result.has_scope("admin")


def test_auth_result_wildcard_scope():
    """Test that wildcard scope grants everything"""
    result = AuthResult(authenticated=True, scopes=["*"])
    assert result.has_scope("read")
    assert result.has_scope("admin")
    assert result.has_scope("anything")


def test_auth_result_empty_scopes():
    """Test that empty scopes denies everything"""
    result = AuthResult(authenticated=True, scopes=[])
    assert not result.has_scope("read")


def test_authenticate_missing_key(authenticator):
    """Test authentication with empty key"""
    result = authenticator.authenticate("")
    assert not result.authenticated
    assert result.error == "API key is required"


def test_authenticate_invalid_key(authenticator, db_manager):
    """Test authentication with unknown key"""
    result = authenticator.authenticate("ak_nonexistent_key_here_1234567890")
    assert not result.authenticated
    assert result.error == "Invalid API key"


def test_authenticate_valid_key(authenticator, active_key_data):
    """Test successful authentication"""
    raw_key, _ = active_key_data
    result = authenticator.authenticate(raw_key)
    assert result.authenticated
    assert result.user_id is not None
    assert "read" in result.scopes
    assert "completions" in result.scopes
    assert result.key_name == "test-key"


def test_authenticate_revoked_key(authenticator, db_manager):
    """Test authentication with revoked key"""
    from toolkit_extensions.database.connection import get_session

    raw_key = APIKeyManager.generate_api_key(prefix="ak")
    key_hash = APIKeyManager.hash_api_key(raw_key)

    with get_session() as session:
        db_key = APIKey(
            key_hash=key_hash,
            key_prefix="ak",
            name="revoked-key",
            scopes=["read"],
            status="revoked",
        )
        session.add(db_key)
        session.commit()

    result = authenticator.authenticate(raw_key)
    assert not result.authenticated
    assert "revoked" in result.error


def test_authenticate_expired_key(authenticator, db_manager):
    """Test authentication with expired key"""
    from toolkit_extensions.database.connection import get_session

    raw_key = APIKeyManager.generate_api_key(prefix="ak")
    key_hash = APIKeyManager.hash_api_key(raw_key)

    with get_session() as session:
        db_key = APIKey(
            key_hash=key_hash,
            key_prefix="ak",
            name="expired-key",
            scopes=["read"],
            status="active",
            expires_at=datetime.utcnow() - timedelta(days=1),
        )
        session.add(db_key)
        session.commit()

    result = authenticator.authenticate(raw_key)
    assert not result.authenticated
    assert "expired" in result.error


def test_require_scope(authenticator, active_key_data):
    """Test require_scope check"""
    raw_key, _ = active_key_data
    result = authenticator.authenticate(raw_key)

    assert authenticator.require_scope(result, "read")
    assert authenticator.require_scope(result, "completions")
    assert not authenticator.require_scope(result, "admin")


def test_require_scope_unauthenticated(authenticator):
    """Test require_scope with unauthenticated result"""
    result = AuthResult(authenticated=False)
    assert not authenticator.require_scope(result, "read")


def test_last_used_updated(authenticator, active_key_data):
    """Test that last_used_at is updated on authentication"""
    from toolkit_extensions.database.connection import get_session

    raw_key, key_id = active_key_data
    authenticator.authenticate(raw_key)

    with get_session() as session:
        db_key = session.query(APIKey).filter_by(id=key_id).first()
        assert db_key.last_used_at is not None


def test_global_authenticator():
    """Test global authenticator singleton"""
    auth1 = get_authenticator()
    auth2 = get_authenticator()
    assert auth1 is auth2


def test_all_scopes_defined():
    """Test that predefined scopes are consistent"""
    assert SCOPE_READ in ALL_SCOPES
    assert SCOPE_WRITE in ALL_SCOPES
    assert SCOPE_ADMIN in ALL_SCOPES
    assert SCOPE_COMPLETIONS in ALL_SCOPES
    assert SCOPE_ANALYTICS in ALL_SCOPES
