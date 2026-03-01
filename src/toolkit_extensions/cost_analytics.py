"""
Cost analytics API for Toolkit LLM Gateway

Provides rich analytics and insights into LLM spending.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from toolkit_extensions.database.connection import get_session
from toolkit_extensions.database.models import LLMRequest, Project, Team, User


class TimeGranularity(str, Enum):
    """Time series granularity"""

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class CostAnalytics:
    """
    Provides cost analytics and insights.

    Features:
    - Time-series cost data
    - Cost breakdowns by model, user, team, project
    - Token usage analytics
    - Performance metrics
    """

    def __init__(self):
        pass

    def get_total_cost(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        user_email: Optional[str] = None,
        team_name: Optional[str] = None,
        project_name: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Decimal:
        """
        Get total cost for a time period and filters.

        Args:
            start_date: Start of period (default: 30 days ago)
            end_date: End of period (default: now)
            user_email: Filter by user
            team_name: Filter by team
            project_name: Filter by project
            model: Filter by model

        Returns:
            Total cost in USD
        """
        if start_date is None:
            start_date = datetime.utcnow() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.utcnow()

        with get_session() as session:
            query = session.query(func.sum(LLMRequest.total_cost))

            # Apply filters
            query = self._apply_filters(
                query, session, start_date, end_date, user_email, team_name, project_name, model
            )

            total = query.scalar()
            return total or Decimal("0")

    def get_cost_by_model(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        user_email: Optional[str] = None,
        team_name: Optional[str] = None,
        project_name: Optional[str] = None,
    ) -> List[Dict]:
        """
        Get cost breakdown by model.

        Returns:
            List of dicts with model, cost, request_count, token_count
        """
        if start_date is None:
            start_date = datetime.utcnow() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.utcnow()

        with get_session() as session:
            query = session.query(
                LLMRequest.model,
                func.sum(LLMRequest.total_cost).label("total_cost"),
                func.count(LLMRequest.id).label("request_count"),
                func.sum(LLMRequest.prompt_tokens + LLMRequest.completion_tokens).label(
                    "total_tokens"
                ),
            ).group_by(LLMRequest.model)

            # Apply filters
            query = self._apply_filters(
                query, session, start_date, end_date, user_email, team_name, project_name, None
            )

            results = query.all()

            return [
                {
                    "model": row.model,
                    "total_cost": float(row.total_cost or 0),
                    "request_count": row.request_count,
                    "total_tokens": int(row.total_tokens or 0),
                }
                for row in results
            ]

    def get_cost_by_user(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        team_name: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """
        Get cost breakdown by user.

        Returns:
            List of dicts with user_email, cost, request_count
        """
        if start_date is None:
            start_date = datetime.utcnow() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.utcnow()

        with get_session() as session:
            query = session.query(
                User.email,
                func.sum(LLMRequest.total_cost).label("total_cost"),
                func.count(LLMRequest.id).label("request_count"),
            ).join(User, LLMRequest.user_id == User.id)

            # Apply filters BEFORE group by and limit
            query = self._apply_filters(
                query, session, start_date, end_date, None, team_name, None, None
            )

            # Then group by, order, and limit
            query = (
                query.group_by(User.email)
                .order_by(func.sum(LLMRequest.total_cost).desc())
                .limit(limit)
            )

            results = query.all()

            return [
                {
                    "user_email": row.email,
                    "total_cost": float(row.total_cost or 0),
                    "request_count": row.request_count,
                }
                for row in results
            ]

    def get_cost_by_team(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """
        Get cost breakdown by team.

        Returns:
            List of dicts with team_name, cost, request_count
        """
        if start_date is None:
            start_date = datetime.utcnow() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.utcnow()

        with get_session() as session:
            query = session.query(
                Team.name,
                func.sum(LLMRequest.total_cost).label("total_cost"),
                func.count(LLMRequest.id).label("request_count"),
            ).join(Team, LLMRequest.team_id == Team.id)

            # Apply filters BEFORE group by and limit
            query = self._apply_filters(
                query, session, start_date, end_date, None, None, None, None
            )

            # Then group by, order, and limit
            query = (
                query.group_by(Team.name)
                .order_by(func.sum(LLMRequest.total_cost).desc())
                .limit(limit)
            )

            results = query.all()

            return [
                {
                    "team_name": row.name,
                    "total_cost": float(row.total_cost or 0),
                    "request_count": row.request_count,
                }
                for row in results
            ]

    def get_cost_by_project(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        team_name: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """
        Get cost breakdown by project.

        Returns:
            List of dicts with project_name, cost, request_count
        """
        if start_date is None:
            start_date = datetime.utcnow() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.utcnow()

        with get_session() as session:
            query = session.query(
                Project.name,
                func.sum(LLMRequest.total_cost).label("total_cost"),
                func.count(LLMRequest.id).label("request_count"),
            ).join(Project, LLMRequest.project_id == Project.id)

            # Apply filters BEFORE group by and limit
            query = self._apply_filters(
                query, session, start_date, end_date, None, team_name, None, None
            )

            # Then group by, order, and limit
            query = (
                query.group_by(Project.name)
                .order_by(func.sum(LLMRequest.total_cost).desc())
                .limit(limit)
            )

            results = query.all()

            return [
                {
                    "project_name": row.name,
                    "total_cost": float(row.total_cost or 0),
                    "request_count": row.request_count,
                }
                for row in results
            ]

    def get_time_series(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        granularity: TimeGranularity = TimeGranularity.DAILY,
        user_email: Optional[str] = None,
        team_name: Optional[str] = None,
        project_name: Optional[str] = None,
        model: Optional[str] = None,
    ) -> List[Dict]:
        """
        Get time-series cost data.

        Returns:
            List of dicts with timestamp, cost, request_count, token_count
        """
        if start_date is None:
            start_date = datetime.utcnow() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.utcnow()

        with get_session() as session:
            # Create time bucket based on granularity
            if granularity == TimeGranularity.HOURLY:
                time_bucket = func.strftime("%Y-%m-%d %H:00:00", LLMRequest.timestamp)
            elif granularity == TimeGranularity.DAILY:
                time_bucket = func.date(LLMRequest.timestamp)
            elif granularity == TimeGranularity.WEEKLY:
                time_bucket = func.strftime("%Y-W%W", LLMRequest.timestamp)
            else:  # MONTHLY
                time_bucket = func.strftime("%Y-%m", LLMRequest.timestamp)

            query = (
                session.query(
                    time_bucket.label("period"),
                    func.sum(LLMRequest.total_cost).label("total_cost"),
                    func.count(LLMRequest.id).label("request_count"),
                    func.sum(LLMRequest.prompt_tokens + LLMRequest.completion_tokens).label(
                        "total_tokens"
                    ),
                )
                .group_by("period")
                .order_by("period")
            )

            # Apply filters
            query = self._apply_filters(
                query, session, start_date, end_date, user_email, team_name, project_name, model
            )

            results = query.all()

            return [
                {
                    "period": row.period,
                    "total_cost": float(row.total_cost or 0),
                    "request_count": row.request_count,
                    "total_tokens": int(row.total_tokens or 0),
                }
                for row in results
            ]

    def get_performance_stats(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        user_email: Optional[str] = None,
        team_name: Optional[str] = None,
        project_name: Optional[str] = None,
        model: Optional[str] = None,
    ) -> Dict:
        """
        Get performance statistics.

        Returns:
            Dict with avg_latency, cache_hit_rate, error_rate, total_requests
        """
        if start_date is None:
            start_date = datetime.utcnow() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.utcnow()

        with get_session() as session:
            from sqlalchemy import case

            # Use CASE for cross-database compatibility
            cache_hit_sum = func.sum(case((LLMRequest.cache_hit == True, 1), else_=0))
            error_sum = func.sum(case((LLMRequest.error_message.isnot(None), 1), else_=0))

            query = session.query(
                func.avg(LLMRequest.latency_ms).label("avg_latency"),
                cache_hit_sum.label("cache_hits"),
                error_sum.label("errors"),
                func.count(LLMRequest.id).label("total_requests"),
            )

            # Apply filters
            query = self._apply_filters(
                query, session, start_date, end_date, user_email, team_name, project_name, model
            )

            result = query.first()

            if not result or result.total_requests == 0:
                return {
                    "avg_latency_ms": 0.0,
                    "cache_hit_rate": 0.0,
                    "error_rate": 0.0,
                    "total_requests": 0,
                }

            cache_hit_rate = (
                (result.cache_hits / result.total_requests * 100) if result.cache_hits else 0.0
            )
            error_rate = (result.errors / result.total_requests * 100) if result.errors else 0.0

            return {
                "avg_latency_ms": float(result.avg_latency or 0),
                "cache_hit_rate": float(cache_hit_rate),
                "error_rate": float(error_rate),
                "total_requests": result.total_requests,
            }

    def get_summary(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        user_email: Optional[str] = None,
        team_name: Optional[str] = None,
        project_name: Optional[str] = None,
    ) -> Dict:
        """
        Get comprehensive cost summary.

        Returns:
            Dict with total_cost, by_model, by_user, by_team, performance_stats
        """
        if start_date is None:
            start_date = datetime.utcnow() - timedelta(days=30)
        if end_date is None:
            end_date = datetime.utcnow()

        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
            },
            "total_cost": float(
                self.get_total_cost(start_date, end_date, user_email, team_name, project_name)
            ),
            "by_model": self.get_cost_by_model(
                start_date, end_date, user_email, team_name, project_name
            ),
            "by_user": (
                self.get_cost_by_user(start_date, end_date, team_name, limit=10)[:10]
                if not user_email
                else []
            ),
            "by_team": (
                self.get_cost_by_team(start_date, end_date, limit=10)[:10] if not team_name else []
            ),
            "by_project": (
                self.get_cost_by_project(start_date, end_date, team_name, limit=10)[:10]
                if not project_name
                else []
            ),
            "performance": self.get_performance_stats(
                start_date, end_date, user_email, team_name, project_name
            ),
        }

    def _apply_filters(
        self,
        query,
        session: Session,
        start_date: datetime,
        end_date: datetime,
        user_email: Optional[str],
        team_name: Optional[str],
        project_name: Optional[str],
        model: Optional[str],
    ):
        """Apply common filters to a query"""
        # Date range
        query = query.filter(
            LLMRequest.timestamp >= start_date,
            LLMRequest.timestamp <= end_date,
        )

        # User filter
        if user_email:
            user = session.query(User).filter_by(email=user_email).first()
            if user:
                query = query.filter(LLMRequest.user_id == str(user.id))

        # Team filter
        if team_name:
            team = session.query(Team).filter_by(name=team_name).first()
            if team:
                query = query.filter(LLMRequest.team_id == str(team.id))

        # Project filter
        if project_name:
            project = session.query(Project).filter_by(name=project_name).first()
            if project:
                query = query.filter(LLMRequest.project_id == str(project.id))

        # Model filter
        if model:
            query = query.filter(LLMRequest.model == model)

        return query


# Global analytics instance
_cost_analytics: Optional[CostAnalytics] = None


def get_cost_analytics() -> CostAnalytics:
    """Get global cost analytics instance"""
    global _cost_analytics
    if _cost_analytics is None:
        _cost_analytics = CostAnalytics()
    return _cost_analytics
