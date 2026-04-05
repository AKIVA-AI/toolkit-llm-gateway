# Model Provenance Registry

**System:** toolkit-llm-gateway
**Standard:** AI Service Standard v1.5 Section 10

This registry tracks the LLM models routed through the gateway. As a proxy/gateway, toolkit-llm-gateway does not train or host models — it routes requests to external providers. Provenance information is inherited from upstream providers.

## Model Tiers (per LLM Gateway Standard v1.2)

| Tier | Purpose | Example Models |
|------|---------|----------------|
| flagship | Complex reasoning, planning, code generation | claude-opus-4-6, gpt-4.1, gemini-2.5-pro |
| standard | General-purpose, balanced cost/quality | claude-sonnet-4-6, gpt-4.1-mini |
| fast | Low-latency, simple tasks | claude-haiku-4-5, gpt-4.1-nano |
| local | On-premises inference | llama-3, mistral, qwen |
| tiny | Classification, extraction, routing | gpt-4.1-nano, gemini-2.0-flash-lite |

## Provider Landscape

| Provider | Models Available | Streaming | Cost Tracking |
|----------|-----------------|-----------|---------------|
| OpenAI | GPT-4.1, GPT-4.1-mini, GPT-4.1-nano | Yes | Yes |
| Anthropic | Claude Opus 4.6, Sonnet 4.6, Haiku 4.5 | Yes | Yes |
| Google | Gemini 2.5 Pro, 2.0 Flash | Yes | Yes |
| Azure OpenAI | GPT-4.1, GPT-4.1-mini (hosted) | Yes | Yes |
| AWS Bedrock | Claude, Llama, Titan | Yes | Yes |
| Groq | Llama 3, Mixtral (fast inference) | Yes | Yes |
| Together AI | Open-weight models (hosted) | Yes | Yes |

## Provenance Fields (per AI Service Standard v1.5 s10)

Each model routed through the gateway has the following provenance tracked:

| Field | Source | Tracked |
|-------|--------|---------|
| model_id | LiteLLM model identifier | Yes (per-request in LLMRequest table) |
| model_provider | Provider name (openai, anthropic, etc.) | Yes (per-request) |
| model_version | Provider-reported version | Partial (when available in response headers) |
| deployment_type | cloud / on-premises / hybrid | Configuration-level |
| cost_per_token | Input/output token pricing | Yes (via LiteLLM cost calculation) |
| capabilities_declared | Text, code, vision, function calling | Configuration-level |
| limitations_documented | Context window, rate limits | Configuration-level |

## Change Log

| Date | Change | Impact |
|------|--------|--------|
| 2026-01-10 | Initial registry with v1.0 launch | Baseline |
| 2026-04-04 | Updated to v2.14 standards, added tier naming | Standards compliance |

## Governance

- Model additions: add to this registry before configuring in gateway
- Model removals: mark as deprecated, maintain for 30 days, then remove
- Provider changes: update this registry and test fallback chains
- Cost changes: verify cost tracking accuracy after provider pricing updates
