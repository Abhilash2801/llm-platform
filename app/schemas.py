from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Target(BaseModel):
    provider: str
    model: str
    weight: float = 1


class RetrySpec(BaseModel):
    max_attempts: int = Field(default=3, ge=1, le=10)
    base_delay_ms: int = Field(default=500, ge=0)
    max_delay_ms: int = Field(default=8000, ge=0)


class GuardrailSpec(BaseModel):
    output: list[str] = Field(default_factory=list)
    on_fail: Literal["retry", "block"] = "block"
    banned_words: list[str] = Field(default_factory=lambda: ["BANNED_PHRASE_42"])
    max_length: int = 4000


class ReliabilityConfig(BaseModel):
    strategy: Literal["fallback", "loadbalance"] = "fallback"
    targets: list[Target]
    on_status_codes: list[int] = Field(default_factory=lambda: [429, 500, 502, 503, 504])
    retry: RetrySpec = Field(default_factory=RetrySpec)
    timeout_ms: int = Field(default=10000, ge=1)
    guardrails: GuardrailSpec | None = None


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    model: str | None = None
    config: ReliabilityConfig | None = None


class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    model: str
    choices: list[dict[str, Any]]
    usage: dict[str, int]
    provider_used: str
    model_used: str
    attempts: int
    fallback_used: bool
    content: str


class UsageResponse(BaseModel):
    caller: str
    request_count: int
    tokens_in: int
    tokens_out: int
    estimated_cost_usd: float
    error_rate: float
    fallback_rate: float
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    by_provider: dict[str, int]


def default_reliability_config() -> ReliabilityConfig:
    from app.providers.registry import demo_target_pair

    primary, _secondary = demo_target_pair()
    return ReliabilityConfig(
        strategy="fallback",
        targets=[Target(provider=primary["provider"], model=primary["model"], weight=1)],
    )
