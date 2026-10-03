"""Direct Anthropic Messages API provider."""
import json, threading, uuid
from typing import Iterator
import requests
from core.text import repair_mojibake
from .base import BaseProvider
from .errors import ProviderHTTPError, AuthError, RateLimitError

class AnthropicProvider(BaseProvider):
    TIMEOUT=(15,300)
    def __init__(self,api_key,base_url="https://api.anthropic.com/v1"):
        self.api_key=api_key; self.base_url=base_url.rstrip("/"); self._cache=None; self._stops={}; self._responses={}; self._lock=threading.Lock()
    @property
    def name(self):return "anthropic"
    def _headers(self):return {"x-api-key":self.api_key,"anthropic-version":"2023-06-01","content-type":"application/json","accept":"text/event-stream"}
    def _raise(self,r):
        if 200<=r.status_code<300:return
        msg={401:"Anthropic authentication failed (401): check API key",429:"Anthropic rate limit exceeded (429)"}.get(r.status_code,f"Anthropic HTTP error ({r.status_code})")
        if r.status_code==401:raise AuthError(msg)
        if r.status_code==429:raise RateLimitError(msg)
        raise ProviderHTTPError(msg)
    def list_models(self):
        if self._cache is not None:return list(self._cache)
        r=requests.get(f"{self.base_url}/models",headers=self._headers(),timeout=self.TIMEOUT); self._raise(r)
        out=[]
        for m in r.json().get("data",[]):
            if not isinstance(m,dict) or not m.get("id"):continue
            mid=m["id"]; out.append({"id":mid,"name":m.get("display_name") or mid,"description":"Direct Anthropic model","context_length":None,"pricing":{},"capabilities":{"vision":"claude" in mid.lower(),"reasoning":"thinking" in mid.lower(),"tools":True}})
        self._cache=out; return list(out)
    @staticmethod
    def _messages(messages):
        system=[]; out=[]
        for m in messages:
            if m.get("role")=="system":system.append(str(m.get("content", "")));continue
            content=m.get("content","")
            if isinstance(content,list):
                blocks=[]
                for b in content:
                    if b.get("type")=="text":blocks.append({"type":"text","text":b.get("text","")})
                    elif b.get("type")=="image_url":
                        url=(b.get("image_url") or {}).get("url","");
                        if url.startswith("data:") and ";base64," in url:
                            head,data=url.split(";base64,",1); media=head[5:]
                            blocks.append({"type":"image","source":{"type":"base64","media_type":media,"data":data}})
                content=blocks
            out.append({"role":m.get("role","user"),"content":content})
        return "\n\n".join(system),out
    def stream_chat(self,messages,model,**kwargs)->Iterator[dict]:
        rid=kwargs.pop("request_id",None) or uuid.uuid4().hex; stop=threading.Event()
        with self._lock:self._stops[rid]=stop
        system,msgs=self._messages(messages); payload={"model":model,"messages":msgs,"max_tokens":kwargs.pop("max_tokens",2048),"stream":True}
        if system:payload["system"]=system
        payload.update(kwargs); response=None
        try:
            response=requests.post(f"{self.base_url}/messages",headers=self._headers(),json=payload,stream=True,timeout=self.TIMEOUT)
            with self._lock:self._responses[rid]=response
            self._raise(response); response.encoding="utf-8"
            for raw in response.iter_lines(chunk_size=1,decode_unicode=True):
                if stop.is_set():yield {"type":"done"};return
                if not raw:continue
                line=raw.decode("utf-8",errors="replace") if isinstance(raw,bytes) else raw
                if line.startswith("data:"):line=line[5:].strip()
                if not line:continue
                try:e=json.loads(line)
                except json.JSONDecodeError:continue
                typ=e.get("type")
                if typ=="content_block_delta":
                    d=e.get("delta") or {}; text=d.get("text") or d.get("thinking")
                    if text:yield {"type":"reasoning" if d.get("thinking") is not None or d.get("type")=="thinking_delta" else "content","content":repair_mojibake(text)}
                elif typ=="message_delta" and isinstance(e.get("usage"),dict):yield {"type":"usage","usage":{"completion_tokens":e["usage"].get("output_tokens",0),"prompt_tokens":e["usage"].get("input_tokens",0)}}
                elif typ=="message_stop":yield {"type":"done"};return
        except requests.RequestException as exc:yield {"type":"error","message":str(exc)}
        except Exception as exc:yield {"type":"error","message":str(exc)}
        finally:
            with self._lock:self._stops.pop(rid,None);active=self._responses.pop(rid,None)
            if active is not None:
                try:active.close()
                except Exception:pass
    def stop_chat(self,request_id):
        with self._lock:event=self._stops.get(request_id);response=self._responses.get(request_id)
        if event is None:return False
        event.set()
        if response is not None:
            try:response.close()
            except Exception:pass
        return True
