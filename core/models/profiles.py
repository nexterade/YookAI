"""Per-model configuration helpers."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

DEFAULT_MODEL_OPTIONS: dict[str, Any] = {
    "temperature": 0.7,
    "top_p": 1.0,
    "max_tokens": 2048,
    "reasoning_effort": "auto",
    "system_prompt": "",
}


def profile_key(provider: str, model: str) -> str:
    return f"{provider}:{model}"


def get_profile(config: dict, provider: str, model: str) -> dict[str, Any]:
    profiles = ((config.get("chat") or {}).get("model_profiles") or {})
    raw = profiles.get(profile_key(provider, model), {})
    result = deepcopy(DEFAULT_MODEL_OPTIONS)
    if isinstance(raw, dict):
        result.update(raw)
    return result


def set_profile(config: dict, provider: str, model: str, options: dict[str, Any]) -> None:
    chat = config.setdefault("chat", {})
    profiles = chat.setdefault("model_profiles", {})
    profiles[profile_key(provider, model)] = dict(options)
