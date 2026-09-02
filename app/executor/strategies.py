from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field

from app.executor.guardrails import run_output_guardrails
from app.executor.retry import sleep_backoff
from app.providers.base import ProviderError, ProviderResponse
from app.providers.registry import get_adapter
from app.schemas import ReliabilityConfig, Target


class GuardrailBlocked(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


@dataclass
class ExecutorResult:
    response: ProviderResponse | None
    attempts: int
    fallback_used: bool
    tried: list[dict] = field(default_factory=list)
    blocked: bool = False
    block_reason: str | None = None
    exhausted: bool = False


async def _call_target(
    target: Target,
    messages: list[dict],
    timeout_s: float,
    adapter_factory=get_adapter,
) -> ProviderResponse:
    adapter = adapter_factory(target.provider)
    return await adapter.chat(messages, target.model, timeout_s)


async def try_target(
    target: Target,
    messages: list[dict],
    config: ReliabilityConfig,
    *,
    sleep_fn=asyncio.sleep,
    adapter_factory=get_adapter,
) -> tuple[ProviderResponse | None, int, list[dict], str | None, bool]:
    max_attempts = config.retry.max_attempts
    timeout_s = config.timeout_ms / 1000.0
    tried: list[dict] = []
    last_status = None
    block_reason = None

    for attempt in range(max_attempts):
        try:
            response = await _call_target(target, messages, timeout_s, adapter_factory)
            check = run_output_guardrails(response.content, config.guardrails)
            if not check.passed:
                on_fail = config.guardrails.on_fail if config.guardrails else "block"
                tried.append(
                    {
                        "provider": target.provider,
                        "model": target.model,
                        "status": 422,
                        "attempt": attempt + 1,
                        "reason": check.reason,
                    }
                )
                if on_fail == "block":
                    return None, attempt + 1, tried, check.reason, False
                last_status = 422
                block_reason = check.reason
            else:
                tried.append(
                    {
                        "provider": target.provider,
                        "model": target.model,
                        "status": response.raw_status or 200,
                        "attempt": attempt + 1,
                    }
                )
                return response, attempt + 1, tried, None, False
        except ProviderError as exc:
            last_status = exc.status
            tried.append(
                {
                    "provider": target.provider,
                    "model": target.model,
                    "status": exc.status,
                    "attempt": attempt + 1,
                    "reason": exc.message,
                }
            )
            if exc.status not in config.on_status_codes:
                return None, attempt + 1, tried, None, False
        if attempt < max_attempts - 1 and last_status in set(config.on_status_codes + [422]):
            await sleep_backoff(
                attempt,
                config.retry.base_delay_ms,
                config.retry.max_delay_ms,
                sleep_fn,
            )

    return None, max_attempts, tried, block_reason, True


def pick_weighted_target(targets: list[Target]) -> Target:
    weights = [max(t.weight, 0) for t in targets]
    if sum(weights) <= 0:
        return targets[0]
    return random.choices(targets, weights=weights, k=1)[0]


async def run_fallback(
    messages: list[dict],
    config: ReliabilityConfig,
    *,
    sleep_fn=asyncio.sleep,
    adapter_factory=get_adapter,
) -> ExecutorResult:
    total_attempts = 0
    all_tried: list[dict] = []
    fallback_used = False

    for index, target in enumerate(config.targets):
        response, attempts, tried, block_reason, retryable = await try_target(
            target,
            messages,
            config,
            sleep_fn=sleep_fn,
            adapter_factory=adapter_factory,
        )
        total_attempts += attempts
        all_tried.extend(tried)
        if index > 0:
            fallback_used = True
        if block_reason and not retryable:
            return ExecutorResult(
                response=None,
                attempts=total_attempts,
                fallback_used=fallback_used,
                tried=all_tried,
                blocked=True,
                block_reason=block_reason,
            )
        if response is not None:
            return ExecutorResult(
                response=response,
                attempts=total_attempts,
                fallback_used=fallback_used,
                tried=all_tried,
            )
        if not retryable:
            break

    last_block = next((t.get("reason") for t in reversed(all_tried) if t.get("status") == 422), None)
    if last_block and all(t.get("status") == 422 for t in all_tried):
        return ExecutorResult(
            response=None,
            attempts=total_attempts,
            fallback_used=fallback_used,
            tried=all_tried,
            blocked=True,
            block_reason=last_block,
        )
    return ExecutorResult(
        response=None,
        attempts=total_attempts,
        fallback_used=fallback_used,
        tried=all_tried,
        exhausted=True,
    )


async def run_loadbalance(
    messages: list[dict],
    config: ReliabilityConfig,
    *,
    sleep_fn=asyncio.sleep,
    adapter_factory=get_adapter,
) -> ExecutorResult:
    target = pick_weighted_target(config.targets)
    response, attempts, tried, block_reason, _retryable = await try_target(
        target,
        messages,
        config,
        sleep_fn=sleep_fn,
        adapter_factory=adapter_factory,
    )
    if block_reason:
        return ExecutorResult(
            response=None,
            attempts=attempts,
            fallback_used=False,
            tried=tried,
            blocked=True,
            block_reason=block_reason,
        )
    if response is None:
        return ExecutorResult(
            response=None,
            attempts=attempts,
            fallback_used=False,
            tried=tried,
            exhausted=True,
        )
    return ExecutorResult(
        response=response,
        attempts=attempts,
        fallback_used=False,
        tried=tried,
    )


async def execute(
    messages: list[dict],
    config: ReliabilityConfig,
    *,
    sleep_fn=asyncio.sleep,
    adapter_factory=get_adapter,
) -> ExecutorResult:
    if config.strategy == "loadbalance":
        return await run_loadbalance(
            messages, config, sleep_fn=sleep_fn, adapter_factory=adapter_factory
        )
    return await run_fallback(messages, config, sleep_fn=sleep_fn, adapter_factory=adapter_factory)
