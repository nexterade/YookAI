import json
import pytest
from core.context.engine import ContextEngine
from core.projects.workspace import ProjectWorkspace, ProjectError
from core.agents.loop import AgentLoop, AgentError
from core.agents.tasks import TaskStore
from core.automation.schedule import ScheduleStore
from core.mcp.protocol import MCPClient, MCPProtocolError

def test_context_budget_keeps_latest_and_system():
    plan=ContextEngine(500,100).plan([{'role':'user','content':'old '*500},{'role':'user','content':'latest'}],'system')
    assert plan.messages[0]['role']=='system' and plan.messages[-1]['content']=='latest'
    assert plan.omitted_messages==1

def test_project_workspace_confines_files(tmp_path):
    ws=ProjectWorkspace(tmp_path); p=ws.create('Research','Rules')
    ws.write_file(p['id'],'notes/a.txt','ok')
    assert ws.list_files(p['id'])[0]['path']=='notes/a.txt'
    assert ws.get(p['id'])['instructions']=='Rules'
    with pytest.raises(ProjectError): ws.resolve_file(p['id'],'../../escape')

def test_agent_loop_calls_tool_then_returns_answer():
    class Spec:
        name='calc'; requires_confirmation=False
    class Registry:
        def list(self): return [Spec()]
        def get(self,n): return Spec() if n=='calc' else None
    n={'v':0}
    def model(history,tools):
        n['v']+=1
        return {'tool_calls':[{'name':'calc','arguments':{'x':2}}]} if n['v']==1 else {'content':'done'}
    out=AgentLoop(Registry()).run([],model,lambda name,args:{'status':'ok','result':args['x']*2})
    assert out['status']=='completed' and out['content']=='done' and len(out['events'])==1

def test_agent_rejects_unknown_tool():
    class R:
        def list(self): return []
        def get(self,n): return None
    with pytest.raises(AgentError): AgentLoop(R()).run([],lambda *_:{'tool_calls':[{'name':'bad'}]},lambda *_:{})

def test_task_store_terminal_and_schedule_validation(tmp_path):
    tasks=TaskStore(tmp_path/'tasks.json'); t=tasks.create('research'); tasks.update(t['id'],'completed',{'ok':True})
    assert tasks.list()[0]['status']=='completed'
    with pytest.raises(ValueError): tasks.update(t['id'],'running')
    schedules=ScheduleStore(tmp_path/'schedules.json'); s=schedules.create('digest',60)
    assert s['enabled'] is False
    with pytest.raises(ValueError): schedules.create('bad',0)

def test_mcp_jsonrpc_validation():
    c=MCPClient(); req=c.request('tools/list'); assert req['jsonrpc']=='2.0'
    assert c.validate_response({'jsonrpc':'2.0','id':req['id'],'result':{'tools':[]}},req['id'])=={'tools':[]}
    with pytest.raises(MCPProtocolError): c.validate_response({'jsonrpc':'2.0','id':99,'result':{}},req['id'])
