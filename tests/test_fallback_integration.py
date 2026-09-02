import os

import pytest

from app.providers.groq_adapter import GroqAdapter
from app.providers.openai_adapter import OpenAIAdapter

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="OPENAI_API_KEY not set")
async def test_openai_adapter_live():
    adapter = OpenAIAdapter(os.environ["OPENAI_API_KEY"])
    response = await adapter.chat(
        [{"role": "user", "content": "Reply with the single word: ok"}],
        "gpt-4o-mini",
        timeout_s=30,
    )
    assert response.content
    assert response.provider == "openai"


@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv("GROQ_API_KEY"), reason="GROQ_API_KEY not set")
async def test_groq_adapter_live():
    adapter = GroqAdapter(os.environ["GROQ_API_KEY"])
    response = await adapter.chat(
        [{"role": "user", "content": "Reply with the single word: ok"}],
        "llama-3.1-8b-instant",
        timeout_s=30,
    )
    assert response.content
    assert response.provider == "groq"


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY") or not os.getenv("GROQ_API_KEY"),
    reason="provider keys not set",
)
async def test_fallback_live_invalid_openai_model():
    from app.executor.strategies import execute
    from app.schemas import ReliabilityConfig, RetrySpec, Target

    config = ReliabilityConfig(
        strategy="fallback",
        targets=[
            Target(provider="openai", model="this-model-does-not-exist-xyz"),
            Target(provider="groq", model="llama-3.1-8b-instant"),
        ],
        on_status_codes=[400, 401, 404, 429, 500, 502, 503, 504],
        retry=RetrySpec(max_attempts=1, base_delay_ms=50, max_delay_ms=200),
        timeout_ms=30000,
    )
    result = await execute(
        [{"role": "user", "content": "Reply with the single word: fallback"}],
        config,
    )
    assert result.response is not None
    assert result.fallback_used is True
    assert result.response.provider == "groq"
