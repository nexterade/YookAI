"""Provider/model latency benchmark orchestration."""
from __future__ import annotations

import time
from typing import Any, Iterable


class BenchmarkRunner:
    def __init__(self, provider_getter):
        self.provider_getter = provider_getter

    def run_provider(self, provider_name: str, max_candidates: int = 8) -> list[dict[str, Any]]:
        provider = self.provider_getter(provider_name)
        models = provider.list_models() or []
        if hasattr(provider, "benchmark_models"):
            return provider.benchmark_models(models, max_candidates=max_candidates)

        # Generic fallback measures model-list discovery only. It deliberately does
        # not send arbitrary chat requests through providers that lack a safe probe.
        started = time.monotonic()
        return [{
            "id": str(m.get("id", "")),
            "name": m.get("name") or m.get("id", ""),
            "status": 200,
            "ttft_ms": None,
            "connect_ms": round((time.monotonic() - started) * 1000),
            "error": None,
            "probe": "model-list-only",
        } for m in models[:max_candidates] if isinstance(m, dict) and m.get("id")]

    @staticmethod
    def best(results: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
        valid = [r for r in results if r.get("ttft_ms") is not None and not r.get("error")]
        return min(valid, key=lambda r: r["ttft_ms"]) if valid else None
