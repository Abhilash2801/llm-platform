from app.providers.base import ProviderAdapter, ProviderError, ProviderResponse
from app.providers.chat_completions import post_chat_completion


class GroqAdapter(ProviderAdapter):
    name = "groq"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def chat(self, messages: list[dict], model: str, timeout_s: float) -> ProviderResponse:
        if not self.api_key:
            raise ProviderError(401, "GROQ_API_KEY is not configured")
        return await post_chat_completion(
            url="https://api.groq.com/openai/v1/chat/completions",
            api_key=self.api_key,
            messages=messages,
            model=model,
            timeout_s=timeout_s,
            provider="groq",
        )
