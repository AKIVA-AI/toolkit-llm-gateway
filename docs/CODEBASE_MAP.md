# Codebase Map — toolkit-llm-gateway

**Last updated:** 2026-04-04
**Archetype:** 9 — Developer Tool / CLI
**Version:** 1.1.0

## Architecture Overview

Three-layer design: LiteLLM proxy (inherited upstream) + toolkit_extensions (custom enterprise layer) + SQLAlchemy data layer.

```
toolkit-llm-gateway/
  src/
    toolkit_extensions/     # Custom enterprise code (4,800+ LOC, 21 files)
      control_plane/        # Akiva control-plane adapter
      database/             # SQLAlchemy models + connection management
    litellm/                # Forked LiteLLM proxy (~101K LOC, inherited)
    alembic/                # Database migrations
  tests/                    # 23 test files, 300+ tests
  dashboard/                # FastAPI monitoring dashboard
  .github/workflows/        # CI/CD pipeline (6 jobs)
  docs/                     # Audit reports, schema docs, provenance
```

## Source Modules (toolkit_extensions/)

| Module | LOC | Purpose | Tests |
|--------|-----|---------|-------|
| `security.py` | 604 | Input validation, PII redaction, rate limiting, API key mgmt, CORS, security headers, payload validation | `test_security.py` (14), `test_security_enhancements.py` (72) |
| `alert_webhooks.py` | 624 | Webhook delivery (Slack/Discord/Teams/Generic), HMAC signing, async retries | `test_alert_webhooks.py` (15), `test_async_webhooks.py` (4) |
| `cost_analytics.py` | 493 | Cost breakdowns by model/user/team/project, time-series, performance stats | `test_cost_analytics.py` (14) |
| `budget_manager.py` | 484 | Budget CRUD, period calculations, alert generation with deduplication | `test_budget_manager.py` (17) |
| `database/models.py` | 385 | 8 SQLAlchemy models, platform-independent types | `test_database_models.py` (12) |
| `cost_tracker.py` | 290 | CostTracker + CostTrackingMiddleware, auto-entity creation | `test_cost_tracker.py` (12) |
| `config_validator.py` | 232 | Env var validation (REQUIRED/RECOMMENDED/OPTIONAL), CLI entry | `test_config_validator.py` (11) |
| `metrics.py` | 215 | Prometheus-compatible metrics (counters, gauges, histograms) | `test_metrics.py` (11) |
| `cost_aggregator.py` | 200 | Materialized aggregates from raw LLM requests | `test_cost_aggregator.py` (7) |
| `database/connection.py` | 187 | DatabaseManager, connection pooling, session factory | (tested via integration) |
| `circuit_breaker.py` | 195 | 3-state circuit breaker (CLOSED/OPEN/HALF_OPEN), per-provider registry | `test_circuit_breaker.py` (24) |
| `health_check.py` | 179 | DB/Redis/provider health, liveness + readiness probes | `test_health_check.py` (10) |
| `auth_middleware.py` | 162 | Scope-based API key authentication (7 scopes + wildcard) | `test_auth_middleware.py` (13) |
| `control_plane/tool_specs.py` | 132 | CLI command to ToolSpec mapping | `test_control_plane.py` (29) |
| `control_plane/contracts.py` | 129 | PermissionScope, ApprovalPolicy, AuthorityBoundary (framework-optional) | `test_control_plane.py` |
| `control_plane/config.py` | 114 | 3-tier config hierarchy | `test_control_plane.py` |
| `logging_config.py` | 90 | StructuredJsonFormatter, configure_logging() | `test_logging_config.py` (6) |
| `cli.py` | 12 | print_version() entry point | `test_version_and_cli.py` (3) |
| `__init__.py` | 11 | Version string | `test_basic_import.py` (3) |

## Database Schema (8 models)

| Model | Table | Key Fields |
|-------|-------|------------|
| Team | teams | id, name, created_at |
| User | users | id, email, team_id, created_at |
| Project | projects | id, name, team_id, created_at |
| LLMRequest | llm_requests | id, request_id, user_id, team_id, project_id, model, provider, tokens, costs, latency, status |
| Budget | budgets | id, user_id/team_id/project_id (CHECK: exactly one), period, limit_amount, alert_threshold |
| BudgetAlert | budget_alerts | id, budget_id, alert_type, current_spend, budget_limit, notification_sent |
| APIKey | api_keys | id, key_hash, user_id, team_id, scopes, rate_limit, expires_at |
| CostAggregate | cost_aggregates | id, dimension, dimension_value, period, total_cost, request_count |

## CI/CD Pipeline (6 jobs)

| Job | Runs | Blocks Build |
|-----|------|-------------|
| test | pytest on Python 3.9, 3.11, 3.12 matrix with Postgres 15 | Yes |
| lint | Black + Ruff + MyPy (all blocking) | Yes |
| security | Safety (CVE) + Bandit (SAST) | Yes |
| sbom | Syft (CycloneDX) + Grype (vulnerability scan) | Yes |
| build | Docker buildx | After test+lint+security+sbom |
| all-checks | Aggregator gate | Branch protection |

## Entry Points

| Command | Target | Purpose |
|---------|--------|---------|
| `toolkit-gateway` | `litellm.proxy.proxy_cli:run_server` | Start LLM proxy server |
| `toolkit-llm-proxy` | `litellm.proxy.proxy_cli:run_server` | Alias for above |
| `toolkit-gateway-version` | `toolkit_extensions.cli:print_version` | Print version |

## Dependencies (core)

httpx, litellm, openai, sqlalchemy, psycopg2-binary, alembic, pydantic, jsonschema, tiktoken, tokenizers, click, jinja2, aiohttp, python-dotenv

## Key Patterns

- **Global singletons**: Module-level `_instance` with `get_*()` factory functions
- **Cost tracking**: Non-blocking — all DB errors caught and logged, never fails LLM requests
- **Platform independence**: JSONType/UUIDType adapters for Postgres and SQLite
- **Circuit breaker**: Per-provider fault isolation, 3-state machine, thread-safe
- **Security**: Constant-time key comparison, PII redaction before storage, restrictive CORS default
