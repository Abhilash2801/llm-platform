from __future__ import annotations

import json
import os

from app.config import settings
from app.providers.anthropic_adapter import AnthropicMessagesAdapter
from app.providers.base import ProviderAdapter, ProviderError, ProviderResponse
from app.providers.catalog import PROVIDERS
from app.providers.chat_completions import post_chat_completion
from app.providers.spec import ProviderSpec


class ChatCompletionsAdapter(ProviderAdapter):
    def __init__(self, spec: ProviderSpec):
        self.spec = spec
        self.name = spec.name

    async def chat(self, messages: list[dict], model: str, timeout_s: float) -> ProviderResponse:
        if not self.spec.api_key and self.spec.name != "ollama":
            raise ProviderError(401, f"{self.spec.key_env} is not configured")
        return await post_chat_completion(
            url=self.spec.chat_url,
            api_key=self.spec.api_key,
            messages=messages,
            model=model,
            timeout_s=timeout_s,
            provider=self.spec.name,
        )


def _from_def(item: dict) -> ProviderSpec:
    key_env = item["key_env"]
    return ProviderSpec(
        name=item["id"],
        protocol=item.get("protocol") or "chat_completions",
        chat_url=item["chat_url"],
        api_key=os.getenv(key_env, "") or "",
        key_env=key_env,
        example_model=item.get("example_model") or "",
        aliases=tuple(item.get("aliases") or ()),
        notes=item.get("notes") or "",
    )


def _builtins() -> dict[str, ProviderSpec]:
    out: dict[str, ProviderSpec] = {}
    for item in PROVIDERS:
        spec = _from_def(item)
        out[spec.name] = spec
        for alias in spec.aliases:
            out[alias] = spec
    return out


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
        key_env = spec.get("api_key_env") or spec.get("api_key_env_name") or f"{name.upper()}_API_KEY"
        api_key = spec.get("api_key") or os.getenv(key_env, "")
        chat_url = (spec.get("chat_url") or spec.get("base_url") or "").rstrip("/")
        protocol = spec.get("protocol") or "chat_completions"
        if protocol == "chat_completions" and chat_url and not chat_url.endswith("/chat/completions"):
            chat_url = f"{chat_url}/chat/completions"
        out[name.lower()] = ProviderSpec(
            name=name.lower(),
            protocol=protocol,
            chat_url=chat_url,
            api_key=api_key,
            key_env=key_env,
            example_model=spec.get("example_model") or "",
            notes=spec.get("notes") or "Registered via EXTRA_PROVIDERS_JSON",
        )
    return out


def provider_catalog() -> dict[str, ProviderSpec]:
    catalog = dict(_builtins())
    catalog.update(_extras())
    return catalog


def list_unique_specs() -> list[ProviderSpec]:
    seen: set[str] = set()
    unique: list[ProviderSpec] = []
    for spec in provider_catalog().values():
        if spec.name in seen:
            continue
        seen.add(spec.name)
        unique.append(spec)
    return unique


def configured_specs() -> list[ProviderSpec]:
    return [s for s in list_unique_specs() if s.api_key]


def demo_target_pair() -> tuple[dict, dict]:
    """Primary/secondary for seed + demo. Env overrides, else first two vendors that have keys."""
    catalog = provider_catalog()
    ready = configured_specs()
    unique = list_unique_specs()
    primary_name = (settings.gateway_primary_provider or "").strip().lower()
    secondary_name = (settings.gateway_secondary_provider or "").strip().lower()
    first = catalog.get(primary_name) if primary_name else (ready[0] if ready else unique[0])
    second = catalog.get(secondary_name) if secondary_name else (ready[1] if len(ready) > 1 else first)
    if first is None or second is None:
        raise RuntimeError("No providers registered. Add a vendor to app/providers/catalog.py")
    return (
        {
            "provider": first.name,
            "model": settings.gateway_primary_model or first.example_model,
            "weight": 1,
        },
        {
            "provider": second.name,
            "model": settings.gateway_secondary_model or second.example_model,
            "weight": 1,
        },
    )


def get_adapter(provider: str) -> ProviderAdapter:
    name = provider.lower()
    catalog = provider_catalog()
    spec = catalog.get(name)
    if spec is None:
        known = ", ".join(sorted(set(catalog)))
        raise ValueError(f"Unknown provider '{provider}'. Registered: {known}")
    if spec.protocol == "anthropic_messages":
        return AnthropicMessagesAdapter(spec)
    return ChatCompletionsAdapter(spec)
