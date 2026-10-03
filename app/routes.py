"""Application-level API route logic for YookAI."""

from copy import deepcopy
import json
import zipfile
import io
from collections.abc import Iterator

from core.config import save_config
from core.attachments import AttachmentStore
from core.memory import MemoryStore
from providers.registry import get_provider, list_providers, provider_specs
from core.models.catalog import ModelCatalog
from core.providers.health import ProviderHealthChecker
from core.providers.benchmark import BenchmarkRunner
from core.routing import SmartRouter
from core.latency import put_result
from core.tools import ToolEngine
from core.tools.builtins import ToolExecutionError
from providers.errors import ProviderHTTPError

from .session import SessionManager


class HTTPError(Exception):
    """Expected API error carrying an HTTP status and safe message."""

    def __init__(self, status: int, message: str):
        self.status = int(status)
        self.message = str(message)
        super().__init__(self.message)


class APIHandler:
    """Implement API operations independently from HTTP transport."""

    def __init__(self, config: dict, session_manager=None, memory_store=None, attachment_store=None):
        self.config = config
        self.sessions = session_manager or SessionManager()
        self.memory = memory_store or MemoryStore()
        self.attachments = attachment_store or AttachmentStore()
        self._provider_cache = {}
        self.tools = ToolEngine(config)

    def _get_provider(self, name):
        try:
            settings = self.config.get("provider", {}).get(name, {})
            if not isinstance(settings, dict):
                settings = {}
            cache_key = (name, settings.get("api_key", ""), settings.get("base_url", ""))
            cached = self._provider_cache.get(name)
            if cached and cached[0] == cache_key:
                return cached[1]
            defaults = {
                "openrouter": "https://openrouter.ai/api/v1",
                "openai": "https://api.openai.com/v1",
                "anthropic": "https://api.anthropic.com/v1",
                "gemini": "https://generativelanguage.googleapis.com/v1beta",
                "ollama": "http://127.0.0.1:11434",
            }
            provider = get_provider(
                name,
                api_key=settings.get("api_key", ""),
                base_url=settings.get("base_url") or defaults.get(name, ""),
            )
            self._provider_cache[name] = (cache_key, provider)
            return provider
        except ValueError as exc:
            raise HTTPError(404, str(exc)) from exc

    def handle_tools(self):
        return {"tools": self.tools.list_tools()}

    def handle_tool_execute(self, body):
        if not isinstance(body, dict):
            raise HTTPError(400, "Request body must be an object")
        tool = body.get("tool")
        if not isinstance(tool, str) or not tool.strip():
            raise HTTPError(400, "tool is required")
        try:
            return self.tools.execute(tool.strip(), body.get("args") or {}, body.get("confirmation_token"))
        except ToolExecutionError as exc:
            raise HTTPError(400, str(exc)) from exc

    def handle_provider_specs(self):
        specs = {item["name"]: item for item in provider_specs()}
        for name, spec in specs.items():
            settings = self.config.get("provider", {}).get(name, {})
            spec["configured"] = bool(settings.get("api_key") or (name == "ollama" and settings.get("base_url")))
        return {"providers": list(specs.values())}

    def handle_catalog(self, provider_names=None):
        names = provider_names or list_providers()
        catalog = ModelCatalog(self._get_provider, names)
        models = []
        errors = []
        for name in names:
            try:
                models.extend(catalog.serialize([name]))
            except Exception as exc:
                errors.append({"provider": name, "error": str(exc)})
        return {"models": models, "errors": errors}

    def handle_provider_health(self, provider_name=None):
        checker = ProviderHealthChecker(self._get_provider)
        names = [provider_name] if provider_name else list_providers()
        return {"health": [item.to_dict() for item in checker.check_all(names)]}

    def handle_benchmark(self, provider_name, max_candidates=8):
        if provider_name not in list_providers():
            raise HTTPError(404, f"Unknown provider: {provider_name}")
        try:
            results = BenchmarkRunner(self._get_provider).run_provider(provider_name, max_candidates=max_candidates)
        except Exception as exc:
            raise HTTPError(502, str(exc)) from exc
        best = BenchmarkRunner.best(results)
        settings = self.config.get("provider", {}).get(provider_name, {})
        put_result(provider_name, settings.get("base_url", ""), {"results": results, "best": best})
        return {"provider": provider_name, "results": results, "best": best, "cached": True}

    def handle_models(self, provider_name):
        """Return normalized models for a provider."""
        settings = self.config.get("provider", {}).get(provider_name, {})
        provider = self._get_provider(provider_name)
        if provider_name != "ollama" and not settings.get("api_key"):
            raise HTTPError(503, f"{provider_name.title()} API key is not configured")
        try:
            return {"models": provider.list_models()}
        except ProviderHTTPError as exc:
            raise HTTPError(exc.status_code or 502, str(exc)) from exc
        except Exception as exc:
            message = str(exc)
            status = 503 if "authentication" in message.lower() or "api key" in message.lower() else 502
            raise HTTPError(status, message) from exc

    def _memory_settings(self):
        memory = self.config.get("memory", {})
        return (
            memory.get("mode", "default") if isinstance(memory, dict) else "default",
            memory.get("project_id", "default") if isinstance(memory, dict) else "default",
            int(memory.get("retrieval_limit", 12)) if isinstance(memory, dict) and str(memory.get("retrieval_limit", "12")).isdigit() else 12,
        )

    def _prepare_messages(self, messages, session_id=None):
        prepared = []
        for message in messages:
            if not isinstance(message, dict):
                raise HTTPError(400, "Each message must be an object")
            role = message.get("role")
            if role not in {"system", "user", "assistant"}:
                raise HTTPError(400, f"Invalid message role: {role!r}")
            content = message.get("content", "")
            if not isinstance(content, (str, list)):
                raise HTTPError(400, "message.content must be a string or content list")
            item = dict(message)
            attachments = message.get("attachments") or []
            if attachments:
                if not isinstance(attachments, list) or len(attachments) > 10:
                    raise HTTPError(400, "attachments must be a list of at most 10 items")
                blocks = []
                if isinstance(content, str) and content:
                    blocks.append({"type": "text", "text": content})
                for attachment in attachments:
                    if not isinstance(attachment, dict) or not attachment.get("id"):
                        raise HTTPError(400, "Invalid attachment metadata")
                    try:
                        meta = self.attachments.get(attachment["id"])
                    except (ValueError, FileNotFoundError) as exc:
                        raise HTTPError(400, str(exc)) from exc
                    mime = meta["mime"]
                    if mime.startswith("image/"):
                        import base64
                        encoded = base64.b64encode(self.attachments.read(meta["id"])).decode("ascii")
                        blocks.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}})
                    else:
                        extracted = self.attachments.read_text(meta["id"])
                        if extracted:
                            blocks.append({"type": "text", "text": f"Attachment {meta['name']}:\n{extracted}"})
                        else:
                            blocks.append({"type": "text", "text": f"Attachment: {meta['name']} ({mime}, {meta['size']} bytes). Content is stored locally but not text-extractable."})
                item["content"] = blocks
            item.pop("attachments", None)
            prepared.append(item)

        mode, project_id, limit = self._memory_settings()
        query = next((m.get("content", "") for m in reversed(messages) if m.get("role") == "user" and isinstance(m.get("content"), str)), "")
        if query:
            memory_context = self.memory.build_context(query, mode, project_id, session_id, limit)
            if memory_context:
                prepared.insert(0, {"role": "system", "content": memory_context})
        return prepared

    def _provider_options(self, provider_name, options):
        kwargs = dict(options)
        system_prompt = kwargs.pop("system_prompt", "")
        if system_prompt and not isinstance(system_prompt, str):
            raise HTTPError(400, "options.system_prompt must be a string")
        if kwargs.get("reasoning_effort") == "auto":
            kwargs.pop("reasoning_effort", None)
        if provider_name == "gemini" and "max_tokens" in kwargs:
            kwargs["max_output_tokens"] = kwargs.pop("max_tokens")
        if provider_name == "ollama":
            ollama_options = {}
            for key in ("temperature", "top_p", "top_k", "num_predict", "repeat_penalty"):
                if key in kwargs:
                    ollama_options[key] = kwargs.pop(key)
            if "max_tokens" in kwargs:
                ollama_options["num_predict"] = kwargs.pop("max_tokens")
            if ollama_options:
                kwargs["options"] = {**(kwargs.get("options") or {}), **ollama_options}
        return kwargs, system_prompt

    def _stream_with_fallback(self, prepared, options, decision):
        candidates = decision.candidates
        last_error = None
        for index, candidate in enumerate(candidates):
            provider_name = candidate.provider
            settings = self.config.get("provider", {}).get(provider_name, {})
            try:
                if provider_name != "ollama" and not settings.get("api_key"):
                    raise RuntimeError(f"{provider_name.title()} API key is not configured")
                provider = self._get_provider(provider_name)
                kwargs, system_prompt = self._provider_options(provider_name, options)
                if system_prompt.strip():
                    request_messages = list(prepared)
                    request_messages.insert(0, {"role": "system", "content": system_prompt.strip()})
                else:
                    request_messages = prepared
                request_id = kwargs.get("request_id")
                if provider_name == "openrouter":
                    kwargs.setdefault("stream_options", {"include_usage": True})
                stream = provider.stream_chat(request_messages, candidate.model, **kwargs)
                emitted = False
                for chunk in stream:
                    if isinstance(chunk, dict) and chunk.get("type") == "error" and not emitted and index < len(candidates) - 1:
                        last_error = RuntimeError(str(chunk.get("message", "provider returned an error")))
                        break
                    if isinstance(chunk, dict) and chunk.get("type") in {"content", "reasoning", "usage", "done"}:
                        emitted = emitted or chunk.get("type") in {"content", "reasoning"}
                    yield chunk
                else:
                    return
                if request_id:
                    try:
                        provider.stop_chat(request_id)
                    except Exception:
                        pass
            except Exception as exc:
                last_error = exc
                if index >= len(candidates) - 1:
                    break
                continue
        if last_error:
            yield {"type": "error", "message": f"All selected AI routes failed: {last_error}"}

    def handle_chat(self, body) -> Iterator[dict]:
        """Validate a chat request and stream through explicit or automatic routing."""
        if not isinstance(body, dict):
            raise HTTPError(400, "Request body must be a JSON object")
        messages = body.get("messages")
        model = body.get("model")
        if model is not None and (not isinstance(model, str) or not model.strip()):
            raise HTTPError(400, "model must be a non-empty string when supplied")
        provider_name = body.get("provider")
        if provider_name is not None and (not isinstance(provider_name, str) or not provider_name.strip()):
            raise HTTPError(400, "provider must be a string when supplied")
        explicit_route = isinstance(model, str) and bool(model.strip()) and model.strip().lower() != "auto"
        if explicit_route or provider_name:
            effective_provider = provider_name or self.config.get("provider", {}).get("default", "openrouter")
            if effective_provider not in list_providers():
                raise HTTPError(404, f"Unknown provider: {effective_provider}")
            settings = self.config.get("provider", {}).get(effective_provider, {})
            if effective_provider != "ollama" and not settings.get("api_key"):
                raise HTTPError(503, f"{effective_provider.title()} API key is not configured")
        if not isinstance(messages, list) or not messages:
            raise HTTPError(400, "messages must be a non-empty list")
        options = body.get("options") or {}
        if not isinstance(options, dict):
            raise HTTPError(400, "options must be an object")
        # Build the request context once; automatic routing happens before provider I/O.
        prepared = self._prepare_messages(messages, body.get("session_id"))
        if provider_name and provider_name not in list_providers():
            raise HTTPError(404, f"Unknown provider: {provider_name}")
        if provider_name:
            settings = self.config.get("provider", {}).get(provider_name, {})
            if provider_name != "ollama" and not settings.get("api_key"):
                raise HTTPError(503, f"{provider_name.title()} API key is not configured")
        try:
            decision = SmartRouter(self.config, self._get_provider, list_providers()).decide(
                {**body, "model": model, "provider": provider_name}, health_by_provider=None
            )
        except ValueError as exc:
            raise HTTPError(503, str(exc)) from exc
        # The router deliberately owns model choice; the selected provider/model are
        # injected into the stream without mutating the caller's body.
        route_options = dict(options)
        request_id = body.get("request_id")
        if request_id is not None:
            if not isinstance(request_id, str) or not request_id:
                raise HTTPError(400, "request_id must be a non-empty string")
            route_options["request_id"] = request_id
        # Explicit model/provider paths return a single candidate; automatic paths
        # may transparently fail over before the first token is emitted.
        return self._stream_with_fallback(prepared, route_options, decision)

    def handle_chat_stop(self, body):
        """Signal cancellation for an active provider request."""
        if not isinstance(body, dict) or not isinstance(body.get("request_id"), str) or not body["request_id"]:
            raise HTTPError(400, "request_id must be a non-empty string")
        name = body.get("provider") or self.config.get("provider", {}).get("default", "openrouter")
        if not isinstance(name, str) or not name:
            raise HTTPError(400, "provider must be a string")
        return {"ok": True, "stopped": self._get_provider(name).stop_chat(body["request_id"])}

    def handle_attachment_upload(self, filename, mime, data):
        if not filename:
            raise HTTPError(400, "Attachment filename is required")
        if not isinstance(data, (bytes, bytearray)) or not data:
            raise HTTPError(400, "Attachment is empty")
        try:
            return self.attachments.save(filename, mime, bytes(data))
        except ValueError as exc:
            raise HTTPError(413 if "20 MB" in str(exc) else 400, str(exc)) from exc

    def handle_session_list(self):
        """Return compact session metadata."""
        return {"sessions": [
            {"id": s["id"], "title": s.get("title", "New Chat"), "updated_at": s.get("updated_at")}
            for s in self.sessions.list_sessions()
        ]}

    def handle_session_save(self, body):
        """Create or update a persisted session."""
        if not isinstance(body, dict):
            raise HTTPError(400, "Request body must be a JSON object")
        messages = body.get("messages", [])
        if not isinstance(messages, list):
            raise HTTPError(400, "messages must be a list")
        session_id = body.get("id")
        if session_id is None:
            provider = body.get("provider") or self.config.get("provider", {}).get("default", "openrouter")
            model = body.get("model") or self.config.get("chat", {}).get("default_model")
            session = self.sessions.create_session(body.get("title", "New Chat"), provider, model)
        else:
            try:
                session = self.sessions.load_session(session_id)
            except ValueError as exc:
                raise HTTPError(400, str(exc)) from exc
            except FileNotFoundError as exc:
                raise HTTPError(404, str(exc)) from exc
        for key in ("title", "provider", "model", "model_config", "metadata"):
            if key in body:
                session[key] = body[key]
        session["messages"] = messages
        if session.get("title") in (None, "", "New Chat"):
            first_user = next((m for m in messages if isinstance(m, dict) and m.get("role") == "user"), None)
            if first_user and isinstance(first_user.get("content"), str):
                title = " ".join(first_user["content"].split())[:80]
                if title:
                    session["title"] = title
        self.sessions.save_session(session)
        mode, project_id, _ = self._memory_settings()
        self.memory.upsert_session(session["id"], messages, mode, project_id)
        return {"ok": True, "id": session["id"]}

    def handle_memory_list(self, query="", mode=None, project_id=None):
        default_mode, default_project, _ = self._memory_settings()
        return {"records": self.memory.list_records(mode or default_mode, project_id or default_project, query=query, limit=300)}

    def handle_memory_delete(self, record_id, mode=None, project_id=None):
        default_mode, default_project, _ = self._memory_settings()
        if not self.memory.delete_record(record_id, mode or default_mode, project_id or default_project):
            raise HTTPError(404, "Memory record not found")
        return {"ok": True}

    def handle_memory_clear(self, mode=None, project_id=None):
        default_mode, default_project, _ = self._memory_settings()
        self.memory.clear(mode or default_mode, project_id or default_project)
        return {"ok": True}

    def handle_attachment_list(self):
        return {"attachments": self.attachments.list()}

    def handle_attachment_delete(self, attachment_id):
        if not self.attachments.delete(attachment_id):
            raise HTTPError(404, "Attachment not found")
        return {"ok": True}

    def handle_attachment_cleanup(self):
        refs=[]
        for session in self.sessions.list_sessions():
            for message in session.get("messages", []):
                refs.extend(a.get("id") for a in (message.get("attachments") or []) if isinstance(a,dict) and a.get("id"))
        return {"ok": True, "removed": self.attachments.cleanup_orphans(refs)}

    def handle_export_session(self, session_id):
        session=self.handle_session_get(session_id)
        payload=json.dumps(session,ensure_ascii=False,indent=2).encode("utf-8")
        return {"filename": f"{session_id}.json", "content": payload.decode("utf-8")}

    def handle_import_session(self, body):
        if not isinstance(body,dict): raise HTTPError(400,"Request body must be an object")
        raw=body.get("session")
        if not isinstance(raw,dict): raise HTTPError(400,"session must be an object")
        messages=raw.get("messages",[])
        if not isinstance(messages,list): raise HTTPError(400,"session.messages must be a list")
        session=self.sessions.create_session(raw.get("title","Imported Chat"),raw.get("provider"),raw.get("model"))
        session["messages"]=messages; session["metadata"]={**(raw.get("metadata") or {}),"imported":True}; self.sessions.save_session(session)
        mode,project,_=self._memory_settings(); self.memory.upsert_session(session["id"],messages,mode,project)
        return {"ok":True,"id":session["id"]}

    def handle_session_stats(self, session_id):
        try:
            session = self.sessions.load_session(session_id)
        except ValueError as exc:
            raise HTTPError(400, str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPError(404, str(exc)) from exc
        messages = [m for m in session.get("messages", []) if isinstance(m, dict)]
        users = [m for m in messages if m.get("role") == "user"]
        assistants = [m for m in messages if m.get("role") == "assistant"]
        def chars(items):
            return sum(len(str(m.get("content", ""))) for m in items)
        def est_tokens(items):
            return sum(max(0, (len(str(m.get("content", ""))) + 3) // 4) for m in items)
        actual_input = sum(int((m.get("usage") or {}).get("prompt_tokens", 0) or 0) for m in assistants)
        actual_output = sum(int((m.get("usage") or {}).get("completion_tokens", 0) or 0) for m in assistants)
        total_cost = 0.0
        for m in assistants:
            usage=m.get("usage") or {}; pricing=m.get("model_pricing") or {}
            try:
                prompt_rate=float(pricing.get("prompt",0) or 0); completion_rate=float(pricing.get("completion",0) or 0)
                total_cost += int(usage.get("prompt_tokens",0) or 0) / 1_000_000 * prompt_rate
                total_cost += int(usage.get("completion_tokens",0) or 0) / 1_000_000 * completion_rate
            except (TypeError,ValueError): pass
        timestamps = [m.get("created_at") for m in messages if m.get("created_at")]
        completed = [m.get("completed_at") for m in messages if m.get("completed_at")]
        from datetime import datetime
        def parse(value):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except (AttributeError, ValueError):
                return None
        starts = [parse(v) for v in timestamps]
        ends = [parse(v) for v in completed]
        valid = [v for v in starts + ends if v]
        duration_ms = int((max(valid) - min(valid)).total_seconds() * 1000) if len(valid) >= 2 else 0
        attachments = sum(len(m.get("attachments") or []) for m in messages)
        return {
            "session_id": session["id"],
            "title": session.get("title", "New Chat"),
            "message_count": len(messages),
            "user_messages": len(users),
            "assistant_messages": len(assistants),
            "character_count": chars(messages),
            "user_character_count": chars(users),
            "assistant_character_count": chars(assistants),
            "estimated_tokens": est_tokens(messages),
            "estimated_input_tokens": est_tokens(users),
            "estimated_output_tokens": est_tokens(assistants),
            "actual_input_tokens": actual_input,
            "actual_output_tokens": actual_output,
            "actual_total_tokens": actual_input + actual_output,
            "estimated_cost_usd": round(total_cost, 8),
            "duration_ms": max(0, duration_ms),
            "attachment_count": attachments,
            "created_at": session.get("created_at"),
            "updated_at": session.get("updated_at"),
        }

    def handle_session_get(self, session_id):
        try:
            return self.sessions.load_session(session_id)
        except ValueError as exc:
            raise HTTPError(400, str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPError(404, str(exc)) from exc

    def handle_session_delete(self, session_id):
        try:
            deleted = self.sessions.delete_session(session_id)
        except ValueError as exc:
            raise HTTPError(400, str(exc)) from exc
        if not deleted:
            raise HTTPError(404, f"Session not found: {session_id}")
        return {"ok": True}

    @staticmethod
    def _mask_api_key(value):
        if not value:
            return ""
        value = str(value)
        return "***" if len(value) <= 8 else value[:7] + "***" + value[-4:]

    @classmethod
    def _sanitize_secrets(cls, value):
        if isinstance(value, dict):
            result = {}
            for key, item in value.items():
                if key.lower() in {"api_key", "apikey", "access_token", "auth_token", "password", "secret"}:
                    result[key] = cls._mask_api_key(item)
                else:
                    result[key] = cls._sanitize_secrets(item)
            return result
        if isinstance(value, list):
            return [cls._sanitize_secrets(item) for item in value]
        return value

    def handle_config_get(self):
        """Return configuration with all credential-like fields masked."""
        return self._sanitize_secrets(deepcopy(self.config))

    @staticmethod
    def _preserve_masked_secrets(incoming, current):
        if not isinstance(incoming, dict) or not isinstance(current, dict):
            return
        secret_keys = {"api_key", "apikey", "access_token", "auth_token", "password", "secret"}
        for key, value in list(incoming.items()):
            if key.lower() in secret_keys:
                if isinstance(value, str) and "***" in value:
                    old = current.get(key)
                    if old:
                        incoming[key] = old
                    else:
                        incoming.pop(key, None)
                continue
            if isinstance(value, dict) and isinstance(current.get(key), dict):
                APIHandler._preserve_masked_secrets(value, current[key])
            elif isinstance(value, list) and isinstance(current.get(key), list):
                for new_item, old_item in zip(value, current[key]):
                    APIHandler._preserve_masked_secrets(new_item, old_item)

    def handle_config_save(self, body):
        """Persist configuration while preserving masked credentials."""
        if not isinstance(body, dict):
            raise HTTPError(400, "Request body must be a JSON object")
        incoming = deepcopy(body)
        self._preserve_masked_secrets(incoming, self.config)
        try:
            save_config(incoming)
        except (ValueError, OSError) as exc:
            raise HTTPError(400, str(exc)) from exc
        self.config.clear()
        self.config.update(incoming)
        self._provider_cache.clear()
        return {"ok": True}