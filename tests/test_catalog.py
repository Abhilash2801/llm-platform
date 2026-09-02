from app.providers.catalog import PROVIDERS, all_ids_and_aliases
from app.providers.registry import get_adapter, provider_catalog


def test_catalog_includes_multiple_vendors():
    ids = {item["id"] for item in PROVIDERS}
    assert "groq" in ids
    assert "anthropic" in ids
    assert "xai" in ids
    assert "together" in ids
    assert "mistral" in ids
    assert "openai" in ids


def test_aliases_resolve():
    names = all_ids_and_aliases()
    assert "grok" in names
    assert "gemini" in names


def test_unknown_provider_lists_registered():
    try:
        get_adapter("not-a-real-vendor")
    except ValueError as exc:
        message = str(exc)
        assert "groq" in message
        assert "anthropic" in message
    else:
        raise AssertionError("expected ValueError")


def test_catalog_has_chat_url_and_key_env():
    for spec in provider_catalog().values():
        assert spec.chat_url
        assert spec.key_env
        assert spec.protocol in {"chat_completions", "anthropic_messages"}
