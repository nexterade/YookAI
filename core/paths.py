"""Canonical YookAI filesystem paths."""
from pathlib import Path

ROOT = Path.home() / ".yookai"
CONFIG_DIR = ROOT / "config"
SESSIONS_DIR = ROOT / "sessions"
PROMPTS_DIR = ROOT / "prompts"
CACHE_DIR = ROOT / "cache"
MEMORY_DIR = ROOT / "memory"
ATTACHMENTS_DIR = ROOT / "attachments"
WORKSPACE_DIR = ROOT / "workspace"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
PROVIDERS_FILE = CONFIG_DIR / "providers.json"

def ensure_layout():
    for directory in (ROOT, CONFIG_DIR, SESSIONS_DIR, PROMPTS_DIR, CACHE_DIR, MEMORY_DIR, ATTACHMENTS_DIR, WORKSPACE_DIR):
        directory.mkdir(parents=True, exist_ok=True)
    return ROOT

def get_project_root():
    return Path(__file__).resolve().parent.parent
