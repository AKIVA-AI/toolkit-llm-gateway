# Toolkit LLM Gateway - API Documentation

Complete API reference for Toolkit LLM Gateway cost tracking, budget management, analytics, and webhooks.

---

## Table of Contents

1. [Cost Tracking API](#cost-tracking-api)
2. [Budget Management API](#budget-management-api)
3. [Cost Analytics API](#cost-analytics-api)
4. [Alert Webhook API](#alert-webhook-api)
5. [Database Models](#database-models)
6. [Examples](#examples)

---

## Cost Tracking API

### CostTracker

Track LLM API costs with automatic attribution and performance metrics.

#### Initialization

```python
from toolkit_extensions.cost_tracker import CostTracker

tracker = CostTracker(enabled=True)
```

**Parameters:**
- `enabled` (bool): Enable/disable cost tracking

#### track_request()

Track an LLM request with full cost and performance details.

```python
tracker.track_request(
    model="gpt-4",
    provider="openai",
    prompt_tokens=1000,
    completion_tokens=500,
    total_cost=0.045,
    user_email="user@company.com",
    team_name="Engineering",
    project_name="ChatBot",
    latency_ms=1250,
    cache_hit=False,
    status="success",
    error_message=None
)
```

**Parameters:**
- `model` (str): LLM model name (e.g., "gpt-4", "claude-2")
- `provider` (str): Provider name (e.g., "openai", "anthropic")
- `prompt_tokens` (int): Number of prompt tokens
- `completion_tokens` (int): Number of completion tokens
- `total_cost` (float): Total cost in USD
- `user_email` (str, optional): User email for attribution
- `team_name` (str, optional): Team name for attribution
- `project_name` (str, optional): Project name for attribution
- `latency_ms` (int, optional): Request latency in milliseconds
- `cache_hit` (bool): Whether request was served from cache
- `status` (str): Request status ("success", "error", "pending")
- `error_message` (str, optional): Error message if status is "error"

**Returns:** Request ID (str)

**Auto-Entity Creation:**
The tracker automatically creates users, teams, and projects if they don't exist.

---

## Budget Management API

### BudgetManager

Create and manage budgets with automatic alert generation.

#### Initialization

```python
from toolkit_extensions.budget_manager import BudgetManager, BudgetPeriod

manager = BudgetManager()
```

#### create_budget()

Create a new budget for user, team, or project.

```python
budget_id = manager.create_budget(
    period=BudgetPeriod.MONTHLY,
    limit_amount=1000.0,
    user_email="user@company.com",
    alert_threshold=0.8
)
```

**Parameters:**
- `period` (BudgetPeriod): Budget period
  - `BudgetPeriod.DAILY`
  - `BudgetPeriod.WEEKLY`
  - `BudgetPeriod.MONTHLY`
  - `BudgetPeriod.YEARLY`
  - `BudgetPeriod.LIFETIME`
- `limit_amount` (float): Budget limit in USD
- `user_email` (str, optional): User email (exclusive with team/project)
- `team_name` (str, optional): Team name (exclusive with user/project)
- `project_name` (str, optional): Project name (exclusive with user/team)
- `alert_threshold` (float): Alert threshold (0.0-1.0, default: 0.8)
- `start_date` (datetime, optional): Budget start date
- `end_date` (datetime, optional): Budget end date

**Returns:** Budget ID (str)

**Note:** Must specify exactly ONE of: user_email, team_name, project_name

#### check_budget()

Check budget status and get details.

```python
status = manager.check_budget(user_email="user@company.com")
```

**Parameters:**
- `user_email` (str, optional): User email
- `team_name` (str, optional): Team name
- `project_name` (str, optional): Project name

**Returns:** Dict with:
- `status` (BudgetStatus): Overall status
  - `OK`: Under alert threshold
  - `APPROACHING`: Over threshold but under limit
  - `EXCEEDED`: Over budget limit
  - `DISABLED`: Budget disabled
- `budgets` (list): List of applicable budgets with details
- `can_proceed` (bool): Whether request should be allowed

#### generate_alerts()

Generate alerts for all budgets exceeding thresholds.

```python
alert_ids = manager.generate_alerts()
```

**Returns:** List of alert IDs created

**Alert Types:**
- `threshold_warning`: Budget usage exceeds alert_threshold
- `budget_exceeded`: Budget usage exceeds limit

**Deduplication:** Alerts are deduplicated per budget per period.

#### get_unsent_alerts()

Get all alerts that haven't been sent via webhooks.

```python
alerts = manager.get_unsent_alerts()
```

**Returns:** List of alert dicts with:
- `id` (str): Alert ID
- `budget_id` (str): Budget ID
- `alert_type` (str): Alert type
- `current_spend` (float): Current spend
- `budget_limit` (float): Budget limit
- `percentage_used` (float): Percentage of budget used
- `triggered_at` (datetime): When alert was triggered

#### mark_alert_sent()

Mark an alert as sent.

```python
manager.mark_alert_sent(alert_id)
```

#### update_budget()

Update budget parameters.

```python
manager.update_budget(
    budget_id,
    limit_amount=2000.0,
    alert_threshold=0.9,
    enabled=True
)
```

**Parameters:**
- `budget_id` (str): Budget ID
- `limit_amount` (float, optional): New limit
- `alert_threshold` (float, optional): New threshold
- `enabled` (bool, optional): Enable/disable budget

---

## Cost Analytics API

### CostAnalytics

Query and analyze cost data with flexible filtering.

#### Initialization

```python
from toolkit_extensions.cost_analytics import CostAnalytics, TimeGranularity
from datetime import datetime, timedelta

analytics = CostAnalytics()
```

#### get_total_cost()

Get total cost for a time period.

```python
total = analytics.get_total_cost(
    start_date=datetime.utcnow() - timedelta(days=30),
    end_date=datetime.utcnow(),
    user_email="user@company.com"
)
```

**Parameters:**
- `start_date` (datetime, optional): Start date (default: 30 days ago)
- `end_date` (datetime, optional): End date (default: now)
- `user_email` (str, optional): Filter by user
- `team_name` (str, optional): Filter by team
- `project_name` (str, optional): Filter by project
- `model` (str, optional): Filter by model

**Returns:** Total cost (float)

#### get_cost_by_model()

Get cost breakdown by LLM model.

```python
by_model = analytics.get_cost_by_model()
```

**Returns:** List of dicts:
```python
[
    {
        "model": "gpt-4",
        "total_cost": 1234.56,
        "request_count": 5000,
        "total_tokens": 2500000
    },
    ...
]
```

#### get_cost_by_user()

Get cost breakdown by user.

```python
by_user = analytics.get_cost_by_user(limit=10)
```

**Parameters:**
- `limit` (int): Max number of results (default: 10)

**Returns:** List of top users by cost

#### get_cost_by_team()

Get cost breakdown by team.

```python
by_team = analytics.get_cost_by_team()
```

**Returns:** List of teams with costs

#### get_cost_by_project()

Get cost breakdown by project.

```python
by_project = analytics.get_cost_by_project()
```

**Returns:** List of projects with costs

#### get_time_series()

Get cost data over time.

```python
time_series = analytics.get_time_series(
    granularity=TimeGranularity.DAILY,
    start_date=datetime.utcnow() - timedelta(days=7)
)
```

**Parameters:**
- `granularity` (TimeGranularity): Time bucket size
  - `HOURLY`: Hour-by-hour data
  - `DAILY`: Day-by-day data
  - `WEEKLY`: Week-by-week data
  - `MONTHLY`: Month-by-month data

**Returns:** List of time buckets with costs:
```python
[
    {
        "period": "2024-12-15",
        "total_cost": 123.45,
        "request_count": 500,
        "avg_cost_per_request": 0.247
    },
    ...
]
```

#### get_performance_stats()

Get performance metrics.

```python
stats = analytics.get_performance_stats()
```

**Returns:** Dict with:
```python
{
    "avg_latency_ms": 1250.5,
    "cache_hit_rate": 0.25,
    "error_rate": 0.01,
    "total_requests": 10000
}
```

#### get_summary()

Get comprehensive summary with all metrics.

```python
summary = analytics.get_summary(
    start_date=datetime.utcnow() - timedelta(days=7)
)
```

**Returns:** Dict with:
- `period`: Time period
- `total_cost`: Total cost
- `by_model`: Cost by model
- `by_user`: Cost by user
- `by_team`: Cost by team
- `by_project`: Cost by project
- `performance`: Performance stats

---

## Alert Webhook API

### AlertWebhookManager

Deliver budget alerts to external systems via webhooks.

#### Initialization

```python
from toolkit_extensions.alert_webhooks import AlertWebhookManager, WebhookProvider

manager = AlertWebhookManager()
```

#### register_webhook()

Register a new webhook endpoint.

```python
webhook_id = manager.register_webhook(
    name="Engineering Slack",
    url="https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
    provider=WebhookProvider.SLACK,
    secret="webhook_secret",
    alert_types=["threshold_warning", "budget_exceeded"],
    teams=["Engineering"],
    max_retries=3
)
```

**Parameters:**
- `name` (str): Webhook name
- `url` (str): Webhook URL
- `provider` (WebhookProvider): Provider type
  - `GENERIC`: Generic HTTP webhook
  - `SLACK`: Slack-compatible
  - `DISCORD`: Discord-compatible
  - `TEAMS`: Microsoft Teams-compatible
- `secret` (str, optional): Secret for HMAC signing
- `alert_types` (list, optional): Filter by alert types
- `teams` (list, optional): Filter by team names
- `users` (list, optional): Filter by user emails
- `max_retries` (int): Max retry attempts (default: 3)
- `enabled` (bool): Enable/disable webhook (default: True)

**Returns:** Webhook ID (str)

#### deliver_pending_alerts()

Deliver all pending alerts to configured webhooks.

```python
result = manager.deliver_pending_alerts()
```

**Returns:** Dict with:
```python
{
    "alerts_processed": 5,
    "success_count": 5,
    "failure_count": 0
}
```

**Behavior:**
- Retries failed deliveries with exponential backoff
- Marks alerts as sent after delivery
- Logs all delivery attempts

#### get_webhooks()

Get all webhooks.

```python
webhooks = manager.get_webhooks(enabled_only=True)
```

**Returns:** List of webhook dicts

#### update_webhook()

Update webhook configuration.

```python
manager.update_webhook(
    webhook_id,
    name="New Name",
    enabled=False
)
```

#### delete_webhook()

Delete a webhook.

```python
manager.delete_webhook(webhook_id)
```

#### get_delivery_stats()

Get delivery statistics for a webhook.

```python
stats = manager.get_delivery_stats(webhook_id)
```

**Returns:** Dict with:
```python
{
    "webhook_id": "...",
    "name": "Engineering Slack",
    "total_deliveries": 100,
    "success_count": 98,
    "failure_count": 2,
    "success_rate": 98.0,
    "last_success": "2024-12-15T10:30:00",
    "last_failure": "2024-12-14T15:45:00"
}
```

---

## Database Models

### Core Tables

#### teams
- `id` (UUID): Team ID
- `name` (str): Team name
- `created_at` (datetime): Creation time

#### users
- `id` (UUID): User ID
- `email` (str): User email
- `team_id` (UUID): Associated team
- `created_at` (datetime): Creation time

#### projects
- `id` (UUID): Project ID
- `name` (str): Project name
- `team_id` (UUID): Associated team
- `created_at` (datetime): Creation time

#### llm_requests
- `id` (UUID): Request ID
- `user_id` (UUID): User
- `team_id` (UUID): Team
- `project_id` (UUID): Project
- `model` (str): LLM model
- `provider` (str): Provider
- `prompt_tokens` (int): Prompt tokens
- `completion_tokens` (int): Completion tokens
- `total_cost` (float): Cost in USD
- `latency_ms` (int): Latency
- `cache_hit` (bool): Cache hit
- `status` (str): Status
- `error_message` (str): Error
- `timestamp` (datetime): Request time

#### budgets
- `id` (UUID): Budget ID
- `user_id` (UUID): User (nullable)
- `team_id` (UUID): Team (nullable)
- `project_id` (UUID): Project (nullable)
- `period` (str): Period type
- `limit_amount` (float): Budget limit
- `alert_threshold` (float): Alert threshold
- `start_date` (datetime): Start date
- `end_date` (datetime): End date
- `enabled` (bool): Enabled flag
- `created_at` (datetime): Creation time

#### budget_alerts
- `id` (UUID): Alert ID
- `budget_id` (UUID): Budget
- `alert_type` (str): Alert type
- `current_spend` (float): Current spend
- `budget_limit` (float): Budget limit
- `percentage_used` (float): Percentage
- `triggered_at` (datetime): Trigger time
- `notified_at` (datetime): Notification time

#### webhook_configs
- `id` (UUID): Webhook ID
- `name` (str): Name
- `provider` (str): Provider type
- `url` (str): Webhook URL
- `secret` (str): HMAC secret
- `enabled` (bool): Enabled flag
- `alert_types` (JSON): Alert filters
- `teams` (JSON): Team filters
- `users` (JSON): User filters
- `max_retries` (int): Max retries
- `success_count` (int): Success count
- `failure_count` (int): Failure count
- `last_success` (datetime): Last success
- `last_failure` (datetime): Last failure

#### webhook_deliveries
- `id` (UUID): Delivery ID
- `webhook_id` (UUID): Webhook
- `alert_id` (UUID): Alert
- `request_payload` (text): Request
- `response_status` (int): HTTP status
- `response_body` (text): Response
- `error_message` (text): Error
- `success` (bool): Success flag
- `attempt_number` (int): Attempt #
- `delivered_at` (datetime): Delivery time

---

## Examples

### Complete Workflow Example

```python
from toolkit_extensions.cost_tracker import CostTracker
from toolkit_extensions.budget_manager import BudgetManager, BudgetPeriod
from toolkit_extensions.cost_analytics import CostAnalytics
from toolkit_extensions.alert_webhooks import AlertWebhookManager, WebhookProvider

# 1. Initialize components
cost_tracker = CostTracker(enabled=True)
budget_manager = BudgetManager()
analytics = CostAnalytics()
webhook_manager = AlertWebhookManager()

# 2. Create budget
budget_id = budget_manager.create_budget(
    period=BudgetPeriod.MONTHLY,
    limit_amount=1000.0,
    team_name="Engineering",
    alert_threshold=0.8
)

# 3. Register webhook
webhook_id = webhook_manager.register_webhook(
    name="Engineering Slack",
    url="https://hooks.slack.com/services/YOUR/WEBHOOK",
    provider=WebhookProvider.SLACK,
    teams=["Engineering"]
)

# 4. Track requests
for i in range(100):
    cost_tracker.track_request(
        model="gpt-4",
        provider="openai",
        prompt_tokens=1000,
        completion_tokens=500,
        total_cost=8.50,  # $850 total
        user_email=f"engineer{i % 10}@company.com",
        team_name="Engineering"
    )

# 5. Check budget status
status = budget_manager.check_budget(team_name="Engineering")
print(f"Status: {status['status']}")
print(f"Can proceed: {status['can_proceed']}")

# 6. Generate and deliver alerts
alert_ids = budget_manager.generate_alerts()
if alert_ids:
    result = webhook_manager.deliver_pending_alerts()
    print(f"Delivered {result['success_count']} alerts")

# 7. Get analytics
total_cost = analytics.get_total_cost()
by_model = analytics.get_cost_by_model()
by_user = analytics.get_cost_by_user()

print(f"Total cost: ${total_cost}")
print(f"Top model: {by_model[0]['model']} (${by_model[0]['total_cost']})")
print(f"Top user: {by_user[0]['user_email']} (${by_user[0]['total_cost']})")
```

### Scheduled Alert Delivery

```python
import schedule
import time

def deliver_alerts():
    """Periodic alert delivery job"""
    manager = AlertWebhookManager()
    result = manager.deliver_pending_alerts()
    print(f"Delivered {result['success_count']} alerts")

# Run every 5 minutes
schedule.every(5).minutes.do(deliver_alerts)

while True:
    schedule.run_pending()
    time.sleep(60)
```

### Custom Analytics Report

```python
from datetime import datetime, timedelta

def generate_weekly_report():
    """Generate weekly cost report"""
    analytics = CostAnalytics()
    
    start_date = datetime.utcnow() - timedelta(days=7)
    
    summary = analytics.get_summary(start_date=start_date)
    time_series = analytics.get_time_series(
        granularity=TimeGranularity.DAILY,
        start_date=start_date
    )
    
    print("=" * 50)
    print(f"Weekly Cost Report ({start_date.date()} - {datetime.utcnow().date()})")
    print("=" * 50)
    print(f"\nTotal Cost: ${summary['total_cost']:.2f}")
    print(f"\nTop 5 Models:")
    for item in summary['by_model'][:5]:
        print(f"  {item['model']}: ${item['total_cost']:.2f} ({item['request_count']} requests)")
    
    print(f"\nTop 5 Users:")
    for item in summary['by_user'][:5]:
        print(f"  {item['user_email']}: ${item['total_cost']:.2f}")
    
    print(f"\nDaily Breakdown:")
    for day in time_series:
        print(f"  {day['period']}: ${day['total_cost']:.2f}")
    
    print(f"\nPerformance:")
    print(f"  Avg Latency: {summary['performance']['avg_latency_ms']:.1f}ms")
    print(f"  Cache Hit Rate: {summary['performance']['cache_hit_rate']:.1%}")
    print(f"  Error Rate: {summary['performance']['error_rate']:.2%}")

generate_weekly_report()
```

---

## Error Handling

All APIs raise standard Python exceptions:

- `ValueError`: Invalid parameters
- `KeyError`: Missing required fields
- `RuntimeError`: Database errors

Example:

```python
try:
    budget_id = budget_manager.create_budget(
        period=BudgetPeriod.MONTHLY,
        limit_amount=1000.0
        # Missing attribution!
    )
except ValueError as e:
    print(f"Error: {e}")
    # Error: Must specify exactly one of: user_email, team_name, project_name
```

---

## Best Practices

1. **Cost Tracking:**
   - Track all requests immediately
   - Include full attribution (user/team/project)
   - Record accurate token counts
   - Set appropriate status and errors

2. **Budget Management:**
   - Create budgets at appropriate levels (user/team/project)
   - Set reasonable thresholds (0.8 = 80% is recommended)
   - Review budgets regularly
   - Update limits as needed

3. **Analytics:**
   - Use time ranges appropriate for your queries
   - Limit result sets for large datasets
   - Cache frequently accessed data
   - Export data for long-term storage

4. **Webhooks:**
   - Use secrets for HMAC signing
   - Filter alerts appropriately
   - Monitor delivery statistics
   - Handle webhook failures gracefully

---

## Performance Considerations

- **Database Indexes:** All foreign keys and timestamp columns are indexed
- **Query Optimization:** Use filters to reduce result sets
- **Caching:** Consider caching frequently accessed analytics
- **Batch Operations:** Track multiple requests before querying
- **Connection Pooling:** Database connections are pooled automatically

---

## Security

- **HMAC Signing:** All webhooks support HMAC-SHA256 signing
- **Database:** Use environment variables for credentials
- **API Keys:** Store only hashed keys (future feature)
- **Attribution:** All costs attributed to specific entities
- **Audit Trail:** Full audit trail in webhook_deliveries table

---

*For more information, see the [README.md](README.md) and [STATUS.md](STATUS.md) files.*


