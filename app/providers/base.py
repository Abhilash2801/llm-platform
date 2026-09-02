from pydantic import BaseModel


class ProviderResponse(BaseModel):
    content: str
    tokens_in: int = 0
    tokens_out: int = 0
    raw_status: int | None = 200
    model: str = ""
    provider: str = ""


class ProviderError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(message)


class ProviderAdapter:
    name: str

    async def chat(self, messages: list[dict], model: str, timeout_s: float) -> ProviderResponse:
        raise NotImplementedError
