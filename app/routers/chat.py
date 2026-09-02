import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import AuthContext, get_auth_context
from app.db.models import UsageLog
from app.db.session import get_db
from app.executor.strategies import execute
from app.schemas import ChatRequest, ChatResponse, ReliabilityConfig
from app.services.cost import estimate_cost_usd

router = APIRouter()


def _apply_model_override(config: ReliabilityConfig, model: str | None) -> ReliabilityConfig:
    if not model or not config.targets:
        return config
    updated = config.model_copy(deep=True)
    updated.targets[0].model = model
    return updated


@router.post("/chat/completions", response_model=ChatResponse)
async def chat_completions(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    config = payload.config or auth.default_config
    config = _apply_model_override(config, payload.model)
    messages = [m.model_dump() for m in payload.messages]

    started = time.perf_counter()
    result = await execute(messages, config)
    latency_ms = int((time.perf_counter() - started) * 1000)

    provider = result.response.provider if result.response else (result.tried[-1]["provider"] if result.tried else None)
    model_used = result.response.model if result.response else (result.tried[-1]["model"] if result.tried else None)
    tokens_in = result.response.tokens_in if result.response else 0
    tokens_out = result.response.tokens_out if result.response else 0

    if result.blocked:
        status_label = "guardrail_blocked"
    elif result.exhausted or result.response is None:
        status_label = "error"
    else:
        status_label = "success"

    db.add(
        UsageLog(
            caller_id=auth.caller.id,
            provider=provider,
            model=model_used,
            attempts=result.attempts,
            fallback_used=result.fallback_used,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            status=status_label,
            cost_usd=estimate_cost_usd(provider, model_used, tokens_in, tokens_out),
        )
    )
    db.commit()

    if result.blocked:
        raise HTTPException(status_code=422, detail={"error": "guardrail_blocked", "reason": result.block_reason})
    if result.response is None:
        raise HTTPException(
            status_code=503,
            detail={"error": "all_targets_exhausted", "tried": result.tried},
        )

    content = result.response.content
    return ChatResponse(
        id=f"chatcmpl-{uuid.uuid4().hex[:24]}",
        model=result.response.model or model_used or "",
        choices=[
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        usage={
            "prompt_tokens": tokens_in,
            "completion_tokens": tokens_out,
            "total_tokens": tokens_in + tokens_out,
        },
        provider_used=result.response.provider,
        model_used=result.response.model or model_used or "",
        attempts=result.attempts,
        fallback_used=result.fallback_used,
        content=content,
    )
