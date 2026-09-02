import hashlib
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.models import ApiKey, Caller, Config
from app.db.session import get_db
from app.schemas import ReliabilityConfig, default_reliability_config

bearer_scheme = HTTPBearer(auto_error=False)


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


@dataclass
class AuthContext:
    caller: Caller
    api_key: ApiKey
    default_config: ReliabilityConfig


def resolve_config_body(body: dict | None) -> ReliabilityConfig:
    if not body:
        return default_reliability_config()
    return ReliabilityConfig.model_validate(body)


def get_auth_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> AuthContext:
    if credentials is None or credentials.scheme.lower() != "bearer" or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key")

    key_hash = hash_api_key(credentials.credentials)
    api_key = db.query(ApiKey).filter(ApiKey.key_hash == key_hash).first()
    if api_key is None or api_key.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    caller = db.get(Caller, api_key.caller_id)
    if caller is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown caller")

    default_config = default_reliability_config()
    if api_key.default_config_id:
        stored = db.get(Config, api_key.default_config_id)
        if stored is not None:
            default_config = resolve_config_body(stored.body)

    return AuthContext(caller=caller, api_key=api_key, default_config=default_config)
