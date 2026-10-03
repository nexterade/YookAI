"""Small persistent task ledger for resumable user-visible background work."""
from __future__ import annotations
import json, threading, uuid
from datetime import datetime, timezone
from pathlib import Path

class TaskStore:
    STATES={'queued','running','completed','failed','cancelled'}
    def __init__(self,path:Path): self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True); self.lock=threading.RLock()
    def _load(self):
        try: v=json.loads(self.path.read_text(encoding='utf-8')); return v if isinstance(v,list) else []
        except (OSError,json.JSONDecodeError): return []
    def _save(self,rows):
        tmp=self.path.with_suffix('.tmp'); tmp.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8'); tmp.replace(self.path)
    def create(self,kind,payload=None):
        with self.lock:
            rows=self._load(); now=datetime.now(timezone.utc).isoformat(); item={'id':uuid.uuid4().hex,'kind':str(kind)[:80],'payload':payload if isinstance(payload,dict) else {},'status':'queued','created_at':now,'updated_at':now,'result':None,'error':None}; rows.append(item); self._save(rows); return item
    def update(self,task_id,status,result=None,error=None):
        if status not in self.STATES: raise ValueError('invalid task status')
        with self.lock:
            rows=self._load()
            for item in rows:
                if item['id']==task_id:
                    if item['status'] in {'completed','failed','cancelled'}: raise ValueError('terminal task cannot be changed')
                    item.update(status=status,result=result,error=str(error)[:2000] if error else None,updated_at=datetime.now(timezone.utc).isoformat()); self._save(rows); return item
            raise KeyError(task_id)
    def list(self):
        with self.lock: return list(reversed(self._load()))
