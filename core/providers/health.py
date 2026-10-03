"""Provider health and latency probing used by routing and diagnostics."""
from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Iterable


@dataclass
class ProviderHealth:
    provider: str
    ok: bool
    latency_ms: int | None = None
    error: str | None = None
    checked_at: float = field(default_factory=time.time)
    model_count: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def score(self) -> float:
        if not self.ok or self.latency_ms is None:
            return float("inf")
        return float(self.latency_ms)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "ok": self.ok,
            "latency_ms": self.latency_ms,
            "error": self.error,
            "checked_at": self.checked_at,
            "model_count": self.model_count,
            "score": self.score,
            "metadata": self.metadata,
        }


class ProviderHealthChecker:
    """Lightweight health check: provider model discovery, not a billable chat call."""

    def __init__(self, provider_getter):
        self.provider_getter = provider_getter

    def check(self, provider_name: str) -> ProviderHealth:
        started = time.monotonic()
        try:
            provider = self.provider_getter(provider_name)
            models = provider.list_models() or []
            return ProviderHealth(
                provider=provider_name,
                ok=True,
                latency_ms=round((time.monotonic() - started) * 1000),
                model_count=len(models),
            )
        except Exception as exc:
            return ProviderHealth(
                provider=provider_name,
                ok=False,
                latency_ms=round((time.monotonic() - started) * 1000),
                error=str(exc),
            )

    def check_all(self, provider_names: Iterable[str]) -> list[ProviderHealth]:
        return [self.check(name) for name in provider_names]
