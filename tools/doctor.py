"""YookAI local diagnostics command."""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow ``python tools/doctor.py`` when launched from the project root.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.paths import ensure_layout, ROOT, CONFIG_DIR, SESSIONS_DIR, ATTACHMENTS_DIR
from core.config import ensure_config, load_config


def collect() -> dict:
    ensure_layout()
    settings = ensure_config()
    config = load_config()
    return {
        "version": config.get("version"),
        "python": __import__("sys").version.split()[0],
        "root": str(ROOT),
        "config": str(settings),
        "directories": {
            "config": CONFIG_DIR.exists(),
            "sessions": SESSIONS_DIR.exists(),
            "attachments": ATTACHMENTS_DIR.exists(),
        },
        "providers": sorted((config.get("provider") or {}).keys()),
    }


def main() -> int:
    print(json.dumps(collect(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
