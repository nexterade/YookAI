"""Latency/capability-aware model and provider routing for YookAI."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable
import time

from core.latency import get_result
from core.models.catalog import ModelCatalog, ModelDescriptor


@dataclass(frozen=True)
class RouteCandidate:
    provider: str
    model: str
    score: float
    latency_ms: float | None = None
    free: bool = False
    capabilities: dict[str, bool] = field(default_factory=dict)
    reason: str = ""


@dataclass(frozen=True)
class RoutingDecision:
    selected: RouteCandidate
    fallbacks: tuple[RouteCandidate, ...] = ()
    strategy: str = "manual"

    @property
    def candidates(self) -> tuple[RouteCandidate, ...]:
        return (self.selected, *self.fallbacks)


class SmartRouter:
    """Select a model without hiding explicit user choices.

    Explicit provider/model values always win. Automatic mode only considers
    configured providers and models whose capabilities satisfy the request.
    Latency measurements are read from the local TTL cache; a provider health
    latency may be supplied by ``health_by_provider`` when benchmark data is
    unavailable. No billable probe is performed by the router itself.
    """

    def __init__(self, config: dict[str, Any], provider_getter, provider_names: Iterable[str]):
        self.config = config
        self.provider_getter = provider_getter
        self.provider_names = list(provider_names)
        self._catalog_cache: dict[str, tuple[float, list[ModelDescriptor]]] = {}
        self.catalog_ttl = 60.0

    def _configured(self, name: str) -> bool:
        settings = (self.config.get("provider") or {}).get(name, {})
        if name == "ollama":
            return bool(settings.get("base_url"))
        return bool(settings.get("api_key"))

    @staticmethod
    def _is_free(model: ModelDescriptor) -> bool:
        pricing = model.pricing or {}
        if not pricing:
            # Unknown pricing is not treated as free.
            return False
        return all(float(pricing.get(k, 0) or 0) <= 0 for k in ("prompt", "completion"))

    @staticmethod
    def _required_capabilities(body: dict[str, Any]) -> set[str]:
        required = set()
        options = body.get("options") or {}
        explicit = options.get("required_capability")
        if isinstance(explicit, str) and explicit in {"reasoning", "vision", "tools", "streaming", "json_mode"}:
            required.add(explicit)
        if options.get("require_vision") is True:
            required.add("vision")
        for message in body.get("messages") or []:
            if not isinstance(message, dict):
                continue
            for attachment in message.get("attachments") or []:
                if isinstance(attachment, dict) and str(attachment.get("mime", "")).startswith("image/"):
                    required.add("vision")
        return required

    def _latency_map(self, provider: str) -> dict[str, float]:
        settings = (self.config.get("provider") or {}).get(provider, {})
        base_url = settings.get("base_url", "")
        cached = get_result(provider, base_url)
        if not isinstance(cached, dict):
            return {}
        values: dict[str, float] = {}
        for item in cached.get("results", []) if isinstance(cached.get("results"), list) else []:
            if not isinstance(item, dict) or item.get("error"):
                continue
            value = item.get("ttft_ms")
            if value is None:
                value = item.get("connect_ms")
            try:
                if value is not None:
                    values[str(item.get("id", ""))] = float(value)
            except (TypeError, ValueError):
                pass
        return values

    def _health_latency(self, provider: str, health_by_provider: dict[str, Any] | None) -> float | None:
        if not health_by_provider:
            return None
        item = health_by_provider.get(provider)
        if isinstance(item, dict):
            try:
                return float(item.get("latency_ms")) if item.get("latency_ms") is not None else None
            except (TypeError, ValueError):
                return None
        return None

    def decide(self, body: dict[str, Any], *, health_by_provider: dict[str, Any] | None = None) -> RoutingDecision:
        requested_provider = body.get("provider")
        requested_model = body.get("model")
        strategy = str(((self.config.get("chat") or {}).get("model_strategy") or "manual"))

        if isinstance(requested_model, str) and requested_model.strip() and requested_model.strip().lower() != "auto":
            provider = requested_provider or (self.config.get("provider") or {}).get("default", "openrouter")
            candidate = RouteCandidate(str(provider), requested_model.strip(), 0.0, reason="explicit model")
            return RoutingDecision(candidate, strategy="manual")

        if requested_provider:
            providers = [str(requested_provider)]
        else:
            default = (self.config.get("provider") or {}).get("default")
            configured = [name for name in self.provider_names if self._configured(name)]
            providers = ([default] if default in configured else []) + [n for n in configured if n != default]

        required = self._required_capabilities(body)
        descriptors: list[ModelDescriptor] = []
        errors = []
        for provider in providers:
            if provider not in self.provider_names:
                continue
            if not self._configured(provider):
                continue
            try:
                cached = self._catalog_cache.get(provider)
                if cached and time.monotonic() - cached[0] <= self.catalog_ttl:
                    descriptors.extend(cached[1])
                else:
                    fresh = ModelCatalog(self.provider_getter, [provider]).fetch()
                    self._catalog_cache[provider] = (time.monotonic(), fresh)
                    descriptors.extend(fresh)
            except Exception as exc:
                errors.append(str(exc))

        candidates: list[RouteCandidate] = []
        prefer_free = strategy.endswith("free") or strategy in {"latency-best-free", "fastest-free"}
        for model in descriptors:
            caps = {key: bool(getattr(model.capabilities, key)) for key in ("reasoning", "vision", "tools", "streaming", "json_mode")}
            if any(not caps.get(cap, False) for cap in required):
                continue
            free = self._is_free(model)
            if prefer_free and not free:
                continue
            latency = self._latency_map(model.provider).get(model.id)
            if latency is None:
                latency = self._health_latency(model.provider, health_by_provider)
            # Unknown latency is deliberately placed after measured candidates.
            latency_score = float(latency) if latency is not None else 1_000_000.0
            free_bonus = -100_000.0 if prefer_free and free else 0.0
            score = latency_score + free_bonus
            candidates.append(RouteCandidate(
                provider=model.provider,
                model=model.id,
                score=score,
                latency_ms=latency,
                free=free,
                capabilities=caps,
                reason="cached benchmark" if model.id in self._latency_map(model.provider) else "provider health",
            ))

        if not candidates:
            detail = f"; provider errors: {' | '.join(errors[:3])}" if errors else ""
            raise ValueError(f"No compatible model is available for automatic routing{detail}")

        candidates.sort(key=lambda c: (c.score, c.provider, c.model))
        # Limit automatic fallback fan-out. Three candidates are enough to cover
        # transient provider/model failures without multiplying request volume.
        return RoutingDecision(candidates[0], tuple(candidates[1:3]), strategy=strategy)
