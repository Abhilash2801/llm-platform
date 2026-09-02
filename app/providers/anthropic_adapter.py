import httpx

from app.providers.base import ProviderAdapter, ProviderError, ProviderResponse
from app.providers.spec import ProviderSpec


class AnthropicMessagesAdapter(ProviderAdapter):
    name = "anthropic"

    def __init__(self, spec: ProviderSpec):
        self.spec = spec
        self.name = spec.name

    async def chat(self, messages: list[dict], model: str, timeout_s: float) -> ProviderResponse:
        if not self.spec.api_key:
            raise ProviderError(401, f"{self.spec.key_env} is not configured")

        system_parts = [m["content"] for m in messages if m.get("role") == "system"]
        converted = [
            {"role": "assistant" if m.get("role") == "assistant" else "user", "content": m.get("content") or ""}
            for m in messages
            if m.get("role") != "system"
        ]
        if not converted:
            converted = [{"role": "user", "content": ""}]

        headers = {
            "x-api-key": self.spec.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload: dict = {"model": model, "max_tokens": 1024, "messages": converted}
        if system_parts:
            payload["system"] = "\n".join(system_parts)

        try:
            async with httpx.AsyncClient(timeout=timeout_s) as client:
                response = await client.post(self.spec.chat_url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise ProviderError(504, "anthropic timeout") from exc
        except httpx.RequestError as exc:
            raise ProviderError(503, f"anthropic unreachable: {exc}") from exc

        if response.status_code >= 400:
            raise ProviderError(response.status_code, response.text[:800])

        data = response.json()
        blocks = data.get("content") or []
        text = "".join(block.get("text") or "" for block in blocks if block.get("type") == "text")
        usage = data.get("usage") or {}
        return ProviderResponse(
            content=text,
            tokens_in=int(usage.get("input_tokens") or 0),
            tokens_out=int(usage.get("output_tokens") or 0),
            raw_status=response.status_code,
            model=data.get("model") or model,
            provider=self.spec.name,
        )
