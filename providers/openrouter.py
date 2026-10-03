"""OpenRouter provider implementation for YookAI."""

import json
import logging
import threading
import time
import uuid
from typing import Iterator

from core.text import repair_mojibake

import requests

from .base import BaseProvider


from .errors import ProviderHTTPError, AuthError, PaymentError, RateLimitError
LOGGER = logging.getLogger("yookai.provider.openrouter")


class OpenRouterProvider(BaseProvider):
    """Provider adapter for OpenRouter's OpenAI-compatible API."""

    MODEL_CACHE_TTL = 60 * 60
    TIMEOUT = (15, 300)

    def __init__(self, api_key, base_url="https://openrouter.ai/api/v1"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._model_cache = None
        self._model_cache_at = 0.0
        self._stop_events: dict[str, threading.Event] = {}
        self._active_responses: dict[str, object] = {}
        self._stop_lock = threading.Lock()

    @property
    def name(self) -> str:
        """Return the OpenRouter provider identifier."""
        return "openrouter"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }

    @staticmethod
    def _raise_http_error(response) -> None:
        status = response.status_code
        if 200 <= status < 300:
            return
        messages = {
            401: "OpenRouter authentication failed (401): check API key",
            402: "OpenRouter payment/credit error (402)",
            429: "OpenRouter rate limit exceeded (429)",
        }
        if status == 401:
            raise AuthError(messages[status])
        if status == 402:
            raise PaymentError(messages[status])
        if status == 429:
            raise RateLimitError(messages[status])
        if 500 <= status <= 599:
            raise requests.HTTPError(
                f"OpenRouter server error ({status})", response=response
            )
        raise requests.HTTPError(
            f"OpenRouter HTTP error ({status})", response=response
        )

    def list_models(self) -> list[dict]:
        """Fetch and normalize OpenRouter models, cached for one hour."""
        now = time.monotonic()
        if self._model_cache is not None and now - self._model_cache_at < self.MODEL_CACHE_TTL:
            return list(self._model_cache)

        response = requests.get(
            f"{self.base_url}/models",
            headers=self._headers(),
            timeout=self.TIMEOUT,
        )
        self._raise_http_error(response)
        payload = response.json()
        models = payload.get("data", [])
        normalized = []
        for model in models:
            if not isinstance(model, dict):
                continue
            normalized.append(
                {
                    "id": model.get("id", ""),
                    "name": model.get("name") or model.get("id", ""),
                    "description": model.get("description", ""),
                    "context_length": model.get("context_length"),
                    "pricing": model.get("pricing", {}),
                    "capabilities": {
                        "vision": "image" in str(model.get("architecture", {}).get("input_modalities", [])).lower() or "vision" in str(model).lower(),
                        "reasoning": "reasoning" in str(model).lower(),
                        "tools": bool(model.get("supported_parameters") and "tools" in model.get("supported_parameters")),
                    },
                    "raw": model,
                }
            )
        self._model_cache = normalized
        self._model_cache_at = now
        return list(normalized)

    def benchmark_models(self, models, max_candidates=8, timeout=(8, 20)) -> list[dict]:
        """Measure time-to-first-event for a bounded set of models.

        The benchmark intentionally targets free models only. It sends one
        streaming request with ``max_tokens=1`` and closes the response as soon
        as the first SSE event arrives, avoiding a full completion. Results are
        intended for choosing a low-latency default, not for model quality
        ranking.
        """
        candidates = []
        for model in models or []:
            if not isinstance(model, dict):
                continue
            model_id = str(model.get("id", "")).strip()
            pricing = model.get("pricing") or {}
            if not model_id:
                continue
            if str(pricing.get("prompt", "")) != "0" or str(pricing.get("completion", "")) != "0":
                continue
            candidates.append(model)
        candidates = candidates[:max_candidates]
        results = []
        for model in candidates:
            model_id = str(model.get("id"))
            started = time.monotonic()
            first = None
            status = None
            error = None
            response = None
            try:
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json={
                        "model": model_id,
                        "messages": [{"role": "user", "content": "ping"}],
                        "stream": True,
                        "max_tokens": 1,
                        "stream_options": {"include_usage": False},
                    },
                    stream=True,
                    timeout=timeout,
                )
                status = response.status_code
                self._raise_http_error(response)
                response.encoding = "utf-8"
                for raw_line in response.iter_lines(chunk_size=1, decode_unicode=True):
                    if raw_line:
                        first = time.monotonic()
                        break
                if first is None:
                    error = "No SSE event received"
            except Exception as exc:
                error = str(exc)
            finally:
                if response is not None:
                    try:
                        response.close()
                    except Exception:
                        pass
            results.append({
                "id": model_id,
                "name": model.get("name") or model_id,
                "status": status,
                "ttft_ms": round((first - started) * 1000) if first is not None else None,
                "connect_ms": round((time.monotonic() - started) * 1000),
                "error": error,
            })
        return sorted(results, key=lambda item: item["ttft_ms"] if item["ttft_ms"] is not None else float("inf"))

    def stream_chat(self, messages, model, **kwargs) -> Iterator[dict]:
        """Stream normalized reasoning/content chunks from OpenRouter."""
        request_id = kwargs.pop("request_id", None) or uuid.uuid4().hex
        stop_event = threading.Event()
        with self._stop_lock:
            self._stop_events[request_id] = stop_event

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        payload.update(kwargs)

        started = time.monotonic()
        first_event_at = None
        LOGGER.info("chat start model=%s request_id=%s", model, request_id)
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
                stream=True,
                timeout=self.TIMEOUT,
            )
            with self._stop_lock:
                self._active_responses[request_id] = response
            self._raise_http_error(response)
            LOGGER.info("chat upstream connected model=%s request_id=%s status=%s connect_ms=%.0f", model, request_id, response.status_code, (time.monotonic() - started) * 1000)
            # OpenRouter streams are UTF-8 JSON/SSE. Force the decoder so a
            # provider/proxy charset cannot turn UTF-8 bytes into mojibake.
            response.encoding = "utf-8"

            for raw_line in response.iter_lines(chunk_size=1, decode_unicode=True):
                if stop_event.is_set():
                    yield {"type": "done"}
                    return
                if not raw_line:
                    continue
                if isinstance(raw_line, bytes):
                    raw_line = raw_line.decode("utf-8", errors="replace")
                line = raw_line.strip()
                # SSE metadata/comments are not JSON payloads. Only parse data fields.
                if line.startswith(":") or not line.startswith("data:"):
                    continue
                line = line[5:].strip()
                if line == "[DONE]":
                    LOGGER.info("chat done model=%s request_id=%s first_event_ms=%s total_ms=%.0f", model, request_id, None if first_event_at is None else round((first_event_at - started) * 1000), (time.monotonic() - started) * 1000)
                    yield {"type": "done"}
                    return
                if not line:
                    continue

                if first_event_at is None:
                    first_event_at = time.monotonic()
                    LOGGER.info("chat first_event model=%s request_id=%s first_event_ms=%.0f", model, request_id, (first_event_at - started) * 1000)
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError as exc:
                    yield {"type": "error", "message": f"Invalid SSE JSON: {exc}"}
                    return

                if isinstance(chunk.get("usage"), dict):
                    yield {"type": "usage", "usage": chunk["usage"]}
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}

                reasoning = delta.get("reasoning")
                if reasoning is None:
                    reasoning = delta.get("reasoning_content")
                if reasoning:
                    yield {"type": "reasoning", "content": repair_mojibake(reasoning)}

                content = delta.get("content")
                if content:
                    yield {"type": "content", "content": repair_mojibake(content)}

        except requests.RequestException as exc:
            yield {"type": "error", "message": str(exc)}
        except Exception as exc:
            yield {"type": "error", "message": str(exc)}
        finally:
            LOGGER.info("chat stream closed model=%s request_id=%s total_ms=%.0f", model, request_id, (time.monotonic() - started) * 1000)
            with self._stop_lock:
                active = self._active_responses.pop(request_id, None)
                self._stop_events.pop(request_id, None)
            if active is not None:
                try:
                    active.close()
                except Exception:
                    pass

    def stop_chat(self, request_id) -> bool:
        """Signal an active stream to stop at its next readable chunk."""
        with self._stop_lock:
            event = self._stop_events.get(request_id)
            if event is None:
                return False
            event.set()
            response = self._active_responses.get(request_id)
        if response is not None:
            try:
                response.close()
            except Exception:
                pass
        return True
