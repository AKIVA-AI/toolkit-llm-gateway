"""
Cost tracking middleware for Toolkit LLM Gateway

Intercepts LLM requests and logs costs to database.
"""

import logging
import time
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional
from uuid import uuid4

from toolkit_extensions.database.connection import get_session
from toolkit_extensions.database.models import LLMRequest, Project, Team, User

logger = logging.getLogger(__name__)


class CostTracker:
    """Tracks costs for LLM requests"""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    def track_request(
        self,
        model: str,
        provider: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_cost: float,
        prompt_cost: Optional[float] = None,
        completion_cost: Optional[float] = None,
        latency_ms: Optional[int] = None,
        cache_hit: bool = False,
        status: str = "success",
        error_message: Optional[str] = None,
        user_email: Optional[str] = None,
        team_name: Optional[str] = None,
        project_name: Optional[str] = None,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Track an LLM request and return the request ID.

        Args:
            model: Model name (e.g., "gpt-4")
            provider: Provider name (e.g., "openai")
            prompt_tokens: Number of prompt tokens
            completion_tokens: Number of completion tokens
            total_cost: Total cost in USD
            prompt_cost: Prompt cost in USD (optional)
            completion_cost: Completion cost in USD (optional)
            latency_ms: Response latency in milliseconds
            cache_hit: Whether response was cached
            status: Request status (success, error, timeout)
            error_message: Error message if status is error
            user_email: User email for attribution
            team_name: Team name for attribution
            project_name: Project name for attribution
            request_id: External request ID (optional)
            metadata: Additional metadata (optional)

        Returns:
            Request ID (UUID) or None if tracking is disabled
        """
        if not self.enabled:
            return None

        try:
            with get_session() as session:
                # Resolve user, team, project IDs
                user_id = self._get_user_id(session, user_email) if user_email else None
                team_id = self._get_team_id(session, team_name) if team_name else None
                project_id = self._get_project_id(session, project_name) if project_name else None

                # Create request record
                request = LLMRequest(
                    request_id=request_id or str(uuid4()),
                    timestamp=datetime.utcnow(),
                    user_id=user_id,
                    team_id=team_id,
                    project_id=project_id,
                    model=model,
                    provider=provider,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                    prompt_cost=Decimal(str(prompt_cost)) if prompt_cost else None,
                    completion_cost=Decimal(str(completion_cost)) if completion_cost else None,
                    total_cost=Decimal(str(total_cost)),
                    latency_ms=latency_ms,
                    cache_hit=cache_hit,
                    status=status,
                    error_message=error_message,
                    extra_metadata=metadata,
                )

                session.add(request)
                session.commit()

                return str(request.id)

        except Exception as e:
            # Log error but don't fail the request
            logger.error("Error tracking request: %s", e, exc_info=True)
            return None

    def _get_user_id(self, session, email: str) -> Optional[str]:
        """Get or create user by email"""
        user = session.query(User).filter_by(email=email).first()
        if not user:
            user = User(email=email)
            session.add(user)
            session.flush()
        return str(user.id)

    def _get_team_id(self, session, name: str) -> Optional[str]:
        """Get or create team by name"""
        team = session.query(Team).filter_by(name=name).first()
        if not team:
            team = Team(name=name)
            session.add(team)
            session.flush()
        return str(team.id)

    def _get_project_id(self, session, name: str) -> Optional[str]:
        """Get or create project by name"""
        project = session.query(Project).filter_by(name=name).first()
        if not project:
            project = Project(name=name)
            session.add(project)
            session.flush()
        return str(project.id)


class CostTrackingMiddleware:
    """
    Middleware to automatically track costs for LiteLLM requests.

    Usage:
        from toolkit_extensions.cost_tracker import CostTrackingMiddleware

        middleware = CostTrackingMiddleware()

        # Wrap LiteLLM completion
        response = completion(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}],
            metadata={
                "user": "alice@company.com",
                "team": "engineering",
                "project": "chatbot-v2"
            }
        )

        # Track the request
        middleware.track_completion(response)
    """

    def __init__(self, enabled: bool = True):
        self.tracker = CostTracker(enabled=enabled)

    def track_completion(
        self,
        response: Any,
        start_time: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Track a completion response from LiteLLM.

        Args:
            response: LiteLLM completion response
            start_time: Request start time (for latency calculation)
            metadata: Additional metadata (user, team, project, etc.)

        Returns:
            Request ID or None
        """
        try:
            # Extract cost information from response
            usage = getattr(response, "usage", None)
            if not usage:
                return None

            prompt_tokens = getattr(usage, "prompt_tokens", 0)
            completion_tokens = getattr(usage, "completion_tokens", 0)

            # Get cost from response (LiteLLM calculates this)
            hidden_params = getattr(response, "_hidden_params", {})
            total_cost = hidden_params.get("response_cost", 0.0)

            # Calculate latency if start_time provided
            latency_ms = None
            if start_time:
                latency_ms = int((time.time() - start_time) * 1000)

            # Extract metadata
            meta = metadata or {}
            user_email = meta.get("user")
            team_name = meta.get("team")
            project_name = meta.get("project")

            # Extract model and provider
            model = getattr(response, "model", "unknown")
            provider = hidden_params.get("custom_llm_provider", "unknown")

            # Check if cached
            cache_hit = hidden_params.get("cache_hit", False)

            # Track the request
            return self.tracker.track_request(
                model=model,
                provider=provider,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_cost=total_cost,
                latency_ms=latency_ms,
                cache_hit=cache_hit,
                status="success",
                user_email=user_email,
                team_name=team_name,
                project_name=project_name,
                metadata=meta,
            )

        except Exception as e:
            logger.error("Error in cost tracking middleware: %s", e, exc_info=True)
            return None

    def track_error(
        self,
        model: str,
        provider: str,
        error_message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Track a failed request.

        Args:
            model: Model name
            provider: Provider name
            error_message: Error message
            metadata: Additional metadata

        Returns:
            Request ID or None
        """
        meta = metadata or {}
        return self.tracker.track_request(
            model=model,
            provider=provider,
            prompt_tokens=0,
            completion_tokens=0,
            total_cost=0.0,
            status="error",
            error_message=error_message,
            user_email=meta.get("user"),
            team_name=meta.get("team"),
            project_name=meta.get("project"),
            metadata=meta,
        )


# Global middleware instance
_middleware: Optional[CostTrackingMiddleware] = None


def get_cost_tracking_middleware() -> CostTrackingMiddleware:
    """Get global cost tracking middleware instance"""
    global _middleware
    if _middleware is None:
        _middleware = CostTrackingMiddleware()
    return _middleware


def enable_cost_tracking():
    """Enable cost tracking globally"""
    middleware = get_cost_tracking_middleware()
    middleware.tracker.enabled = True


def disable_cost_tracking():
    """Disable cost tracking globally"""
    middleware = get_cost_tracking_middleware()
    middleware.tracker.enabled = False
