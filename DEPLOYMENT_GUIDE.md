# Toolkit LLM Gateway - Deployment Guide

Complete guide for deploying Toolkit LLM Gateway in production.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Database Setup](#database-setup)
4. [Configuration](#configuration)
5. [Integration](#integration)
6. [Monitoring](#monitoring)
7. [Scaling](#scaling)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements
- Python 3.10+
- PostgreSQL 13+ (or SQLite for development)
- 2GB RAM minimum
- 10GB disk space

### Dependencies
```bash
pip install -r requirements.txt
```

**Core Dependencies:**
- sqlalchemy>=2.0.0
- psycopg2-binary>=2.9.0 (for PostgreSQL)
- httpx (for webhooks)
- python-dotenv

---

## Installation

### Development Setup

1. **Clone Repository:**
```bash
git clone <your-repo-url>
cd <repo-root>/enterprise-tools/oss/llm-gateway
```

2. **Install Dependencies:**
```bash
pip install -r requirements.txt
```

3. **Initialize Database:**
```python
from toolkit_extensions.database.connection import init_database, DatabaseConfig

config = DatabaseConfig(database_url="sqlite:///./gateway.db")
db_manager = init_database(config)
```

4. **Run Tests:**
```bash
pytest tests/ -v
```

### Production Setup

1. **Use PostgreSQL:**
```bash
# Create database
createdb gateway

# Set environment variable
export DATABASE_URL="postgresql://user:password@localhost:5432/gateway"
```

2. **Initialize Database:**
```python
from toolkit_extensions.database.connection import init_database, DatabaseConfig

config = DatabaseConfig()  # Uses DATABASE_URL from environment
db_manager = init_database(config)
```

3. **Configure Connection Pooling:**
```python
config = DatabaseConfig(
    pool_size=20,
    max_overflow=10,
    pool_timeout=30
)
```

---

## Database Setup

### PostgreSQL (Recommended)

**Create Database:**
```sql
CREATE DATABASE gateway;
CREATE USER gateway_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE gateway TO gateway_user;
```

**Connection String:**
```
postgresql://gateway_user:secure_password@localhost:5432/gateway
```

**Environment Variable:**
```bash
export DATABASE_URL="postgresql://gateway_user:secure_password@localhost:5432/gateway"
```

### MySQL

**Create Database:**
```sql
CREATE DATABASE gateway CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'gateway_user'@'localhost' IDENTIFIED BY 'secure_password';
GRANT ALL PRIVILEGES ON gateway.* TO 'gateway_user'@'localhost';
```

**Connection String:**
```
mysql+pymysql://gateway_user:secure_password@localhost:3306/gateway
```

### SQLite (Development Only)

```python
config = DatabaseConfig(database_url="sqlite:///./gateway.db")
```

**Note:** SQLite is not recommended for production due to concurrency limitations.

---

## Configuration

### Environment Variables

Create `.env` file:
```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/gateway

# Optional: Connection pool
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30

# Optional: Logging
LOG_LEVEL=INFO
```

### Python Configuration

```python
import os
from dotenv import load_dotenv
from toolkit_extensions.database.connection import init_database, DatabaseConfig

# Load environment variables
load_dotenv()

# Initialize database
config = DatabaseConfig(
    database_url=os.getenv("DATABASE_URL"),
    pool_size=int(os.getenv("DB_POOL_SIZE", 20)),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", 10)),
    pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", 30))
)

db_manager = init_database(config)
```

---

## Integration

### FastAPI Integration

```python
from fastapi import FastAPI, HTTPException
from toolkit_extensions.cost_tracker import CostTracker
from toolkit_extensions.budget_manager import BudgetManager

app = FastAPI()

# Initialize components
cost_tracker = CostTracker(enabled=True)
budget_manager = BudgetManager()

@app.post("/track-request")
async def track_request(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_cost: float,
    user_email: str
):
    """Track an LLM request"""
    
    # Check budget first
    status = budget_manager.check_budget(user_email=user_email)
    if not status["can_proceed"]:
        raise HTTPException(status_code=429, detail="Budget exceeded")
    
    # Track request
    request_id = cost_tracker.track_request(
        model=model,
        provider="openai",
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_cost=total_cost,
        user_email=user_email,
        status="success"
    )
    
    return {"request_id": request_id}

@app.get("/budget-status")
async def get_budget_status(user_email: str):
    """Get budget status for user"""
    status = budget_manager.check_budget(user_email=user_email)
    return status
```

### Flask Integration

```python
from flask import Flask, request, jsonify
from toolkit_extensions.cost_tracker import CostTracker
from toolkit_extensions.budget_manager import BudgetManager

app = Flask(__name__)

cost_tracker = CostTracker(enabled=True)
budget_manager = BudgetManager()

@app.route("/track-request", methods=["POST"])
def track_request():
    data = request.json
    
    # Check budget
    status = budget_manager.check_budget(user_email=data["user_email"])
    if not status["can_proceed"]:
        return jsonify({"error": "Budget exceeded"}), 429
    
    # Track request
    request_id = cost_tracker.track_request(
        model=data["model"],
        provider=data["provider"],
        prompt_tokens=data["prompt_tokens"],
        completion_tokens=data["completion_tokens"],
        total_cost=data["total_cost"],
        user_email=data["user_email"],
        status="success"
    )
    
    return jsonify({"request_id": request_id})
```

### LangChain Integration

```python
from langchain.callbacks.base import BaseCallbackHandler
from toolkit_extensions.cost_tracker import CostTracker

class ToolkitCostCallback(BaseCallbackHandler):
    """LangChain callback for cost tracking"""
    
    def __init__(self, user_email: str, team_name: str = None):
        self.user_email = user_email
        self.team_name = team_name
        self.tracker = CostTracker(enabled=True)
    
    def on_llm_end(self, response, **kwargs):
        """Track cost after LLM call"""
        llm_output = response.llm_output
        
        self.tracker.track_request(
            model=llm_output.get("model_name", "unknown"),
            provider="openai",
            prompt_tokens=llm_output.get("token_usage", {}).get("prompt_tokens", 0),
            completion_tokens=llm_output.get("token_usage", {}).get("completion_tokens", 0),
            total_cost=self._calculate_cost(llm_output),
            user_email=self.user_email,
            team_name=self.team_name,
            status="success"
        )
    
    def _calculate_cost(self, llm_output):
        # Implement cost calculation based on your pricing
        pass

# Usage
from langchain.llms import OpenAI

callback = ToolkitCostCallback(user_email="user@company.com", team_name="Engineering")
llm = OpenAI(callbacks=[callback])
llm("Hello, world!")
```

---

## Monitoring

### Scheduled Alert Delivery

```python
import schedule
import time
from toolkit_extensions.alert_webhooks import AlertWebhookManager

def deliver_alerts():
    """Deliver pending alerts"""
    manager = AlertWebhookManager()
    result = manager.deliver_pending_alerts()
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Delivered {result['success_count']} alerts")

# Run every 5 minutes
schedule.every(5).minutes.do(deliver_alerts)

print("Alert delivery service started...")
while True:
    schedule.run_pending()
    time.sleep(60)
```

### Metrics Collection

```python
from toolkit_extensions.cost_analytics import CostAnalytics
from datetime import datetime, timedelta

def collect_metrics():
    """Collect and log metrics"""
    analytics = CostAnalytics()
    
    # Get today's costs
    today = datetime.utcnow().date()
    start_date = datetime.combine(today, datetime.min.time())
    
    total_cost = analytics.get_total_cost(start_date=start_date)
    performance = analytics.get_performance_stats(start_date=start_date)
    
    print(f"Today's cost: ${total_cost:.2f}")
    print(f"Avg latency: {performance['avg_latency_ms']:.1f}ms")
    print(f"Cache hit rate: {performance['cache_hit_rate']:.1%}")
    print(f"Error rate: {performance['error_rate']:.2%}")

# Run every hour
schedule.every().hour.do(collect_metrics)
```

### Health Check Endpoint

```python
from fastapi import FastAPI
from toolkit_extensions.database.connection import get_session

app = FastAPI()

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check database connection
        with get_session() as session:
            session.execute("SELECT 1")
        
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }, 500
```

---

## Scaling

### Horizontal Scaling

**Load Balancer Configuration:**
```nginx
upstream gateway {
    server 10.0.1.10:8000;
    server 10.0.1.11:8000;
    server 10.0.1.12:8000;
}

server {
    listen 80;
    server_name toolkit-gateway.company.com;
    
    location / {
        proxy_pass http://gateway;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**Database Connection Pooling:**
```python
config = DatabaseConfig(
    database_url=os.getenv("DATABASE_URL"),
    pool_size=50,        # Increase for more connections
    max_overflow=20,     # Allow burst capacity
    pool_timeout=30
)
```

### Vertical Scaling

**PostgreSQL Tuning:**
```sql
-- Increase shared buffers (25% of RAM)
ALTER SYSTEM SET shared_buffers = '4GB';

-- Increase work memory
ALTER SYSTEM SET work_mem = '256MB';

-- Increase max connections
ALTER SYSTEM SET max_connections = 200;

-- Reload configuration
SELECT pg_reload_conf();
```

### Caching

```python
from functools import lru_cache
from datetime import datetime, timedelta

@lru_cache(maxsize=100)
def get_cached_analytics(date_key: str):
    """Cache analytics for a specific date"""
    analytics = CostAnalytics()
    start_date = datetime.fromisoformat(date_key)
    return analytics.get_summary(start_date=start_date)

# Usage
today_key = datetime.utcnow().date().isoformat()
summary = get_cached_analytics(today_key)
```

---

## Troubleshooting

### Common Issues

**1. Database Connection Errors**

```bash
Error: could not connect to server: Connection refused
```

**Solution:**
- Check DATABASE_URL environment variable
- Verify database is running: `pg_isready -h localhost -p 5432`
- Check firewall rules
- Verify credentials

**2. Webhook Delivery Failures**

```bash
Error: [Errno 110] Connection timed out
```

**Solution:**
- Verify webhook URL is accessible
- Check firewall/security groups
- Increase timeout: `httpx.post(..., timeout=60)`
- Review webhook logs: `manager.get_delivery_stats(webhook_id)`

**3. High Database Load**

**Symptoms:**
- Slow queries
- Connection pool exhaustion
- Timeout errors

**Solutions:**
- Add database indexes
- Increase connection pool size
- Implement query caching
- Use read replicas for analytics

**4. Memory Issues**

```bash
MemoryError: Unable to allocate array
```

**Solution:**
- Limit result sets: `analytics.get_cost_by_user(limit=100)`
- Use pagination for large datasets
- Implement streaming for exports
- Increase server memory

### Debug Mode

```python
# Enable debug logging
config = DatabaseConfig(
    database_url=os.getenv("DATABASE_URL"),
    echo=True  # Log all SQL queries
)

# Enable cost tracker debugging
tracker = CostTracker(enabled=True)
tracker.track_request(...)  # All queries logged
```

### Monitoring Queries

```sql
-- Check active connections
SELECT count(*) FROM pg_stat_activity WHERE state = 'active';

-- Find slow queries
SELECT pid, now() - query_start AS duration, query
FROM pg_stat_activity
WHERE state = 'active' AND now() - query_start > interval '5 seconds';

-- Check table sizes
SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

---

## Production Checklist

### Before Deployment

- [ ] Environment variables configured
- [ ] Database initialized and tested
- [ ] Connection pooling configured
- [ ] Webhooks registered and tested
- [ ] Budgets created for all entities
- [ ] Health check endpoint working
- [ ] Monitoring configured
- [ ] Backup strategy implemented
- [ ] SSL/TLS certificates installed
- [ ] Security review completed

### After Deployment

- [ ] Verify database connections
- [ ] Test cost tracking
- [ ] Verify budget checks
- [ ] Test webhook delivery
- [ ] Monitor error rates
- [ ] Review performance metrics
- [ ] Set up alerts
- [ ] Document configuration
- [ ] Train team members
- [ ] Schedule regular reviews

---

## Security Best Practices

1. **Database:**
   - Use strong passwords
   - Enable SSL connections
   - Restrict network access
   - Regular backups

2. **Webhooks:**
   - Use HMAC signing
   - Validate webhook URLs
   - Implement rate limiting
   - Monitor delivery failures

3. **API:**
   - Use HTTPS only
   - Implement authentication
   - Rate limit endpoints
   - Log all requests

4. **Monitoring:**
   - Monitor failed logins
   - Track unusual spending patterns
   - Alert on database errors
   - Review audit logs

---

## Support

For issues or questions:
- GitHub Issues: <your-issue-tracker-url>
- Email: <support-email>
- Documentation: See [API_DOCUMENTATION.md](API_DOCUMENTATION.md)

---

*Last updated: 2024-12-15*




