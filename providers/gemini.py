"""Google Gemini Generative Language API provider."""
import json, threading, uuid
from typing import Iterator
import requests
from core.text import repair_mojibake
from .base import BaseProvider
from .errors import ProviderHTTPError, AuthError, RateLimitError

class GeminiProvider(BaseProvider):
    TIMEOUT=(15,300)
    def __init__(self,api_key,base_url="https://generativelanguage.googleapis.com/v1beta"):
        self.api_key=api_key;self.base_url=base_url.rstrip("/");self._cache=None;self._stops={};self._responses={};self._lock=threading.Lock()
    @property
    def name(self):return "gemini"
    def _raise(self,r):
        if 200<=r.status_code<300:return
        msg={401:"Gemini authentication failed (401): check API key",429:"Gemini rate limit exceeded (429)"}.get(r.status_code,f"Gemini HTTP error ({r.status_code})")
        if r.status_code==401:raise AuthError(msg)
        if r.status_code==429:raise RateLimitError(msg)
        raise ProviderHTTPError(msg)
    def list_models(self):
        if self._cache is not None:return list(self._cache)
        r=requests.get(f"{self.base_url}/models",params={"key":self.api_key},timeout=self.TIMEOUT);self._raise(r)
        out=[]
        for m in r.json().get("models",[]):
            mid=str(m.get("name","")).split("/",1)[-1]
            if not mid or "generateContent" not in str(m.get("supportedGenerationMethods",[])):continue
            out.append({"id":mid,"name":m.get("displayName") or mid,"description":m.get("description","") or "Direct Gemini model","context_length":m.get("inputTokenLimit"),"pricing":{},"capabilities":{"vision":True,"reasoning":"thinking" in mid.lower(),"tools":"function" in str(m).lower()}})
        self._cache=out;return list(out)
    @staticmethod
    def _convert(messages):
        contents=[];system=[]
        for m in messages:
            role=m.get("role");content=m.get("content","")
            if role=="system":system.append(str(content));continue
            parts=[]
            if isinstance(content,list):
                for b in content:
                    if b.get("type")=="text":parts.append({"text":b.get("text","")})
                    elif b.get("type")=="image_url":
                        url=(b.get("image_url") or {}).get("url","")
                        if url.startswith("data:") and ";base64," in url:
                            head,data=url.split(";base64,",1);parts.append({"inline_data":{"mime_type":head[5:],"data":data}})
            else:parts=[{"text":str(content)}]
            contents.append({"role":"model" if role=="assistant" else "user","parts":parts})
        return system,contents
    def stream_chat(self,messages,model,**kwargs)->Iterator[dict]:
        rid=kwargs.pop("request_id",None) or uuid.uuid4().hex;stop=threading.Event()
        with self._lock:self._stops[rid]=stop
        system,contents=self._convert(messages);payload={"contents":contents}
        generation={}
        for key in ("temperature","top_p","top_k","max_output_tokens","stop_sequences"):
            if key in kwargs:generation[key]=kwargs.pop(key)
        if generation:payload["generationConfig"]=generation
        if system:payload["systemInstruction"]={"parts":[{"text":"\n\n".join(system)}]}
        response=None
        try:
            url=f"{self.base_url}/models/{model}:streamGenerateContent"
            response=requests.post(url,params={"alt":"sse","key":self.api_key},json=payload,headers={"Content-Type":"application/json","Accept":"text/event-stream"},stream=True,timeout=self.TIMEOUT)
            with self._lock:self._responses[rid]=response
            self._raise(response);response.encoding="utf-8"
            for raw in response.iter_lines(chunk_size=1,decode_unicode=True):
                if stop.is_set():yield {"type":"done"};return
                if not raw:continue
                line=raw.decode("utf-8",errors="replace") if isinstance(raw,bytes) else raw
                if line.startswith("data:"):line=line[5:].strip()
                if not line:continue
                try:e=json.loads(line)
                except json.JSONDecodeError:continue
                for cand in e.get("candidates") or []:
                    for part in ((cand.get("content") or {}).get("parts") or []):
                        text=part.get("text")
                        if text:yield {"type":"reasoning" if part.get("thought") else "content","content":repair_mojibake(text)}
                usage=e.get("usageMetadata")
                if isinstance(usage,dict):yield {"type":"usage","usage":{"prompt_tokens":usage.get("promptTokenCount",0),"completion_tokens":usage.get("candidatesTokenCount",0),"total_tokens":usage.get("totalTokenCount",0)}}
            yield {"type":"done"}
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
