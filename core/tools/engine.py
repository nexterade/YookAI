"""Tool orchestration, permissions, and confirmation tokens."""
from __future__ import annotations

import secrets
import threading
import time
from pathlib import Path
from typing import Any

from core.paths import ROOT
from .builtins import SafeCalculator, SafeShell, ToolExecutionError, WorkspaceFS
from .registry import ToolRegistry, ToolSpec


class ToolEngine:
    def __init__(self, config: dict[str, Any], workspace: Path | None = None):
        self.config = config
        self.workspace = Path(workspace or (ROOT / "workspace")).resolve()
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.registry = ToolRegistry()
        self._tokens: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()
        calculator = SafeCalculator()
        fs = WorkspaceFS(self.workspace)
        shell_cfg = (config.get("tools") or {}).get("shell") or {}
        shell = SafeShell(self.workspace, timeout=int(shell_cfg.get("timeout", 10)))
        self.shell_enabled = bool(shell_cfg.get("enabled", False))
        self.registry.register(ToolSpec("calculator", "Evaluate safe numeric arithmetic", calculator.evaluate, requires_confirmation=False))
        self.registry.register(ToolSpec("filesystem.list", "List files inside the YookAI workspace", fs.list, requires_confirmation=False))
        self.registry.register(ToolSpec("filesystem.read", "Read UTF-8 text inside the YookAI workspace", fs.read, requires_confirmation=False))
        if self.shell_enabled:
            self.registry.register(ToolSpec("shell", "Run a small allowlisted command inside the YookAI workspace", shell.execute, requires_confirmation=True))

    def list_tools(self) -> list[dict[str, Any]]:
        return [{"name": s.name, "description": s.description, "requires_confirmation": s.requires_confirmation} for s in self.registry.list()]

    def issue_confirmation(self, tool_name: str) -> str:
        spec = self.registry.get(tool_name)
        if spec is None:
            raise ToolExecutionError("unknown tool")
        token = secrets.token_urlsafe(24)
        with self._lock:
            self._tokens[token] = (tool_name, time.monotonic() + 120)
            self._prune()
        return token

    def _prune(self):
        now = time.monotonic()
        self._tokens = {k: v for k, v in self._tokens.items() if v[1] > now}

    def _consume(self, token: str | None, tool_name: str) -> bool:
        if not token:
            return False
        with self._lock:
            item = self._tokens.pop(token, None)
        return bool(item and item[0] == tool_name and item[1] > time.monotonic())

    def execute(self, tool_name: str, args: dict[str, Any] | None = None, confirmation_token: str | None = None) -> dict[str, Any]:
        spec = self.registry.get(tool_name)
        if spec is None:
            raise ToolExecutionError(f"Unknown tool: {tool_name}")
        args = args or {}
        if not isinstance(args, dict):
            raise ToolExecutionError("args must be an object")
        if spec.requires_confirmation and not self._consume(confirmation_token, tool_name):
            return {"status": "confirmation_required", "tool": tool_name, "confirmation_token": self.issue_confirmation(tool_name)}
        try:
            result = spec.handler(**args)
        except TypeError as exc:
            raise ToolExecutionError(str(exc)) from exc
        return {"status": "ok", "tool": tool_name, "result": result}
