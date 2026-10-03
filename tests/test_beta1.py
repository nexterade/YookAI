import tempfile
import unittest
from pathlib import Path

from app.session import SessionManager
from core.models.catalog import ModelDescriptor
from core.routing.smart import SmartRouter


class FakeProvider:
    def __init__(self, models):
        self.models = models

    def list_models(self):
        return self.models


class Beta1Tests(unittest.TestCase):
    def config(self):
        return {
            "provider": {
                "default": "fast",
                "fast": {"api_key": "x", "base_url": "fast://"},
                "slow": {"api_key": "x", "base_url": "slow://"},
            },
            "chat": {"default_model": "auto", "model_strategy": "latency-best-free"},
        }

    def test_router_prefers_free_and_compatible_model(self):
        providers = {
            "fast": FakeProvider([
                {"id": "fast-paid", "pricing": {"prompt": 1, "completion": 1}},
                {"id": "fast-free", "pricing": {"prompt": 0, "completion": 0}, "vision": True},
            ]),
            "slow": FakeProvider([
                {"id": "slow-free", "pricing": {"prompt": 0, "completion": 0}, "vision": True},
            ]),
        }
        router = SmartRouter(self.config(), providers.__getitem__, providers)
        decision = router.decide({"model": "auto", "messages": [{"role": "user", "content": "hi", "attachments": [{"mime": "image/png"}]}]})
        self.assertEqual(decision.selected.model, "fast-free")
        self.assertEqual(decision.selected.provider, "fast")

    def test_explicit_model_wins(self):
        router = SmartRouter(self.config(), lambda name: None, ["fast"])
        decision = router.decide({"provider": "fast", "model": "my-model", "messages": []})
        self.assertEqual(decision.selected.model, "my-model")
        self.assertEqual(decision.strategy, "manual")
        self.assertEqual(len(decision.fallbacks), 0)

    def test_router_returns_fallback_candidates(self):
        providers = {
            "fast": FakeProvider([{"id": "fast-free", "pricing": {"prompt": 0, "completion": 0}}]),
            "slow": FakeProvider([{"id": "slow-free", "pricing": {"prompt": 0, "completion": 0}}]),
        }
        router = SmartRouter(self.config(), providers.__getitem__, providers)
        decision = router.decide({"model": "auto", "messages": [{"role": "user", "content": "hello"}]})
        self.assertLessEqual(len(decision.fallbacks), 2)
        self.assertIn(decision.selected.provider, {"fast", "slow"})

    def test_session_schema_v2(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = SessionManager(Path(tmp))
            session = manager.create_session()
            self.assertEqual(session["schema_version"], 2)
            self.assertEqual(session["model_config"], {})
            self.assertEqual(session["routing"], {})


if __name__ == "__main__":
    unittest.main()
