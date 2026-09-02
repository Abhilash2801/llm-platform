import asyncio

import pytest

from app.executor.retry import backoff_seconds, sleep_backoff


def test_backoff_doubles_and_caps():
    first = backoff_seconds(0, base_delay_ms=500, max_delay_ms=8000)
    second = backoff_seconds(1, base_delay_ms=500, max_delay_ms=8000)
    capped = backoff_seconds(10, base_delay_ms=500, max_delay_ms=8000)
    assert 0.4 <= first <= 0.6
    assert 0.8 <= second <= 1.2
    assert capped <= 8.0 * 1.2


@pytest.mark.asyncio
async def test_retry_sleep_is_called_with_backoff(monkeypatch):
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    await sleep_backoff(0, 100, 1000, fake_sleep)
    await sleep_backoff(1, 100, 1000, fake_sleep)
    assert len(sleeps) == 2
    assert sleeps[1] > sleeps[0] * 0.5
