from app.providers.base import ProviderAdapter, ProviderError, ProviderResponse
from app.providers.openai_adapter import openai_compatible_chat


class GroqAdapter(ProviderAdapter):
    name = "groq"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def chat(self, messages: list[dict], model: str, timeout_s: float) -> ProviderResponse:
        if not self.api_key:
            raise ProviderError(401, "GROQ_API_KEY is not configured")
        return await openai_compatible_chat(
            url="https://api.groq.com/openai/v1/chat/completions",
            api_key=self.api_key,
            messages=messages,
            model=model,
            timeout_s=timeout_s,
            provider="groq",
        )
