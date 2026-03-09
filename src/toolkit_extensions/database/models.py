"""
SQLAlchemy models for Toolkit LLM Gateway cost tracking
"""

import json
from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    TypeDecorator,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class JSONType(TypeDecorator):
    """
    Platform-independent JSON type.
    Uses JSONB for PostgreSQL, Text for SQLite.
    """

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        else:
            return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        return json.loads(value)


class UUIDType(TypeDecorator):
    """
    Platform-independent UUID type.
    Uses UUID for PostgreSQL, String(36) for SQLite.
    """

    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        from uuid import UUID as PyUUID

        return PyUUID(value) if isinstance(value, str) else value


class Team(Base):
    """Organizational team or department"""

    __tablename__ = "teams"

    id = Column(UUIDType, primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    cost_center = Column(String(100), index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = Column(String(50), default="active", index=True)
    extra_metadata = Column(JSONType)

    # Relationships
    users = relationship("User", back_populates="team")
    projects = relationship("Project", back_populates="team")
    requests = relationship("LLMRequest", back_populates="team")
    budgets = relationship("Budget", back_populates="team")

    def __repr__(self):
        return f"<Team(id={self.id}, name={self.name})>"


class User(Base):
    """Individual user"""

    __tablename__ = "users"

    id = Column(UUIDType, primary_key=True, default=uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255))
    team_id = Column(UUIDType, ForeignKey("teams.id"), index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = Column(String(50), default="active", index=True)
    extra_metadata = Column(JSONType)

    # Relationships
    team = relationship("Team", back_populates="users")
    projects = relationship("Project", back_populates="owner")
    requests = relationship("LLMRequest", back_populates="user")
    budgets = relationship("Budget", back_populates="user")
    api_keys = relationship("APIKey", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email})>"


class Project(Base):
    """Project that consumes LLM resources"""

    __tablename__ = "projects"

    id = Column(UUIDType, primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    team_id = Column(UUIDType, ForeignKey("teams.id"), index=True)
    owner_id = Column(UUIDType, ForeignKey("users.id"), index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = Column(String(50), default="active")
    extra_metadata = Column(JSONType)

    # Relationships
    team = relationship("Team", back_populates="projects")
    owner = relationship("User", back_populates="projects")
    requests = relationship("LLMRequest", back_populates="project")
    budgets = relationship("Budget", back_populates="project")

    def __repr__(self):
        return f"<Project(id={self.id}, name={self.name})>"


class LLMRequest(Base):
    """Individual LLM request with cost information"""

    __tablename__ = "llm_requests"

    id = Column(UUIDType, primary_key=True, default=uuid4)

    # Request Info
    request_id = Column(String(255))
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    # Attribution
    user_id = Column(UUIDType, ForeignKey("users.id"), index=True)
    team_id = Column(UUIDType, ForeignKey("teams.id"), index=True)
    project_id = Column(UUIDType, ForeignKey("projects.id"), index=True)

    # Model Info
    model = Column(String(255), nullable=False, index=True)
    provider = Column(String(100), index=True)

    # Usage
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)
    total_tokens = Column(Integer)

    # Cost (in USD)
    prompt_cost = Column(Numeric(10, 6))
    completion_cost = Column(Numeric(10, 6))
    total_cost = Column(Numeric(10, 6), nullable=False, index=True)

    # Performance
    latency_ms = Column(Integer)
    cache_hit = Column(Boolean, default=False)

    # Status
    status = Column(String(50), index=True)
    error_message = Column(Text)

    # Metadata
    extra_metadata = Column(JSONType)

    # Relationships
    user = relationship("User", back_populates="requests")
    team = relationship("Team", back_populates="requests")
    project = relationship("Project", back_populates="requests")

    # Composite indexes
    __table_args__ = (
        Index("idx_requests_user_date", "user_id", text("DATE(timestamp)")),
        Index("idx_requests_team_date", "team_id", text("DATE(timestamp)")),
    )

    def __repr__(self):
        return f"<LLMRequest(id={self.id}, model={self.model}, cost=${self.total_cost})>"


class Budget(Base):
    """Budget limits for users, teams, or projects"""

    __tablename__ = "budgets"

    id = Column(UUIDType, primary_key=True, default=uuid4)

    # Attribution (exactly one must be set)
    user_id = Column(UUIDType, ForeignKey("users.id"), index=True)
    team_id = Column(UUIDType, ForeignKey("teams.id"), index=True)
    project_id = Column(UUIDType, ForeignKey("projects.id"), index=True)

    # Budget Details
    period = Column(String(50), nullable=False, index=True)  # daily, weekly, monthly, yearly
    limit_amount = Column(Numeric(10, 2), nullable=False)
    alert_threshold = Column(Numeric(5, 4), default=0.8)

    # Period
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime)

    # Status
    enabled = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Metadata
    extra_metadata = Column(JSONType)

    # Relationships
    user = relationship("User", back_populates="budgets")
    team = relationship("Team", back_populates="budgets")
    project = relationship("Project", back_populates="budgets")
    alerts = relationship("BudgetAlert", back_populates="budget")

    # Constraint: exactly one of user_id, team_id, or project_id must be set
    __table_args__ = (
        CheckConstraint(
            """
            (user_id IS NOT NULL AND team_id IS NULL AND project_id IS NULL) OR
            (user_id IS NULL AND team_id IS NOT NULL AND project_id IS NULL) OR
            (user_id IS NULL AND team_id IS NULL AND project_id IS NOT NULL)
            """,
            name="budget_attribution_check",
        ),
    )

    def __repr__(self):
        entity = "user" if self.user_id else "team" if self.team_id else "project"
        return f"<Budget(id={self.id}, entity={entity}, period={self.period}, limit=${self.limit_amount})>"


class BudgetAlert(Base):
    """Alert history for budget overruns"""

    __tablename__ = "budget_alerts"

    id = Column(UUIDType, primary_key=True, default=uuid4)

    budget_id = Column(UUIDType, ForeignKey("budgets.id"), nullable=False, index=True)

    # Alert Info
    alert_type = Column(String(50), nullable=False, index=True)
    current_spend = Column(Numeric(10, 2), nullable=False)
    budget_limit = Column(Numeric(10, 2), nullable=False)
    percentage_used = Column(Numeric(5, 2), nullable=False)

    # Notification
    notified_at = Column(DateTime, default=datetime.utcnow, index=True)
    notification_sent = Column(Boolean, default=False)
    notification_channels = Column(JSONType)

    # Metadata
    extra_metadata = Column(JSONType)

    # Relationships
    budget = relationship("Budget", back_populates="alerts")

    def __repr__(self):
        return f"<BudgetAlert(id={self.id}, type={self.alert_type}, spend=${self.current_spend})>"


class APIKey(Base):
    """API keys for gateway access"""

    __tablename__ = "api_keys"

    id = Column(UUIDType, primary_key=True, default=uuid4)

    key_hash = Column(String(255), unique=True, nullable=False, index=True)
    key_prefix = Column(String(20))

    # Attribution
    user_id = Column(UUIDType, ForeignKey("users.id"), index=True)
    team_id = Column(UUIDType, ForeignKey("teams.id"))

    # Details
    name = Column(String(255))
    description = Column(Text)

    # Permissions
    scopes = Column(JSONType)

    # Rate Limiting
    rate_limit_rpm = Column(Integer)
    rate_limit_tpm = Column(Integer)

    # Status
    status = Column(String(50), default="active", index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, index=True)
    last_used_at = Column(DateTime)

    # Metadata
    extra_metadata = Column(JSONType)

    # Relationships
    user = relationship("User", back_populates="api_keys")

    def __repr__(self):
        return f"<APIKey(id={self.id}, prefix={self.key_prefix}, user_id={self.user_id})>"


class CostAggregate(Base):
    """Pre-computed cost aggregates for fast analytics"""

    __tablename__ = "cost_aggregates"

    id = Column(UUIDType, primary_key=True, default=uuid4)

    # Dimension
    dimension_type = Column(String(50), nullable=False, index=True)
    dimension_id = Column(String(255), nullable=False, index=True)

    # Time Period
    period_type = Column(String(50), nullable=False, index=True)
    period_start = Column(DateTime, nullable=False, index=True)
    period_end = Column(DateTime, nullable=False)

    # Metrics
    total_requests = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    total_cost = Column(Numeric(10, 2), nullable=False, default=0, index=True)

    # Performance
    avg_latency_ms = Column(Integer)
    cache_hit_rate = Column(Numeric(5, 4))
    error_rate = Column(Numeric(5, 4))

    # Updated
    computed_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index(
            "idx_aggregates_unique",
            "dimension_type",
            "dimension_id",
            "period_type",
            "period_start",
            unique=True,
        ),
    )

    def __repr__(self):
        return f"<CostAggregate({self.dimension_type}={self.dimension_id}, period={self.period_type}, cost=${self.total_cost})>"
