import pytest

from app.executor.strategies import execute
from app.providers.base import ProviderError, ProviderResponse
from app.schemas import ReliabilityConfig, RetrySpec, Target


class SequenceAdapter:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    async def chat(self, messages, model, timeout_s):
        self.calls += 1
        item = self.outcomes.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class Factory:
    def __init__(self, adapters: dict):
        self.adapters = adapters

    def __call__(self, provider: str):
        return self.adapters[provider]


async def _no_sleep(_seconds):
    return None


@pytest.mark.asyncio
async def test_retries_then_succeeds():
    openai = SequenceAdapter(
        [
            ProviderError(500, "boom"),
            ProviderError(500, "boom"),
            ProviderResponse(content="ok", tokens_in=1, tokens_out=1, provider="openai", model="gpt-4o-mini"),
        ]
    )
    config = ReliabilityConfig(
        strategy="fallback",
        targets=[Target(provider="openai", model="gpt-4o-mini")],
        retry=RetrySpec(max_attempts=3, base_delay_ms=1, max_delay_ms=1),
        timeout_ms=1000,
    )
    result = await execute([], config, sleep_fn=_no_sleep, adapter_factory=Factory({"openai": openai}))
    assert result.response is not None
    assert result.response.content == "ok"
    assert result.attempts == 3
    assert openai.calls == 3


@pytest.mark.asyncio
async def test_fallback_to_groq():
    openai = SequenceAdapter([ProviderError(429, "rate limit")])
    groq = SequenceAdapter(
        [ProviderResponse(content="from groq", tokens_in=2, tokens_out=3, provider="groq", model="llama-3.1-8b-instant")]
    )
    config = ReliabilityConfig(
        strategy="fallback",
        targets=[
            Target(provider="openai", model="gpt-4o-mini"),
            Target(provider="groq", model="llama-3.1-8b-instant"),
        ],
        retry=RetrySpec(max_attempts=1, base_delay_ms=1, max_delay_ms=1),
        timeout_ms=1000,
    )
    result = await execute([], config, sleep_fn=_no_sleep, adapter_factory=Factory({"openai": openai, "groq": groq}))
    assert result.fallback_used is True
    assert result.response.provider == "groq"
    assert result.response.content == "from groq"


@pytest.mark.asyncio
async def test_non_trigger_status_does_not_fallback():
    openai = SequenceAdapter([ProviderError(400, "bad request")])
    groq = SequenceAdapter(
        [ProviderResponse(content="should not run", tokens_in=1, tokens_out=1, provider="groq", model="x")]
    )
    config = ReliabilityConfig(
        strategy="fallback",
        targets=[
            Target(provider="openai", model="gpt-4o-mini"),
            Target(provider="groq", model="llama-3.1-8b-instant"),
        ],
        on_status_codes=[429, 500],
        retry=RetrySpec(max_attempts=2, base_delay_ms=1, max_delay_ms=1),
        timeout_ms=1000,
    )
    result = await execute([], config, sleep_fn=_no_sleep, adapter_factory=Factory({"openai": openai, "groq": groq}))
    assert result.response is None
    assert groq.calls == 0
    assert openai.calls == 1
