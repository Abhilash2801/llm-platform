# Deployment Guide

## 1. Target Platform
**Railway** (Docker deploy + managed Postgres in one click, fast public HTTPS URL). Render is an equally valid fallback.

## 2. Prerequisites
- GitHub repo pushed with the structure from `02_ARCHITECTURE.md` §8.
- Accounts: Railway (or Render), OpenAI API key, Anthropic API key.

## 3. Local Verification (before deploying)
```bash
cp .env.example .env   # fill in real provider keys
docker-compose up --build
python scripts/seed_callers.py
python scripts/demo.py   # against http://localhost:8000
```
Do not deploy until the local demo script passes cleanly, including the fallback and load-balance sections.

## 4. Provisioning
1. **Postgres**: Railway → Add Service → Database → PostgreSQL. Copy the generated `DATABASE_URL`.
2. No other external services required — this build has no vector store or third-party observability dependency by design, which also makes deployment meaningfully faster than a RAG-inclusive version.

## 5. Deploy Steps (Railway)
1. New Project → Deploy from GitHub repo.
2. Set environment variables: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `DATABASE_URL`.
3. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
4. Run the Alembic migration as a one-off job (`railway run alembic upgrade head`).
5. Run `railway run python scripts/seed_callers.py` once — save the printed API keys; they're shown only this one time.
6. Deploy, note the public URL.

## 6. Post-Deploy Smoke Test
```bash
curl https://<your-app>.up.railway.app/health
python scripts/demo.py --base-url https://<your-app>.up.railway.app
```
Confirm:
- [ ] A normal `/v1/chat/completions` call succeeds.
- [ ] Temporarily breaking the primary target (invalid key or bogus model name via env var) produces a visible `fallback_used=true` response on the next call, then restore normal config.
- [ ] A burst of load-balanced calls shows a provider split roughly matching configured weights.
- [ ] A guardrail-tripping call returns `422` as configured.
- [ ] `/v1/usage` shows distinct, non-zero numbers for both demo callers.

## 7. What to Show in the Interview
- Open `/docs` (FastAPI's auto-generated OpenAPI UI) live on the deployed URL — signals "real API," not a notebook.
- Live-trigger the fallback: temporarily set an invalid `OPENAI_API_KEY` in Railway's env vars, make a call, show the Anthropic fallback firing with `fallback_used: true` in the response, then restore the key. This single moment is the strongest demo beat in the whole project.
- Screen-share the config object from `02_ARCHITECTURE.md` §4 while narrating why reliability-as-config (not reliability-as-code) is the platform-engineering insight the whole build is built around — this is the same pattern Portkey's own gateway uses, which is a good thing to say explicitly if asked about prior art.

## 8. Rollback / Troubleshooting Notes
- If Railway's free tier sleeps the app between attempts, send a warm-up curl a minute before the interview.
- If both provider keys are temporarily rate-limited during rehearsal, the demo script's fallback/load-balance sections can run against a local mock provider adapter — keep one behind a feature flag as a rehearsal safety net, but never demo the mock live; always demo against real providers in the interview itself.
