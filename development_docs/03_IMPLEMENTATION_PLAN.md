# Implementation Plan — Execution Checklist

For a coding agent to execute sequentially. Each phase has concrete tasks and an acceptance check. Do not proceed until the current phase's check passes.

## Phase 0 — Scaffolding (30 min)
- [ ] Create repo structure per `02_ARCHITECTURE.md` §8.
- [ ] `requirements.txt`: fastapi, uvicorn, sqlalchemy, psycopg2-binary, alembic, openai, anthropic, pydantic-settings, python-dotenv, httpx, pytest, pytest-asyncio.
- [ ] `docker-compose.yml`: `app` + `postgres` services only (no vector store needed).
- [ ] `.env.example`: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `DATABASE_URL`.
- **Acceptance**: `docker-compose up --build` starts cleanly; root/health endpoint returns 200.

## Phase 1 — Data layer (45 min)
- [ ] SQLAlchemy models for `callers`, `api_keys`, `configs`, `usage_logs` per architecture §6.
- [ ] Alembic migration.
- [ ] `scripts/seed_callers.py`: creates `team-a` (fallback config: OpenAI→Anthropic) and `team-b` (loadbalance config: two configs/weights across providers), prints raw API keys once.
- **Acceptance**: seeding is idempotent; two distinct keys printed; each caller's `configs.body` is valid JSON matching the schema in architecture §4.

## Phase 2 — Provider adapters (1 hr)
- [ ] `app/providers/base.py`: `ProviderAdapter` protocol + `ProviderResponse` model.
- [ ] `openai_adapter.py`, `anthropic_adapter.py`: implement `.chat()`, normalize errors so HTTP status / timeout / rate-limit are all surfaced consistently to the executor (this normalization is what makes fallback logic provider-agnostic).
- **Acceptance**: a standalone script can call each adapter directly and get a normalized `ProviderResponse` back from both providers.

## Phase 3 — Auth + config resolution (45 min)
- [ ] `app/auth.py`: dependency resolving `Authorization: Bearer <key>` → `caller_id` + the caller's default `configs.body`, raising `401` on invalid/revoked key.
- [ ] Request-level config override: if the request body includes a `config` object, it takes precedence over the caller's default for that call only (not persisted).
- **Acceptance**: valid key resolves the right default config; invalid key → 401; a request with an inline `config` override visibly uses different targets than the caller's stored default.

## Phase 4 — Retry + backoff (1 hr)
- [ ] `app/executor/retry.py`: exponential backoff with jitter per architecture §5, bounded by `retry.max_attempts` and per-attempt `timeout_ms`.
- [ ] Unit test: mock a target that fails twice then succeeds — assert it took exactly 3 attempts with delays following the backoff formula (allow timing tolerance).
- **Acceptance**: retry test passes deterministically (mock the sleep, don't actually wait in tests).

## Phase 5 — Fallback strategy (1.5 hrs)
- [ ] `app/executor/strategies.py`: `run_fallback(targets, config)` — tries target[0] with retries, moves to target[1] on exhaustion, etc., per architecture §5.
- [ ] Integration test: force target[0] (e.g., via an invalid OpenAI key in test env) to fail, assert the response comes from target[1] with `fallback_used=true`.
- [ ] Wire into `POST /v1/chat/completions`.
- **Acceptance**: the fallback integration test passes against real provider APIs (not mocked) — this is the single most important proof point in the whole project; do not settle for a mocked-only version.

## Phase 6 — Load balancing (1 hr)
- [ ] `run_loadbalance(targets, config)` — weighted random target selection, same retry/timeout logic applied to the chosen target.
- [ ] Test: run 200 simulated calls with weights [0.7, 0.3], assert the observed split is within a reasonable tolerance (e.g., ±10%) of the configured weights.
- **Acceptance**: distribution test passes; `/v1/chat/completions` honors `strategy: "loadbalance"` configs.

## Phase 7 — Guardrails (45 min)
- [ ] `app/executor/guardrails.py`: `banned_words_check`, `max_length_check`, both `(text) -> bool`.
- [ ] Wire guardrail evaluation into the executor per architecture §5 (`on_fail: retry | block`).
- **Acceptance**: a request engineered to trigger the banned-word guardrail with `on_fail: "block"` returns `422`; with `on_fail: "retry"` it retries and (if the retry also fails the check) eventually returns the block response.

## Phase 8 — Usage analytics (1 hr)
- [ ] `app/services/cost.py`: static $/1K-token table per provider/model.
- [ ] Log every attempt (not just the final outcome) to `usage_logs`, with `attempts` and `fallback_used` reflecting the whole request lifecycle on the final row.
- [ ] `GET /v1/usage`: aggregate per caller per architecture §7.
- **Acceptance**: after a scripted mixed sequence of calls for team-a and team-b, `/v1/usage` shows correct, differentiated numbers including a non-zero `fallback_rate` for whichever caller's demo run triggered a fallback.

## Phase 9 — Deploy (1 hr)
- See `04_DEPLOYMENT.md`.
- **Acceptance**: the demo script (Phase 10) runs successfully against the deployed URL.

## Phase 10 — Demo script + README (1 hr)
- [ ] `scripts/demo.py`: seeds callers if needed, then (a) makes a normal `/v1/chat/completions` call, (b) deliberately breaks the primary target (e.g., temporarily swaps in a bad key or points at an invalid model) to trigger and print a visible fallback, (c) fires a burst of load-balanced calls and prints the observed provider split, (d) fires a call engineered to trip a guardrail, (e) prints `/v1/usage` for both callers.
- [ ] `README.md`: pitch, architecture diagram (from `02_ARCHITECTURE.md` §1), setup steps, and the demo script's expected output.
- **Acceptance**: a stranger can clone, follow the README, and reproduce the full demo unaided.

## Explicit Cut List (if time runs short)
Cut in this order, stopping as soon as the timeline recovers:
1. Guardrails (Phase 7) — document as a stretch goal, keep the pluggable interface stubbed.
2. Load balancing (Phase 6) — fallback alone still satisfies the PRD's core reliability story.
3. Cost table granularity — flat per-provider rate instead of per-model if time-pressed.

Never cut: fallback (Phase 5), retry/backoff (Phase 4), or usage analytics (Phase 8) — these three are the entire point of the project.
