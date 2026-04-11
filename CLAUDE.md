# LLM Gateway — LLM proxy with unified API for 100+ providers and cost tracking

**Archetype:** 9 — Developer Tool / CLI Utility
**Standards:** See `akiva-enterprise-products/CLAUDE.md` for current Akiva Build Standard version and full standards reference.
**Ontology ID:** TK-02

## Stack
- Language: Python 3.9+
- Test: `pytest`
- Lint: `ruff check src/ tests/ && black --check src/`
- Build: `pip install -e .`

## Verification Commands
| Command | Purpose |
|---------|---------|
| `pytest` | Run tests |
| `ruff check src/ tests/ && black --check src/` | Lint |

## Current State

- Audit Score: 67.3/100 (v2.14 baseline, 2026-04-04, post-remediation)
- Prior Audit: 61/100 (v2.13 baseline, 2026-03-09)
- Tests: 307 (91.3% coverage)
- All Archetype 9 minimums met and exceeded

## Key Rules
- Archetype 9: single-purpose CLI tool, zero or minimal dependencies in core
- Tests first, security fixes before features
- One task at a time, verified before moving to next
