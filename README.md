<<<<<<< HEAD
# llm-platform
=======
# LLM API Gateway

OpenAI-compatible `POST /v1/chat/completions` in front of multiple LLM vendors. Live demo path is **OpenAI** and **Groq**. Any other OpenAI-compatible HTTP API (xAI Grok, Together, Fireworks, …) can be registered without changing executor code.

Reliability behavior lives in a JSON **config** (per API key, or overridden on the request). Product callers only send `Authorization: Bearer <gateway-key>` and an OpenAI-style `messages` array.

This is a portfolio-scale slice of the same category as [Portkey's AI Gateway](https://github.com/Portkey-AI/gateway): the reliability primitives, not the full guardrail catalog.

## Architecture

```
Client  --Bearer key-->  FastAPI gateway
                           auth + config resolver
                           executor (fallback | loadbalance, retry, timeout)
                           provider catalog (OpenAI-compatible HTTP)
                           usage_logs --> Postgres
```

## Quick start

```bash
cp .env.example .env   # set OPENAI_API_KEY and GROQ_API_KEY
docker compose up --build
python scripts/seed_callers.py
# copy TEAM_A_KEY and TEAM_B_KEY from the seed output
export TEAM_A_KEY=...
export TEAM_B_KEY=...
python scripts/demo.py
```

Without Docker for the app (Postgres still via Compose):

```bash
docker compose up -d postgres
# use any Python 3.12+ env that has the packages in requirements.txt
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

OpenAPI UI: `http://localhost:8000/docs`

## Config object

Attach as the caller's default (seeded) or as `config` on the request body:

```json
{
  "strategy": "fallback",
  "targets": [
    {"provider": "openai", "model": "gpt-4o-mini", "weight": 1},
    {"provider": "groq", "model": "llama-3.1-8b-instant", "weight": 1}
  ],
  "on_status_codes": [429, 500, 502, 503, 504],
  "retry": {"max_attempts": 3, "base_delay_ms": 500, "max_delay_ms": 8000},
  "timeout_ms": 10000,
  "guardrails": {"output": ["banned_words", "max_length"], "on_fail": "block"}
}
```

`strategy: "loadbalance"` picks a target by `weight` and retries that target only.

## Demo callers

| Caller | Default behavior |
|---|---|
| team-a | Fallback OpenAI `gpt-4o-mini` → Groq `llama-3.1-8b-instant` |
| team-b | Load-balance 70% OpenAI / 30% Groq |

## Adding another provider

If the vendor speaks OpenAI's `/v1/chat/completions` API, register it. Built-ins: `openai`, `groq`, `xai` (alias `grok`). Extra vendors via env (keys stay in env vars, not in the JSON):

```bash
EXTRA_PROVIDERS_JSON='{"together":{"base_url":"https://api.together.xyz/v1","api_key_env":"TOGETHER_API_KEY"}}'
```

Then use `"provider": "together"` in a target. Native (non-OpenAI) APIs still need a small adapter class.

## Tests

```bash
pytest tests/test_retry.py tests/test_guardrails.py tests/test_loadbalance.py tests/test_fallback.py
pytest tests/test_fallback_integration.py   # needs live keys
```

## Notes

- Gateway API keys are stored as SHA-256 hashes. Provider keys stay in environment variables and are never committed.
- Live testing in this workspace uses OpenAI + Groq. xAI Grok is wired as `xai` / `grok` when `XAI_API_KEY` is set.
- Semantic cache, a management UI, quotas, and distributed tracing are out of scope for this build.
>>>>>>> Add OpenAI-compatible LLM gateway with Docker.
