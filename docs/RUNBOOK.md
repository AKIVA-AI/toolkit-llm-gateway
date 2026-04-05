# Operational Runbook — toolkit-llm-gateway

**Last updated:** 2026-04-04
**On-call contact:** See SECURITY.md for security incidents

## Health Checks

### Liveness probe
```
GET /health
```
Returns `{"status": "healthy"}` when process is running. Use for container orchestrator liveness checks.

### Readiness probe
```
GET /health?detailed=true
```
Returns component-level health (database, Redis, providers). Use for load balancer readiness checks.

**Expected response:**
```json
{
  "status": "healthy",
  "checks": {
    "database": {"healthy": true, "response_time_ms": 2},
    "redis": {"healthy": true, "response_time_ms": 1},
    "providers": {
      "openai": {"available": true},
      "anthropic": {"available": true}
    }
  }
}
```

## Common Operational Procedures

### 1. Start the gateway

```bash
# Development
toolkit-gateway --config config.yaml

# Production (Docker)
docker-compose up -d

# Verify startup
curl http://localhost:4000/health
```

### 2. Check circuit breaker status

Circuit breakers are per-provider. When a provider's breaker opens:
- Requests fail fast (no timeout wait)
- After recovery_timeout (default 60s), one probe request is allowed
- If probe succeeds, breaker closes; if it fails, breaker re-opens

**Diagnosis:**
- Check logs for `"Circuit breaker <provider>: closed -> open"` messages
- Check provider status pages for outages
- Verify API keys are valid and not rate-limited

**Resolution:**
- Wait for recovery timeout (auto-recovery)
- If provider is confirmed down, fallback chain handles routing
- Manual reset: restart the gateway process

### 3. Budget exceeded alerts

When a user/team/project exceeds their budget:
- Alert webhook fires to configured channels (Slack/Discord/Teams)
- If `block_on_exceeded=True`, further LLM requests are blocked
- Dashboard shows exceeded budgets in red

**Resolution:**
- Review spend in dashboard: `GET /api/summary`
- Increase budget: update via BudgetManager API
- Or wait for next budget period (daily/weekly/monthly reset)

### 4. Database connection issues

**Symptoms:** Health check returns `"database": {"healthy": false}`

**Diagnosis:**
```bash
# Check Postgres connectivity
pg_isready -h <host> -p 5432

# Check connection pool stats in logs
grep "QueuePool" logs/gateway.log
```

**Resolution:**
- Verify DATABASE_URL environment variable
- Check Postgres is running and accepting connections
- Check connection pool exhaustion (default max: 20 + 10 overflow)
- Restart gateway if pool is corrupted

### 5. High latency

**Diagnosis:**
- Check Prometheus metrics: `request_duration_seconds` histogram
- Check provider-specific latency in cost tracking data
- Check database query times in health check response_time_ms

**Resolution:**
- If provider latency: check provider status, consider routing to faster tier
- If database latency: check indexes, consider running cost aggregation
- If gateway latency: check connection pool, memory, CPU

## Alerting Tiers

| Tier | Condition | Response Time | Action |
|------|-----------|---------------|--------|
| P0 | Gateway unreachable | 15 min | Restart, escalate |
| P1 | All providers down (circuit breakers open) | 30 min | Check providers, rotate keys |
| P2 | Single provider down | 1 hour | Monitor, fallback active |
| P3 | Budget alert | Next business day | Review and adjust |

## Environment Variables (critical)

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| DATABASE_URL | Yes | sqlite:///gateway.db | Database connection string |
| OPENAI_API_KEY | Conditional | — | OpenAI provider key |
| ANTHROPIC_API_KEY | Conditional | — | Anthropic provider key |
| REDIS_URL | No | — | Redis cache connection |
| LOG_LEVEL | No | INFO | Logging verbosity |
| LOG_FORMAT | No | text | Set to "json" for structured logging |

## Rollback Procedure

1. Identify the failing version from CI/CD logs
2. Pull previous Docker image: `docker pull toolkit-llm-gateway:<previous-sha>`
3. Update docker-compose.yml or deployment config
4. Restart: `docker-compose up -d`
5. Verify: `curl http://localhost:4000/health`
6. Document in incident log

## Incident Response

1. **Detect**: Health check failure, alert webhook, or user report
2. **Triage**: Classify as P0-P3 per alerting tiers above
3. **Communicate**: Post to #incidents channel
4. **Mitigate**: Apply appropriate resolution from procedures above
5. **Resolve**: Verify health checks pass, confirm with reporter
6. **Review**: Post-incident review within 48 hours for P0/P1

## HUMAN ACTION REQUIRED

The following operational items require human setup:

- [ ] Configure monitoring/alerting service (Datadog, PagerDuty, etc.)
- [ ] Set up on-call rotation
- [ ] Configure production provider API keys
- [ ] Enable branch protection on main branch
- [ ] Set up production database with proper backup schedule
- [ ] Configure TLS termination (reverse proxy or load balancer)
