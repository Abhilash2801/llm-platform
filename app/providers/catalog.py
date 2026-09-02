"""Built-in vendor catalog. Executor code does not change when you add a row here."""

from __future__ import annotations

from typing import TypedDict


class ProviderDef(TypedDict, total=False):
    id: str
    protocol: str  # chat_completions | anthropic_messages
    chat_url: str
    key_env: str
    example_model: str
    aliases: list[str]
    notes: str


# protocol chat_completions = POST {chat_url} with {model, messages} (widely used shape).
# protocol anthropic_messages = Anthropic Messages API.
PROVIDERS: list[ProviderDef] = [
    {
        "id": "anthropic",
        "protocol": "anthropic_messages",
        "chat_url": "https://api.anthropic.com/v1/messages",
        "key_env": "ANTHROPIC_API_KEY",
        "example_model": "claude-3-5-haiku-20241022",
        "notes": "Native Messages API, not the chat-completions shape.",
    },
    {
        "id": "deepseek",
        "protocol": "chat_completions",
        "chat_url": "https://api.deepseek.com/chat/completions",
        "key_env": "DEEPSEEK_API_KEY",
        "example_model": "deepseek-chat",
    },
    {
        "id": "fireworks",
        "protocol": "chat_completions",
        "chat_url": "https://api.fireworks.ai/inference/v1/chat/completions",
        "key_env": "FIREWORKS_API_KEY",
        "example_model": "accounts/fireworks/models/llama-v3p1-8b-instruct",
    },
    {
        "id": "google",
        "protocol": "chat_completions",
        "chat_url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "key_env": "GOOGLE_API_KEY",
        "example_model": "gemini-2.0-flash",
        "aliases": ["gemini"],
        "notes": "Gemini via Google's chat-completions-compatible endpoint.",
    },
    {
        "id": "groq",
        "protocol": "chat_completions",
        "chat_url": "https://api.groq.com/openai/v1/chat/completions",
        "key_env": "GROQ_API_KEY",
        "example_model": "llama-3.1-8b-instant",
    },
    {
        "id": "mistral",
        "protocol": "chat_completions",
        "chat_url": "https://api.mistral.ai/v1/chat/completions",
        "key_env": "MISTRAL_API_KEY",
        "example_model": "mistral-small-latest",
    },
    {
        "id": "ollama",
        "protocol": "chat_completions",
        "chat_url": "http://127.0.0.1:11434/v1/chat/completions",
        "key_env": "OLLAMA_API_KEY",
        "example_model": "llama3.1",
        "notes": "Local. Key optional for default Ollama.",
    },
    {
        "id": "openai",
        "protocol": "chat_completions",
        "chat_url": "https://api.openai.com/v1/chat/completions",
        "key_env": "OPENAI_API_KEY",
        "example_model": "gpt-4o-mini",
    },
    {
        "id": "openrouter",
        "protocol": "chat_completions",
        "chat_url": "https://openrouter.ai/api/v1/chat/completions",
        "key_env": "OPENROUTER_API_KEY",
        "example_model": "openrouter/auto",
    },
    {
        "id": "perplexity",
        "protocol": "chat_completions",
        "chat_url": "https://api.perplexity.ai/chat/completions",
        "key_env": "PERPLEXITY_API_KEY",
        "example_model": "sonar",
    },
    {
        "id": "together",
        "protocol": "chat_completions",
        "chat_url": "https://api.together.xyz/v1/chat/completions",
        "key_env": "TOGETHER_API_KEY",
        "example_model": "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
    },
    {
        "id": "xai",
        "protocol": "chat_completions",
        "chat_url": "https://api.x.ai/v1/chat/completions",
        "key_env": "XAI_API_KEY",
        "example_model": "grok-2-latest",
        "aliases": ["grok"],
        "notes": "xAI Grok. Not the same as Groq.",
    },
]


def all_ids_and_aliases() -> list[str]:
    names: list[str] = []
    for item in PROVIDERS:
        names.append(item["id"])
        names.extend(item.get("aliases") or [])
    return names
