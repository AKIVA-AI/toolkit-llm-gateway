"""
Budget management system for Toolkit LLM Gateway

Enforces spending limits and generates alerts.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from toolkit_extensions.database.connection import get_session
from toolkit_extensions.database.models import Budget, BudgetAlert, LLMRequest, Project, Team, User


class BudgetPeriod(str, Enum):
    """Budget period types"""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    LIFETIME = "lifetime"


class BudgetStatus(str, Enum):
    """Budget status types"""

    OK = "ok"
    APPROACHING = "approaching"
    EXCEEDED = "exceeded"
    DISABLED = "disabled"


class BudgetManager:
    """
    Manages budgets and enforces spending limits.

    Features:
    - Create budgets per user, team, or project
    - Check current spend against budgets
    - Generate alerts when thresholds are crossed
    - Block requests when budgets are exceeded (optional)
    """

    def __init__(self, block_on_exceeded: bool = False):
        """
        Initialize budget manager.

        Args:
            block_on_exceeded: If True, block requests when budget is exceeded
        """
        self.block_on_exceeded = block_on_exceeded

    def create_budget(
        self,
        period: BudgetPeriod,
        limit_amount: float,
        user_email: Optional[str] = None,
        team_name: Optional[str] = None,
        project_name: Optional[str] = None,
        alert_threshold: float = 0.8,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> str:
        """
        Create a new budget.

        Args:
            period: Budget period (daily, weekly, monthly, yearly, lifetime)
            limit_amount: Budget limit in USD
            user_email: User email (if user-level budget)
            team_name: Team name (if team-level budget)
            project_name: Project name (if project-level budget)
            alert_threshold: Alert when spend reaches this % of limit (0.0-1.0)
            start_date: Budget start date (default: now)
            end_date: Budget end date (optional)

        Returns:
            Budget ID

        Raises:
            ValueError: If attribution is invalid or budget already exists
        """
        # Validate attribution (must have exactly one)
        attribution_count = sum(
            [user_email is not None, team_name is not None, project_name is not None]
        )

        if attribution_count != 1:
            raise ValueError("Must specify exactly one of: user_email, team_name, project_name")

        if alert_threshold < 0.0 or alert_threshold > 1.0:
            raise ValueError("alert_threshold must be between 0.0 and 1.0")

        with get_session() as session:
            # Resolve entity IDs
            user_id = self._get_user_id(session, user_email) if user_email else None
            team_id = self._get_team_id(session, team_name) if team_name else None
            project_id = self._get_project_id(session, project_name) if project_name else None

            # Check if budget already exists for this period
            existing = self._get_active_budget(session, period, user_id, team_id, project_id)
            if existing:
                raise ValueError(f"Active {period} budget already exists for this entity")

            # Create budget
            budget = Budget(
                user_id=user_id,
                team_id=team_id,
                project_id=project_id,
                period=period,
                limit_amount=Decimal(str(limit_amount)),
                alert_threshold=Decimal(str(alert_threshold)),
                start_date=start_date or datetime.utcnow(),
                end_date=end_date,
                enabled=True,
            )

            session.add(budget)
            session.commit()

            return str(budget.id)

    def check_budget(
        self,
        user_email: Optional[str] = None,
        team_name: Optional[str] = None,
        project_name: Optional[str] = None,
    ) -> Dict[str, any]:
        """
        Check budget status for an entity.

        Args:
            user_email: User email
            team_name: Team name
            project_name: Project name

        Returns:
            Budget status dict with:
            - status: BudgetStatus (ok, approaching, exceeded, disabled)
            - budgets: List of active budgets with spend info
            - can_proceed: Boolean - whether request should be allowed
        """
        with get_session() as session:
            # Resolve entity IDs
            user_id = self._get_user_id(session, user_email) if user_email else None
            team_id = self._get_team_id(session, team_name) if team_name else None
            project_id = self._get_project_id(session, project_name) if project_name else None

            # Get all active budgets for this entity
            budgets = (
                session.query(Budget)
                .filter(
                    Budget.enabled == True,
                    or_(
                        Budget.user_id == user_id if user_id else False,
                        Budget.team_id == team_id if team_id else False,
                        Budget.project_id == project_id if project_id else False,
                    ),
                )
                .all()
            )

            if not budgets:
                return {
                    "status": BudgetStatus.OK,
                    "budgets": [],
                    "can_proceed": True,
                }

            # Check each budget
            budget_info = []
            worst_status = BudgetStatus.OK

            for budget in budgets:
                current_spend = self._get_current_spend(session, budget)
                percentage_used = (
                    (current_spend / budget.limit_amount * 100) if budget.limit_amount > 0 else 0
                )

                # Determine status
                if not budget.enabled:
                    status = BudgetStatus.DISABLED
                elif current_spend >= budget.limit_amount:
                    status = BudgetStatus.EXCEEDED
                elif percentage_used >= (budget.alert_threshold * 100):
                    status = BudgetStatus.APPROACHING
                else:
                    status = BudgetStatus.OK

                budget_info.append(
                    {
                        "id": str(budget.id),
                        "period": budget.period,
                        "limit": float(budget.limit_amount),
                        "current_spend": float(current_spend),
                        "percentage_used": float(percentage_used),
                        "status": status,
                        "start_date": budget.start_date.isoformat() if budget.start_date else None,
                        "end_date": budget.end_date.isoformat() if budget.end_date else None,
                    }
                )

                # Track worst status
                if status == BudgetStatus.EXCEEDED:
                    worst_status = BudgetStatus.EXCEEDED
                elif status == BudgetStatus.APPROACHING and worst_status == BudgetStatus.OK:
                    worst_status = BudgetStatus.APPROACHING

            # Determine if request can proceed
            can_proceed = worst_status != BudgetStatus.EXCEEDED or not self.block_on_exceeded

            return {
                "status": worst_status,
                "budgets": budget_info,
                "can_proceed": can_proceed,
            }

    def update_budget(
        self,
        budget_id: str,
        limit_amount: Optional[float] = None,
        alert_threshold: Optional[float] = None,
        enabled: Optional[bool] = None,
    ) -> None:
        """
        Update an existing budget.

        Args:
            budget_id: Budget ID
            limit_amount: New limit amount
            alert_threshold: New alert threshold
            enabled: Enable/disable budget
        """
        with get_session() as session:
            budget = session.query(Budget).filter_by(id=budget_id).first()
            if not budget:
                raise ValueError(f"Budget {budget_id} not found")

            if limit_amount is not None:
                budget.limit_amount = Decimal(str(limit_amount))
            if alert_threshold is not None:
                if alert_threshold < 0.0 or alert_threshold > 1.0:
                    raise ValueError("alert_threshold must be between 0.0 and 1.0")
                budget.alert_threshold = Decimal(str(alert_threshold))
            if enabled is not None:
                budget.enabled = enabled

            session.commit()

    def generate_alerts(self) -> List[str]:
        """
        Check all budgets and generate alerts for those crossing thresholds.

        Returns:
            List of alert IDs created
        """
        alert_ids = []

        with get_session() as session:
            # Get all active budgets
            budgets = session.query(Budget).filter_by(enabled=True).all()

            for budget in budgets:
                current_spend = self._get_current_spend(session, budget)
                percentage_used = (
                    (current_spend / budget.limit_amount * 100) if budget.limit_amount > 0 else 0
                )

                # Check if we should generate an alert
                should_alert = False
                alert_type = None

                if current_spend >= budget.limit_amount:
                    # Budget exceeded
                    alert_type = "budget_exceeded"
                    should_alert = True
                elif percentage_used >= (budget.alert_threshold * 100):
                    # Approaching budget
                    alert_type = "threshold_warning"
                    should_alert = True

                if should_alert:
                    # Check if we already alerted for this period
                    recent_alert = (
                        session.query(BudgetAlert)
                        .filter(
                            BudgetAlert.budget_id == budget.id,
                            BudgetAlert.alert_type == alert_type,
                            BudgetAlert.notified_at >= self._get_period_start(budget),
                        )
                        .first()
                    )

                    if not recent_alert:
                        # Create alert
                        alert = BudgetAlert(
                            budget_id=budget.id,
                            alert_type=alert_type,
                            current_spend=current_spend,
                            budget_limit=budget.limit_amount,
                            percentage_used=Decimal(str(percentage_used)),
                            notification_sent=False,
                        )
                        session.add(alert)
                        session.commit()
                        alert_ids.append(str(alert.id))

        return alert_ids

    def get_unsent_alerts(self) -> List[Dict]:
        """
        Get all alerts that haven't been sent yet.

        Returns:
            List of alert dicts
        """
        with get_session() as session:
            alerts = session.query(BudgetAlert).filter_by(notification_sent=False).all()

            return [
                {
                    "id": str(alert.id),
                    "budget_id": str(alert.budget_id),
                    "alert_type": alert.alert_type,
                    "current_spend": float(alert.current_spend),
                    "budget_limit": float(alert.budget_limit),
                    "percentage_used": float(alert.percentage_used),
                    "triggered_at": alert.notified_at.isoformat() if alert.notified_at else None,
                }
                for alert in alerts
            ]

    def mark_alert_sent(self, alert_id: str, channels: Dict[str, bool] = None) -> None:
        """
        Mark an alert as sent.

        Args:
            alert_id: Alert ID
            channels: Dict of notification channels used (e.g., {"email": True, "slack": False})
        """
        with get_session() as session:
            alert = session.query(BudgetAlert).filter_by(id=alert_id).first()
            if alert:
                alert.notification_sent = True
                if channels:
                    alert.notification_channels = channels
                session.commit()

    def _get_user_id(self, session: Session, email: str) -> Optional[str]:
        """Get or create user by email"""
        user = session.query(User).filter_by(email=email).first()
        if not user:
            user = User(email=email)
            session.add(user)
            session.flush()
        return str(user.id)

    def _get_team_id(self, session: Session, name: str) -> Optional[str]:
        """Get or create team by name"""
        team = session.query(Team).filter_by(name=name).first()
        if not team:
            team = Team(name=name)
            session.add(team)
            session.flush()
        return str(team.id)

    def _get_project_id(self, session: Session, name: str) -> Optional[str]:
        """Get or create project by name"""
        project = session.query(Project).filter_by(name=name).first()
        if not project:
            project = Project(name=name)
            session.add(project)
            session.flush()
        return str(project.id)

    def _get_active_budget(
        self,
        session: Session,
        period: str,
        user_id: Optional[str],
        team_id: Optional[str],
        project_id: Optional[str],
    ) -> Optional[Budget]:
        """Get active budget for entity and period"""
        return (
            session.query(Budget)
            .filter(
                Budget.period == period,
                Budget.enabled == True,
                Budget.user_id == user_id,
                Budget.team_id == team_id,
                Budget.project_id == project_id,
            )
            .first()
        )

    def _get_current_spend(self, session: Session, budget: Budget) -> Decimal:
        """Calculate current spend for a budget"""
        period_start = self._get_period_start(budget)
        period_end = self._get_period_end(budget)

        # Build query based on attribution
        query = session.query(func.sum(LLMRequest.total_cost))

        if budget.user_id:
            query = query.filter(LLMRequest.user_id == budget.user_id)
        elif budget.team_id:
            query = query.filter(LLMRequest.team_id == budget.team_id)
        elif budget.project_id:
            query = query.filter(LLMRequest.project_id == budget.project_id)

        # Filter by date range
        query = query.filter(
            LLMRequest.timestamp >= period_start,
            LLMRequest.timestamp < period_end,
        )

        total = query.scalar()
        return total or Decimal("0")

    def _get_period_start(self, budget: Budget) -> datetime:
        """Get start of current budget period"""
        now = datetime.utcnow()

        if budget.period == BudgetPeriod.DAILY:
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif budget.period == BudgetPeriod.WEEKLY:
            # Start of week (Monday)
            days_since_monday = now.weekday()
            return (now - timedelta(days=days_since_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        elif budget.period == BudgetPeriod.MONTHLY:
            return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif budget.period == BudgetPeriod.YEARLY:
            return now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:  # lifetime
            return budget.start_date or datetime.min

    def _get_period_end(self, budget: Budget) -> datetime:
        """Get end of current budget period"""
        if budget.end_date:
            return budget.end_date

        now = datetime.utcnow()

        if budget.period == BudgetPeriod.DAILY:
            return now.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif budget.period == BudgetPeriod.WEEKLY:
            # End of week (Sunday)
            days_until_sunday = 6 - now.weekday()
            return (now + timedelta(days=days_until_sunday)).replace(
                hour=23, minute=59, second=59, microsecond=999999
            )
        elif budget.period == BudgetPeriod.MONTHLY:
            # Last day of month
            if now.month == 12:
                next_month = now.replace(year=now.year + 1, month=1, day=1)
            else:
                next_month = now.replace(month=now.month + 1, day=1)
            return (next_month - timedelta(days=1)).replace(
                hour=23, minute=59, second=59, microsecond=999999
            )
        elif budget.period == BudgetPeriod.YEARLY:
            return now.replace(month=12, day=31, hour=23, minute=59, second=59, microsecond=999999)
        else:  # lifetime
            return datetime.max


# Global budget manager instance
_budget_manager: Optional[BudgetManager] = None


def get_budget_manager(block_on_exceeded: bool = False) -> BudgetManager:
    """Get global budget manager instance"""
    global _budget_manager
    if _budget_manager is None:
        _budget_manager = BudgetManager(block_on_exceeded=block_on_exceeded)
    return _budget_manager
