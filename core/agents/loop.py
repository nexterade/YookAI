"""Bounded, explicit AI-tool-AI loop; provider integration supplies model_step."""
from __future__ import annotations
import json
from typing import Any, Callable

class AgentError(ValueError): pass
class AgentLoop:
    def __init__(self, registry, max_steps=5, max_result_chars=12000):
        self.registry=registry; self.max_steps=max(1,min(12,int(max_steps))); self.max_result_chars=max(256,int(max_result_chars))
    def run(self, messages:list[dict[str,Any]], model_step:Callable, execute:Callable, approve:Callable|None=None):
        history=[dict(m) for m in messages]; events=[]
        for step in range(self.max_steps):
            response=model_step(history, self.registry.list())
            if not isinstance(response,dict): raise AgentError('model_step must return an object')
            calls=response.get('tool_calls') or []
            content=response.get('content','')
            if not calls:
                return {'status':'completed','content':content,'messages':history+[{'role':'assistant','content':content}],'events':events,'steps':step+1}
            history.append({'role':'assistant','content':content,'tool_calls':calls})
            for call in calls:
                name=call.get('name'); args=call.get('arguments',{})
                if isinstance(args,str):
                    try: args=json.loads(args)
                    except json.JSONDecodeError: raise AgentError('tool arguments must be valid JSON')
                spec=self.registry.get(name) if isinstance(name,str) else None
                if spec is None: raise AgentError(f'unknown tool: {name}')
                if not isinstance(args,dict): raise AgentError('tool arguments must be an object')
                if spec.requires_confirmation and (approve is None or not approve(name,args)):
                    result={'status':'denied','message':'User approval required'}
                else: result=execute(name,args)
                encoded=json.dumps(result,ensure_ascii=False,default=str)[:self.max_result_chars]
                history.append({'role':'tool','name':name,'content':encoded})
                events.append({'step':step+1,'tool':name,'status':result.get('status','ok') if isinstance(result,dict) else 'ok'})
        return {'status':'step_limit','content':'Agent stopped at the configured tool-call limit.','messages':history,'events':events,'steps':self.max_steps}
