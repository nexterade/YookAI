"""Project-scoped local workspace with path confinement and atomic metadata writes."""
from __future__ import annotations
import json, re, uuid
from pathlib import Path
from typing import Any
from core.paths import ROOT

class ProjectError(ValueError): pass
class ProjectWorkspace:
    def __init__(self, root: Path|None=None):
        self.root=Path(root or (ROOT/'projects')).expanduser().resolve(); self.root.mkdir(parents=True,exist_ok=True)
    @staticmethod
    def _id(value):
        value=re.sub(r'[^A-Za-z0-9._-]+','-',str(value or '').strip())[:72].strip('-.')
        if not value: raise ProjectError('project id is required')
        return value
    def path(self, project_id):
        p=(self.root/self._id(project_id)).resolve()
        if p.parent!=self.root: raise ProjectError('invalid project id')
        return p
    def create(self,name, instructions=''):
        pid=uuid.uuid4().hex[:12]; p=self.path(pid); p.mkdir()
        for d in ('files','memory','tools'): (p/d).mkdir()
        meta={'id':pid,'name':str(name)[:120] or 'Untitled Project','instructions':str(instructions)[:12000]}
        self._write(p/'project.json',meta); return meta
    @staticmethod
    def _write(path,data):
        tmp=path.with_suffix(path.suffix+'.tmp'); tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8'); tmp.replace(path)
    def list(self):
        out=[]
        for p in self.root.iterdir():
            f=p/'project.json'
            if p.is_dir() and f.is_file():
                try: out.append(json.loads(f.read_text(encoding='utf-8')))
                except (OSError,json.JSONDecodeError): continue
        return sorted(out,key=lambda x:x.get('name','').lower())
    def get(self,project_id):
        f=self.path(project_id)/'project.json'
        if not f.is_file(): raise ProjectError('project not found')
        return json.loads(f.read_text(encoding='utf-8'))
    def update_instructions(self,project_id,instructions):
        meta=self.get(project_id); meta['instructions']=str(instructions)[:12000]; self._write(self.path(project_id)/'project.json',meta); return meta
    def resolve_file(self,project_id,relative):
        base=(self.path(project_id)/'files').resolve(); target=(base/str(relative)).resolve()
        if target!=base and base not in target.parents: raise ProjectError('path escapes project files')
        return target
    def write_file(self,project_id,relative,content):
        target=self.resolve_file(project_id,relative); target.parent.mkdir(parents=True,exist_ok=True)
        data=content.encode('utf-8') if isinstance(content,str) else bytes(content)
        if len(data)>10_000_000: raise ProjectError('file exceeds 10 MB limit')
        target.write_bytes(data); return {'path':str(target.relative_to(self.path(project_id)/'files')),'size':len(data)}
    def list_files(self,project_id):
        base=self.path(project_id)/'files'; out=[]
        for p in sorted(base.rglob('*')):
            if p.is_file() and not p.is_symlink(): out.append({'path':p.relative_to(base).as_posix(),'size':p.stat().st_size})
        return out
