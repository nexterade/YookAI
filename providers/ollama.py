"""Ollama HTTP API adapter; connects to a separately running Ollama server."""
import json, threading, uuid
from typing import Iterator
import requests
from core.text import repair_mojibake
from .base import BaseProvider
from .errors import ProviderHTTPError

class OllamaProvider(BaseProvider):
    TIMEOUT=(5,600)
    def __init__(self,api_key="",base_url="http://127.0.0.1:11434"):
        self.api_key=api_key;self.base_url=base_url.rstrip("/");self._stops={};self._responses={};self._lock=threading.Lock();self._cache=None
    @property
    def name(self):return "ollama"
    def list_models(self):
        r=requests.get(f"{self.base_url}/api/tags",timeout=(5,15));
        if r.status_code>=400:raise ProviderHTTPError(f"Ollama HTTP error ({r.status_code})")
        out=[]
        for m in r.json().get("models",[]):
            name=m.get("name") or m.get("model")
            if not name:continue
            out.append({"id":name,"name":name,"description":"Ollama API model","context_length":None,"pricing":{"prompt":"0","completion":"0"},"capabilities":{"vision":"vision" in name.lower(),"reasoning":"think" in name.lower() or "reason" in name.lower(),"tools":True}})
        self._cache=out;return list(out)
    def stream_chat(self,messages,model,**kwargs)->Iterator[dict]:
        rid=kwargs.pop("request_id",None) or uuid.uuid4().hex;stop=threading.Event()
        with self._lock:self._stops[rid]=stop
        normalized=[]
        for message in messages:
            item={"role":message.get("role","user"),"content":""}
            content=message.get("content","")
            if isinstance(content,list):
                text=[]; images=[]
                for block in content:
                    if block.get("type")=="text": text.append(str(block.get("text", "")))
                    elif block.get("type")=="image_url":
                        url=(block.get("image_url") or {}).get("url","")
                        if ";base64," in url: images.append(url.split(";base64,",1)[1])
                item["content"]="\n".join(text)
                if images:item["images"]=images
            else:item["content"]=str(content)
            normalized.append(item)
        payload={"model":model,"messages":normalized,"stream":True};payload.update(kwargs)
        response=None
        try:
            response=requests.post(f"{self.base_url}/api/chat",json=payload,stream=True,timeout=self.TIMEOUT)
            with self._lock:self._responses[rid]=response
            if response.status_code>=400:raise ProviderHTTPError(f"Ollama HTTP error ({response.status_code})")
            response.encoding="utf-8"
            for raw in response.iter_lines(chunk_size=1,decode_unicode=True):
                if stop.is_set():yield {"type":"done"};return
                if not raw:continue
                line=raw.decode("utf-8",errors="replace") if isinstance(raw,bytes) else raw
                try:e=json.loads(line)
                except json.JSONDecodeError:continue
                msg=e.get("message") or {};content=msg.get("content")
                if content:yield {"type":"content","content":repair_mojibake(content)}
                if e.get("done"):
                    usage={"prompt_tokens":e.get("prompt_eval_count",0),"completion_tokens":e.get("eval_count",0)}
                    if any(usage.values()):yield {"type":"usage","usage":usage}
                    yield {"type":"done"};return
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
