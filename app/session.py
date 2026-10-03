"""Persistent YookAI chat session manager."""

import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.paths import SESSIONS_DIR


_SESSION_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-\d{3}$")
_SESSION_CREATE_LOCK = threading.Lock()


class SessionManager:
    """Create, persist, query, and mutate chat sessions as JSON files."""

    def __init__(self, sessions_dir=SESSIONS_DIR):
        self.sessions_dir = Path(sessions_dir)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _validate_id(session_id: str) -> None:
        if not isinstance(session_id, str) or not _SESSION_ID_RE.fullmatch(session_id):
            raise ValueError(f"Invalid session ID: {session_id!r}")

    def get_session_path(self, session_id: str) -> Path:
        """Return the canonical JSON path for a validated session ID."""
        self._validate_id(session_id)
        return self.sessions_dir / f"{session_id}.json"

    def _next_id(self) -> str:
        today = datetime.now().strftime("%Y-%m-%d")
        existing = []
        prefix = f"{today}-"
        for path in self.sessions_dir.glob(f"{today}-*.json"):
            suffix = path.stem[len(prefix):]
            if suffix.isdigit() and len(suffix) == 3:
                existing.append(int(suffix))
        return f"{today}-{(max(existing, default=0) + 1):03d}"

    def create_session(self, title="New Chat", provider=None, model=None) -> dict[str, Any]:
        """Create, persist, and return a new session dictionary."""
        with _SESSION_CREATE_LOCK:
            now = self._now()
            session = {
                "schema_version": 2,
                "id": self._next_id(),
                "title": title,
                "provider": provider,
                "model": model,
                "created_at": now,
                "updated_at": now,
                "messages": [],
                "metadata": {},
            }
            self.save_session(session)
            return session

    def save_session(self, session: dict[str, Any]) -> dict[str, Any]:
        """Validate and persist a session, updating its timestamp."""
        if not isinstance(session, dict) or "id" not in session:
            raise ValueError("Session must be a dictionary containing id")
        session_id = session["id"]
        path = self.get_session_path(session_id)
        session.setdefault("schema_version", 2)
        session.setdefault("messages", [])
        session.setdefault("metadata", {})
        session.setdefault("model_config", {})
        session.setdefault("routing", {})
        session.setdefault("title", "New Chat")
        session.setdefault("provider", None)
        session.setdefault("model", None)
        session.setdefault("created_at", self._now())
        session["updated_at"] = self._now()

        temp_path = path.with_name(f".{path.name}.{threading.get_ident()}.{uuid.uuid4().hex}.tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(session, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        temp_path.replace(path)
        return session

    def load_session(self, session_id: str) -> dict[str, Any]:
        """Load one session or raise FileNotFoundError/ValueError."""
        path = self.get_session_path(session_id)
        if not path.exists():
            raise FileNotFoundError(f"Session not found: {session_id}")
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Corrupt session JSON: {session_id}") from exc
        if not isinstance(data, dict):
            raise ValueError(f"Corrupt session JSON: {session_id}")
        return data

    def list_sessions(self) -> list[dict[str, Any]]:
        """Load all valid session JSON files sorted newest by updated_at."""
        sessions = []
        for path in self.sessions_dir.glob("*.json"):
            try:
                session = self.load_session(path.stem)
            except (ValueError, FileNotFoundError):
                continue
            sessions.append(session)
        sessions.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        return sessions

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and return whether the file existed."""
        path = self.get_session_path(session_id)
        if not path.exists():
            return False
        path.unlink()
        return True

    def rename_session(self, session_id: str, new_title: str) -> bool:
        """Rename an existing session."""
        session = self.load_session(session_id)
        session["title"] = str(new_title)
        self.save_session(session)
        return True

    def add_message(self, session_id: str, role: str, content: str, **extra) -> dict[str, Any]:
        """Append a message and optionally auto-title a new session from its first user message."""
        session = self.load_session(session_id)
        message = {"role": role, "content": content}
        message.update(extra)
        session.setdefault("messages", []).append(message)

        if role == "user" and len(session["messages"]) == 1 and session.get("title") == "New Chat":
            auto_title = session.get("metadata", {}).get("auto_title", True)
            if auto_title:
                normalized = " ".join(str(content).split())
                session["title"] = normalized[:80] or "New Chat"

        self.save_session(session)
        return message
