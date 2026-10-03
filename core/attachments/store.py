"""Secure local attachment storage and lifecycle management."""
from __future__ import annotations
import json,mimetypes,re,uuid
from pathlib import Path
from typing import Any
from core import paths
from core.documents import DocumentExtractor
class AttachmentStore:
    MAX_BYTES=20*1024*1024
    def __init__(self,root:Path|None=None): self.root=Path(root or paths.ATTACHMENTS_DIR); self.root.mkdir(parents=True,exist_ok=True)
    @staticmethod
    def _safe_name(name):
        name=Path(name or 'attachment').name; name=re.sub(r'[^A-Za-z0-9._ -]+','_',name).strip(' .'); return name[:180] or 'attachment'
    def save(self,filename,mime,data):
        if len(data)>self.MAX_BYTES: raise ValueError('Attachment exceeds the 20 MB limit')
        aid=uuid.uuid4().hex; name=self._safe_name(filename); detected=mime or mimetypes.guess_type(name)[0] or 'application/octet-stream'
        (self.root/f'{aid}.bin').write_bytes(data)
        meta={'id':aid,'name':name,'mime':detected,'size':len(data),'created_at':__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()}
        meta['document']=DocumentExtractor.extract(meta,data)
        (self.root/f'{aid}.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); return meta
    def get(self,aid):
        if not re.fullmatch(r'[0-9a-f]{32}',str(aid)): raise ValueError('Invalid attachment ID')
        mp=self.root/f'{aid}.json'; dp=self.root/f'{aid}.bin'
        if not mp.exists() or not dp.exists(): raise FileNotFoundError(f'Attachment not found: {aid}')
        data=json.loads(mp.read_text(encoding='utf-8')); data['path']=dp; return data
    def read(self,aid): return self.get(aid)['path'].read_bytes()
    def read_text(self,aid,max_chars=120000): return str(self.get(aid).get('document',{}).get('text',''))[:max_chars]
    def list(self,limit=500):
        out=[]
        for p in self.root.glob('*.json'):
            try: out.append(json.loads(p.read_text(encoding='utf-8')))
            except Exception: continue
        out.sort(key=lambda x:x.get('created_at',''),reverse=True); return out[:limit]
    def delete(self,aid):
        try: meta=self.get(aid)
        except FileNotFoundError:return False
        meta['path'].unlink(missing_ok=True); (self.root/f'{aid}.json').unlink(missing_ok=True); return True
    def cleanup_orphans(self,referenced_ids):
        refs=set(referenced_ids); removed=0
        for meta in self.list(10000):
            if meta.get('id') not in refs and self.delete(meta.get('id')): removed+=1
        return removed
