(function(){
  'use strict';

  const CACHE_KEY = 'yookai-model-cache';
  const MODEL_KEY = 'yookai-model';
  const ACTIVE_SESSION_KEY = 'yookai-active-session';
  const SERVER_INSTANCE_KEY = 'yookai-server-instance';
  const CACHE_TTL = 60 * 60 * 1000;
  const RECOMMENDED = [
    'deepseek/deepseek-r1',
    'deepseek/deepseek-chat',
    'anthropic/claude-3.5-sonnet',
    'openai/gpt-4o',
    'google/gemini-flash-1.5',
  ];

  const state = {
    currentSessionId: null,
    sessions: [],
    messages: [],
    currentModel: null,
    currentProvider: 'openrouter',
    isStreaming: false,
    abortController: null,
    requestId: null,
    config: {},
    userScrolledUp: false,
    generation: 0,
    pendingAttachments: [],
    uploadingCount: 0,
    modelOptions: {temperature:0.7, top_p:1, max_tokens:2048, reasoning_effort:'auto', system_prompt:''},
  };

  const $ = (id) => document.getElementById(id);
  const client = new YookAIClient();
  let eventsBound = false;

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  function repairMojibake(value) {
    let text = String(value ?? '');
    const markers = ['Ã', 'Â', 'â', 'ð', '�'];
    const score = (v) => markers.reduce((n, marker) => n + v.split(marker).length - 1, 0);
    let bestScore = score(text);
    if (!bestScore) return text;
    for (let i = 0; i < 3; i += 1) {
      try {
        const bytes = Uint8Array.from(unescape(encodeURIComponent(text)).split('').map(c => c.charCodeAt(0)));
        const candidate = new TextDecoder('utf-8', {fatal:true}).decode(new Uint8Array(bytes));
        const nextScore = score(candidate);
        if (nextScore >= bestScore) break;
        text = candidate; bestScore = nextScore;
      } catch (_) { break; }
    }
    return text;
  }

  const SVG = {
    copy: '<svg viewBox="0 0 24 24" focusable="false"><rect x="8" y="8" width="11" height="11" rx="2"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/></svg>',
    edit: '<svg viewBox="0 0 24 24" focusable="false"><path d="m4 16-.7 4.7L8 20l10.8-10.8a2.5 2.5 0 0 0-3.5-3.5L4 16Z"/><path d="m14 7 3 3"/></svg>',
    retry: '<svg viewBox="0 0 24 24" focusable="false"><path d="M20 11a8 8 0 1 0 1 4"/><path d="M20 5v6h-6"/></svg>',
    share: '<svg viewBox="0 0 24 24" focusable="false"><path d="m13 5 7 7-7 7"/><path d="M20 12H5"/></svg>',
    star: '<svg viewBox="0 0 24 24" focusable="false"><path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-2.9-5.6 2.9 1.1-6.2L3 9.6l6.2-.9L12 3Z"/></svg>',
    more: '<svg viewBox="0 0 24 24" focusable="false"><circle cx="5" cy="12" r="1.4"/><circle cx="12" cy="12" r="1.4"/><circle cx="19" cy="12" r="1.4"/></svg>',
    paperclip: '<svg viewBox="0 0 24 24" focusable="false"><path d="m8.5 12.5 6.8-6.8a3.2 3.2 0 1 1 4.5 4.5l-8.1 8.1a5 5 0 1 1-7.1-7.1l8-8"/></svg>',
    image: '<svg viewBox="0 0 24 24" focusable="false"><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="8" cy="9" r="1.5"/><path d="m4 17 5-5 3.5 3 2.5-2.5 5 5"/></svg>',
    archive: '<svg viewBox="0 0 24 24" focusable="false"><path d="M4 7h16v13H4z"/><path d="M3 4h18v3H3zM10 10h4M10 13h4M10 16h4"/></svg>',
    speaker: '<svg viewBox="0 0 24 24" focusable="false"><path d="M4 10v4h4l5 4V6l-5 4H4Z"/><path d="M17 9a5 5 0 0 1 0 6M19.5 6.5a9 9 0 0 1 0 11"/></svg>'
  };

  function uuid() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  function formatNumber(value) { return new Intl.NumberFormat('id-ID').format(Number(value || 0)); }
  function formatDurationMs(ms) {
    ms = Math.max(0, Number(ms || 0));
    const seconds = Math.floor(ms / 1000);
    const h = Math.floor(seconds / 3600), m = Math.floor((seconds % 3600) / 60), s = seconds % 60;
    return h ? `${h}j ${m}m ${s}d` : m ? `${m}m ${s}d` : `${s}d`;
  }

  const StreamRender = {
    frames: new Map(),
    schedule(row, bubble, getText) {
      if (!row || !bubble) return;
      if (this.frames.has(row)) return;
      this.frames.set(row, requestAnimationFrame(() => {
        this.frames.delete(row);
        bubble.innerHTML = window.renderMarkdown ? renderMarkdown(repairMojibake(getText())) : escapeHtml(getText());
      }));
    },
    cancel(row) {
      const frame = this.frames.get(row);
      if (frame) cancelAnimationFrame(frame);
      this.frames.delete(row);
    }
  };

  async function uploadFiles(files) {
    const selected = files.filter(Boolean);
    for (const file of selected) {
      if (file.size > 20 * 1024 * 1024) { showToast(`${file.name} terlalu besar (maks. 20 MB).`, 'error'); continue; }
      const temp = {uploading: true, name: file.name, mime: file.type || 'application/octet-stream', progress: 0, temp_id: uuid()};
      state.pendingAttachments.push(temp);
      state.uploadingCount += 1;
      renderAttachmentList();
      updateComposerState();
      try {
        const meta = await client.uploadAttachment(file, (progress) => {
          temp.progress = Math.min(99, Number(progress || 0));
          renderAttachmentList();
        });
        temp.progress = 100; temp.uploading = false; renderAttachmentList();
        const index = state.pendingAttachments.indexOf(temp);
        if (index >= 0) state.pendingAttachments[index] = meta;
      } catch (error) {
        state.pendingAttachments = state.pendingAttachments.filter((item) => item !== temp);
        showToast(error.message || `Gagal upload ${file.name}.`, 'error');
      } finally {
        state.uploadingCount = Math.max(0, state.uploadingCount - 1);
        renderAttachmentList();
        updateComposerState();
      }
    }
  }

  function renderAttachmentList() {
    const list = $('attachment-list');
    if (!list) return;
    list.innerHTML = state.pendingAttachments.map((item, index) => {
      if (item.uploading) {
        const progress = Math.max(0, Math.min(100, Number(item.progress || 0)));
        return `<div class="attachment-chip attachment-uploading" aria-busy="true"><span class="upload-spinner" aria-hidden="true"></span><span title="${escapeHtml(item.name)}">${escapeHtml(item.name)}</span><span class="upload-progress-text">${progress}%</span><div class="upload-progress"><i style="width:${progress}%"></i></div></div>`;
      }
      const icon = item.mime?.startsWith('image/') ? SVG.image : item.name?.toLowerCase().endsWith('.zip') ? SVG.archive : SVG.paperclip;
      return `<div class="attachment-chip"><span title="${escapeHtml(item.name)}">${icon} ${escapeHtml(item.name)}</span><button type="button" data-remove-attachment="${index}" aria-label="Hapus ${escapeHtml(item.name)}"><svg viewBox="0 0 24 24" focusable="false"><path d="m6 6 12 12M18 6 6 18"/></svg></button></div>`;
    }).join('');
  }

  function showToast(message, kind = 'info', action) {
    const toast = $('toast');
    if (!toast) return;
    toast.className = `toast show toast-${kind}`;
    toast.textContent = '';
    const text = document.createElement('span');
    text.textContent = message;
    toast.appendChild(text);
    if (action) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'toast-action';
      button.textContent = action.label;
      button.addEventListener('click', () => { action.run(); hideToast(); });
      toast.appendChild(button);
    }
    clearTimeout(showToast.timer);
    showToast.timer = setTimeout(hideToast, 2200);
  }

  function hideToast() {
    const toast = $('toast');
    if (!toast) return;
    toast.classList.remove('show');
  }

  function renderErrorState(message = 'Terjadi kesalahan.') {
    const canvas = $('chat-canvas');
    if (!canvas) return;
    canvas.innerHTML = `<div class="error-state"><div class="error-icon" aria-hidden="true">⚠</div><h2>Terjadi kesalahan</h2><p>${escapeHtml(message)}</p><button type="button" class="btn primary" id="retry-load">Coba lagi</button></div>`;
    $('retry-load')?.addEventListener('click', init, {once:true});
  }

  function announce(message) {
    const node = $('sr-announcer');
    if (!node) return;
    node.textContent = '';
    requestAnimationFrame(() => { node.textContent = message; });
  }

  function normalizeModel(model) {
    const value = model || {};
    return {
      id: String(value.id || ''),
      name: String(value.name || value.id || 'Unknown model'),
      pricing: value.pricing || {},
      context_length: value.context_length || null,
      capabilities: value.capabilities || {},
    };
  }

  const PROVIDER_LABELS = {openrouter:'OpenRouter', openai:'OpenAI', anthropic:'Anthropic', gemini:'Google Gemini', ollama:'Ollama API'};
  const DEFAULT_MODEL_OPTIONS = {temperature:0.7, top_p:1, max_tokens:2048, reasoning_effort:'auto', system_prompt:''};

  function profileKey(provider = state.currentProvider, model = state.currentModel) { return `${provider}:${model || ''}`; }
  function getModelProfile(provider = state.currentProvider, model = state.currentModel) {
    const profiles = state.config.chat?.model_profiles || {};
    return {...DEFAULT_MODEL_OPTIONS, ...(profiles[profileKey(provider, model)] || {})};
  }
  function setModelProfile(provider, model, options) {
    state.config.chat ||= {};
    state.config.chat.model_profiles ||= {};
    state.config.chat.model_profiles[profileKey(provider, model)] = {...DEFAULT_MODEL_OPTIONS, ...options};
    state.modelOptions = {...DEFAULT_MODEL_OPTIONS, ...options};
  }
  function providerLabel(name) { return PROVIDER_LABELS[name] || name; }

  const ModelSelector = {
    models: [], providers: [], filtered: [], currentModelId: null, isOpen: false, activeIndex: -1,
    init() {
      if (this.initialized) return;
      this.trigger=$('model-trigger'); this.dropdown=$('model-dropdown'); this.search=$('model-search'); this.providerSelect=$('model-provider-select');
      if (!this.trigger || !this.dropdown || !this.search) return;
      this.trigger.addEventListener('click',()=>this.isOpen?this.close():this.open());
      this.search.addEventListener('input',(e)=>this.handleSearch(e));
      this.search.addEventListener('keydown',(e)=>this.handleKeydown(e));
      this.dropdown.addEventListener('click',(e)=>{const option=e.target.closest('.model-option');if(option)this.select(option.dataset.modelId);});
      this.providerSelect?.addEventListener('change',async(e)=>{await this.selectProvider(e.target.value);});
      document.addEventListener('click',(e)=>{if(!e.target.closest('#model-selector'))this.close();});
      this.initialized=true; this.currentModelId=localStorage.getItem(MODEL_KEY)||null; this.updateHeader();
    },
    async loadProviders() {
      try { const data=await client.listProviders(); this.providers=data.providers||[]; }
      catch (_) { this.providers=Object.keys(PROVIDER_LABELS).map(name=>({name,configured:name==='ollama'})); }
      if(this.providerSelect){this.providerSelect.innerHTML=this.providers.map(p=>`<option value="${escapeHtml(p.name)}">${escapeHtml(providerLabel(p.name))}${p.configured?'':' · not configured'}</option>`).join('');this.providerSelect.value=state.currentProvider;}
      return this.providers;
    },
    async selectProvider(provider) {
      if(!provider || provider===state.currentProvider)return;
      state.currentProvider=provider; state.currentModel=null; this.currentModelId=null; localStorage.removeItem(MODEL_KEY); this.updateHeader();
      this.invalidateCache();
      try { await this.loadModels(); announce(`Provider dipilih: ${providerLabel(provider)}`); if(state.currentSessionId&&!state.isStreaming)await saveSession({refresh:true}); }
      catch(e){showToast(e.message||`Gagal memuat model ${providerLabel(provider)}.`,'error');}
    },
    async loadModels() {
      const cached=localStorage.getItem(`${CACHE_KEY}:${state.currentProvider}`);
      if(cached){try{const parsed=JSON.parse(cached);if(Date.now()-parsed.savedAt<CACHE_TTL&&Array.isArray(parsed.models)){this.models=parsed.models.map(normalizeModel).filter(m=>m.id);this.providerForLoadedModels=state.currentProvider;this.ensureDefaultModel();this.render(this.models,'');return this.models;}}catch(_){localStorage.removeItem(`${CACHE_KEY}:${state.currentProvider}`);}}
      this.renderLoading(); const data=await client.listModels(state.currentProvider); this.models=(data.models||[]).map(normalizeModel).filter(m=>m.id); this.providerForLoadedModels=state.currentProvider;
      localStorage.setItem(`${CACHE_KEY}:${state.currentProvider}`,JSON.stringify({savedAt:Date.now(),models:this.models})); this.ensureDefaultModel(); this.render(this.models,''); return this.models;
    },
    invalidateCache(){localStorage.removeItem(`${CACHE_KEY}:${state.currentProvider}`);},
    ensureDefaultModel(){
      const configured=state.config.chat?.default_model; const candidate=this.currentModelId||configured;
      const found=this.models.find(m=>m.id===candidate); this.currentModelId=found?found.id:(this.models[0]?.id)||candidate||null;
      if(this.currentModelId)localStorage.setItem(MODEL_KEY,this.currentModelId); state.currentModel=this.currentModelId; state.modelOptions=getModelProfile(); this.updateHeader();
    },
    getRecommended(){return this.models.filter(m=>RECOMMENDED.includes(m.id));},
    getFree(){return this.models.filter(m=>{const p=m.pricing||{};return (String(p.prompt??'')==='0'&&String(p.completion??'')==='0')||state.currentProvider==='ollama';});},
    renderLoading(){['recommended','free','all'].forEach(g=>{const list=$(`model-list-${g}`);if(list)list.innerHTML='<li class="model-skeleton"></li><li class="model-skeleton"></li>';});if($('model-empty'))$('model-empty').hidden=true;},
    render(models,query=''){const q=String(query||'').trim().toLowerCase();this.filtered=models.filter(m=>`${m.id} ${m.name}`.toLowerCase().includes(q));const rec=new Set(this.getRecommended().map(m=>m.id)),free=new Set(this.getFree().map(m=>m.id));this.renderGroup('recommended',this.filtered.filter(m=>rec.has(m.id)));this.renderGroup('free',this.filtered.filter(m=>free.has(m.id)&&!rec.has(m.id)));this.renderGroup('all',this.filtered.filter(m=>!rec.has(m.id)&&!free.has(m.id)));if($('model-empty'))$('model-empty').hidden=this.filtered.length!==0;this.activeIndex=-1;},
    renderGroup(group,models){const list=$(`model-list-${group}`),wrapper=list?.closest('.model-group');if(!list||!wrapper)return;wrapper.hidden=models.length===0;list.innerHTML=models.map(model=>`<li><button type="button" class="model-option${model.id===this.currentModelId?' active':''}" role="option" aria-selected="${model.id===this.currentModelId}" data-model-id="${escapeHtml(model.id)}"><span class="model-option-name">${escapeHtml(model.name)}</span><small>${escapeHtml(model.id)}</small></button></li>`).join('');},
    open(){if(!this.dropdown)return;this.isOpen=true;this.dropdown.hidden=false;this.trigger.setAttribute('aria-expanded','true');this.render(this.models,this.search.value);this.providerSelect&&(this.providerSelect.value=state.currentProvider);this.search.focus();this.search.select();},
    close(){if(!this.dropdown)return;this.isOpen=false;this.dropdown.hidden=true;this.trigger.setAttribute('aria-expanded','false');this.activeIndex=-1;},
    select(modelId){const model=this.models.find(m=>m.id===modelId);if(!model)return;this.currentModelId=model.id;state.currentModel=model.id;state.modelOptions=getModelProfile();localStorage.setItem(MODEL_KEY,model.id);this.updateHeader();this.render(this.models,this.search.value);this.close();announce(`Model dipilih: ${model.name}`);if(state.currentSessionId&&!state.isStreaming){saveSession({refresh:true}).catch(()=>{});}},
    updateHeader(){const label=$('current-model-name'),provider=$('current-provider-name'),model=this.models.find(m=>m.id===this.currentModelId);if(label)label.textContent=model?model.name:(this.currentModelId||'Pilih Model');if(provider)provider.textContent=providerLabel(state.currentProvider);},
    getVisibleOptions(){return [...document.querySelectorAll('.model-option')].filter(el=>el.offsetParent!==null);},
    handleKeydown(e){if(!this.isOpen)return;const options=this.getVisibleOptions();if(e.key==='Escape'){e.preventDefault();this.close();this.trigger.focus();return;}if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();if(!options.length)return;this.activeIndex=(this.activeIndex+(e.key==='ArrowDown'?1:-1)+options.length)%options.length;options.forEach((el,i)=>el.classList.toggle('keyboard-active',i===this.activeIndex));options[this.activeIndex].scrollIntoView({block:'nearest'});}else if(e.key==='Enter'){e.preventDefault();const target=options[this.activeIndex]||options.find(el=>el.getAttribute('aria-selected')==='true');if(target)this.select(target.dataset.modelId);}},
    handleSearch(e){clearTimeout(this.searchTimer);const value=e.target.value;this.searchTimer=setTimeout(()=>this.render(this.models,value),200);}
  };

  const ThinkingBlock = {
    timers: new Map(),
    startedAt: new Map(),
    userCollapsed: new Set(),

    create(messageEl) {
      let block = messageEl.querySelector('.thinking-block');
      if (block) return block;
      const slot = messageEl.querySelector('.thinking-slot');
      if (!slot) return null;
      const template = document.querySelector('#thinking-block-template');
      if (template && template.content.firstElementChild) {
        block = template.content.firstElementChild.cloneNode(true);
      } else {
        block = document.createElement('details');
        block.className = 'thinking-block';
        block.innerHTML = '<summary class="thinking-summary"><span class="thinking-spinner" aria-hidden="true"><span></span><span></span><span></span></span><span class="thinking-chevron" aria-hidden="true"><svg viewBox="0 0 20 20" focusable="false"><path d="m7 4 6 6-6 6"/></svg></span><span class="thinking-label">Thinking</span><span class="thinking-timer" data-thinking-timer>0.0s</span></summary><div class="thinking-body" data-thinking-body></div>';
      }
      block.classList.add('thinking-instance');
      block.dataset.thinkingId = uuid();
      block.open = true;
      block.addEventListener('toggle', () => this.toggle(block));
      slot.appendChild(block);
      this.startedAt.set(block.dataset.thinkingId, Date.now());
      this.startTimer(block);
      return block;
    },

    appendReasoning(block, text) {
      if (!block) return;
      const id = block.dataset.thinkingId;
      if (!this.startedAt.has(id)) { this.startedAt.set(id, Date.now()); this.startTimer(block); }
      if (!this.userCollapsed.has(id)) block.open = true;
      const label = block.querySelector('.thinking-label');
      if (label) label.textContent = 'Thinking';
      const body = block.querySelector('[data-thinking-body]');
      if (!body) return;
      if (body.dataset.reasoningUnavailable === 'true') {
        body.textContent = '';
        delete body.dataset.reasoningUnavailable;
      }
      body.dataset.raw = (body.dataset.raw || '') + String(text || '');
      body.innerHTML = window.renderMarkdown ? renderMarkdown(body.dataset.raw) : escapeHtml(body.dataset.raw);
    },

    finalize(block) {
      if (!block || block.dataset.finalized === 'true') return;
      block.dataset.finalized = 'true';
      this.stopTimer(block);
      const spinner = block.querySelector('.thinking-spinner');
      if (spinner) spinner.classList.add('done');
      // Many chat models expose no private reasoning stream. Keep the Thinking
      // disclosure useful without fabricating reasoning when no transcript exists.
      const body = block.querySelector('[data-thinking-body]');
      if (body && !String(body.dataset.raw || '').trim() && !body.dataset.reasoningUnavailable) {
        body.textContent = 'Model tidak mengirimkan data Thinking pada respons ini.';
        body.dataset.reasoningUnavailable = 'true';
      }
      const id = block.dataset.thinkingId;
      setTimeout(() => {
        if (!this.userCollapsed.has(id)) block.open = false;
      }, 500);
    },

    startTimer(block) {
      const id = block.dataset.thinkingId;
      this.stopTimer(block);
      this.timers.set(id, setInterval(() => {
        const started = this.startedAt.get(id) || Date.now();
        const timer = block.querySelector('[data-thinking-timer]');
        if (timer) timer.textContent = this.formatDuration(Date.now() - started);
      }, 100));
    },

    stopTimer(block) {
      const id = block.dataset.thinkingId;
      if (this.timers.has(id)) { clearInterval(this.timers.get(id)); this.timers.delete(id); }
    },

    toggle(block) {
      if (!block || !block.dataset.thinkingId) return;
      const id = block.dataset.thinkingId;
      if (block.open) this.userCollapsed.delete(id);
      else this.userCollapsed.add(id);
    },

    formatDuration(ms) { return `${(Math.max(0, ms) / 1000).toFixed(1)}s`; },
  };

  function renderMessage(msg) {
    const row = document.createElement('article');
    row.className = `message-row ${msg.role === 'user' ? 'user-row' : 'ai-row'}`;
    row.dataset.role = msg.role;
    row.dataset.index = String(state.messages.indexOf(msg));
    if (msg.role === 'user') {
      row.innerHTML = `<div class="message-column"><div class="message-bubble user-bubble"></div><div class="message-actions"><button type="button" data-action="copy" aria-label="Salin pesan">${SVG.copy}</button><button type="button" data-action="edit" aria-label="Edit pesan">${SVG.edit}</button><button type="button" data-action="retry" aria-label="Kirim ulang">${SVG.retry}</button></div></div>`;
      row.querySelector('.user-bubble').textContent = repairMojibake(msg.content || '');
      if (Array.isArray(msg.attachments) && msg.attachments.length) {
        const attachments = document.createElement('div'); attachments.className = 'attachment-list';
        attachments.innerHTML = msg.attachments.map((a) => `<div class="attachment-chip"><span>📎 ${escapeHtml(a.name || 'attachment')}</span></div>`).join('');
        row.querySelector('.message-column').insertBefore(attachments, row.querySelector('.message-actions'));
      }
    } else {
      row.innerHTML = `<div class="message-column"><div class="ai-content"><div class="thinking-slot"></div><div class="message-bubble ai-bubble"></div></div><div class="message-actions"><button type="button" data-action="copy" aria-label="Salin jawaban">${SVG.copy}</button><button type="button" data-action="tts" aria-label="Bacakan jawaban">${SVG.speaker}</button><button type="button" data-action="share" aria-label="Bagikan jawaban">${SVG.share}</button><button type="button" data-action="bookmark" aria-label="Simpan jawaban">${SVG.star}</button><button type="button" data-action="menu" aria-label="Menu jawaban">${SVG.more}</button></div></div>`;
      if (msg.content) row.querySelector('.ai-bubble').innerHTML = renderMarkdown(repairMojibake(msg.content));
      if (msg.reasoning) {
        const block = ThinkingBlock.create(row);
        ThinkingBlock.appendReasoning(block, repairMojibake(msg.reasoning));
        ThinkingBlock.finalize(block);
      }
    }
    return row;
  }

  function renderMessages() {
    const canvas = $('chat-canvas');
    if (!canvas) return;
    canvas.innerHTML = '';
    if (!state.messages.length) {
      const empty = document.createElement('div');
      empty.innerHTML = `<div class="empty-state" id="empty-state"><div class="empty-icon yookai-mark" aria-hidden="true"><svg viewBox="0 0 48 48" focusable="false"><path d="M24 5c-9.4 0-17 7.6-17 17v17.5c0 1.5 1.8 2.2 2.9 1.1l4-3.9 4.2 3.9 3.9-3.9 4 3.9 4.1-3.9 4.1 3.9 4-3.9 4 3.9c1.1 1.1 2.9.4 2.9-1.1V22C41 12.6 33.4 5 24 5Z"/><circle cx="18" cy="22" r="2"/><circle cx="30" cy="22" r="2"/><path d="M17 30c4 3 10 3 14 0"/></svg></div><h1>Mulai percakapan baru</h1><p>Pilih model, tulis prompt, gaskeun.</p><div class="prompt-suggestions" role="list"><button type="button" data-suggestion="Jelaskan konsep ini dengan sederhana">Jelaskan konsep ini dengan sederhana</button><button type="button" data-suggestion="Bantu saya menulis kode yang rapi">Bantu saya menulis kode yang rapi</button><button type="button" data-suggestion="Analisis masalah ini langkah demi langkah">Analisis masalah ini langkah demi langkah</button></div></div>`;
      canvas.appendChild(empty.firstElementChild);
      return;
    }
    state.messages.forEach((msg) => canvas.appendChild(renderMessage(msg)));
    scrollToBottom(false);
  }

  function renderSessionList(sessions = state.sessions) {
    const list = $('session-list');
    if (!list) return;
    if (!sessions.length) { list.innerHTML = '<div class="session-empty">Belum ada chat</div>'; return; }
    const now = Date.now();
    const groups = [['Hari Ini', []], ['Kemarin', []], ['7 Hari', []], ['30 Hari', []], ['Lebih Lama', []]];
    sessions.forEach((session) => {
      const time = Date.parse(session.updated_at || '') || 0;
      const days = Math.floor((now - time) / 86400000);
      const index = days <= 0 ? 0 : days === 1 ? 1 : days <= 7 ? 2 : days <= 30 ? 3 : 4;
      groups[index][1].push(session);
    });
    list.innerHTML = groups.filter(([, items]) => items.length).map(([label, items]) => `<section class="session-group"><h3>${label}</h3>${items.map((s) => `<button type="button" class="session-item${s.id === state.currentSessionId ? ' active' : ''}" data-session-id="${escapeHtml(s.id)}"><span>${escapeHtml(s.title || 'New Chat')}</span></button>`).join('')}</section>`).join('');
  }

  async function refreshSessions() {
    const data = await client.listSessions();
    state.sessions = data.sessions || [];
    renderSessionList();
  }

  async function saveSession({createIfMissing = false, refresh = true} = {}) {
    if (!state.messages.length) return null;
    if (!state.currentSessionId && !createIfMissing) return null;
    const existing = state.sessions.find((s) => s.id === state.currentSessionId);
    const firstUser = state.messages.find((m) => m.role === 'user');
    const payload = {
      ...(state.currentSessionId ? {id: state.currentSessionId} : {}),
      title: existing?.title || 'New Chat',
      provider: state.currentProvider,
      model: state.currentModel,
      model_config: {...state.modelOptions},
      messages: state.messages,
    };
    if (!existing && firstUser?.content) payload.title = String(firstUser.content).trim().slice(0, 80) || 'New Chat';
    const result = await client.saveSession(payload);
    state.currentSessionId = result.id;
    try { sessionStorage.setItem(ACTIVE_SESSION_KEY, result.id); } catch (_) {}
    if (refresh) await refreshSessions();
    return result;
  }

  async function ensureSessionPersisted() {
    if (state.currentSessionId) return state.currentSessionId;
    const result = await saveSession({createIfMissing: true, refresh: true});
    return result?.id || null;
  }

  async function newChat() {
    state.generation += 1;
    if (state.isStreaming) await handleStop();
    state.currentSessionId = null;
    try { sessionStorage.removeItem(ACTIVE_SESSION_KEY); } catch (_) {}
    state.messages = [];
    state.userScrolledUp = false;
    renderMessages();
    updateSidebarActive(null);
    closeSidebar();
    $('composer-input')?.focus();
  }

  async function loadSession(id) {
    try {
      if (state.isStreaming) await handleStop();
      const session = await client.loadSession(id);
      state.currentSessionId = session.id;
      try { sessionStorage.setItem(ACTIVE_SESSION_KEY, session.id); } catch (_) {}
      state.currentProvider = session.provider || state.currentProvider;
      state.currentModel = session.model || state.currentModel;
      if (state.currentProvider !== ModelSelector.providerForLoadedModels) {
        ModelSelector.providerForLoadedModels = state.currentProvider;
        try { await ModelSelector.loadModels(); } catch (_) {}
      }
      state.modelOptions = {...getModelProfile(session.provider || state.currentProvider, session.model || state.currentModel), ...(session.model_config || {})};
      if (state.currentModel) {
        ModelSelector.currentModelId = state.currentModel;
        localStorage.setItem(MODEL_KEY, state.currentModel);
        ModelSelector.updateHeader();
      }
      state.messages = Array.isArray(session.messages) ? session.messages : [];
      renderMessages();
      updateSidebarActive(id);
      closeSidebar();
    } catch (error) {
      if (error.status === 404) { await newChat(); showToast('Session tidak ditemukan.', 'error'); }
      else showToast(error.message || 'Gagal memuat session.', 'error');
    }
  }

  async function deleteSession(id) {
    try {
      await client.deleteSession(id);
      if (id === state.currentSessionId) await newChat();
      await refreshSessions();
    } catch (error) { showToast(error.message || 'Gagal menghapus session.', 'error'); }
  }

  async function handleSend(text) {
    const content = String(text || '').trim();
    if (!content || state.isStreaming || state.uploadingCount > 0) { if (state.uploadingCount > 0) showToast('Tunggu upload selesai.', 'info'); return; }
    if (!state.currentModel) { showToast('Pilih model terlebih dahulu.', 'error'); ModelSelector.open(); return; }
    const generation = ++state.generation;
    const startedAt = new Date().toISOString();
    const attachments = state.pendingAttachments.splice(0);
    renderAttachmentList();
    state.messages.push({role:'user', content, attachments, created_at: startedAt});
    const selectedModel = ModelSelector.models.find((m) => m.id === state.currentModel);
    const modelOptions = {...getModelProfile()}; state.modelOptions = modelOptions;
    state.messages.push({role:'assistant', content:'', reasoning:'', created_at: startedAt, started_at: startedAt, model: state.currentModel, provider: state.currentProvider, model_options: modelOptions, model_pricing: selectedModel?.pricing || {}});
    renderMessages();
    state.isStreaming = true;
    updateComposerState(true);
    state.abortController = new AbortController();
    state.requestId = uuid();
    const requestId = state.requestId;
    const aiIndex = state.messages.length - 1;
    const aiRow = $('chat-canvas')?.lastElementChild;
    let thinking = ThinkingBlock.create(aiRow);
    try {
      // Persist immediately so the chat appears in History even while the model is
      // still thinking. The final save updates the same session after streaming.
      await ensureSessionPersisted();
      await client.streamChat({provider: state.currentProvider, model: state.currentModel, session_id: state.currentSessionId, messages: state.messages.slice(0, -1), options: modelOptions, request_id: requestId}, (chunk) => {
        if (generation !== state.generation || requestId !== state.requestId || !state.messages[aiIndex]) return;
        if (chunk.type === 'reasoning') {
          ThinkingBlock.appendReasoning(thinking, chunk.content || '');
          state.messages[aiIndex].reasoning += repairMojibake(chunk.content || '');
        } else if (chunk.type === 'content') {
          state.messages[aiIndex].content += repairMojibake(chunk.content || '');
          const bubble = aiRow?.querySelector('.ai-bubble');
          if (bubble) StreamRender.schedule(aiRow, bubble, () => state.messages[aiIndex]?.content || '');
          aiRow?.classList.add('streaming-cursor');
          if (!state.userScrolledUp) scheduleScroll();
        } else if (chunk.type === 'usage') {
          state.messages[aiIndex].usage = chunk.usage || {};
        } else if (chunk.type === 'error') {
          throw new Error(chunk.message || 'Provider error');
        } else if (chunk.type === 'done') {
          if (thinking) {
            // Preserve the thinking transcript after completion; only stop its live timer/animation.
            ThinkingBlock.finalize(thinking);
          }
          // Some compatible providers can terminate successfully without a text delta.
          // Never leave an apparently completed, empty assistant turn in the transcript.
          if (!String(state.messages[aiIndex].content || '').trim()) {
            const emptyReasoning = !String(state.messages[aiIndex].reasoning || '').trim();
            state.messages[aiIndex].content = emptyReasoning
              ? 'Model mengakhiri respons tanpa mengirim teks. Coba kirim ulang prompt atau pilih model lain.'
              : 'Model hanya mengirim reasoning tanpa jawaban akhir. Coba kirim ulang prompt.';
            const bubble = aiRow?.querySelector('.ai-bubble');
            if (bubble) bubble.textContent = state.messages[aiIndex].content;
          }
          // A terminal SSE event is authoritative: unlock the composer now,
          // rather than waiting for a mobile browser to observe stream EOF.
          aiRow?.classList.remove('streaming-cursor');
          StreamRender.cancel(aiRow);
          state.isStreaming = false;
          state.abortController = null;
          state.requestId = null;
          updateComposerState(false);
        }
      }, state.abortController.signal);
      if (generation !== state.generation || requestId !== state.requestId) return;
      if (thinking) ThinkingBlock.finalize(thinking);
      StreamRender.cancel(aiRow);
      const finalBubble = aiRow?.querySelector('.ai-bubble');
      if (finalBubble) finalBubble.innerHTML = renderMarkdown(repairMojibake(state.messages[aiIndex].content || ''));
      aiRow?.classList.remove('streaming-cursor');
      state.messages[aiIndex].completed_at = new Date().toISOString();
      state.messages[aiIndex].duration_ms = Math.max(0, Date.parse(state.messages[aiIndex].completed_at) - Date.parse(state.messages[aiIndex].started_at || startedAt));
      // Release the composer as soon as the stream has ended; persistence must not
      // keep the UI in a false streaming state if a save is slow or stalled.
      state.isStreaming = false;
      state.abortController = null;
      state.requestId = null;
      updateComposerState(false);
      await saveSession();
    } catch (error) {
      if (error.name !== 'AbortError' && generation === state.generation) {
        showToast(error.message || 'Gagal mengirim pesan.', 'error', {label:'Retry', run:() => handleRetry(aiIndex)});
        if (state.messages[aiIndex] && !state.messages[aiIndex].content && !state.messages[aiIndex].reasoning) state.messages.splice(aiIndex, 1);
        // Keep the user message in history if the upstream failed after the
        // session was created; this makes failures auditable/retryable.
        try { if (state.currentSessionId) await saveSession(); } catch (_) {}
        renderMessages();
      }
    } finally {
      if (generation === state.generation) {
        state.isStreaming = false;
        state.abortController = null;
        state.requestId = null;
        updateComposerState(false);
      }
    }
  }

  async function handleStop() {
    if (!state.isStreaming) return;
    const requestId = state.requestId;
    const provider = state.currentProvider;
    // Release the UI synchronously: stop requests and session persistence can be
    // delayed by a slow network, but must never leave the composer in Thinking.
    state.generation += 1;
    state.abortController?.abort();
    state.isStreaming = false;
    state.abortController = null;
    state.requestId = null;
    updateComposerState(false);

    document.querySelectorAll('.thinking-block').forEach((block) => ThinkingBlock.finalize(block));
    document.querySelectorAll('.streaming-cursor').forEach((row) => StreamRender.cancel(row));
    const last = state.messages[state.messages.length - 1];
    if (last?.role === 'assistant') {
      last.completed_at = new Date().toISOString();
      last.duration_ms = Math.max(0, Date.parse(last.completed_at) - Date.parse(last.started_at || last.created_at || new Date().toISOString()));
    }
    // Cancellation and persistence are best-effort background cleanup. The
    // generation guard prevents their late completion from changing a new turn.
    if (requestId) client.stopChat(requestId, state.currentProvider).catch(() => {});
    if (last?.role === 'assistant') saveSession().catch(() => {});
  }

  async function handleRetry(msgIndex) {
    if (state.isStreaming) return;
    const target=state.messages[msgIndex];
    const user=target?.role==='user' ? target : state.messages.slice(0,msgIndex).reverse().find(m=>m.role==='user');
    if(!user)return;
    const retryAttachments=target?.role==='user' && Array.isArray(user.attachments) ? user.attachments : [];
    // A retry on a user message replaces that turn. A retry on an assistant
    // message regenerates the answer without duplicating the user turn.
    state.messages=state.messages.slice(0,target?.role==='user'?msgIndex:msgIndex);
    state.pendingAttachments.push(...retryAttachments);
    renderMessages(); renderAttachmentList();
    if(state.currentSessionId){try{await saveSession();}catch(_) {}}
    const text=user.content||'';
    await handleSend(text);
  }

  async function handleEdit(msgIndex) {
    const msg = state.messages[msgIndex];
    if (!msg || msg.role !== 'user') return;
    const input = $('composer-input');
    input.value = msg.content;
    state.messages = state.messages.slice(0, msgIndex);
    renderMessages();
    updateComposerState(false);
    if (state.currentSessionId) { try { await saveSession(); } catch (_) {} }
    input.focus();
    input.setSelectionRange(input.value.length, input.value.length);
  }

  async function copyText(text, button) {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        const area = document.createElement('textarea');
        area.value = String(text || '');
        area.style.position = 'fixed'; area.style.opacity = '0';
        document.body.appendChild(area); area.select();
        if (!document.execCommand('copy')) throw new Error('Clipboard unavailable');
        area.remove();
      }
      if (!button) return;
      const old = button.textContent;
      button.textContent = '✓';
      button.classList.add('copy-success');
      setTimeout(() => { button.textContent = old; button.classList.remove('copy-success'); }, 1000);
    } catch (_) { showToast('Gagal menyalin.', 'error'); }
  }

  function scheduleScroll() {
    if (scheduleScroll.pending) return;
    scheduleScroll.pending = true;
    requestAnimationFrame(() => { scheduleScroll.pending = false; scrollToBottom(false); });
  }

  function scrollToBottom(smooth = true) {
    const node = $('chat-scroll');
    if (!node || state.userScrolledUp) return;
    node.scrollTo({top: node.scrollHeight, behavior: smooth ? 'smooth' : 'auto'});
  }

  function updateComposerState(streaming = state.isStreaming) {
    const input = $('composer-input');
    const send = $('send-btn');
    const stop = $('stop-btn');
    if (input) input.disabled = streaming;
    if (send) { send.disabled = streaming || state.uploadingCount > 0 || !input?.value.trim(); send.hidden = streaming; send.classList.remove('loading'); send.setAttribute('aria-busy', String(streaming)); }
    if (stop) stop.hidden = !streaming;
  }

  function autoResize() {
    const input = $('composer-input');
    if (!input) return;
    input.style.height = 'auto';
    input.style.height = `${Math.min(input.scrollHeight, 180)}px`;
  }

  function updateSidebarActive(id) {
    document.querySelectorAll('.session-item').forEach((item) => item.classList.toggle('active', item.dataset.sessionId === id));
  }

  function isCompactLayout() { return window.matchMedia('(max-width: 1024px)').matches; }

  function closeSidebar() {
    const shell = $('app-shell');
    if (!shell) return;
    if (isCompactLayout()) {
      shell.classList.remove('sidebar-open');
      $('toggle-sidebar')?.setAttribute('aria-expanded', 'false');
    }
  }

  function collapseSidebar() {
    const shell = $('app-shell');
    if (!shell || isCompactLayout()) return;
    shell.classList.add('sidebar-collapsed');
    localStorage.setItem('yookai-sidebar-collapsed', 'true');
    $('toggle-sidebar')?.setAttribute('aria-expanded', 'false');
  }

  function toggleSidebar() {
    const shell = $('app-shell');
    if (!shell) return;
    if (isCompactLayout()) {
      const open = shell.classList.toggle('sidebar-open');
      $('toggle-sidebar')?.setAttribute('aria-expanded', String(open));
    } else {
      const collapsed = shell.classList.toggle('sidebar-collapsed');
      localStorage.setItem('yookai-sidebar-collapsed', String(collapsed));
      $('toggle-sidebar')?.setAttribute('aria-expanded', String(!collapsed));
    }
  }

  function applyTheme(theme) {
    const value = theme === 'light' ? 'light' : 'dark';
    document.documentElement.dataset.theme = value;
    localStorage.setItem('yookai-theme', value);
    $('theme-toggle')?.setAttribute('aria-label', value === 'dark' ? 'Aktifkan tema terang' : 'Aktifkan tema gelap');
    $('theme-toggle').innerHTML = value === 'dark' ? '<svg viewBox="0 0 24 24" focusable="false"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/></svg>' : '<svg viewBox="0 0 24 24" focusable="false"><path d="M20 15.5A8.5 8.5 0 0 1 8.5 4 8.5 8.5 0 1 0 20 15.5Z"/></svg>';
  }

  function toggleTheme() { applyTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'); }

  function populateProviderSelect(selectId, includeCurrent=true) {
    const select=$(selectId); if(!select)return;
    const providers=ModelSelector.providers.length?ModelSelector.providers:Object.keys(PROVIDER_LABELS).map(name=>({name}));
    select.innerHTML=providers.map(p=>`<option value="${escapeHtml(p.name)}">${escapeHtml(providerLabel(p.name))}</option>`).join('');
    if(includeCurrent)select.value=state.currentProvider;
  }

  function openSettings() {
    const modal=$('settings-modal'); if(!modal)return;
    populateProviderSelect('settings-provider');
    const provider=state.config.provider?.[state.currentProvider]||{};
    $('settings-api-key').value=provider.api_key||'';
    $('settings-base-url').value=provider.base_url||'';
    $('settings-default-model').value=state.config.chat?.default_model||state.currentModel||'';
    $('settings-memory-mode').value=state.config.memory?.mode||'default';
    $('settings-project-id').value=state.config.memory?.project_id||'default';
    modal.showModal(); $('settings-api-key').focus();
  }

  function openModelSettings() {
    const modal=$('model-settings-modal'); if(!modal||!state.currentModel){showToast('Pilih model terlebih dahulu.','error');return;}
    populateProviderSelect('model-settings-provider');
    $('model-settings-provider').value=state.currentProvider;
    $('model-settings-model').value=state.currentModel;
    const options=getModelProfile();
    $('model-settings-temperature').value=options.temperature;
    $('model-settings-top-p').value=options.top_p;
    $('model-settings-max-tokens').value=options.max_tokens;
    $('model-settings-reasoning').value=options.reasoning_effort||'auto';
    $('model-settings-system').value=options.system_prompt||'';
    modal.showModal();
  }

  async function saveModelSettings() {
    if(!state.currentModel)return;
    const options={
      temperature:Math.min(2,Math.max(0,Number($('model-settings-temperature').value||0.7))),
      top_p:Math.min(1,Math.max(0,Number($('model-settings-top-p').value||1))),
      max_tokens:Math.min(131072,Math.max(1,Math.floor(Number($('model-settings-max-tokens').value||2048)))),
      reasoning_effort:$('model-settings-reasoning').value||'auto',
      system_prompt:$('model-settings-system').value||''
    };
    setModelProfile(state.currentProvider,state.currentModel,options);
    try {
      await client.saveConfig(state.config);
      state.config=await client.getConfig(); state.modelOptions=getModelProfile();
      if(state.currentSessionId&&!state.isStreaming){try{await saveSession({refresh:true});}catch(_){}}
      $('model-settings-modal').close(); showToast('Model profile disimpan.','success');
    } catch(e){showToast(e.message||'Gagal menyimpan model profile.','error');}
  }

  async function saveSettings() {
    const config=typeof structuredClone==='function'?structuredClone(state.config):JSON.parse(JSON.stringify(state.config));
    config.provider ||= {};
    const providerName=$('settings-provider').value||state.currentProvider;
    config.provider[providerName] ||= {};
    const key=$('settings-api-key').value.trim();
    if(key&&!key.includes('***'))config.provider[providerName].api_key=key;
    config.provider[providerName].base_url=$('settings-base-url').value.trim() || config.provider[providerName].base_url;
    config.provider.default=providerName;
    config.chat ||= {};
    config.chat.default_model=$('settings-default-model').value.trim()||state.currentModel||config.chat.default_model;
    config.chat.model_profiles ||= {};
    config.memory ||= {};
    config.memory.mode=$('settings-memory-mode').value;
    config.memory.project_id=$('settings-project-id').value.trim()||'default';
    config.memory.retrieval_limit=Number(config.memory.retrieval_limit||12);
    try {
      await client.saveConfig(config); state.config=await client.getConfig(); state.currentProvider=providerName;
      ModelSelector.providers=ModelSelector.providers.length?ModelSelector.providers:await ModelSelector.loadProviders();
      ModelSelector.currentModelId=null; ModelSelector.models=[]; ModelSelector.invalidateCache();
      await ModelSelector.loadModels(); $('settings-modal').close(); showToast('Settings disimpan.','success');
    } catch(error){showToast(error.message||'Gagal menyimpan konfigurasi.','error');}
  }

  async function openStats() {
    const modal = $('stats-modal');
    const grid = $('stats-grid');
    if (!modal || !grid) return;
    if (!state.currentSessionId) {
      grid.innerHTML = '<div class="session-empty">Belum ada percakapan aktif.</div>';
      modal.showModal();
      return;
    }
    grid.innerHTML = '<div class="session-empty">Menghitung statistics…</div>';
    modal.showModal();
    try {
      const stats = await client.getSessionStats(state.currentSessionId);
      const items = [
        ['Pesan', stats.message_count], ['User', stats.user_messages], ['AI', stats.assistant_messages],
        ['Karakter', formatNumber(stats.character_count)], ['Est. token', formatNumber(stats.estimated_tokens)],
        ['Input token', formatNumber(stats.actual_input_tokens || stats.estimated_input_tokens)],
        ['Output token', formatNumber(stats.actual_output_tokens || stats.estimated_output_tokens)],
        ['Durasi', formatDurationMs(stats.duration_ms)], ['Attachment', stats.attachment_count], ['Cost', stats.estimated_cost_usd ? `$${Number(stats.estimated_cost_usd).toFixed(6)}` : '—'],
        ['Mulai', stats.created_at ? new Date(stats.created_at).toLocaleString('id-ID') : '—'],
        ['Update', stats.updated_at ? new Date(stats.updated_at).toLocaleString('id-ID') : '—'],
      ];
      grid.innerHTML = items.map(([label, value]) => `<div class="stat-card"><small>${label}</small><strong>${value}</strong></div>`).join('');
    } catch (error) {
      grid.innerHTML = `<div class="session-empty">${escapeHtml(error.message || 'Gagal menghitung statistics.')}</div>`;
    }
  }

  function handleAction(event) {
    const button = event.target.closest('[data-action]');
    if (!button) return;
    const row = button.closest('.message-row');
    const index = Number(row?.dataset.index);
    const msg = state.messages[index];
    if (!msg) return;
    if (button.dataset.action === 'copy') copyText(msg.content || msg.reasoning || '', button);
    else if (button.dataset.action === 'edit') handleEdit(index);
    else if (button.dataset.action === 'retry') handleRetry(index);
    else if (button.dataset.action === 'tts' && 'speechSynthesis' in window) speechSynthesis.speak(new SpeechSynthesisUtterance(msg.content || ''));
    else if (button.dataset.action === 'share') navigator.share?.({title:'YookAI', text:msg.content || ''});
    else if (button.dataset.action === 'bookmark') showToast('Bookmark akan tersedia di versi berikutnya.');
    else if (button.dataset.action === 'menu') showToast('Menu jawaban belum memiliki aksi tambahan.');
  }

  async function openMemory() {
    const modal=$('memory-modal'), list=$('memory-list'); if(!modal||!list)return;
    modal.showModal(); list.innerHTML='<div class="session-empty">Loading memory…</div>';
    await refreshMemory(); $('memory-search')?.focus();
  }
  async function refreshMemory() {
    const list=$('memory-list'); if(!list)return;
    try {
      const data=await client.listMemory($('memory-search')?.value||'');
      const records=data.records||[];
      list.innerHTML=records.length?records.map(r=>`<article class="memory-record"><div class="memory-record-head"><span>${escapeHtml(r.role||'memory')} · ${r.created_at?new Date(r.created_at).toLocaleString('id-ID'):''}</span><button class="memory-delete" data-memory-id="${escapeHtml(r.id)}" type="button">Delete</button></div><p>${escapeHtml(r.content||'')}</p></article>`).join(''):'<div class="session-empty">No memory records.</div>';
    } catch(e){ list.innerHTML=`<div class="session-empty">${escapeHtml(e.message||'Failed to load memory.')}</div>`; }
  }
  async function clearMemory() {
    if(!confirm('Clear the current memory store?')) return;
    try { await client.clearMemory(state.config.memory?.mode||'default',state.config.memory?.project_id||'default'); await refreshMemory(); showToast('Memory cleared.','success'); }
    catch(e){showToast(e.message||'Failed to clear memory.','error');}
  }
  async function searchChats(query) {
    const results=$('search-results'); if(!results)return;
    const q=String(query||'').trim().toLowerCase();
    const items=state.sessions.filter(x=>!q||String(x.title||'').toLowerCase().includes(q));
    results.innerHTML=items.length?items.map(x=>`<button class="search-result" data-search-session="${escapeHtml(x.id)}" type="button"><strong>${escapeHtml(x.title||'New Chat')}</strong><small>${x.updated_at?new Date(x.updated_at).toLocaleString('id-ID'):''}</small></button>`).join(''):'<div class="session-empty">No matching chats.</div>';
  }
  function openSearch(){ const m=$('search-modal'); if(!m)return; m.showModal(); searchChats(''); $('chat-search')?.focus(); }
  async function exportCurrentSession(){
    if(!state.currentSessionId){showToast('No active chat.','error');return;}
    try { const data=await client.exportSession(state.currentSessionId); const blob=new Blob([data.content],{type:'application/json'}); const a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download=data.filename||'yookai-chat.json'; a.click(); URL.revokeObjectURL(a.href); }
    catch(e){showToast(e.message||'Export failed.','error');}
  }
  function renderAttachmentPreview(){ renderAttachmentList(); }

  const ToolsPanel = {
    current: null,
    async open() {
      const modal = $('tools-modal');
      if (!modal) return;
      modal.showModal();
      const list = $('tools-list');
      if (list) list.innerHTML = '<div class="model-skeleton"></div><div class="model-skeleton"></div>';
      try {
        const data = await client.listTools();
        const tools = data.tools || [];
        if (!tools.length) { list.innerHTML = '<p class="muted">No local tools are available.</p>'; return; }
        list.innerHTML = tools.map(tool => `<article class="tool-card"><strong>${escapeHtml(tool.name)}</strong><small>${escapeHtml(tool.description)}</small><span class="tool-badge">${tool.requires_confirmation ? 'Confirmation required' : 'Safe by default'}</span><br><button class="btn secondary" type="button" data-run-tool="${escapeHtml(tool.name)}">Run</button></article>`).join('');
      } catch (error) { list.innerHTML = `<p class="muted">${escapeHtml(error.message || 'Failed to load tools.')}</p>`; }
    },
    choose(name) {
      this.current = name;
      const consoleEl = $('tool-console');
      const title = $('tool-console-title');
      const args = $('tool-args');
      const result = $('tool-result');
      if (!consoleEl || !args) return;
      title.textContent = name;
      result.textContent = '';
      args.value = name === 'calculator' ? '{"expression":"2 + 2"}' : name === 'filesystem.list' ? '{"path":"."}' : name === 'filesystem.read' ? '{"path":"README.md"}' : '{"command":"pwd"}';
      consoleEl.hidden = false;
      args.focus();
    },
    async run() {
      if (!this.current) return;
      let args;
      try { args = JSON.parse($('tool-args').value || '{}'); } catch (_) { showToast('Tool arguments must be valid JSON.','error'); return; }
      const resultEl = $('tool-result');
      resultEl.textContent = 'Running…';
      try {
        let data = await client.executeTool(this.current, args);
        if (data.status === 'confirmation_required') {
          const confirmed = window.confirm(`Tool "${this.current}" requires confirmation. Continue?`);
          if (!confirmed) { resultEl.textContent = 'Cancelled.'; return; }
          data = await client.executeTool(this.current, args, data.confirmation_token);
        }
        resultEl.textContent = JSON.stringify(data.result ?? data, null, 2);
      } catch (error) { resultEl.textContent = error.message || 'Tool execution failed.'; }
    }
  };

  function setupEvents() {
    if (eventsBound) return;
    eventsBound = true;
    $('composer-form')?.addEventListener('submit', (e) => { e.preventDefault(); const input = $('composer-input'); const value = input.value; input.value=''; autoResize(); updateComposerState(); handleSend(value); });
    $('composer-input')?.addEventListener('input', () => { autoResize(); updateComposerState(); });
    $('composer-input')?.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); $('composer-form').requestSubmit(); } });
    $('stop-btn')?.addEventListener('click', handleStop);
    $('attach-btn')?.addEventListener('click', () => $('attachment-input')?.click());
    $('attachment-input')?.addEventListener('change', (e) => { uploadFiles([...e.target.files]); e.target.value = ''; });
    $('composer-form')?.addEventListener('dragover', (e) => { e.preventDefault(); $('composer')?.classList.add('dragging'); });
    $('composer-form')?.addEventListener('dragleave', () => $('composer')?.classList.remove('dragging'));
    $('composer-form')?.addEventListener('drop', (e) => { e.preventDefault(); $('composer')?.classList.remove('dragging'); uploadFiles([...e.dataTransfer.files]); });
    $('attachment-list')?.addEventListener('click', (e) => {
      const button = e.target.closest('[data-remove-attachment]');
      if (button) { state.pendingAttachments.splice(Number(button.dataset.removeAttachment), 1); renderAttachmentList(); }
    });
    $('new-chat')?.addEventListener('click', newChat);
    $('toggle-sidebar')?.addEventListener('click', toggleSidebar);
    $('sidebar-collapse')?.addEventListener('click', () => isCompactLayout() ? closeSidebar() : collapseSidebar());
    $('open-stats')?.addEventListener('click', openStats);
    $('open-memory')?.addEventListener('click', openMemory);
    $('open-tools')?.addEventListener('click', () => ToolsPanel.open());
    $('close-tools')?.addEventListener('click', () => $('tools-modal')?.close());
    $('close-tool-console')?.addEventListener('click', () => { $('tool-console').hidden = true; });
    $('tools-list')?.addEventListener('click', (e) => { const b=e.target.closest('[data-run-tool]'); if(b) ToolsPanel.choose(b.dataset.runTool); });
    $('run-tool')?.addEventListener('click', () => ToolsPanel.run());
    $('tools-modal')?.addEventListener('click', (e) => { if(e.target === $('tools-modal')) $('tools-modal').close(); });
    $('close-memory')?.addEventListener('click', () => $('memory-modal')?.close());
    $('memory-search')?.addEventListener('input', () => refreshMemory());
    $('clear-memory')?.addEventListener('click', clearMemory);
    $('memory-list')?.addEventListener('click', async (e) => { const b=e.target.closest('[data-memory-id]'); if(!b)return; try{await client.deleteMemory(b.dataset.memoryId);await refreshMemory();}catch(err){showToast(err.message||'Failed to delete memory.','error');} });
    $('open-search')?.addEventListener('click', openSearch);
    $('close-search')?.addEventListener('click', () => $('search-modal')?.close());
    $('chat-search')?.addEventListener('input', e => searchChats(e.target.value));
    $('search-results')?.addEventListener('click', e => { const b=e.target.closest('[data-search-session]'); if(b){ $('search-modal')?.close(); loadSession(b.dataset.searchSession); } });
    $('export-chat')?.addEventListener('click', exportCurrentSession);
    $('close-stats-bottom')?.addEventListener('click', () => $('stats-modal')?.close());
    $('close-stats')?.addEventListener('click', () => $('stats-modal')?.close());
    $('stats-modal')?.addEventListener('click', (e) => { if (e.target === $('stats-modal')) $('stats-modal').close(); });
    $('sidebar-backdrop')?.addEventListener('click', closeSidebar);
    $('theme-toggle')?.addEventListener('click', toggleTheme);
    $('header-settings')?.addEventListener('click', openSettings);
    $('open-settings')?.addEventListener('click', openSettings);
    $('save-settings')?.addEventListener('click', saveSettings);
    $('settings-provider')?.addEventListener('change',(e)=>{const provider=state.config.provider?.[e.target.value]||{};$('settings-api-key').value=provider.api_key||'';$('settings-base-url').value=provider.base_url||'';$('settings-default-model').value=state.config.chat?.default_model||'';});
    $('model-settings-trigger')?.addEventListener('click', (e)=>{e.preventDefault();e.stopPropagation();ModelSelector.close();openModelSettings();});
    $('save-model-settings')?.addEventListener('click', saveModelSettings);
    document.querySelectorAll('[data-close-model-settings]').forEach(el=>el.addEventListener('click',()=>$('model-settings-modal')?.close()));
    $('model-settings-modal')?.addEventListener('click',e=>{if(e.target===$('model-settings-modal'))$('model-settings-modal').close();});
    document.querySelectorAll('[data-close-settings]').forEach((el) => el.addEventListener('click', () => $('settings-modal')?.close()));
    $('settings-modal')?.addEventListener('click', (e) => { if (e.target === $('settings-modal')) $('settings-modal').close(); });
    $('chat-canvas')?.addEventListener('click', (e) => {
      const suggestion = e.target.closest('[data-suggestion]');
      if (suggestion) { $('composer-input').value = suggestion.dataset.suggestion; updateComposerState(); $('composer-input').focus(); }
    });
    $('chat-canvas')?.addEventListener('click', handleAction);
    $('session-list')?.addEventListener('click', (e) => { const item=e.target.closest('.session-item'); if(item) loadSession(item.dataset.sessionId); });
    $('chat-scroll')?.addEventListener('scroll', () => { const node=$('chat-scroll'); state.userScrolledUp = node.scrollTop + node.clientHeight < node.scrollHeight - 80; });
    document.addEventListener('keydown', (e) => {
      const mod = e.ctrlKey || e.metaKey;
      if (mod && e.key.toLowerCase() === 'k') { e.preventDefault(); newChat(); }
      if (mod && e.key === '/') { e.preventDefault(); openSearch(); }
      if (e.key === 'Escape') { ModelSelector.close(); if ($('settings-modal')?.open) $('settings-modal').close(); if ($('model-settings-modal')?.open) $('model-settings-modal').close(); if ($('tools-modal')?.open) $('tools-modal').close(); }
    });
  }

  async function init() {
    ModelSelector.init();
    setupEvents();
    applyTheme(localStorage.getItem('yookai-theme') || document.documentElement.dataset.theme || 'dark');
    if (!isCompactLayout() && localStorage.getItem('yookai-sidebar-collapsed') === 'true') $('app-shell')?.classList.add('sidebar-collapsed');
    updateComposerState(false);
    let restoreSessionId = null;
    try {
      state.config = await client.getConfig();
      const serverInstance = state.config._server_instance_id || '';
      try {
        const priorServer = sessionStorage.getItem(SERVER_INSTANCE_KEY);
        const nav = performance.getEntriesByType?.('navigation')?.[0];
        const isReload = nav?.type === 'reload';
        if (serverInstance && priorServer === serverInstance && isReload) {
          restoreSessionId = sessionStorage.getItem(ACTIVE_SESSION_KEY);
        } else {
          sessionStorage.removeItem(ACTIVE_SESSION_KEY);
        }
        if (serverInstance) sessionStorage.setItem(SERVER_INSTANCE_KEY, serverInstance);
      } catch (_) {}
      state.currentProvider = state.config.provider?.default || 'openrouter';
      // The CLI's configured theme is the initial source of truth. A browser
      // theme explicitly chosen by the user remains respected via localStorage.
      const configuredTheme = state.config.ui?.theme;
      const previousConfiguredTheme = localStorage.getItem('yookai-config-theme');
      if (configuredTheme && previousConfiguredTheme !== configuredTheme) {
        localStorage.setItem('yookai-config-theme', configuredTheme);
        applyTheme(configuredTheme);
      } else if (!localStorage.getItem('yookai-theme') && configuredTheme) applyTheme(configuredTheme);
      // Refresh a stale browser model when the CLI default has changed.
      const configuredModel = state.config.chat?.default_model || '';
      const previousConfiguredModel = localStorage.getItem('yookai-config-default-model');
      if (configuredModel && previousConfiguredModel !== configuredModel) {
        localStorage.setItem('yookai-config-default-model', configuredModel);
        localStorage.setItem(MODEL_KEY, configuredModel);
        ModelSelector.currentModelId = configuredModel;
      }
      if (isCompactLayout() && state.config.ui?.sidebar_default === 'open') {
        $('app-shell')?.classList.add('sidebar-open');
        $('toggle-sidebar')?.setAttribute('aria-expanded', 'true');
      } else if (!isCompactLayout() && localStorage.getItem('yookai-sidebar-collapsed') !== 'true') {
        $('toggle-sidebar')?.setAttribute('aria-expanded', 'true');
      }
    } catch (error) {
      showToast(error.message || 'Gagal memuat konfigurasi/server.', 'error');
      renderErrorState(error.message || 'Periksa server dan konfigurasi.');
      announce('Gagal memuat YookAI. Periksa server dan konfigurasi.');
      return;
    }

    await ModelSelector.loadProviders();
    const modelTask = ModelSelector.loadModels().catch((error) => {
      ModelSelector.models = [];
      ModelSelector.ensureDefaultModel();
      showToast(error.message || 'Daftar model belum tersedia. Atur API key di Settings.', 'error');
    });
    const sessionTask = refreshSessions().catch((error) => {
      showToast(error.message || 'Gagal memuat daftar session.', 'error');
    });
    await Promise.allSettled([modelTask, sessionTask]);
    if (state.sessions.length && restoreSessionId && state.sessions.some((item) => item.id === restoreSessionId)) {
      await loadSession(restoreSessionId);
    } else {
      state.currentSessionId = null;
      state.messages = [];
      renderMessages();
      updateSidebarActive(null);
    }
  }

  window.YookAI = {state, newChat, loadSession, handleSend, handleStop, handleRetry, handleEdit, toggleTheme, ModelSelector, ThinkingBlock, ToolsPanel};
  init();
})();
