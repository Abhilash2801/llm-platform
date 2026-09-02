# LLM Gateway

One chat API for product teams. Many model vendors behind it. Failover, retries, timeouts, load balancing, and usage logs are driven by a JSON **config**, not by vendor-specific code in each app.

Callers send `Authorization: Bearer <gateway-key>` and a `messages` list. They do not need to know which vendor answered.

```
Client  -->  POST /v1/chat/completions
                auth + per-key config
                executor (fallback | loadbalance)
                provider catalog  -->  vendor A / vendor B / …
                usage_logs --> Postgres
```

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
