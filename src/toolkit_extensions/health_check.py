"""
Toolkit LLM Gateway - Health Check Module

Provides health check endpoints for monitoring and orchestration.
Checks database connectivity, Redis (if configured), and LLM provider availability.
"""

import os
import time
from datetime import datetime
from typing import Any, Dict

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from toolkit_extensions import __version__


class HealthChecker:
    """Health check service for Toolkit LLM Gateway"""

    def __init__(self, db_manager=None, redis_client=None):
        """
        Initialize health checker

        Args:
            db_manager: DatabaseManager instance
            redis_client: Redis client instance (optional)
        """
        self.db_manager = db_manager
        self.redis_client = redis_client
        self.start_time = time.time()

    def check_health(self, detailed: bool = False) -> Dict[str, Any]:
        """
        Perform health check

        Args:
            detailed: If True, include detailed component checks

        Returns:
            Health check result dictionary
        """
        health: Dict[str, Any] = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": int(time.time() - self.start_time),
            "version": __version__,
        }

        if detailed:
            checks: Dict[str, Any] = {}

            # Check database
            db_check = self._check_database()
            checks["database"] = db_check
            if not db_check["healthy"]:
                health["status"] = "unhealthy"

            # Check Redis if configured
            if self.redis_client:
                redis_check = self._check_redis()
                checks["redis"] = redis_check
                if not redis_check["healthy"]:
                    health["status"] = "degraded"

            # Check LLM providers
            provider_checks = self._check_providers()
            checks["providers"] = provider_checks
            if not any(p["available"] for p in provider_checks.values()):
                if health["status"] != "unhealthy":
                    health["status"] = "degraded"

            health["checks"] = checks

        return health

    def check_readiness(self) -> Dict[str, Any]:
        """
        Check if service is ready to accept requests

        Returns:
            Readiness check result
        """
        ready: Dict[str, Any] = {
            "ready": True,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Database must be accessible
        db_check = self._check_database()
        if not db_check["healthy"]:
            ready["ready"] = False
            ready["reason"] = "Database not accessible"
            return ready

        # At least one LLM provider should be configured
        provider_checks = self._check_providers()
        if not any(p["available"] for p in provider_checks.values()):
            ready["ready"] = False
            ready["reason"] = "No LLM providers configured"
            return ready

        return ready

    def _check_database(self) -> Dict[str, Any]:
        """Check database connectivity"""
        check: Dict[str, Any] = {
            "healthy": False,
            "response_time_ms": None,
            "error": None,
        }

        if not self.db_manager:
            check["error"] = "Database manager not initialized"
            return check

        try:
            start = time.time()

            # Use the context-manager session() method (not get_session())
            with self.db_manager.session() as session:
                session.execute(text("SELECT 1"))

            check["healthy"] = True
            check["response_time_ms"] = int((time.time() - start) * 1000)
        except SQLAlchemyError as e:
            check["error"] = str(e)
        except Exception as e:
            check["error"] = f"Unexpected error: {str(e)}"

        return check

    def _check_redis(self) -> Dict[str, Any]:
        """Check Redis connectivity"""
        check: Dict[str, Any] = {
            "healthy": False,
            "response_time_ms": None,
            "error": None,
        }

        if not self.redis_client:
            check["error"] = "Redis client not initialized"
            return check

        try:
            start = time.time()
            self.redis_client.ping()
            check["healthy"] = True
            check["response_time_ms"] = int((time.time() - start) * 1000)
        except Exception as e:
            check["error"] = str(e)

        return check

    def _check_providers(self) -> Dict[str, Dict[str, Any]]:
        """Check LLM provider configuration"""
        providers = {
            "openai": {
                "available": bool(os.getenv("OPENAI_API_KEY")),
                "configured": bool(os.getenv("OPENAI_API_KEY")),
            },
            "anthropic": {
                "available": bool(os.getenv("ANTHROPIC_API_KEY")),
                "configured": bool(os.getenv("ANTHROPIC_API_KEY")),
            },
            "google": {
                "available": bool(os.getenv("GOOGLE_API_KEY")),
                "configured": bool(os.getenv("GOOGLE_API_KEY")),
            },
        }

        return providers


# Convenience functions for FastAPI endpoints
def create_health_checker(db_manager=None, redis_client=None) -> HealthChecker:
    """Create a health checker instance"""
    return HealthChecker(db_manager=db_manager, redis_client=redis_client)
