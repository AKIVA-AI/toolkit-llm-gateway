# ðŸš€ Toolkit LLM Gateway

**Enterprise LLM Proxy with Advanced Cost Tracking & Analytics**

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status: Beta](https://img.shields.io/badge/status-beta-orange.svg)]()

---

## ðŸ“‹ Overview

**Toolkit LLM Gateway** is an enterprise-grade LLM proxy that provides:

- ðŸ”Œ **Unified API** for 100+ LLM providers (OpenAI, Anthropic, Cohere, Groq, etc.)
- ðŸ’° **Advanced Cost Tracking** per user, team, project, and model
- ðŸ“Š **Real-time Analytics Dashboard** with usage insights
- ðŸ›¡ï¸ **Rate Limiting & Budgets** to control spending
- âš¡ **Intelligent Caching** to reduce costs by 30-70%
- ðŸ”„ **Load Balancing & Fallbacks** for high availability
- ðŸ” **Enterprise Security** with SSO, RBAC, and audit logs
- ðŸ“ˆ **Cost Optimization** recommendations

**Based on:** [LiteLLM](https://github.com/BerriAI/litellm) by BerriAI (MIT License)  
**Enhanced by:** Toolkit with enterprise features and Toolkit ecosystem integration

---

## âœ¨ Key Features

### ðŸŽ¯ **Core Capabilities**

- **Multi-Provider Support**: Single API for OpenAI, Anthropic, Azure, AWS Bedrock, Google, Groq, and 100+ more
- **Drop-in Replacement**: Compatible with OpenAI SDK (just change the base URL)
- **Async/Streaming**: Full support for streaming responses and async operations
- **Function Calling**: Works with OpenAI, Anthropic, and other compatible APIs

### ðŸ’¼ **Toolkit Enterprise Features**

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

### ðŸ”— **Toolkit Ecosystem Integration**

- Integrates with **Toolkit ML FinOps** (coming soon)
- Connects to **Toolkit Prompt Studio** (coming soon)
- Works with **Toolkit Cost-Latency Optimizer**
- Exports metrics to **Toolkit Model Monitor** (coming soon)

---

## ðŸš€ Quick Start

### Installation

```bash
# Install core package
pip install toolkit-llm-gateway

# Install with proxy server
pip install "toolkit-llm-gateway[proxy]"

# Install with analytics
pip install "toolkit-llm-gateway[analytics]"

# Install everything
pip install "toolkit-llm-gateway[all]"
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
export Toolkit_GATEWAY_PORT=8000
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

## ðŸ“Š Configuration

### Basic Configuration (`config.yaml`)

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
  
  - model_name: command-r-plus
    litellm_params:
      model: command-r-plus
      api_key: ${COHERE_API_KEY}

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
    rpm: 100  # requests per minute
    tpm: 100000  # tokens per minute
    budget: 100.00  # USD per day

# Analytics
analytics:
  enabled: true
  dashboard_port: 8001
```

---

## ðŸ’° Cost Tracking

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

### Budget Alerts

```yaml
# config.yaml
budgets:
  - entity_type: user
    entity_id: alice@company.com
    limit: 50.00  # USD per day
    alert_threshold: 0.8  # Alert at 80%
    
  - entity_type: team
    entity_id: data-science
    limit: 500.00  # USD per day
```

### Cost Analytics API

```python
# Get cost breakdown
GET /v1/analytics/costs?start_date=2024-01-01&end_date=2024-01-31
```

Response:
```json
{
  "total_cost": 1234.56,
  "by_model": {
    "gpt-4": 856.34,
    "claude-3-opus": 378.22
  },
  "by_team": {
    "data-science": 645.23,
    "engineering": 589.33
  },
  "by_project": {
    "customer-insights": 423.12,
    "chatbot-v2": 811.44
  }
}
```

---

## âš¡ Performance Features

### Intelligent Caching

```python
# Semantic caching - similar prompts return cached results
response1 = completion(
    model="gpt-4",
    messages=[{"role": "user", "content": "What is machine learning?"}],
    caching=True
)

# Similar prompt hits cache (30-70% cost savings)
response2 = completion(
    model="gpt-4",
    messages=[{"role": "user", "content": "Explain machine learning"}],
    caching=True
)

print(f"Cache hit: {response2._hidden_params.get('cache_hit', False)}")
```

### Load Balancing

```yaml
# config.yaml
models:
  - model_name: gpt-4-balanced
    litellm_params:
      model: gpt-4
      api_base: 
        - https://api.openai.com/v1  # Primary
        - https://api.azure.com/v1   # Fallback
      api_key:
        - ${OPENAI_API_KEY}
        - ${AZURE_API_KEY}
    load_balancing: round_robin
```

### Automatic Fallbacks

```yaml
# config.yaml
models:
  - model_name: smart-llm
    litellm_params:
      model: gpt-4
      api_key: ${OPENAI_API_KEY}
      fallbacks:
        - model: claude-3-opus
          api_key: ${ANTHROPIC_API_KEY}
        - model: command-r-plus
          api_key: ${COHERE_API_KEY}
```

---

## ðŸ” Security & Compliance

### API Key Management

```bash
# Create API key for user
toolkit-gateway create-key --user alice@company.com --teams data-science --budget 100

# List keys
toolkit-gateway list-keys

# Revoke key
toolkit-gateway revoke-key <key_id>
```

### SSO Integration

```yaml
# config.yaml
authentication:
  type: oauth
  provider: okta
  client_id: ${OKTA_CLIENT_ID}
  client_secret: ${OKTA_CLIENT_SECRET}
  domain: company.okta.com
```

### Audit Logs

```python
# All requests are automatically logged
GET /v1/audit-logs?user=alice@company.com&start_date=2024-01-01
```

---

## ðŸ“ˆ Analytics Dashboard

Start the built-in analytics dashboard:

```bash
toolkit-gateway --dashboard
# Access at http://localhost:8001
```

**Dashboard Features:**
- Real-time usage metrics
- Cost breakdown charts
- Provider performance comparison
- Cache hit rate tracking
- Budget utilization
- Top users/teams/projects

---

## ðŸ”§ Advanced Configuration

### Custom Cost Calculation

```python
# Override default cost calculation
from litellm import register_cost_calculator

@register_cost_calculator("gpt-4-custom")
def custom_cost(prompt_tokens, completion_tokens, **kwargs):
    # Custom pricing logic
    prompt_cost = prompt_tokens * 0.00003  # $0.03 per 1K tokens
    completion_cost = completion_tokens * 0.00006  # $0.06 per 1K tokens
    return prompt_cost + completion_cost
```

### Webhooks for Cost Alerts

```yaml
# config.yaml
webhooks:
  - event: budget_exceeded
    url: https://slack.com/api/webhooks/...
    payload:
      text: "ðŸš¨ Budget exceeded: {entity_type} {entity_id}"
  
  - event: high_cost_request
    url: https://company.com/api/alerts
    threshold: 5.00  # Alert for requests > $5
```

---

## ðŸ¤ Integration with Toolkit Tools

### With Toolkit Cost-Latency Optimizer

```python
# Export metrics for optimization
toolkit-gateway export-metrics --tool cost-optimizer --output metrics.json
```

### With Toolkit ML FinOps (Coming Soon)

```yaml
# config.yaml
integrations:
  ml_finops:
    enabled: true
    endpoint: http://localhost:9000
    sync_interval: 300  # 5 minutes
```

---

## ðŸ“¦ Supported Providers

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

[See full provider list](https://docs.litellm.ai/docs/providers)

---

## ðŸ§ª Testing

```bash
# Run tests
pytest tests/

# Run with coverage
pytest tests/ --cov=litellm --cov-report=html

# Test specific provider
pytest tests/test_openai.py -v
```

---

## ðŸ“– Documentation

- **Documentation**: see this repository `README.md` and `docs/` folder
- **LiteLLM Docs**: [docs.litellm.ai](https://docs.litellm.ai) (upstream documentation)
- **API Reference**: `/docs` endpoint when server is running
- **Examples**: See `examples/` directory

---

## ðŸ¤ Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## ðŸ“œ License

MIT License - see [LICENSE](LICENSE) for details.

**Based on LiteLLM** by BerriAI (MIT License)  
**Enhanced by Toolkit** with enterprise features

---

## ðŸ™ Credits

- **Upstream Project**: [LiteLLM](https://github.com/BerriAI/litellm) by BerriAI
- **Toolkit Enhancements**: Toolkit team
- **Contributors**: See [CONTRIBUTORS.md](CONTRIBUTORS.md)

---

## ðŸ†˜ Support

- **Issues/Discussions**: use the hosting repository's issue tracker (if published standalone, use that repo)
- **Email**: <support-email>

---

## ðŸŽ¯ Roadmap

### âœ… Current (v1.0.0)
- [x] Fork LiteLLM core
- [x] Toolkit branding
- [x] Enhanced cost tracking
- [x] Basic analytics dashboard

### ðŸš§ In Progress (v1.1.0 - Week 2)
- [ ] Advanced team/project attribution
- [ ] Budget alerts and forecasts
- [ ] Improved caching strategies
- [ ] Enhanced dashboard with visualizations

### ðŸ“… Planned (v1.2.0 - Week 3)
- [ ] Integration with Toolkit ML FinOps
- [ ] Integration with Toolkit Prompt Studio
- [ ] Advanced analytics and reporting
- [ ] Cost optimization recommendations
- [ ] Performance benchmarking

### ðŸ”® Future
- [ ] Multi-tenancy support
- [ ] Advanced RBAC
- [ ] Custom model hosting
- [ ] A/B testing framework

---

**Built with â¤ï¸ by Toolkit**

*Making enterprise LLM operations simple, cost-effective, and transparent.*




