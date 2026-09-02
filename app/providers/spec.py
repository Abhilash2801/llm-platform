from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    protocol: str
    chat_url: str
    api_key: str
    key_env: str
    example_model: str = ""
    aliases: tuple[str, ...] = field(default_factory=tuple)
    notes: str = ""
