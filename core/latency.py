"""Local cache for provider latency benchmarks."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from . import paths


CACHE_FILE = paths.CONFIG_DIR / "latency.json"
DEFAULT_TTL = 6 * 60 * 60


def load_cache() -> dict[str, Any]:
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_cache(data: dict[str, Any]) -> None:
    paths.ensure_layout()
    tmp = CACHE_FILE.with_name(f".{CACHE_FILE.name}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(CACHE_FILE)


def get_result(provider: str, base_url: str, ttl: int = DEFAULT_TTL) -> dict[str, Any] | None:
    cache = load_cache()
    item = cache.get(f"{provider}:{base_url}")
    if not isinstance(item, dict):
        return None
    if time.time() - float(item.get("tested_at", 0)) > ttl:
        return None
    return item


def put_result(provider: str, base_url: str, result: dict[str, Any]) -> None:
    cache = load_cache()
    cache[f"{provider}:{base_url}"] = {**result, "tested_at": time.time()}
    save_cache(cache)
