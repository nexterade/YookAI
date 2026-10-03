"""Configuration loading and validation for YookAI."""
import json
import uuid
from pathlib import Path
from typing import Any
from . import paths

_REQUIRED_PATHS = (("provider",),("provider","default"),("chat",),("chat","default_model"),("ui",),("server",),("server","host"),("server","port"))

def _read_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        data=json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Configuration must be a JSON object: {path}")
    return data

def validate_config(data: dict[str, Any]):
    if not isinstance(data, dict):
        raise ValueError("Configuration must be a JSON object")
    for key_path in _REQUIRED_PATHS:
        current: Any=data
        for key in key_path:
            if not isinstance(current, dict) or key not in current:
                raise ValueError(f"Missing required config key: {'.'.join(key_path)}")
            current=current[key]
    port = data["server"]["port"]
    if isinstance(port, bool) or not isinstance(port, int):
        raise ValueError("Config key server.port must be an integer")
    if not 1 <= port <= 65535:
        raise ValueError("Config key server.port must be between 1 and 65535")
    if not isinstance(data["server"]["host"], str) or not data["server"]["host"].strip():
        raise ValueError("Config key server.host must be a non-empty string")
    if not isinstance(data["provider"], dict) or not isinstance(data["chat"], dict) or not isinstance(data["ui"], dict) or not isinstance(data["server"], dict):
        raise ValueError("Configuration sections must be JSON objects")
    if not isinstance(data["provider"]["default"], str) or not data["provider"]["default"].strip():
        raise ValueError("Config key provider.default must be a non-empty string")
    if not isinstance(data["chat"]["default_model"], str) or not data["chat"]["default_model"].strip():
        raise ValueError("Config key chat.default_model must be a non-empty string")
    memory = data.get("memory", {})
    if not isinstance(memory, dict):
        raise ValueError("Config section memory must be an object")
    mode = memory.get("mode", "default")
    if mode not in {"default", "project-only"}:
        raise ValueError("Config key memory.mode must be 'default' or 'project-only'")
    retrieval_limit = memory.get("retrieval_limit", 12)
    if isinstance(retrieval_limit, bool) or not isinstance(retrieval_limit, int) or not 1 <= retrieval_limit <= 100:
        raise ValueError("Config key memory.retrieval_limit must be an integer between 1 and 100")
    project_id = memory.get("project_id", "default")
    if not isinstance(project_id, str) or not project_id.strip():
        raise ValueError("Config key memory.project_id must be a non-empty string")
    return data

def load_config():
    if not paths.SETTINGS_FILE.exists():
        raise FileNotFoundError(f"Config file not found: {paths.SETTINGS_FILE}")
    return validate_config(_read_json(paths.SETTINGS_FILE))

def save_config(data):
    validate_config(data)
    paths.ensure_layout()
    temp_path = paths.SETTINGS_FILE.with_name(f".{paths.SETTINGS_FILE.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        temp_path.replace(paths.SETTINGS_FILE)
    finally:
        temp_path.unlink(missing_ok=True)
    return paths.SETTINGS_FILE

def load_providers():
    if not paths.PROVIDERS_FILE.exists():
        return {}
    return _read_json(paths.PROVIDERS_FILE)

def save_providers(data):
    if not isinstance(data, dict):
        raise ValueError("Providers configuration must be a JSON object")
    paths.ensure_layout()
    temp_path = paths.PROVIDERS_FILE.with_name(f".{paths.PROVIDERS_FILE.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        temp_path.replace(paths.PROVIDERS_FILE)
    finally:
        temp_path.unlink(missing_ok=True)
    return paths.PROVIDERS_FILE

def ensure_config():
    paths.ensure_layout()
    if paths.SETTINGS_FILE.exists():
        validate_config(_read_json(paths.SETTINGS_FILE))
        return paths.SETTINGS_FILE
    source=paths.get_project_root() / "config.example.json"
    if not source.exists():
        raise FileNotFoundError(f"Config template not found: {source}")
    data=_read_json(source)
    validate_config(data)
    save_config(data)
    return paths.SETTINGS_FILE
