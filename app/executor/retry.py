import random


def backoff_seconds(attempt: int, base_delay_ms: int, max_delay_ms: int) -> float:
    """Delay after a failed attempt. `attempt` is 0-indexed (first retry uses attempt=0)."""
    delay_ms = min(max_delay_ms, base_delay_ms * (2**attempt))
    jitter = delay_ms * random.uniform(-0.2, 0.2)
    return max(0.0, (delay_ms + jitter) / 1000.0)


async def sleep_backoff(attempt: int, base_delay_ms: int, max_delay_ms: int, sleep_fn) -> None:
    await sleep_fn(backoff_seconds(attempt, base_delay_ms, max_delay_ms))
