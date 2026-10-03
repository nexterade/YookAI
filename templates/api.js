class APIError extends Error {
  constructor(status, message) { super(message); this.name = 'APIError'; this.status = status; }
}

class YookAIClient {
  constructor(baseUrl = '') { this.baseUrl = baseUrl.replace(/\/$/, ''); }
  async request(path, options = {}) {
    const response = await fetch(this.baseUrl + path, { ...options, headers: { 'Content-Type': 'application/json', ...(options.headers || {}) } });
    const text = await response.text();
    let data = null;
    try { data = text ? JSON.parse(text) : {}; } catch (_) { data = { message: text }; }
    if (!response.ok) throw new APIError(response.status, data.error || data.message || `HTTP ${response.status}`);
    return data;
  }
  async listProviders() { return this.request('/api/providers'); }
  async listModels(provider = 'openrouter') { return this.request(`/api/providers/${encodeURIComponent(provider)}/models`); }
  async streamChat(payload, onChunk, signal) {
    const response = await fetch(this.baseUrl + '/api/chat', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload), signal });
    if (!response.ok) { let message = `HTTP ${response.status}`; try { const data = await response.json(); message = data.error || message; } catch (_) {} throw new APIError(response.status, message); }
    if (!response.body) throw new APIError(500, 'Streaming tidak didukung browser');
    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';
    let dataLines = [];
    const dispatch = () => {
      if (!dataLines.length) return;
      const value = dataLines.join('\n');
      dataLines = [];
      if (!value.trim() || value.trim() === '[DONE]') return;
      let chunk;
      try { chunk = JSON.parse(value); }
      catch (error) { throw new APIError(502, `SSE response JSON tidak valid: ${error.message}`); }
      // Do not swallow callback exceptions: callers use them to terminate a bad stream.
      onChunk(chunk);
    };
    const consumeLine = (line) => {
      if (line === '') { dispatch(); return; }
      if (line.startsWith(':')) return; // SSE comment / keep-alive
      if (line.startsWith('data:')) dataLines.push(line.slice(5).replace(/^ /, ''));
    };
    try {
      while (true) {
        const {value, done} = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, {stream:true});
        const lines = buffer.split(/\r?\n/);
        buffer = lines.pop() || '';
        for (const line of lines) consumeLine(line);
      }
      buffer += decoder.decode();
      if (buffer) consumeLine(buffer);
      dispatch();
    } catch (error) {
      try { await reader.cancel(error); } catch (_) {}
      throw error;
    }
  }
  async uploadAttachment(file, onProgress) {
    const form = new FormData(); form.append('file', file, file.name);
    // XHR is used here because fetch does not expose upload progress in the
    // browser APIs supported by the project. The request remains same-origin.
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', this.baseUrl + '/api/attachments');
      xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable && typeof onProgress === 'function') onProgress(Math.round((event.loaded / event.total) * 100));
      });
      xhr.addEventListener('load', () => {
        let data = {};
        try { data = xhr.responseText ? JSON.parse(xhr.responseText) : {}; } catch (_) {}
        if (xhr.status >= 200 && xhr.status < 300) resolve(data);
        else reject(new APIError(xhr.status, data.error || `HTTP ${xhr.status}`));
      });
      xhr.addEventListener('error', () => reject(new APIError(0, 'Upload gagal: koneksi terputus')));
      xhr.addEventListener('abort', () => reject(new APIError(0, 'Upload dibatalkan')));
      xhr.send(form);
    });
  }
  async getSessionStats(id) { return this.request(`/api/session/${encodeURIComponent(id)}/stats`); }
  async listMemory(query='') { return this.request(`/api/memory?q=${encodeURIComponent(query)}`); }
  async deleteMemory(id) { return this.request(`/api/memory/${encodeURIComponent(id)}`, {method:'DELETE'}); }
  async clearMemory(mode, projectId) { return this.request('/api/memory/clear', {method:'POST', body:JSON.stringify({mode, project_id:projectId})}); }
  async listAttachments() { return this.request('/api/attachments'); }
  async deleteAttachment(id) { return this.request(`/api/attachments/${encodeURIComponent(id)}`, {method:'DELETE'}); }
  async cleanupAttachments() { return this.request('/api/attachments/cleanup', {method:'POST'}); }
  async exportSession(id) { return this.request(`/api/session/${encodeURIComponent(id)}/export`); }
  async importSession(session) { return this.request('/api/session/import', {method:'POST', body:JSON.stringify({session})}); }
  async stopChat(requestId, provider) { return this.request('/api/chat/stop', {method:'POST', body:JSON.stringify({request_id:requestId, provider} )}); }
  async listSessions() { return this.request('/api/session/list'); }
  async saveSession(session) { return this.request('/api/session/save', {method:'POST', body:JSON.stringify(session)}); }
  async loadSession(id) { return this.request(`/api/session/${encodeURIComponent(id)}`); }
  async deleteSession(id) { return this.request(`/api/session/${encodeURIComponent(id)}`, {method:'DELETE'}); }
  async getConfig() { return this.request('/api/config'); }
  async saveConfig(config) { return this.request('/api/config', {method:'POST', body:JSON.stringify(config)}); }
  async listTools() { return this.request('/api/tools'); }
  async executeTool(tool, args = {}, confirmationToken = null) { return this.request('/api/tools/execute', {method:'POST', body:JSON.stringify({tool, args, confirmation_token: confirmationToken})}); }
}
window.YookAIClient = YookAIClient; window.APIError = APIError;
