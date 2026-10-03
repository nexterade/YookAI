"""Small HTTP middleware helpers kept independent from route logic."""
from __future__ import annotations

import json
from typing import Any


def json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
