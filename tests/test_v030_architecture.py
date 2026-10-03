from core.chat.engine import ChatEngine
from core.models.catalog import ModelDescriptor, ModelCapability
from core.models.profiles import get_profile, set_profile, profile_key
from core.providers.health import ProviderHealth
from core.tools.registry import ToolRegistry, ToolSpec
from core.sessions.manager import SessionManager
from core.attachments.manager import AttachmentStore


def test_model_descriptor_normalizes_capabilities():
    model = ModelDescriptor.from_dict("demo", {
        "id": "demo/model",
        "context_length": "8192",
        "capabilities": {"reasoning": True, "vision": True, "tools": True},
        "pricing": {"prompt": "1.2", "completion": 3},
    })
    assert model.provider == "demo"
    assert model.context_length == 8192
    assert model.capabilities == ModelCapability(reasoning=True, vision=True, tools=True)
    assert model.pricing == {"prompt": 1.2, "completion": 3.0}


def test_model_profiles_are_provider_model_scoped():
    config = {"chat": {"model_profiles": {}}}
    set_profile(config, "demo", "model-a", {"temperature": 0.2})
    assert profile_key("demo", "model-a") == "demo:model-a"
    assert get_profile(config, "demo", "model-a")["temperature"] == 0.2
    assert get_profile(config, "demo", "model-b")["temperature"] == 0.7


def test_provider_health_score():
    assert ProviderHealth("demo", True, 123).score == 123
    assert ProviderHealth("demo", False, None).score == float("inf")


def test_tool_registry():
    registry = ToolRegistry()
    fn = lambda: "ok"
    registry.register(ToolSpec("demo", "Demo", fn))
    assert registry.get("demo").handler() == "ok"
    assert registry.list()[0].requires_confirmation is True


def test_compatibility_facades_exist():
    assert SessionManager is not None
    assert AttachmentStore is not None


def test_chat_engine_delegates():
    class API:
        def handle_chat(self, request):
            return iter([{"type": "done"}])
        def handle_chat_stop(self, request):
            return {"ok": True}

    engine = ChatEngine(API())
    assert list(engine.stream({"messages": []})) == [{"type": "done"}]
    assert engine.stop("demo", "req")["ok"] is True
