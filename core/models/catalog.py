"""Live, normalized model catalog for YookAI."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable


@dataclass(frozen=True)
class ModelCapability:
    reasoning: bool = False
    vision: bool = False
    tools: bool = False
    streaming: bool = True
    json_mode: bool = False


@dataclass(frozen=True)
class ModelDescriptor:
    id: str
    provider: str
    name: str | None = None
    context_length: int | None = None
    capabilities: ModelCapability = field(default_factory=ModelCapability)
    pricing: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, provider: str, value: dict[str, Any]) -> "ModelDescriptor":
        raw_caps = value.get("capabilities") or {}
        caps = ModelCapability(
            reasoning=bool(raw_caps.get("reasoning", value.get("reasoning", False))),
            vision=bool(raw_caps.get("vision", value.get("vision", False))),
            tools=bool(raw_caps.get("tools", value.get("tools", False))),
            streaming=bool(raw_caps.get("streaming", True)),
            json_mode=bool(raw_caps.get("json_mode", value.get("json_mode", False))),
        )
        context = value.get("context_length", value.get("context_window"))
        try:
            context = int(context) if context is not None else None
        except (TypeError, ValueError):
            context = None
        pricing = value.get("pricing") or {}
        normalized_pricing = {}
        for key in ("prompt", "completion"):
            if key in pricing:
                try:
                    normalized_pricing[key] = float(pricing[key])
                except (TypeError, ValueError):
                    pass
        return cls(
            id=str(value.get("id", "")),
            provider=provider,
            name=value.get("name") or value.get("id"),
            context_length=context,
            capabilities=caps,
            pricing=normalized_pricing,
            metadata={k: v for k, v in value.items() if k not in {"id", "name", "pricing", "capabilities"}},
        )

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["capabilities"] = asdict(self.capabilities)
        return result


def infer_capabilities(model: dict[str, Any]) -> dict[str, bool]:
    """Infer missing capabilities conservatively from provider metadata/model id."""
    raw = model.get("capabilities") or {}
    text = str(model.get("id", "")) + " " + str(model.get("name", "")) + " " + str(model.get("description", ""))
    lower = text.lower()
    return {
        "reasoning": bool(raw.get("reasoning", model.get("reasoning", False)) or any(x in lower for x in ("reason", "thinking", "r1", "o1", "o3", "o4"))),
        "vision": bool(raw.get("vision", model.get("vision", False)) or any(x in lower for x in ("vision", "vl", "image", "multimodal", "gemini"))),
        "tools": bool(raw.get("tools", model.get("tools", False)) or "tool" in lower or "function" in lower),
        "streaming": bool(raw.get("streaming", model.get("streaming", True))),
        "json_mode": bool(raw.get("json_mode", model.get("json_mode", False)) or "json" in lower),
    }


class ModelCatalog:
    """Aggregates live models from registered providers without owning HTTP transport."""

    def __init__(self, provider_getter, provider_names: Iterable[str] | None = None):
        self.provider_getter = provider_getter
        self.provider_names = list(provider_names or [])

    def fetch(self, provider_names: Iterable[str] | None = None) -> list[ModelDescriptor]:
        names = list(provider_names or self.provider_names)
        descriptors: list[ModelDescriptor] = []
        for provider_name in names:
            provider = self.provider_getter(provider_name)
            for raw in provider.list_models() or []:
                if not isinstance(raw, dict) or not raw.get("id"):
                    continue
                item = dict(raw)
                item["capabilities"] = infer_capabilities(item)
                descriptors.append(ModelDescriptor.from_dict(provider_name, item))
        return descriptors

    def serialize(self, provider_names: Iterable[str] | None = None) -> list[dict[str, Any]]:
        return [item.to_dict() for item in self.fetch(provider_names)]

    @staticmethod
    def filter_capability(models: Iterable[ModelDescriptor], capability: str) -> list[ModelDescriptor]:
        if capability not in {"reasoning", "vision", "tools", "streaming", "json_mode"}:
            raise ValueError(f"Unknown capability: {capability}")
        return [m for m in models if getattr(m.capabilities, capability)]
