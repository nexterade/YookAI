"""MCP JSON-RPC message helpers. Transport/process lifecycle is intentionally caller-owned."""
from __future__ import annotations
import itertools
class MCPProtocolError(ValueError): pass
class MCPClient:
    def __init__(self): self._ids=itertools.count(1)
    def request(self,method,params=None):
        if not isinstance(method,str) or not method: raise MCPProtocolError('method required')
        return {'jsonrpc':'2.0','id':next(self._ids),'method':method,'params':params or {}}
    @staticmethod
    def validate_response(message,request_id):
        if not isinstance(message,dict) or message.get('jsonrpc')!='2.0' or message.get('id')!=request_id: raise MCPProtocolError('invalid or mismatched JSON-RPC response')
        if 'error' in message: raise MCPProtocolError(str(message['error']))
        if 'result' not in message: raise MCPProtocolError('response missing result')
        return message['result']
