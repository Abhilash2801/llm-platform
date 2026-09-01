# PRD — LLM API Gateway

## 1. Summary
A lightweight, self-hosted LLM API Gateway: a single OpenAI-compatible endpoint that any internal team can call to reach multiple LLM providers, with reliability features (fallbacks, retries, load balancing, timeouts) and observability (usage analytics, cost tracking) built in — so product teams never talk to OpenAI/Anthropic directly.

This is a 2-day portfolio build for an AI-platform-role interview. Scope and terminology are deliberately modeled on [Portkey's open-source AI Gateway](https://github.com/Portkey-AI/gateway), a widely-used reference implementation of this exact category of product — reproducing its core reliability primitives (not its guardrails/compliance surface, which is out of scope for a 2-day build) demonstrates the builder understands the category, not just one clever demo.

## 2. Problem Statement
Every team that adds an LLM call to their product re-solves the same problems: what happens when the provider times out, rate-limits, or goes down; how to spread load across multiple keys; how to know what anything is costing. A platform team owns this once, centrally, behind one API, so product teams only write `POST /v1/chat/completions` and never think about provider failure modes.

## 3. Goals
- G1: One OpenAI-compatible endpoint (`/v1/chat/completions`) fronts multiple LLM providers.
- G2: A request that fails against its primary target automatically falls back to a secondary target, based on a configurable list of trigger conditions (e.g. specific status codes).
- G3: Failed requests are automatically retried with exponential backoff, up to a configurable max attempts.
- G4: Traffic can be distributed across multiple providers/API keys by weight (load balancing), not just primary/secondary.
- G5: Every request has a configurable timeout after which it's terminated rather than hanging.
- G6: Every request is logged with enough detail (tenant/caller, provider, tokens, latency, cost, status) to answer "who used what, how much, and how reliably" via a usage endpoint.
- G7: Reliability behavior (which fallbacks, how many retries, which weights) is driven by a **config object attached to the request or route** — not hardcoded — mirroring how Portkey's `config` object works, since config-driven reliability is the feature that most clearly signals "platform," not "app."

## 4. Non-Goals (explicitly out of scope for this build)
- The 40+ pre-built guardrails Portkey ships — instead, ship 2-3 simple guardrails (e.g. a banned-word check, a max-output-length check) to demonstrate the *pattern*, not the catalog.
- SOC2/HIPAA/GDPR/CCPA certification — document how the architecture supports compliance (no plaintext key storage, structured audit logs) without claiming certification.
- Semantic caching — simple exact-match response caching is a stretch goal only, not core scope.
- A management UI/console — a `/v1/usage` JSON endpoint is sufficient; no dashboard required.
- Multi-modal (vision/audio/image) routing — text chat completions only.
- Prompt template management / prompt playground.
- Horizontal autoscaling, multi-region, or Kubernetes deployment.

## 5. Users & Personas
- **Platform consumer (product engineer)**: calls one endpoint, gets a completion, doesn't want to know or care which provider served it or what happens on failure.
- **Platform owner (the builder, in this narrative)**: needs to configure reliability behavior per route/team and see aggregate usage/cost/error-rate.

## 6. User Stories
1. As a product engineer, I call `POST /v1/chat/completions` with OpenAI-style messages and get a completion back, regardless of which provider actually served it.
2. As a platform owner, I define a config specifying "try OpenAI gpt-4o-mini first; on a 429 or 5xx, fall back to Anthropic claude-3-5-haiku" — and the gateway honors it without any client-side change.
3. As a platform owner, I define a config that load-balances 70% of traffic to Provider A and 30% to Provider B (e.g., two OpenAI keys with different rate limits), and traffic actually splits that way.
4. As a platform owner, a request that would normally hang for 60s on a stuck provider is killed at my configured timeout (e.g. 10s) and either retried or failed fast.
5. As a platform owner, I can call `/v1/usage?caller=team-a` and see request count, token totals, cost, error rate, and average latency for that caller over a time window.
6. As a platform owner, I can attach a simple output guardrail (e.g., "reject if response contains X") and see the gateway retry or block the response accordingly.

## 7. Functional Requirements

### 7.1 Chat Completions Endpoint
- `POST /v1/chat/completions` — OpenAI-compatible request/response shape (`messages`, `model`, optional `config` override).
- Auth via `Authorization: Bearer <api_key>` resolved to a `caller_id` (stand-in for "team").

### 7.2 Reliability Config (the core feature)
A JSON config, attachable per API key (default) or per-request (override), shaped like:
```json
{
  "strategy": "fallback",
  "targets": [
    {"provider": "openai", "model": "gpt-4o-mini", "weight": 1},
    {"provider": "anthropic", "model": "claude-3-5-haiku-20241022", "weight": 1}
  ],
  "on_status_codes": [429, 500, 502, 503, 504],
  "retry": {"max_attempts": 3, "base_delay_ms": 500},
  "timeout_ms": 10000
}
```
- `strategy: "fallback"` — try targets in order, move to next on a trigger condition.
- `strategy: "loadbalance"` — distribute across targets by `weight`.
- Retries apply **within** a single target before moving on (or after, depending on config) — exponential backoff: `base_delay_ms * 2^attempt`, capped at a max delay, jittered.
- Timeout is enforced per attempt, not just per overall request.

### 7.3 Guardrails (minimal, pattern-only)
- Output guardrail interface: a pluggable check function `(response_text) -> pass/fail`.
- Ship two: banned-word/regex check, max-length check.
- Config specifies `on_fail: "retry" | "block"`.

### 7.4 Usage Analytics
- Every request logged: caller_id, provider, model, tokens_in, tokens_out, latency_ms, status, retries_used, fallback_used, cost_usd, timestamp.
- `GET /v1/usage?caller=<id>&since=<date>` returns aggregates: request count, token totals, total cost, error rate, p50/p95 latency, breakdown by provider.

### 7.5 Key/Caller Management
- Minimal: a seed script creates 2-3 demo callers with API keys and distinct default configs (e.g., team-a = fallback-only, team-b = load-balanced).

## 8. Non-Functional Requirements
- **Resilience**: a single provider outage never surfaces as a bare 500 to the caller if a fallback target is configured and healthy.
- **Configurability**: reliability behavior changes via config, not code deploys.
- **Observability**: every request traceable to a caller with full outcome detail.
- **Latency overhead**: gateway adds under 100ms beyond the underlying provider call time (excluding intentional retry delays).
- **Deployability**: fresh clone → running instance in under 15 minutes.

## 9. Success Metrics (for the demo)
- A live demo where the primary provider is deliberately broken (bad key/blocked) and the response still succeeds via fallback, visibly logged with `fallback_used: true`.
- A load-balance config where repeated calls visibly split across two targets roughly matching configured weights.
- A timeout demo where an artificially slow target is killed at the configured `timeout_ms`.
- `/v1/usage` showing accurate, differentiated numbers per caller after a scripted call sequence.

## 10. Assumptions
- OpenAI and Anthropic API keys available as secrets (two independent providers are required to demonstrate fallback/load-balancing meaningfully).
- Deployment target: Railway or Render.
- No production-scale traffic — correctness and clarity of the reliability mechanics matter far more than raw throughput for this demo.

## 11. Timeline
2 working days. See `03_IMPLEMENTATION_PLAN.md`. If time is short, cut guardrails and load-balancing before ever cutting fallback, retries, or usage analytics — those three are the non-negotiable proof points.
