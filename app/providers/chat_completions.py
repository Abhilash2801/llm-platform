"""HTTP helper for the common {model, messages} chat completions request shape."""

import httpx

from app.providers.base import ProviderError, ProviderResponse


async def post_chat_completion(
    *,
    url: str,
    api_key: str,
    messages: list[dict],
    model: str,
    timeout_s: float,
    provider: str,
    extra_headers: dict[str, str] | None = None,
) -> ProviderResponse:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if extra_headers:
        headers.update(extra_headers)
    payload = {"model": model, "messages": messages}
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            response = await client.post(url, headers=headers, json=payload)
    except httpx.TimeoutException as exc:
        raise ProviderError(504, f"{provider} timeout") from exc
    except httpx.RequestError as exc:
        raise ProviderError(503, f"{provider} unreachable: {exc}") from exc

    if response.status_code >= 400:
        raise ProviderError(response.status_code, response.text[:800])

    data = response.json()
    choices = data.get("choices") or []
    content = ""
    if choices:
        content = (choices[0].get("message") or {}).get("content") or ""
    usage = data.get("usage") or {}
    return ProviderResponse(
        content=content,
        tokens_in=int(usage.get("prompt_tokens") or 0),
        tokens_out=int(usage.get("completion_tokens") or 0),
        raw_status=response.status_code,
        model=data.get("model") or model,
        provider=provider,
    )
