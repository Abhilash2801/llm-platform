from __future__ import annotations

import json
import os
from dataclasses import dataclass

from app.config import settings
from app.providers.base import ProviderAdapter, ProviderError, ProviderResponse
from app.providers.openai_adapter import openai_compatible_chat


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    chat_url: str
    api_key: str
    key_env: str


class OpenAICompatibleAdapter(ProviderAdapter):
    """Works with any vendor that implements OpenAI's chat completions HTTP API."""

    def __init__(self, spec: ProviderSpec):
        self.spec = spec
        self.name = spec.name

    async def chat(self, messages: list[dict], model: str, timeout_s: float) -> ProviderResponse:
        if not self.spec.api_key:
            raise ProviderError(401, f"{self.spec.key_env} is not configured")
        return await openai_compatible_chat(
            url=self.spec.chat_url,
            api_key=self.spec.api_key,
            messages=messages,
            model=model,
            timeout_s=timeout_s,
            provider=self.spec.name,
        )


def _builtins() -> dict[str, ProviderSpec]:
    openai = ProviderSpec(
        name="openai",
        chat_url="https://api.openai.com/v1/chat/completions",
        api_key=settings.openai_api_key,
        key_env="OPENAI_API_KEY",
    )
    groq = ProviderSpec(
        name="groq",
        chat_url="https://api.groq.com/openai/v1/chat/completions",
        api_key=settings.groq_api_key,
        key_env="GROQ_API_KEY",
    )
    xai = ProviderSpec(
        name="xai",
        chat_url="https://api.x.ai/v1/chat/completions",
        api_key=settings.xai_api_key,
        key_env="XAI_API_KEY",
    )
    return {
        "openai": openai,
        "groq": groq,
        "xai": xai,
        "grok": xai,  # alias: xAI's Grok models
    }


def _extras() -> dict[str, ProviderSpec]:
    raw = (settings.extra_providers_json or "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"EXTRA_PROVIDERS_JSON is not valid JSON: {exc}") from exc
    out: dict[str, ProviderSpec] = {}
    for name, spec in data.items():
        key_env = spec.get("api_key_env") or spec.get("api_key_env_name") or ""
        api_key = spec.get("api_key") or (os.getenv(key_env, "") if key_env else "")
        chat_url = (spec.get("chat_url") or spec.get("base_url") or "").rstrip("/")
        if chat_url and not chat_url.endswith("/chat/completions"):
            chat_url = f"{chat_url}/chat/completions"
        out[name.lower()] = ProviderSpec(
            name=name.lower(),
            chat_url=chat_url,
            api_key=api_key,
            key_env=key_env or f"{name.upper()}_API_KEY",
        )
    return out


def provider_catalog() -> dict[str, ProviderSpec]:
    catalog = dict(_builtins())
    catalog.update(_extras())
    return catalog


def get_adapter(provider: str) -> ProviderAdapter:
    name = provider.lower()
    catalog = provider_catalog()
    spec = catalog.get(name)
    if spec is None:
        known = ", ".join(sorted(set(catalog)))
        raise ValueError(f"Unknown provider '{provider}'. Registered: {known}")
    return OpenAICompatibleAdapter(spec)
