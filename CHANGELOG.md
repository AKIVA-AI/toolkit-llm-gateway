# Changelog

All notable changes to the Toolkit LLM Gateway will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-03-09

### Added
- API key authentication middleware with scope-based access control (`auth_middleware.py`).
  Predefined scopes: read, write, admin, completions, analytics, budgets, webhooks.
- Async webhook delivery using `httpx.AsyncClient` with non-blocking `asyncio.sleep`
  retries. Replaces blocking `time.sleep` in the retry loop.
- Cost aggregate materialization (`cost_aggregator.py`) -- populates the `CostAggregate`
  table from raw LLM request data. Supports hourly and daily periods across model,
  provider, user, team, and project dimensions.
- Structured JSON logging via `StructuredJsonFormatter` and `configure_logging()`.
  Enable with `LOG_FORMAT=json` environment variable.
- Version endpoint (`/version`) and health check with dependency status (`/health?detailed=true`).
- `toolkit-gateway-version` CLI entry point for `--version` output.
- Coverage threshold enforcement: `--cov-fail-under=70` in pytest configuration.
- Comprehensive test suites for: auth middleware, cost aggregator, health check,
  metrics, config validator, structured logging, async webhooks, and CLI version.
- `CHANGELOG.md` (this file).
- Architecture and deployment documentation improvements in README.

### Changed
- Bumped version from 1.0.0 to 1.1.0.
- Health check module now uses `db_manager.session()` context manager instead of
  `db_manager.get_session()` (bug fix for incorrect context manager usage).
- Health check response now includes `version` field from `__version__`.
- Dashboard `/health` endpoint now supports `?detailed=true` query parameter
  for dependency status checks (database, Redis, LLM providers).

### Fixed
- Health checker `_check_database` was calling `get_session()` as a context manager
  but that method returns a raw Session. Now correctly uses `session()`.

## [1.0.0] - 2026-01-10

### Added
- Initial release forking LiteLLM with custom `toolkit_extensions` package.
- Cost tracking middleware with per-user, per-team, per-project attribution.
- Budget management with daily/weekly/monthly/yearly/lifetime periods.
- Alert webhook system supporting Slack, Discord, Microsoft Teams, and generic HTTP.
- Analytics dashboard (FastAPI) with cost-by-model, cost-by-user, cost-by-team,
  time-series, and performance endpoints.
- API key management with SHA-256 hashing and HMAC payload signing.
- Input validation and rate limiting.
- SQLAlchemy models with platform-independent types (PostgreSQL / SQLite).
- Prometheus-compatible metrics export.
- Configuration validator with REQUIRED/RECOMMENDED/OPTIONAL levels.
- Docker and docker-compose deployment support.
- GitHub Actions CI with test, lint, security scan, and Docker build jobs.
- Dependabot configuration for pip and GitHub Actions.
