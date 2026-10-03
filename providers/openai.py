"""Direct OpenAI provider using the OpenAI-compatible Chat Completions API."""
import json, threading, time, uuid
from typing import Iterator
import requests
from core.text import repair_mojibake
from .base import BaseProvider
from .errors import ProviderHTTPError, AuthError, PaymentError, RateLimitError

class OpenAIProvider(BaseProvider):
    TIMEOUT=(15,300)
    def __init__(self, api_key, base_url="https://api.openai.com/v1"):
        self.api_key=api_key; self.base_url=base_url.rstrip("/")
        self._cache=None; self._cache_at=0.0; self._stops={}; self._responses={}; self._lock=threading.Lock()
    @property
    def name(self): return "openai"
    def _headers(self): return {"Authorization":f"Bearer {self.api_key}","Content-Type":"application/json","Accept":"text/event-stream"}
    def _raise(self,r):
        if 200<=r.status_code<300:return
        msg={401:"OpenAI authentication failed (401): check API key",402:"OpenAI payment/credit error (402)",429:"OpenAI rate limit exceeded (429)"}.get(r.status_code,f"OpenAI HTTP error ({r.status_code})")
        if r.status_code==401: raise AuthError(msg)
        if r.status_code==402: raise PaymentError(msg)
        if r.status_code==429: raise RateLimitError(msg)
        raise ProviderHTTPError(msg)
    def list_models(self):
        now=time.monotonic()
        if self._cache is not None and now-self._cache_at<3600:return list(self._cache)
        r=requests.get(f"{self.base_url}/models",headers={"Authorization":f"Bearer {self.api_key}"},timeout=self.TIMEOUT); self._raise(r)
        out=[]
        for m in r.json().get("data",[]):
            if not isinstance(m,dict) or not m.get("id"):continue
            mid=m["id"]
            out.append({"id":mid,"name":mid,"description":"Direct OpenAI model","context_length":None,"pricing":{},"capabilities":{"vision":any(x in mid.lower() for x in ("gpt-4o","gpt-4.1","o4","vision")),"reasoning":any(x in mid.lower() for x in ("o1","o3","o4")),"tools":True}})
        self._cache=out; self._cache_at=now; return list(out)
    def stream_chat(self,messages,model,**kwargs)->Iterator[dict]:
        rid=kwargs.pop("request_id",None) or uuid.uuid4().hex; stop=threading.Event()
        with self._lock:self._stops[rid]=stop
        payload={"model":model,"messages":messages,"stream":True}; payload.update(kwargs)
        response=None; started=time.monotonic(); first=None
        try:
            response=requests.post(f"{self.base_url}/chat/completions",headers=self._headers(),json=payload,stream=True,timeout=self.TIMEOUT)
            with self._lock:self._responses[rid]=response
            self._raise(response); response.encoding="utf-8"
            for raw in response.iter_lines(chunk_size=1,decode_unicode=True):
                if stop.is_set():yield {"type":"done"}; return
                if not raw:continue
                line=raw.decode("utf-8",errors="replace") if isinstance(raw,bytes) else raw
                line=line.strip()
                # Ignore SSE comments and metadata (event:, id:, retry:, etc.).
                if line.startswith(":") or not line.startswith("data:"):continue
                line=line[5:].strip()
                if line=="[DONE]":yield {"type":"done"}; return
                if not line:continue
                if first is None:first=time.monotonic()
                try:chunk=json.loads(line)
                except json.JSONDecodeError as exc:yield {"type":"error","message":f"Invalid SSE JSON: {exc}"}; return
                if isinstance(chunk.get("usage"),dict):yield {"type":"usage","usage":chunk["usage"]}
                choices=chunk.get("choices") or []
                if not choices:continue
                delta=choices[0].get("delta") or {}
                reasoning=delta.get("reasoning") or delta.get("reasoning_content")
                if reasoning:yield {"type":"reasoning","content":repair_mojibake(reasoning)}
                content=delta.get("content")
                if content:yield {"type":"content","content":repair_mojibake(content)}
        except requests.RequestException as exc:yield {"type":"error","message":str(exc)}
        except Exception as exc:yield {"type":"error","message":str(exc)}
        finally:
            with self._lock:self._stops.pop(rid,None); active=self._responses.pop(rid,None)
            if active is not None:
                try:active.close()
                except Exception:pass
    def stop_chat(self,request_id):
        with self._lock:event=self._stops.get(request_id); response=self._responses.get(request_id)
        if event is None:return False
        event.set()
        if response is not None:
            try:response.close()
            except Exception:pass
        return True
