from fastapi import APIRouter

from app.providers.registry import list_unique_specs

router = APIRouter()


@router.get("/providers")
def list_providers():
    """Catalog of backends this gateway can call. `configured` means the env key is set (value is never returned)."""
    providers = []
    for spec in list_unique_specs():
        providers.append(
            {
                "id": spec.name,
                "protocol": spec.protocol,
                "example_model": spec.example_model,
                "key_env": spec.key_env,
                "aliases": list(spec.aliases),
                "configured": bool(spec.api_key),
                "notes": spec.notes,
            }
        )
    return {
        "providers": providers,
        "add_builtin": "Copy the vendor's key_env into .env, then use that id in config.targets[].provider.",
        "add_custom": {
            "env": "EXTRA_PROVIDERS_JSON",
            "example": {
                "myvendor": {
                    "base_url": "https://api.example.com/v1",
                    "api_key_env": "MYVENDOR_API_KEY",
                    "protocol": "chat_completions",
                    "example_model": "their-model-id",
                }
            },
            "native_api": "If the vendor is not chat-completions shaped, add a small adapter and a protocol branch in get_adapter (see anthropic_messages).",
        },
    }
