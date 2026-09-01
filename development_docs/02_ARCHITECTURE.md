# Engineering Architecture — LLM API Gateway

## 1. System Overview

```
                     ┌───────────────────────────────────────┐
                     │              Clients                    │
                     │   (Team A service, Team B service,       │
                     │    curl / demo scripts)                  │
                     └────────────────┬──────────────────────────┘
                                       │ Authorization: Bearer <api_key>
                                       ▼
                     ┌───────────────────────────────────────┐
                     │        API Gateway (FastAPI)             │
                     │  ┌──────────────┐  ┌──────────────────┐ │
                     │  │ Auth/Caller   │  │ Config Resolver   │ │
                     │  │ Resolver      │  │ (per-key default   │ │
                     │  │               │  │  or per-request)   │ │
                     │  └──────────────┘  └──────────────────┘ │
                     └───┬───────────────────────┬───────────────┘
                         │                       │
             ┌───────────▼──────────┐  ┌─────────▼───────────┐
             │   Request Executor     │  │  Guardrail Engine     │
             │  - strategy dispatch    │  │  (pre/post checks)    │
             │  - retry w/ backoff     │  └────────────────────────┘
             │  - per-attempt timeout  │
             └───┬──────────┬─────────┘
                 │          │
          ┌──────▼───┐ ┌────▼───────┐
          │ OpenAI    │ │ Anthropic   │   ...additional provider adapters
          │ adapter   │ │ adapter     │   behind a common interface
          └───────────┘ └─────────────┘
                 │
        ┌────────▼─────────┐
        │ Usage Logger       │───────► Postgres (usage_logs)
        │ (sync, per request)│
        └────────────────────┘
```

## 2. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| API framework | FastAPI (Python) | async-native; needed for concurrent provider calls with timeouts |
| LLM providers | OpenAI (primary target family), Anthropic (secondary) | two independent providers required to prove fallback/load-balance |
| Relational store | PostgreSQL | callers, api_keys, configs, usage_logs |
| Containerization | Docker + docker-compose | local/deploy parity |
| Deployment | Railway or Render | fastest path to a public HTTPS URL |

Note: no vector store or embedding model in this build — RAG was deliberately cut from scope to keep the gateway's reliability mechanics the centerpiece.

## 3. Provider Adapter Interface

Every provider is wrapped behind a common Python interface so the executor never branches on provider-specific SDK quirks:

```python
class ProviderAdapter(Protocol):
    async def chat(self, messages: list[dict], model: str, timeout_s: float) -> ProviderResponse: ...

class ProviderResponse(BaseModel):
    content: str
    tokens_in: int
    tokens_out: int
    raw_status: int | None  # underlying HTTP status if available, for trigger matching
```
`OpenAIAdapter` and `AnthropicAdapter` implement this; adding a third provider later means writing one adapter, not touching the executor.

## 4. Config Object (core abstraction)

Resolved per request as: **per-request `config` field in the body** (if present) → else the caller's **default config** stored on their `api_keys`/`callers` row → else a **global default** (single target, no fallback).

```json
{
  "strategy": "fallback",           // "fallback" | "loadbalance"
  "targets": [
    {"provider": "openai", "model": "gpt-4o-mini", "weight": 1},
    {"provider": "anthropic", "model": "claude-3-5-haiku-20241022", "weight": 1}
  ],
  "on_status_codes": [429, 500, 502, 503, 504],
  "retry": {"max_attempts": 3, "base_delay_ms": 500, "max_delay_ms": 8000},
  "timeout_ms": 10000,
  "guardrails": {"output": ["banned_words", "max_length"], "on_fail": "retry"}
}
```

Stored as JSONB in Postgres (`configs` table) so it's editable without a code deploy — this is the detail that makes the project "a platform," not "a script."

## 5. Execution Logic (Request Executor)

**Fallback strategy:**
1. Take `targets` in list order. For target[0]: attempt up to `retry.max_attempts`, with exponential backoff (`base_delay_ms * 2^attempt`, capped at `max_delay_ms`, ±jitter), each attempt bounded by `timeout_ms`.
2. If all attempts on target[0] end in a status in `on_status_codes` (or a timeout), move to target[1] and repeat.
3. If all targets exhaust → return `503` with a structured error body listing what was tried.
4. Every attempt (success or fail) is logged; the final response includes `provider_used`, `attempts`, `fallback_used`.

**Load-balance strategy:**
1. Pick a target using weighted random selection based on `weight`.
2. Apply the same retry/timeout logic to the chosen target only (no automatic fallback to other targets unless explicitly also configured as `strategy: "loadbalance_with_fallback"` — documented as a stretch goal, not core scope, to avoid over-engineering the strategy matrix in 2 days).

**Guardrail check (post-response, both strategies):**
- Run configured checks against the response content.
- On fail with `on_fail: "retry"` → treat as a failure for retry/fallback purposes (bounded by the same `max_attempts`).
- On fail with `on_fail: "block"` → return a `422` to the caller instead of the model's output.

## 6. Data Model (PostgreSQL)

### `callers`
| column | type | notes |
|---|---|---|
| id | uuid, PK | |
| name | text | e.g. "team-a" |
| created_at | timestamptz | |

### `api_keys`
| column | type | notes |
|---|---|---|
| id | uuid, PK | |
| caller_id | uuid, FK → callers.id | |
| key_hash | text | hashed, never stored raw |
| default_config_id | uuid, FK → configs.id, nullable | |
| revoked_at | timestamptz, nullable | |

### `configs`
| column | type | notes |
|---|---|---|
| id | uuid, PK | |
| name | text | human label, e.g. "team-a-default" |
| body | jsonb | the config object from §4 |
| created_at | timestamptz | |

### `usage_logs`
| column | type | notes |
|---|---|---|
| id | bigserial, PK | |
| caller_id | uuid, FK → callers.id | |
| provider | text | which target actually served the request |
| model | text | |
| attempts | int | total attempts across all targets |
| fallback_used | boolean | |
| tokens_in | int | |
| tokens_out | int | |
| latency_ms | int | end-to-end, including retries |
| status | text | `success`, `error`, `guardrail_blocked` |
| cost_usd | numeric(10,6) | computed from a static per-provider rate table |
| created_at | timestamptz | |

## 7. API Contracts

### `POST /v1/chat/completions`
Request:
```json
{
  "messages": [{"role": "user", "content": "string"}],
  "model": "optional override of the first target's model",
  "config": "optional full config object override, per §4"
}
```
Response:
```json
{
  "content": "string",
  "provider_used": "openai | anthropic",
  "model_used": "string",
  "tokens_in": 0,
  "tokens_out": 0,
  "attempts": 1,
  "fallback_used": false
}
```
Errors: `401` invalid/missing key, `422` guardrail-blocked, `503` all targets exhausted.

### `GET /v1/usage?since=ISO8601`
Response:
```json
{
  "caller": "team-a",
  "request_count": 0,
  "tokens_in": 0,
  "tokens_out": 0,
  "estimated_cost_usd": 0.0,
  "error_rate": 0.0,
  "fallback_rate": 0.0,
  "avg_latency_ms": 0,
  "p95_latency_ms": 0,
  "by_provider": {"openai": 0, "anthropic": 0}
}
```

## 8. Repository Structure
```
llm-gateway/
├── app/
│   ├── main.py
│   ├── auth.py                 # API key → caller_id + default config resolution
│   ├── routers/
│   │   ├── chat.py
│   │   └── usage.py
│   ├── executor/
│   │   ├── strategies.py       # fallback / loadbalance dispatch
│   │   ├── retry.py            # backoff + jitter logic
│   │   └── guardrails.py       # pluggable check functions
│   ├── providers/
│   │   ├── base.py             # ProviderAdapter protocol
│   │   ├── openai_adapter.py
│   │   └── anthropic_adapter.py
│   ├── services/
│   │   └── cost.py
│   ├── db/
│   │   ├── models.py
│   │   └── session.py
│   └── config.py               # app-level settings, not to be confused with the request config object
├── scripts/
│   ├── seed_callers.py
│   └── demo.py
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── requirements.txt
└── README.md
```

## 9. Security Notes
- API keys stored as hashes only; never logged in plaintext, never returned after initial creation.
- Provider API keys (OpenAI/Anthropic) live only in environment secrets, never in the `configs` table or logs.
- No PII redaction or compliance certification claimed — documented explicitly as a known gap relative to Portkey's enterprise tier, not silently omitted.
