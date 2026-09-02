# LLM Gateway

One chat API for product teams. Many model vendors behind it. Reliability, guardrails, and usage are driven by a JSON **config**, not by vendor-specific code in each app.

Callers send `Authorization: Bearer <gateway-key>` and a `messages` list. They do not need to know which vendor answered.

## Features

| Feature | What it does |
|---|---|
| Multi-vendor routing | One `POST /v1/chat/completions` in front of a provider catalog (Groq, xAI/Grok, OpenAI, Anthropic, Mistral, …). |
| Fallback | Try target A; on timeout / 429 / 5xx (configurable), try target B. |
| Retries | Exponential backoff with jitter, per target, up to `max_attempts`. |
| Timeouts | Each attempt is killed after `timeout_ms` so a hung vendor cannot hang the caller. |
| Load balancing | Weighted random split across targets (`strategy: "loadbalance"`). |
| Output guardrails | Banned-word check and max-length check on the model reply. `on_fail`: `block` (HTTP 422) or `retry`. |
| Auth / callers | Gateway API keys, stored hashed, mapped to a caller (e.g. team-a / team-b) and a default config. |
| Usage analytics | `GET /v1/usage` — request count, tokens, estimated cost, error rate, fallback rate, latency p50/p95, breakdown by vendor. |
| Provider catalog | `GET /v1/providers` — ids, env var names, example models, `configured: true/false` (never the secret). |

```
Client  -->  POST /v1/chat/completions
                auth + per-key config
                executor (fallback | loadbalance | retry | timeout)
                output guardrails
                provider catalog  -->  vendor A / vendor B / …
                usage_logs --> Postgres
```

## HTTP API

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/health` | no | liveness |
| GET | `/docs` | no | OpenAPI UI |
| GET | `/v1/providers` | no | vendor catalog |
| POST | `/v1/chat/completions` | Bearer gateway key | chat |
| GET | `/v1/usage` | Bearer gateway key | usage aggregates |

Errors: `401` bad/missing key, `422` guardrail blocked, `503` all targets exhausted.

## Output guardrails

Implemented in `app/executor/guardrails.py`. They run on the **model output** after a successful vendor call.

| Check | Config | Behavior |
|---|---|---|
| `banned_words` | `banned_words`: list of strings (default demo token `BANNED_PHRASE_42`) | Fail if the reply contains a listed phrase |
| `max_length` | `max_length`: character cap (default 4000) | Fail if the reply is too long |

`on_fail`:

- `"block"` — return **422** to the caller (`guardrail_blocked`). Do not send the model text.
- `"retry"` — treat it like a failed attempt (retry the same target, then fallback if the strategy allows).

Enable them on the request or on the caller’s stored config:

```json
"guardrails": {
  "output": ["banned_words", "max_length"],
  "on_fail": "block",
  "banned_words": ["BANNED_PHRASE_42"],
  "max_length": 4000
}
```

`scripts/demo.py` includes a guardrail case: a prompt that forces `BANNED_PHRASE_42` should return 422.

## Add a vendor

**1. Built-in (set a key, then use the id in config)**

`GET /v1/providers` lists every built-in id, env var name, example model, and whether a key is present (`configured`, never the secret).

| id | Env var | Protocol |
|---|---|---|
| anthropic | `ANTHROPIC_API_KEY` | Anthropic Messages |
| deepseek | `DEEPSEEK_API_KEY` | chat completions |
| fireworks | `FIREWORKS_API_KEY` | chat completions |
| google / gemini | `GOOGLE_API_KEY` | chat completions |
| groq | `GROQ_API_KEY` | chat completions |
| mistral | `MISTRAL_API_KEY` | chat completions |
| ollama | `OLLAMA_API_KEY` (optional) | chat completions (local) |
| openai | `OPENAI_API_KEY` | chat completions |
| openrouter | `OPENROUTER_API_KEY` | chat completions |
| perplexity | `PERPLEXITY_API_KEY` | chat completions |
| together | `TOGETHER_API_KEY` | chat completions |
| xai / grok | `XAI_API_KEY` | chat completions (xAI Grok, not Groq) |

Fill any of those in `.env`. Leave the rest empty.

**2. Vendor not in the table**

If they speak the common `{model, messages}` chat-completions HTTP API:

```bash
EXTRA_PROVIDERS_JSON={"myvendor":{"base_url":"https://api.example.com/v1","api_key_env":"MYVENDOR_API_KEY","example_model":"their-model"}}
MYVENDOR_API_KEY=...
```

Use `"provider": "myvendor"` in `config.targets`. Do not put secrets inside the JSON.

**3. Completely different HTTP API**

Add a small adapter class (see `app/providers/anthropic_adapter.py`) and a `protocol` row in `app/providers/catalog.py`. The executor does not change.

## Reliability config

Attach as the caller’s default (seed) or as `config` on one request. Provider ids are catalog ids, not hardcoded vendors.

```json
{
  "strategy": "fallback",
  "targets": [
    {"provider": "groq", "model": "llama-3.1-8b-instant", "weight": 1},
    {"provider": "xai", "model": "grok-2-latest", "weight": 1}
  ],
  "on_status_codes": [429, 500, 502, 503, 504],
  "retry": {"max_attempts": 3, "base_delay_ms": 500, "max_delay_ms": 8000},
  "timeout_ms": 10000,
  "guardrails": {"output": ["banned_words", "max_length"], "on_fail": "block"}
}
```

`strategy: "loadbalance"` picks a target by `weight` and retries that target only.

The `guardrails` object is optional. If omitted, replies are not scanned.

## Quick start

```bash
cp .env.example .env          # set keys for the vendors you actually have
docker compose up --build
python scripts/seed_callers.py
export TEAM_A_KEY=...         # printed once
export TEAM_B_KEY=...
python scripts/demo.py
```

Optional: pin which two vendors seed/demo use:

```bash
GATEWAY_PRIMARY_PROVIDER=groq
GATEWAY_PRIMARY_MODEL=llama-3.1-8b-instant
GATEWAY_SECONDARY_PROVIDER=openai
GATEWAY_SECONDARY_MODEL=gpt-4o-mini
```

If those are empty, seed uses the first two vendors that have keys set.

App only (Postgres via Compose):

```bash
docker compose up -d postgres
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

OpenAPI: `http://localhost:8000/docs`  
Catalog: `http://localhost:8000/v1/providers`

## Demo callers

| Caller | Default |
|---|---|
| team-a | fallback: primary vendor → secondary vendor |
| team-b | load-balance 70% / 30% across the same pair |

## Tests

```bash
pytest tests/test_retry.py tests/test_guardrails.py tests/test_loadbalance.py tests/test_fallback.py tests/test_catalog.py
```

## Notes

- Gateway keys are hashed. Vendor keys stay in env / secret store, never in git.
- Public chat path is `POST /v1/chat/completions` so existing client SDKs keep working; backends are not limited to one company.
- Quotas, hard tenancy, and distributed tracing are not in this build.
