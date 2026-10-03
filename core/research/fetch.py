"""Bounded HTTP fetch utility with conservative URL validation."""
from __future__ import annotations
import ipaddress, socket
from urllib.parse import urlparse
from urllib.request import Request, urlopen
class ResearchError(ValueError): pass
def _validate(url):
    p=urlparse(str(url))
    if p.scheme!='https' or not p.hostname or p.username or p.password: raise ResearchError('only public HTTPS URLs are supported')
    host=p.hostname.lower()
    if host in {'localhost','localhost.localdomain'} or host.endswith('.local'): raise ResearchError('local hosts are blocked')
    try:
        for info in socket.getaddrinfo(host,None):
            ip=ipaddress.ip_address(info[4][0])
            if not ip.is_global: raise ResearchError('non-public network targets are blocked')
    except socket.gaierror as exc: raise ResearchError('host could not be resolved') from exc
    return p

def fetch(url,max_bytes=1_000_000,timeout=8):
    p=_validate(url); req=Request(url,headers={'User-Agent':'YookAI/0.3.0-final research-fetch'})
    try:
        with urlopen(req,timeout=min(15,max(1,int(timeout)))) as r:
            if urlparse(r.geturl()).hostname!=p.hostname: raise ResearchError('cross-host redirects are blocked')
            if r.status!=200: raise ResearchError(f'HTTP status {r.status}')
            raw=r.read(min(max(1,int(max_bytes)),2_000_000)+1)
            if len(raw)>max_bytes: raise ResearchError('response exceeds size limit')
            return {'url':r.geturl(),'content_type':r.headers.get('Content-Type',''),'text':raw.decode('utf-8','replace')}
    except ResearchError: raise
    except Exception as exc: raise ResearchError(f'fetch failed: {exc}') from exc
