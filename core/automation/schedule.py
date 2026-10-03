"""Validated cron-like interval scheduling metadata (no implicit task execution)."""
from __future__ import annotations
from datetime import datetime, timezone
import json, threading, uuid
from pathlib import Path
class ScheduleStore:
    def __init__(self,path:Path): self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self.lock=threading.RLock()
    def _load(self):
        try: x=json.loads(self.path.read_text(encoding='utf-8')); return x if isinstance(x,list) else []
        except (OSError,json.JSONDecodeError): return []
    def create(self,name,interval_minutes,payload=None):
        interval=int(interval_minutes)
        if not 1<=interval<=525600: raise ValueError('interval_minutes must be between 1 and 525600')
        with self.lock:
            rows=self._load(); item={'id':uuid.uuid4().hex,'name':str(name)[:120],'interval_minutes':interval,'payload':payload if isinstance(payload,dict) else {},'enabled':False,'created_at':datetime.now(timezone.utc).isoformat()}; rows.append(item); tmp=self.path.with_suffix('.tmp'); tmp.write_text(json.dumps(rows,indent=2,ensure_ascii=False),encoding='utf-8'); tmp.replace(self.path); return item
    def list(self):
        with self.lock:return self._load()
