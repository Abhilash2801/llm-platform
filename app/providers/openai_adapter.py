import httpx

from app.providers.base import ProviderAdapter, ProviderError, ProviderResponse


async def openai_compatible_chat(
    *,
    url: str,
    api_key: str,
    messages: list[dict],
    model: str,
    timeout_s: float,
    provider: str,
) -> ProviderResponse:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
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


class OpenAIAdapter(ProviderAdapter):
    name = "openai"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def chat(self, messages: list[dict], model: str, timeout_s: float) -> ProviderResponse:
        if not self.api_key:
            raise ProviderError(401, "OPENAI_API_KEY is not configured")
        return await openai_compatible_chat(
            url="https://api.openai.com/v1/chat/completions",
            api_key=self.api_key,
            messages=messages,
            model=model,
            timeout_s=timeout_s,
            provider="openai",
        )
