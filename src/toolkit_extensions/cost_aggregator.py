"""
Toolkit LLM Gateway - Cost Aggregate Materialization

Populates the CostAggregate table with pre-computed cost data
for fast analytics queries.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import case, func

from toolkit_extensions.database.connection import get_session
from toolkit_extensions.database.models import CostAggregate, LLMRequest

logger = logging.getLogger(__name__)


class CostAggregator:
    """
    Materializes cost aggregates from raw LLM request data.

    Supports aggregation by:
    - Dimension: model, provider, user, team, project
    - Period: hourly, daily, weekly, monthly
    """

    DIMENSION_TYPES = ("model", "provider", "user", "team", "project")
    PERIOD_TYPES = ("hourly", "daily")

    def materialize(
        self,
        period_type: str = "daily",
        target_date: Optional[datetime] = None,
    ) -> int:
        """
        Materialize cost aggregates for a given period.

        Args:
            period_type: "hourly" or "daily"
            target_date: Date to aggregate (default: yesterday for daily,
                         last hour for hourly)

        Returns:
            Number of aggregate rows upserted.
        """
        if period_type not in self.PERIOD_TYPES:
            raise ValueError(f"period_type must be one of {self.PERIOD_TYPES}")

        if target_date is None:
            now = datetime.utcnow()
            if period_type == "daily":
                target_date = (now - timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
            else:
                target_date = (now - timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)

        period_start, period_end = self._get_period_bounds(period_type, target_date)

        total_upserted = 0

        for dimension_type in self.DIMENSION_TYPES:
            count = self._materialize_dimension(
                dimension_type, period_type, period_start, period_end
            )
            total_upserted += count

        logger.info(
            "Materialized %d aggregates for %s period starting %s",
            total_upserted,
            period_type,
            period_start.isoformat(),
        )

        return total_upserted

    def _materialize_dimension(
        self,
        dimension_type: str,
        period_type: str,
        period_start: datetime,
        period_end: datetime,
    ) -> int:
        """Materialize aggregates for a single dimension."""
        with get_session() as session:
            # Build the dimension column
            dim_column = self._get_dimension_column(dimension_type)
            if dim_column is None:
                return 0

            # Query raw data grouped by dimension
            cache_hit_sum = func.sum(case((LLMRequest.cache_hit == True, 1), else_=0))  # noqa: E712
            error_sum = func.sum(case((LLMRequest.error_message.isnot(None), 1), else_=0))

            rows = (
                session.query(
                    dim_column.label("dim_id"),
                    func.count(LLMRequest.id).label("total_requests"),
                    func.sum(LLMRequest.prompt_tokens + LLMRequest.completion_tokens).label(
                        "total_tokens"
                    ),
                    func.sum(LLMRequest.total_cost).label("total_cost"),
                    func.avg(LLMRequest.latency_ms).label("avg_latency_ms"),
                    cache_hit_sum.label("cache_hits"),
                    error_sum.label("errors"),
                )
                .filter(
                    LLMRequest.timestamp >= period_start,
                    LLMRequest.timestamp < period_end,
                    dim_column.isnot(None),
                )
                .group_by(dim_column)
                .all()
            )

            count = 0
            for row in rows:
                dim_id = str(row.dim_id) if row.dim_id else None
                if not dim_id:
                    continue

                total_requests = row.total_requests or 0
                cache_hit_rate = (
                    Decimal(str(row.cache_hits / total_requests))
                    if total_requests > 0 and row.cache_hits
                    else Decimal("0")
                )
                error_rate = (
                    Decimal(str(row.errors / total_requests))
                    if total_requests > 0 and row.errors
                    else Decimal("0")
                )

                # Upsert: delete existing, then insert
                session.query(CostAggregate).filter(
                    CostAggregate.dimension_type == dimension_type,
                    CostAggregate.dimension_id == dim_id,
                    CostAggregate.period_type == period_type,
                    CostAggregate.period_start == period_start,
                ).delete()

                agg = CostAggregate(
                    id=uuid4(),
                    dimension_type=dimension_type,
                    dimension_id=dim_id,
                    period_type=period_type,
                    period_start=period_start,
                    period_end=period_end,
                    total_requests=total_requests,
                    total_tokens=int(row.total_tokens or 0),
                    total_cost=row.total_cost or Decimal("0"),
                    avg_latency_ms=(int(row.avg_latency_ms) if row.avg_latency_ms else None),
                    cache_hit_rate=cache_hit_rate,
                    error_rate=error_rate,
                    computed_at=datetime.utcnow(),
                )
                session.add(agg)
                count += 1

            session.commit()
            return count

    @staticmethod
    def _get_dimension_column(dimension_type: str):
        """Map dimension type to SQLAlchemy column."""
        mapping = {
            "model": LLMRequest.model,
            "provider": LLMRequest.provider,
            "user": LLMRequest.user_id,
            "team": LLMRequest.team_id,
            "project": LLMRequest.project_id,
        }
        return mapping.get(dimension_type)

    @staticmethod
    def _get_period_bounds(period_type: str, target_date: datetime):
        """Get start and end of the period."""
        if period_type == "hourly":
            start = target_date.replace(minute=0, second=0, microsecond=0)
            end = start + timedelta(hours=1)
        else:  # daily
            start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        return start, end


# Global instance
_cost_aggregator: Optional[CostAggregator] = None


def get_cost_aggregator() -> CostAggregator:
    """Get global cost aggregator instance."""
    global _cost_aggregator
    if _cost_aggregator is None:
        _cost_aggregator = CostAggregator()
    return _cost_aggregator
