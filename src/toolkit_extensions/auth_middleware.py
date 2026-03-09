"""
Toolkit LLM Gateway - API Key Authentication Middleware

Enforces API key authentication with scope-based access control
on protected endpoints.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Set

from toolkit_extensions.database.connection import get_session
from toolkit_extensions.database.models import APIKey
from toolkit_extensions.security import APIKeyManager

logger = logging.getLogger(__name__)


class AuthResult:
    """Result of an authentication attempt."""

    def __init__(
        self,
        authenticated: bool,
        user_id: Optional[str] = None,
        team_id: Optional[str] = None,
        scopes: Optional[List[str]] = None,
        key_name: Optional[str] = None,
        error: Optional[str] = None,
    ):
        self.authenticated = authenticated
        self.user_id = user_id
        self.team_id = team_id
        self.scopes = scopes or []
        self.key_name = key_name
        self.error = error

    def has_scope(self, scope: str) -> bool:
        """Check if the authenticated key has a specific scope."""
        if not self.scopes:
            return False
        # Wildcard scope grants everything
        if "*" in self.scopes:
            return True
        return scope in self.scopes


# Predefined scopes
SCOPE_READ = "read"
SCOPE_WRITE = "write"
SCOPE_ADMIN = "admin"
SCOPE_COMPLETIONS = "completions"
SCOPE_ANALYTICS = "analytics"
SCOPE_BUDGETS = "budgets"
SCOPE_WEBHOOKS = "webhooks"

ALL_SCOPES = {
    SCOPE_READ,
    SCOPE_WRITE,
    SCOPE_ADMIN,
    SCOPE_COMPLETIONS,
    SCOPE_ANALYTICS,
    SCOPE_BUDGETS,
    SCOPE_WEBHOOKS,
}


class APIKeyAuthenticator:
    """
    Authenticates requests using API keys stored in the database.

    Checks the key hash, expiration, status, and scopes.
    """

    def authenticate(self, api_key: str) -> AuthResult:
        """
        Authenticate an API key and return the result.

        Args:
            api_key: The raw API key string from the request header.

        Returns:
            AuthResult with authentication status and metadata.
        """
        if not api_key:
            return AuthResult(authenticated=False, error="API key is required")

        key_hash = APIKeyManager.hash_api_key(api_key)

        try:
            with get_session() as session:
                db_key = session.query(APIKey).filter_by(key_hash=key_hash).first()

                if not db_key:
                    logger.warning("Authentication failed: unknown API key")
                    return AuthResult(authenticated=False, error="Invalid API key")

                # Check status
                if db_key.status != "active":
                    logger.warning(
                        "Authentication failed: key %s is %s",
                        db_key.key_prefix,
                        db_key.status,
                    )
                    return AuthResult(
                        authenticated=False,
                        error=f"API key is {db_key.status}",
                    )

                # Check expiration
                if db_key.expires_at and db_key.expires_at < datetime.utcnow():
                    logger.warning(
                        "Authentication failed: key %s expired at %s",
                        db_key.key_prefix,
                        db_key.expires_at,
                    )
                    return AuthResult(authenticated=False, error="API key has expired")

                # Update last_used_at
                db_key.last_used_at = datetime.utcnow()
                session.commit()

                scopes = db_key.scopes if db_key.scopes else []

                return AuthResult(
                    authenticated=True,
                    user_id=str(db_key.user_id) if db_key.user_id else None,
                    team_id=str(db_key.team_id) if db_key.team_id else None,
                    scopes=scopes,
                    key_name=db_key.name,
                )

        except Exception as e:
            logger.error("Authentication error: %s", e, exc_info=True)
            return AuthResult(authenticated=False, error="Authentication service error")

    def require_scope(self, auth_result: AuthResult, scope: str) -> bool:
        """
        Check if an authenticated result has the required scope.

        Args:
            auth_result: The authentication result to check.
            scope: The scope required for the operation.

        Returns:
            True if the scope is present or wildcard is granted.
        """
        if not auth_result.authenticated:
            return False
        return auth_result.has_scope(scope)


# Global authenticator instance
_authenticator: Optional[APIKeyAuthenticator] = None


def get_authenticator() -> APIKeyAuthenticator:
    """Get global authenticator instance."""
    global _authenticator
    if _authenticator is None:
        _authenticator = APIKeyAuthenticator()
    return _authenticator
