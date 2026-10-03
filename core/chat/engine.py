"""Chat orchestration boundary.

v0.3 keeps the existing HTTP/API implementation intact while exposing a clean
service boundary. New features should depend on this boundary rather than on
HTTP handlers directly.
"""
from __future__ import annotations

from typing import Any, Iterator


class ChatEngine:
    def __init__(self, api_handler):
        self.api = api_handler

    def stream(self, request: dict[str, Any]) -> Iterator[dict[str, Any]]:
        """Stream a normalized chat request through the existing API service."""
        return self.api.handle_chat(request)

    def stop(self, provider: str, request_id: str) -> dict[str, Any]:
        return self.api.handle_chat_stop({"provider": provider, "request_id": request_id})
