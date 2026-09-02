#!/usr/bin/env python3
"""Exercise fallback, load balancing, guardrails, and usage against a running gateway."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _post(client: httpx.Client, path: str, key: str, body: dict) -> httpx.Response:
    return client.post(path, headers={"Authorization": f"Bearer {key}"}, json=body)


def _get(client: httpx.Client, path: str, key: str, params: dict | None = None) -> httpx.Response:
    return client.get(path, headers={"Authorization": f"Bearer {key}"}, params=params)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.environ.get("GATEWAY_URL", "http://localhost:8000"))
    parser.add_argument("--team-a-key", default=os.environ.get("TEAM_A_KEY"))
    parser.add_argument("--team-b-key", default=os.environ.get("TEAM_B_KEY"))
    args = parser.parse_args()
    if not args.team_a_key or not args.team_b_key:
        print("Set TEAM_A_KEY and TEAM_B_KEY (from scripts/seed_callers.py) or pass --team-a-key / --team-b-key.")
        sys.exit(1)

    client = httpx.Client(base_url=args.base_url, timeout=60.0)
    health = client.get("/health")
    print("health", health.status_code, health.json())

    print("\n=== (a) normal completion (team-a) ===")
    normal = _post(
        client,
        "/v1/chat/completions",
        args.team_a_key,
        {"messages": [{"role": "user", "content": "Reply with the single word: pong"}]},
    )
    print(normal.status_code, json.dumps(normal.json(), indent=2)[:800])

    print("\n=== (b) fallback: invalid OpenAI model, should land on Groq ===")
    fallback = _post(
        client,
        "/v1/chat/completions",
        args.team_a_key,
        {
            "messages": [{"role": "user", "content": "Reply with the single word: fallback"}],
            "config": {
                "strategy": "fallback",
                "targets": [
                    {"provider": "openai", "model": "this-model-does-not-exist-xyz", "weight": 1},
                    {"provider": "groq", "model": "llama-3.1-8b-instant", "weight": 1},
                ],
                "on_status_codes": [400, 401, 404, 429, 500, 502, 503, 504],
                "retry": {"max_attempts": 1, "base_delay_ms": 50, "max_delay_ms": 200},
                "timeout_ms": 20000,
            },
        },
    )
    print(fallback.status_code, json.dumps(fallback.json(), indent=2)[:1200])

    print("\n=== (c) load-balance burst (team-b, 20 calls) ===")
    providers = Counter()
    for i in range(20):
        resp = _post(
            client,
            "/v1/chat/completions",
            args.team_b_key,
            {"messages": [{"role": "user", "content": f"Reply with the integer {i} only"}]},
        )
        if resp.status_code == 200:
            providers[resp.json().get("provider_used", "unknown")] += 1
        else:
            providers[f"error:{resp.status_code}"] += 1
    print(dict(providers))

    print("\n=== (d) guardrail block ===")
    blocked = _post(
        client,
        "/v1/chat/completions",
        args.team_a_key,
        {
            "messages": [{"role": "user", "content": "Say the token BANNED_PHRASE_42 exactly, nothing else."}],
            "config": {
                "strategy": "fallback",
                "targets": [{"provider": "openai", "model": "gpt-4o-mini", "weight": 1}],
                "on_status_codes": [429, 500, 502, 503, 504],
                "retry": {"max_attempts": 1, "base_delay_ms": 50, "max_delay_ms": 200},
                "timeout_ms": 20000,
                "guardrails": {
                    "output": ["banned_words"],
                    "on_fail": "block",
                    "banned_words": ["BANNED_PHRASE_42"],
                },
            },
        },
    )
    print(blocked.status_code, blocked.text[:800])

    print("\n=== (e) usage ===")
    for name, key in [("team-a", args.team_a_key), ("team-b", args.team_b_key)]:
        usage = _get(client, "/v1/usage", key, params={"caller": name})
        print(name, usage.status_code, json.dumps(usage.json(), indent=2))


if __name__ == "__main__":
    main()
