# LLM Gateway — LLM proxy with unified API for 100+ providers and cost tracking

**Archetype:** 9 — Developer Tool / CLI Utility
**Standards:** Akiva Build Standard v2.13
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
- Audit Score: 61/100
- Tests: 18

## Key Rules
- Archetype 9: single-purpose CLI tool, zero or minimal dependencies in core
- Tests first, security fixes before features
- One task at a time, verified before moving to next
