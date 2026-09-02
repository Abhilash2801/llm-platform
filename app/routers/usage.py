from datetime import datetime
from statistics import mean

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import AuthContext, get_auth_context
from app.db.models import Caller, UsageLog
from app.db.session import get_db
from app.schemas import UsageResponse

router = APIRouter()


def _percentile(values: list[int], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(round((pct / 100.0) * (len(ordered) - 1)))
    return float(ordered[index])


@router.get("/usage", response_model=UsageResponse)
def get_usage(
    caller: str | None = Query(default=None),
    since: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
    auth: AuthContext = Depends(get_auth_context),
):
    target_name = caller or auth.caller.name
    row = db.query(Caller).filter(Caller.name == target_name).first()
    if row is None:
        return UsageResponse(
            caller=target_name,
            request_count=0,
            tokens_in=0,
            tokens_out=0,
            estimated_cost_usd=0.0,
            error_rate=0.0,
            fallback_rate=0.0,
            avg_latency_ms=0.0,
            p50_latency_ms=0.0,
            p95_latency_ms=0.0,
            by_provider={},
        )

    q = db.query(UsageLog).filter(UsageLog.caller_id == row.id)
    if since is not None:
        q = q.filter(UsageLog.created_at >= since)
    logs = q.all()
    count = len(logs)
    if count == 0:
        return UsageResponse(
            caller=target_name,
            request_count=0,
            tokens_in=0,
            tokens_out=0,
            estimated_cost_usd=0.0,
            error_rate=0.0,
            fallback_rate=0.0,
            avg_latency_ms=0.0,
            p50_latency_ms=0.0,
            p95_latency_ms=0.0,
            by_provider={},
        )

    errors = sum(1 for log in logs if log.status != "success")
    fallbacks = sum(1 for log in logs if log.fallback_used)
    latencies = [int(log.latency_ms) for log in logs]
    by_provider: dict[str, int] = {}
    for log in logs:
        key = log.provider or "unknown"
        by_provider[key] = by_provider.get(key, 0) + 1

    return UsageResponse(
        caller=target_name,
        request_count=count,
        tokens_in=sum(int(log.tokens_in) for log in logs),
        tokens_out=sum(int(log.tokens_out) for log in logs),
        estimated_cost_usd=float(sum(float(log.cost_usd) for log in logs)),
        error_rate=round(errors / count, 4),
        fallback_rate=round(fallbacks / count, 4),
        avg_latency_ms=round(mean(latencies), 2),
        p50_latency_ms=_percentile(latencies, 50),
        p95_latency_ms=_percentile(latencies, 95),
        by_provider=by_provider,
    )
