from unittest.mock import Mock

from core.models.catalog import ModelCatalog, infer_capabilities
from core.providers.health import ProviderHealthChecker
from core.providers.benchmark import BenchmarkRunner
from providers.registry import provider_specs, PROVIDER_SPECS


def test_capability_inference():
    caps = infer_capabilities({"id": "foo/vision-reasoning", "name": "Vision Reasoning"})
    assert caps["vision"] is True
    assert caps["reasoning"] is True
    assert caps["streaming"] is True


def test_live_model_catalog_normalizes_provider_models():
    provider = Mock()
    provider.list_models.return_value = [{"id": "demo/r1", "name": "R1", "capabilities": {"reasoning": True}}]
    catalog = ModelCatalog(lambda name: provider, ["demo"])
    models = catalog.fetch()
    assert models[0].provider == "demo"
    assert models[0].capabilities.reasoning is True
    assert catalog.serialize()[0]["id"] == "demo/r1"


def test_provider_health_checker():
    provider = Mock()
    provider.list_models.return_value = [{"id": "one"}, {"id": "two"}]
    result = ProviderHealthChecker(lambda name: provider).check("demo")
    assert result.ok is True
    assert result.model_count == 2
    assert result.latency_ms is not None


def test_benchmark_uses_provider_native_probe():
    provider = Mock()
    provider.list_models.return_value = [{"id": "fast", "pricing": {"prompt": "0", "completion": "0"}}]
    provider.benchmark_models.return_value = [{"id": "fast", "ttft_ms": 12, "error": None}]
    result = BenchmarkRunner(lambda name: provider).run_provider("demo")
    assert result[0]["ttft_ms"] == 12
    provider.benchmark_models.assert_called_once()


def test_provider_specs_include_local_ollama():
    specs = {item["name"]: item for item in provider_specs()}
    assert specs["ollama"]["kind"] == "remote"
    assert specs["ollama"]["requires_api_key"] is False
    assert set(PROVIDER_SPECS) >= {"openrouter", "openai", "anthropic", "gemini", "ollama"}
