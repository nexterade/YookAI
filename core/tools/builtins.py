"""Built-in local tools with explicit safety boundaries."""
from __future__ import annotations

import ast
import operator
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any


class ToolExecutionError(Exception):
    pass


class SafeCalculator:
    _ops = {
        ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod, ast.Pow: operator.pow,
        ast.USub: operator.neg, ast.UAdd: operator.pos,
    }

    def evaluate(self, expression: str) -> str:
        if not isinstance(expression, str) or not expression.strip():
            raise ToolExecutionError("expression is required")
        if len(expression) > 500:
            raise ToolExecutionError("expression is too long")
        try:
            tree = ast.parse(expression, mode="eval")
            value = self._eval(tree.body)
        except (SyntaxError, ValueError, TypeError, ZeroDivisionError, OverflowError) as exc:
            raise ToolExecutionError(f"Invalid calculation: {exc}") from exc
        if isinstance(value, float) and not value.is_integer() and abs(value) > 1e100:
            raise ToolExecutionError("result is too large")
        return str(value)

    def _eval(self, node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.UnaryOp) and type(node.op) in self._ops:
            return self._ops[type(node.op)](self._eval(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in self._ops:
            left, right = self._eval(node.left), self._eval(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 1000:
                raise ToolExecutionError("exponent is too large")
            return self._ops[type(node.op)](left, right)
        raise ToolExecutionError("only numeric arithmetic is allowed")


class WorkspaceFS:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, path: str = ".") -> Path:
        if not isinstance(path, str):
            raise ToolExecutionError("path must be a string")
        candidate = (self.root / path).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise ToolExecutionError("path escapes the YookAI workspace") from exc
        return candidate

    def list(self, path=".") -> list[dict[str, Any]]:
        target = self._resolve(path)
        if not target.exists():
            raise ToolExecutionError("path does not exist")
        if not target.is_dir():
            raise ToolExecutionError("path is not a directory")
        out = []
        for item in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))[:500]:
            out.append({"name": item.name, "type": "directory" if item.is_dir() else "file", "size": item.stat().st_size if item.is_file() else None})
        return out

    def read(self, path: str, max_bytes: int = 1_000_000) -> str:
        target = self._resolve(path)
        if not target.is_file():
            raise ToolExecutionError("file does not exist")
        if target.stat().st_size > max_bytes:
            raise ToolExecutionError(f"file exceeds {max_bytes} byte read limit")
        try:
            return target.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ToolExecutionError("file is not UTF-8 text") from exc


class SafeShell:
    """Very small command runner; disabled by default and never invokes a shell."""
    ALLOWED = {"pwd", "ls", "find", "grep", "head", "tail", "wc", "file", "du"}

    def __init__(self, root: Path, timeout=10):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.timeout = int(timeout)

    def execute(self, command: str) -> dict[str, Any]:
        if not isinstance(command, str) or not command.strip():
            raise ToolExecutionError("command is required")
        if len(command) > 500:
            raise ToolExecutionError("command is too long")
        try:
            argv = shlex.split(command)
        except ValueError as exc:
            raise ToolExecutionError(f"invalid command: {exc}") from exc
        if not argv or argv[0] not in self.ALLOWED:
            raise ToolExecutionError(f"command is not allowed; allowed: {', '.join(sorted(self.ALLOWED))}")
        if any(token in command for token in (";", "&&", "||", "|", ">", "<", "`", "$((", "$(")):
            raise ToolExecutionError("shell operators are not allowed")
        for token in argv[1:]:
            if token.startswith("/") or token == ".." or token.startswith("../") or "/../" in token:
                raise ToolExecutionError("absolute paths and parent traversal are not allowed")
        try:
            proc = subprocess.run(argv, cwd=self.root, capture_output=True, text=True, timeout=self.timeout, shell=False)
        except subprocess.TimeoutExpired as exc:
            raise ToolExecutionError(f"command timed out after {self.timeout}s") from exc
        output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        return {"exit_code": proc.returncode, "output": output[:100_000]}
