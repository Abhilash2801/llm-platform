#!/usr/bin/env python3
"""Create demo callers. Prints raw API keys once; they are stored hashed."""

import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth import hash_api_key
from app.db.models import ApiKey, Caller, Config
from app.db.session import Base, SessionLocal, engine

TEAM_A_CONFIG = {
    "strategy": "fallback",
    "targets": [
        {"provider": "openai", "model": "gpt-4o-mini", "weight": 1},
        {"provider": "groq", "model": "llama-3.1-8b-instant", "weight": 1},
    ],
    "on_status_codes": [429, 500, 502, 503, 504],
    "retry": {"max_attempts": 2, "base_delay_ms": 200, "max_delay_ms": 2000},
    "timeout_ms": 15000,
}

TEAM_B_CONFIG = {
    "strategy": "loadbalance",
    "targets": [
        {"provider": "openai", "model": "gpt-4o-mini", "weight": 0.7},
        {"provider": "groq", "model": "llama-3.1-8b-instant", "weight": 0.3},
    ],
    "on_status_codes": [429, 500, 502, 503, 504],
    "retry": {"max_attempts": 2, "base_delay_ms": 200, "max_delay_ms": 2000},
    "timeout_ms": 15000,
}


def upsert_caller(db, name: str, config_name: str, config_body: dict) -> str:
    caller = db.query(Caller).filter(Caller.name == name).first()
    if caller is None:
        caller = Caller(name=name)
        db.add(caller)
        db.flush()

    config = db.query(Config).filter(Config.name == config_name).first()
    if config is None:
        config = Config(name=config_name, body=config_body)
        db.add(config)
        db.flush()
    else:
        config.body = config_body

    existing_key = db.query(ApiKey).filter(ApiKey.caller_id == caller.id).first()
    if existing_key is not None:
        existing_key.default_config_id = config.id
        return f"(existing key for {name} — not re-printed)"

    raw_key = f"gw_{name.replace('-', '_')}_{secrets.token_urlsafe(24)}"
    db.add(
        ApiKey(
            caller_id=caller.id,
            key_hash=hash_api_key(raw_key),
            default_config_id=config.id,
        )
    )
    return raw_key


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        team_a_key = upsert_caller(db, "team-a", "team-a-default", TEAM_A_CONFIG)
        team_b_key = upsert_caller(db, "team-b", "team-b-default", TEAM_B_CONFIG)
        db.commit()
    finally:
        db.close()

    print("Demo callers seeded.")
    print(f"TEAM_A_KEY={team_a_key}")
    print(f"TEAM_B_KEY={team_b_key}")
    print("Save these keys. They are stored hashed and will not be shown again unless you reseed with a fresh DB.")


if __name__ == "__main__":
    main()
