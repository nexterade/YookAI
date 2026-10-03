"""Provider registry 2.0: metadata, factories, and stable provider discovery."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Type

from .base import BaseProvider
from .openrouter import OpenRouterProvider
from .openai import OpenAIProvider
from .anthropic import AnthropicProvider
from .gemini import GeminiProvider
from .ollama import OllamaProvider


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    display_name: str
    kind: str = "remote"
    requires_api_key: bool = True
    supports_model_list: bool = True
    supports_streaming: bool = True
    base_url: str = ""


PROVIDER_SPECS: dict[str, ProviderSpec] = {}
PROVIDER_REGISTRY: dict[str, Type[BaseProvider]] = {}
_PROVIDER_INSTANCES: dict[str, BaseProvider] = {}

DEFAULT_BASE_URLS = {
    "openrouter": "https://openrouter.ai/api/v1",
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta",
    "ollama": "http://127.0.0.1:11434",
}


def register_provider(name: str, provider_class: Type[BaseProvider], *, display_name: str | None = None,
                      kind: str = "remote", requires_api_key: bool = True, base_url: str | None = None) -> None:
    if not name:
        raise ValueError("Provider name cannot be empty")
    if not issubclass(provider_class, BaseProvider):
        raise TypeError("Provider class must inherit BaseProvider")
    PROVIDER_REGISTRY[name] = provider_class
    PROVIDER_SPECS[name] = ProviderSpec(
        name=name,
        display_name=display_name or name.title(),
        kind=kind,
        requires_api_key=requires_api_key,
        base_url=base_url or DEFAULT_BASE_URLS.get(name, ""),
    )
    _PROVIDER_INSTANCES.pop(name, None)


def get_provider(name: str, **kwargs) -> BaseProvider:
    try:
        provider_class = PROVIDER_REGISTRY[name]
    except KeyError as exc:
        raise ValueError(f"Unknown provider: {name}") from exc
    if kwargs:
        return provider_class(**kwargs)
    if name in _PROVIDER_INSTANCES:
        return _PROVIDER_INSTANCES[name]
    from core.config import ensure_config, load_config
    ensure_config()
    provider_config = load_config().get("provider", {}).get(name, {})
    spec = PROVIDER_SPECS[name]
    instance = provider_class(
        api_key=provider_config.get("api_key", ""),
        base_url=provider_config.get("base_url") or spec.base_url,
    )
    _PROVIDER_INSTANCES[name] = instance
    return instance


def list_providers() -> list[str]:
    return list(PROVIDER_REGISTRY)


def provider_specs() -> list[dict]:
    return [asdict(PROVIDER_SPECS[name]) for name in list_providers()]


register_provider("openrouter", OpenRouterProvider, display_name="OpenRouter")
register_provider("openai", OpenAIProvider, display_name="OpenAI")
register_provider("anthropic", AnthropicProvider, display_name="Anthropic")
register_provider("gemini", GeminiProvider, display_name="Google Gemini")
register_provider("ollama", OllamaProvider, display_name="Ollama API", kind="remote", requires_api_key=False)
