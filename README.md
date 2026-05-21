# Toolkit LLM Gateway

**Enterprise LLM Proxy with Advanced Cost Tracking and Analytics**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status: Beta](https://img.shields.io/badge/status-beta-orange.svg)]()

---

## Overview

**Toolkit LLM Gateway** is an enterprise-grade LLM proxy that provides:

- **Unified API** for 100+ LLM providers (OpenAI, Anthropic, Cohere, Groq, etc.)
- **Advanced Cost Tracking** per user, team, project, and model
- **Real-time Analytics Dashboard** with usage insights
- **Rate Limiting and Budgets** to control spending
  - Per-API-key token-bucket rate limiting (RPM/TPM) with automatic refill
  - Proactive budget monitor with background checks and configurable thresholds
- **Intelligent Caching** to reduce costs by 30-70%
- **Load Balancing and Fallbacks** for high availability
- **Enterprise Security** with SSO, RBAC, and audit logs
- **Cost Optimization** recommendations

**Based on:** [LiteLLM](https://github.com/BerriAI/litellm) by BerriAI (MIT License)  
**Enhanced by:** Toolkit with enterprise features and Toolkit ecosystem integration

---

## Key Features

### Core Capabilities

- **Multi-Provider Support**: Single API for OpenAI, Anthropic, Azure, AWS Bedrock, Google, Groq, and 100+ more
- **Drop-in Replacement**: Compatible with OpenAI SDK (just change the base URL)
- **Async/Streaming**: Full support for streaming responses and async operations
- **Function Calling**: Works with OpenAI, Anthropic, and other compatible APIs

### Toolkit Enterprise Features

- **Advanced Cost Attribution**:
  - Track costs per user, team, project, model, and prompt
  - Budget alerts and spending forecasts
  - Chargeback/showback reporting
  - ROI calculation per model

- **Analytics Dashboard**:
  - Real-time usage metrics
  - Cost breakdown visualizations
  - Performance benchmarking
  - Provider comparison

- **Intelligent Caching**:
  - Semantic caching for similar prompts
  - Exact match caching
  - Cost savings tracking

- **Enterprise Security**:
  - SSO integration (OAuth, SAML)
  - Role-based access control (RBAC)
  - API key management
  - Audit logs and compliance reporting

### Toolkit Ecosystem Integration

- Integrates with **Toolkit ML FinOps** (coming soon)
- Connects to **Toolkit Prompt Studio** (coming soon)
- Works with **Toolkit Cost-Latency Optimizer**
- Exports metrics to **Toolkit Model Monitor** (coming soon)

---

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/AKIVA-AI/toolkit-llm-gateway.git
cd toolkit-llm-gateway

# Install core package (editable mode)
pip install -e .

# Install with proxy server
pip install -e ".[proxy]"

# Install with analytics
pip install -e ".[analytics]"

# Install everything (proxy + analytics + dev tools)
pip install -e ".[all]"
```

### Basic Usage (Python SDK)

```python
from litellm import completion

# Call any LLM provider with the same interface
response = completion(
    model="gpt-4",
    messages=[{"role": "user", "content": "Hello!"}],
    # Optional: Track costs
    metadata={
        "user": "john@company.com",
        "team": "engineering",
        "project": "chatbot-v2"
    }
)

print(response.choices[0].message.content)
```

### Run as Proxy Server

```bash
# Start the gateway server
toolkit-gateway --config config.yaml

# Or use environment variables
export TOOLKIT_GATEWAY_PORT=8000
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-...
toolkit-gateway
```

### Use with OpenAI SDK

```python
import openai

# Just point to Toolkit Gateway
openai.api_base = "http://localhost:8000"
openai.api_key = "your-toolkit-gateway-key"

# Use exactly like OpenAI API
response = openai.ChatCompletion.create(
    model="gpt-4",  # or "claude-3-opus", "command-r-plus", etc.
    messages=[{"role": "user", "content": "Hello!"}]
)
```

---

## Configuration

### Basic Configuration (config.yaml)

```yaml
# Toolkit LLM Gateway Configuration

# Server Settings
server:
  host: "0.0.0.0"
  port: 8000
  workers: 4

# Model Configuration
models:
  - model_name: gpt-4
    litellm_params:
      model: gpt-4
      api_key: ${OPENAI_API_KEY}
  
  - model_name: claude-3-opus
    litellm_params:
      model: claude-3-opus-20240229
      api_key: ${ANTHROPIC_API_KEY}

# Cost Tracking
cost_tracking:
  enabled: true
  database: postgresql://user:pass@localhost/gateway

# Caching
caching:
  enabled: true
  type: redis
  host: localhost
  port: 6379
  ttl: 3600  # 1 hour

# Rate Limiting
rate_limiting:
  - user: default
    rpm: 100
    tpm: 100000
    budget: 100.00  # USD per day

# Analytics
analytics:
  enabled: true
  dashboard_port: 8001
```

---

## Cost Tracking

### Track Costs per User/Team/Project

```python
from litellm import completion

response = completion(
    model="gpt-4",
    messages=[{"role": "user", "content": "Analyze this data..."}],
    metadata={
        "user": "alice@company.com",
        "team": "data-science",
        "project": "customer-insights",
        "cost_center": "CC-1234"
    }
)

# Automatic cost calculation and attribution
print(f"Cost: ${response._hidden_params.get('response_cost', 0):.4f}")
```

---

## Security and Compliance

### API Key Management

API keys are managed via the proxy's REST API while the gateway is running:

```bash
# Create API key for user
curl -X POST http://localhost:8000/key/generate \
  -H "Authorization: Bearer <master-key>" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "alice@company.com", "team_id": "data-science", "max_budget": 100}'

# List keys
curl http://localhost:8000/key/info \
  -H "Authorization: Bearer <master-key>"

# Delete key
curl -X POST http://localhost:8000/key/delete \
  -H "Authorization: Bearer <master-key>" \
  -H "Content-Type: application/json" \
  -d '{"keys": ["<key_to_delete>"]}'
```

---

## Supported Providers

**100+ LLM Providers Supported:**

- **OpenAI**: GPT-4, GPT-3.5, etc.
- **Anthropic**: Claude 3 (Opus, Sonnet, Haiku)
- **Google**: Gemini, Palm
- **AWS Bedrock**: Claude, Llama, Titan
- **Azure OpenAI**: All OpenAI models on Azure
- **Cohere**: Command-R, Command-R+
- **Groq**: Fast inference for Llama, Mixtral
- **Mistral AI**: Mistral models
- **Perplexity**: Online LLMs
- **Together AI**, **Replicate**, **HuggingFace**, and many more!

---

## Architecture

The gateway is organized into three layers:

```text
+---------------------------------------------------------+
|  LiteLLM Proxy (src/)                                   |
|  Unified API for 100+ LLM providers, routing, caching   |
+---------------------------------------------------------+
|  toolkit_extensions/                                     |
|  +-----------+  +-----------+  +------------------+     |
|  | cost_     |  | budget_   |  | alert_webhooks   |     |
|  | tracker   |  | manager   |  | (async delivery) |     |
|  +-----------+  +-----------+  +------------------+     |
|  +-----------+  +-----------+  +------------------+     |
|  | cost_     |  | auth_     |  | security         |     |
|  | analytics |  | middleware|  | (keys, rate lim.)|     |
|  +-----------+  +-----------+  +------------------+     |
|  +-----------+  +-----------+  +------------------+     |
|  | cost_     |  | health_   |  | metrics          |     |
|  | aggregator|  | check     |  | (Prometheus)     |     |
|  +-----------+  +-----------+  +------------------+     |
|  +-----------+  +-----------+  +------------------+     |
|  | config_   |  | logging_  |  | rate_limiter     |     |
|  | validator |  | config    |  | budget_monitor   |     |
|  +-----------+  +-----------+  +------------------+     |
+---------------------------------------------------------+
|  Database Layer (SQLAlchemy)                             |
|  Models: Team, User, Project, LLMRequest, Budget,       |
|          BudgetAlert, APIKey, CostAggregate              |
|  Backends: PostgreSQL (production), SQLite (development) |
+---------------------------------------------------------+
```

**Key design decisions:**
- `toolkit_extensions/` is cleanly separated from the forked LiteLLM code in `src/`
- Platform-independent types (JSONType, UUIDType) allow SQLite for dev, PostgreSQL for prod
- Global singletons for managers (cost tracker, budget manager, etc.) with lazy initialization
- Webhook delivery uses `httpx.AsyncClient` with non-blocking `asyncio.sleep` retries
- Cost aggregation materializes pre-computed data from raw requests for fast dashboard queries

---

## Deployment Guide

### Docker (Recommended)

```bash
# Build the image
docker build -t toolkit-llm-gateway .

# Run with docker-compose
docker-compose up -d
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `OPENAI_API_KEY` | Recommended | OpenAI API key |
| `ANTHROPIC_API_KEY` | Recommended | Anthropic API key |
| `DASHBOARD_API_KEY` | Recommended | API key for dashboard auth |
| `SECRET_KEY` | Recommended | Secret for webhook HMAC signing |
| `REDIS_URL` | Optional | Redis connection for caching |
| `LOG_LEVEL` | Optional | DEBUG, INFO, WARNING, ERROR (default: INFO) |
| `LOG_FORMAT` | Optional | Set to `json` for structured JSON logging |
| `HOST` | Optional | Server host (default: 0.0.0.0) |
| `PORT` | Optional | Server port (default: 12000) |

### Health Checks

```bash
# Basic health check
curl http://localhost:12000/health

# Detailed health check with dependency status
curl http://localhost:12000/health?detailed=true

# Version
curl http://localhost:12000/version
```

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests with coverage
pytest

# Coverage threshold is enforced at 70%
```

---

## Version

Check the installed version:

```bash
toolkit-gateway-version
# or
python -c "from toolkit_extensions import __version__; print(__version__)"
```

---

## License

MIT License - see [LICENSE](LICENSE) for details.

**Based on LiteLLM** by BerriAI (MIT License)
**Enhanced by Toolkit** with enterprise features

---

## Support

- **Issues/Discussions**: Use the hosting repository's issue tracker
- **Email**: Contact support
