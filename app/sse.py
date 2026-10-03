"""Server-Sent Events helpers for YookAI."""

import json

_ALLOWED_TYPES = {"reasoning", "content", "usage", "done", "error"}


def normalize_chunk(chunk: dict) -> dict:
    """Normalize a provider chunk to the public YookAI SSE contract."""
    if not isinstance(chunk, dict):
        return {"type": "error", "message": "Invalid stream chunk"}
    kind = chunk.get("type")
    if kind not in _ALLOWED_TYPES:
        choices = chunk.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            delta = choices[0].get("delta") or {}
            if isinstance(delta, dict):
                if delta.get("reasoning") is not None:
                    return {"type": "reasoning", "content": str(delta.get("reasoning", ""))}
                if delta.get("content") is not None:
                    return {"type": "content", "content": str(delta.get("content", ""))}
        if chunk.get("done") is True:
            return {"type": "done"}
        return {"type": "error", "message": "Unknown stream chunk type"}
    if kind in {"reasoning", "content"}:
        return {"type": kind, "content": str(chunk.get("content", ""))}
    if kind == "usage":
        usage = chunk.get("usage")
        return {"type": "usage", "usage": usage if isinstance(usage, dict) else {}}
    if kind == "error":
        return {"type": "error", "message": str(chunk.get("message", "Unknown error"))}
    return {"type": "done"}


def format_sse(data: dict) -> str:
    """Format one normalized dictionary as an SSE event."""
    return f"data: {json.dumps(normalize_chunk(data), ensure_ascii=False)}\n\n"


class SSEStreamer:
    """Write YookAI SSE events to a file-like HTTP response stream."""

    def __init__(self, wfile):
        self.wfile = wfile
        self.closed = False

    def send_event(self, data: dict):
        """Send one JSON SSE event and flush."""
        if self.closed:
            return
        self.wfile.write(format_sse(data).encode("utf-8"))
        self.wfile.flush()

    def send_raw(self, line: str):
        """Send one raw SSE line and flush."""
        if self.closed:
            return
        self.wfile.write((str(line) + "\n").encode("utf-8"))
        self.wfile.flush()

    def close(self):
        """Mark the SSE writer closed without closing BaseHTTPRequestHandler.wfile.

        ``BaseHTTPRequestHandler`` owns ``wfile`` and flushes it again after the
        request handler returns. Closing it here causes the ``ValueError: I/O
        operation on closed file`` seen in Termux after an SSE request.
        """
        if self.closed:
            return
        try:
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError, ValueError):
            pass
        self.closed = True