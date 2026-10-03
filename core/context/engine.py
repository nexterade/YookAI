"""Deterministic context budgeting and safe history compaction."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class ContextPlan:
    messages: list[dict[str, Any]]
    estimated_tokens: int
    omitted_messages: int
    summary: str = ""

def estimate_tokens(value: Any) -> int:
    if not isinstance(value, str): value = str(value)
    return max(1, (len(value) + 3) // 4)

class ContextEngine:
    def __init__(self, max_tokens: int = 24000, reserve_tokens: int = 3000):
        self.max_tokens=max(256,int(max_tokens)); self.reserve_tokens=max(0,int(reserve_tokens))
    def plan(self, messages: list[dict[str, Any]], system: str = "") -> ContextPlan:
        budget=max(128,self.max_tokens-self.reserve_tokens)
        normalized=[dict(m) for m in messages if isinstance(m,dict) and m.get('role') in {'system','user','assistant','tool'}]
        prefix=[]
        if system.strip(): prefix.append({'role':'system','content':system})
        # Preserve initial system messages and the newest conversational turns; never split a message.
        initial=[m for m in normalized if m.get('role')=='system']
        rest=[m for m in normalized if m.get('role')!='system']
        chosen=[]; used=sum(estimate_tokens(m.get('content','')) for m in prefix+initial)
        for m in reversed(rest):
            cost=estimate_tokens(m.get('content',''))
            if used+cost>budget and chosen: break
            if used+cost>budget: continue
            chosen.append(m); used+=cost
        result=prefix+initial+list(reversed(chosen))
        return ContextPlan(result,used,len(normalized)-len(initial)-len(chosen))
    @staticmethod
    def summarize(messages: list[dict[str, Any]], max_chars: int=4000) -> str:
        lines=[]
        for m in messages:
            if not isinstance(m,dict) or m.get('role') not in {'user','assistant'}: continue
            content=m.get('content',''); content=content if isinstance(content,str) else str(content)
            if content.strip(): lines.append(f"{m['role']}: {' '.join(content.split())}")
        text='\n'.join(lines)
        return text[-max(1,int(max_chars)):]
