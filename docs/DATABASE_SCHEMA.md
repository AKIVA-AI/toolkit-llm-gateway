# ðŸ—„ï¸ Toolkit LLM Gateway - Database Schema

**Purpose:** Cost tracking, budget management, and analytics

---

## ðŸ“Š Schema Overview

The database tracks:
- LLM request costs
- User/team/project attribution
- Budget limits and alerts
- Usage patterns and analytics

**Database Type:** PostgreSQL (recommended) or SQLite (development)

---

## ðŸ“‹ Tables

### 1. **users**
Tracks individual users of the gateway.

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    team_id UUID REFERENCES teams(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'active',  -- active, suspended
    metadata JSONB  -- Additional user metadata
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_team ON users(team_id);
CREATE INDEX idx_users_status ON users(status);
```

---

### 2. **teams**
Organizational teams or departments.

```sql
CREATE TABLE teams (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    cost_center VARCHAR(100),  -- For accounting/chargeback
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB
);

CREATE INDEX idx_teams_name ON teams(name);
CREATE INDEX idx_teams_cost_center ON teams(cost_center);
```

---

### 3. **projects**
Individual projects that consume LLM resources.

```sql
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    team_id UUID REFERENCES teams(id),
    owner_id UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'active',
    metadata JSONB
);

CREATE INDEX idx_projects_name ON projects(name);
CREATE INDEX idx_projects_team ON projects(team_id);
CREATE INDEX idx_projects_owner ON projects(owner_id);
```

---

### 4. **llm_requests**
Every LLM request with cost information.

```sql
CREATE TABLE llm_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Request Info
    request_id VARCHAR(255),  -- External request ID
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Attribution
    user_id UUID REFERENCES users(id),
    team_id UUID REFERENCES teams(id),
    project_id UUID REFERENCES projects(id),
    
    -- Model Info
    model VARCHAR(255) NOT NULL,
    provider VARCHAR(100),  -- openai, anthropic, etc.
    
    -- Usage
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    
    -- Cost (in USD)
    prompt_cost DECIMAL(10, 6),
    completion_cost DECIMAL(10, 6),
    total_cost DECIMAL(10, 6) NOT NULL,
    
    -- Performance
    latency_ms INTEGER,  -- Response time in milliseconds
    cache_hit BOOLEAN DEFAULT false,
    
    -- Status
    status VARCHAR(50),  -- success, error, timeout
    error_message TEXT,
    
    -- Metadata
    metadata JSONB  -- Additional request metadata
);

-- Indexes for fast queries
CREATE INDEX idx_requests_timestamp ON llm_requests(timestamp DESC);
CREATE INDEX idx_requests_user ON llm_requests(user_id, timestamp DESC);
CREATE INDEX idx_requests_team ON llm_requests(team_id, timestamp DESC);
CREATE INDEX idx_requests_project ON llm_requests(project_id, timestamp DESC);
CREATE INDEX idx_requests_model ON llm_requests(model);
CREATE INDEX idx_requests_provider ON llm_requests(provider);
CREATE INDEX idx_requests_status ON llm_requests(status);

-- Composite indexes for analytics
CREATE INDEX idx_requests_user_date ON llm_requests(user_id, DATE(timestamp));
CREATE INDEX idx_requests_team_date ON llm_requests(team_id, DATE(timestamp));
CREATE INDEX idx_requests_cost ON llm_requests(total_cost DESC);
```

---

### 5. **budgets**
Budget limits for users, teams, or projects.

```sql
CREATE TABLE budgets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Attribution (one of these must be set)
    user_id UUID REFERENCES users(id),
    team_id UUID REFERENCES teams(id),
    project_id UUID REFERENCES projects(id),
    
    -- Budget Details
    period VARCHAR(50) NOT NULL,  -- daily, weekly, monthly, yearly
    limit_amount DECIMAL(10, 2) NOT NULL,  -- USD
    alert_threshold DECIMAL(5, 4) DEFAULT 0.8,  -- Alert at 80%
    
    -- Period
    start_date DATE NOT NULL,
    end_date DATE,  -- NULL for recurring budgets
    
    -- Status
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Metadata
    metadata JSONB,
    
    -- Constraints
    CHECK (
        (user_id IS NOT NULL AND team_id IS NULL AND project_id IS NULL) OR
        (user_id IS NULL AND team_id IS NOT NULL AND project_id IS NULL) OR
        (user_id IS NULL AND team_id IS NULL AND project_id IS NOT NULL)
    )
);

CREATE INDEX idx_budgets_user ON budgets(user_id);
CREATE INDEX idx_budgets_team ON budgets(team_id);
CREATE INDEX idx_budgets_project ON budgets(project_id);
CREATE INDEX idx_budgets_period ON budgets(period);
CREATE INDEX idx_budgets_enabled ON budgets(enabled);
```

---

### 6. **budget_alerts**
Alert history for budget overruns.

```sql
CREATE TABLE budget_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    budget_id UUID REFERENCES budgets(id) NOT NULL,
    
    -- Alert Info
    alert_type VARCHAR(50) NOT NULL,  -- threshold_warning, limit_exceeded
    current_spend DECIMAL(10, 2) NOT NULL,
    budget_limit DECIMAL(10, 2) NOT NULL,
    percentage_used DECIMAL(5, 2) NOT NULL,
    
    -- Notification
    notified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notification_sent BOOLEAN DEFAULT false,
    notification_channels JSONB,  -- email, slack, webhook, etc.
    
    -- Metadata
    metadata JSONB
);

CREATE INDEX idx_alerts_budget ON budget_alerts(budget_id, notified_at DESC);
CREATE INDEX idx_alerts_type ON budget_alerts(alert_type);
CREATE INDEX idx_alerts_notified ON budget_alerts(notified_at DESC);
```

---

### 7. **api_keys**
API keys for gateway access.

```sql
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    key_hash VARCHAR(255) UNIQUE NOT NULL,  -- Hashed API key
    key_prefix VARCHAR(20),  -- First few chars for identification
    
    -- Attribution
    user_id UUID REFERENCES users(id),
    team_id UUID REFERENCES teams(id),
    
    -- Details
    name VARCHAR(255),
    description TEXT,
    
    -- Permissions
    scopes JSONB,  -- Array of allowed scopes/permissions
    
    -- Rate Limiting
    rate_limit_rpm INTEGER,  -- Requests per minute
    rate_limit_tpm INTEGER,  -- Tokens per minute
    
    -- Status
    status VARCHAR(50) DEFAULT 'active',  -- active, suspended, revoked
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    last_used_at TIMESTAMP,
    
    -- Metadata
    metadata JSONB
);

CREATE INDEX idx_keys_hash ON api_keys(key_hash);
CREATE INDEX idx_keys_user ON api_keys(user_id);
CREATE INDEX idx_keys_status ON api_keys(status);
CREATE INDEX idx_keys_expires ON api_keys(expires_at);
```

---

### 8. **cost_aggregates**
Pre-computed cost aggregates for fast analytics (materialized view or table).

```sql
CREATE TABLE cost_aggregates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Dimension
    dimension_type VARCHAR(50) NOT NULL,  -- user, team, project, model, provider
    dimension_id VARCHAR(255) NOT NULL,
    
    -- Time Period
    period_type VARCHAR(50) NOT NULL,  -- hour, day, week, month
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,
    
    -- Metrics
    total_requests INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    total_cost DECIMAL(10, 2) NOT NULL DEFAULT 0,
    
    -- Performance
    avg_latency_ms INTEGER,
    cache_hit_rate DECIMAL(5, 4),
    error_rate DECIMAL(5, 4),
    
    -- Updated
    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(dimension_type, dimension_id, period_type, period_start)
);

CREATE INDEX idx_aggregates_dimension ON cost_aggregates(dimension_type, dimension_id);
CREATE INDEX idx_aggregates_period ON cost_aggregates(period_type, period_start DESC);
CREATE INDEX idx_aggregates_cost ON cost_aggregates(total_cost DESC);
```

---

## ðŸ”„ Views

### **v_current_spend**
Current spending for active budgets.

```sql
CREATE VIEW v_current_spend AS
SELECT 
    b.id AS budget_id,
    b.user_id,
    b.team_id,
    b.project_id,
    b.period,
    b.limit_amount,
    b.alert_threshold,
    COALESCE(SUM(r.total_cost), 0) AS current_spend,
    (COALESCE(SUM(r.total_cost), 0) / b.limit_amount) AS percentage_used,
    CASE 
        WHEN COALESCE(SUM(r.total_cost), 0) >= b.limit_amount THEN 'exceeded'
        WHEN COALESCE(SUM(r.total_cost), 0) >= (b.limit_amount * b.alert_threshold) THEN 'warning'
        ELSE 'ok'
    END AS status
FROM budgets b
LEFT JOIN llm_requests r ON (
    (b.user_id IS NOT NULL AND r.user_id = b.user_id) OR
    (b.team_id IS NOT NULL AND r.team_id = b.team_id) OR
    (b.project_id IS NOT NULL AND r.project_id = b.project_id)
)
AND r.timestamp >= CASE b.period
    WHEN 'daily' THEN CURRENT_DATE
    WHEN 'weekly' THEN DATE_TRUNC('week', CURRENT_DATE)
    WHEN 'monthly' THEN DATE_TRUNC('month', CURRENT_DATE)
    WHEN 'yearly' THEN DATE_TRUNC('year', CURRENT_DATE)
END
WHERE b.enabled = true
GROUP BY b.id, b.user_id, b.team_id, b.project_id, b.period, b.limit_amount, b.alert_threshold;
```

---

### **v_daily_costs**
Daily cost summary by user/team/project.

```sql
CREATE VIEW v_daily_costs AS
SELECT 
    DATE(timestamp) AS date,
    user_id,
    team_id,
    project_id,
    model,
    provider,
    COUNT(*) AS request_count,
    SUM(total_tokens) AS total_tokens,
    SUM(total_cost) AS total_cost,
    AVG(latency_ms) AS avg_latency_ms,
    SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END)::FLOAT / COUNT(*) AS cache_hit_rate,
    SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END)::FLOAT / COUNT(*) AS error_rate
FROM llm_requests
GROUP BY DATE(timestamp), user_id, team_id, project_id, model, provider;
```

---

## ðŸ“ˆ Sample Queries

### Get user's current month spending:
```sql
SELECT 
    u.email,
    COUNT(r.id) AS requests,
    SUM(r.total_cost) AS total_cost,
    AVG(r.total_cost) AS avg_cost_per_request
FROM users u
LEFT JOIN llm_requests r ON u.id = r.user_id
WHERE r.timestamp >= DATE_TRUNC('month', CURRENT_DATE)
AND u.email = 'alice@company.com'
GROUP BY u.email;
```

### Get top spending teams this month:
```sql
SELECT 
    t.name,
    COUNT(r.id) AS requests,
    SUM(r.total_cost) AS total_cost
FROM teams t
LEFT JOIN llm_requests r ON t.id = r.team_id
WHERE r.timestamp >= DATE_TRUNC('month', CURRENT_DATE)
GROUP BY t.name
ORDER BY total_cost DESC
LIMIT 10;
```

### Get cost breakdown by model:
```sql
SELECT 
    model,
    provider,
    COUNT(*) AS requests,
    SUM(total_tokens) AS tokens,
    SUM(total_cost) AS cost,
    AVG(total_cost) AS avg_cost_per_request
FROM llm_requests
WHERE timestamp >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY model, provider
ORDER BY cost DESC;
```

### Check budgets exceeding threshold:
```sql
SELECT * FROM v_current_spend
WHERE status IN ('warning', 'exceeded')
ORDER BY percentage_used DESC;
```

---

## ðŸš€ Migration Scripts

### Initial Migration
```python
# migrations/001_initial_schema.py
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    # Create teams table
    op.create_table(
        'teams',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('cost_center', sa.String(100)),
        sa.Column('created_at', sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column('status', sa.String(50), server_default='active'),
        sa.Column('metadata', postgresql.JSONB),
    )
    
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('name', sa.String(255)),
        sa.Column('team_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('teams.id')),
        sa.Column('created_at', sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP, server_default=sa.func.now()),
        sa.Column('status', sa.String(50), server_default='active'),
        sa.Column('metadata', postgresql.JSONB),
    )
    
    # ... (rest of tables)

def downgrade():
    op.drop_table('users')
    op.drop_table('teams')
    # ... (rest of tables)
```

---

## ðŸ”§ Database Configuration

### PostgreSQL (Production)
```yaml
# config.yaml
database:
  type: postgresql
  host: localhost
  port: 5432
  database: gateway
  username: gateway_user
  password: ${DB_PASSWORD}
  pool_size: 20
  max_overflow: 10
```

### SQLite (Development)
```yaml
database:
  type: sqlite
  path: ./gateway.db
```

---

## ðŸ“Š Indexes Strategy

**Purpose:** Fast queries for common access patterns

- **Timestamp indexes**: Fast time-range queries
- **Attribution indexes**: Quick filtering by user/team/project
- **Cost indexes**: Fast sorting by cost
- **Composite indexes**: Optimize complex queries

**Maintenance:**
```sql
-- Analyze tables for query optimization
ANALYZE llm_requests;
ANALYZE cost_aggregates;

-- Vacuum to reclaim space
VACUUM ANALYZE llm_requests;
```

---

## ðŸ” Security Considerations

1. **API Key Hashing**: Store only hashed keys (bcrypt/argon2)
2. **Row-Level Security**: PostgreSQL RLS for multi-tenancy
3. **Encryption**: Encrypt sensitive metadata at rest
4. **Audit Logs**: Track all schema changes

---

## ðŸ“ˆ Performance Optimization

1. **Partitioning**: Partition `llm_requests` by month
2. **Archiving**: Move old data to cold storage (>90 days)
3. **Aggregates**: Pre-compute daily/monthly aggregates
4. **Caching**: Cache frequent queries (Redis)

---

**Schema Version:** 1.0  
**Last Updated:** December 15, 2024


