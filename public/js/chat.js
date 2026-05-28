const Chat = {
  user: null, history: [],
  lastTraceHash: null,
  activeLogId: null,
  lastAgentId: null,

  init() { this.setupInput(); },
  
  setUser(u) {
    this.user = u;
    this.history = [];
    if (u) {
      this.loadSessions(u.id);
    }
  },

  async loadSessions(userId) {
    try {
      const r = await fetch(`/api/chat/sessions?userId=${userId}`);
      const d = await r.json();
      const list = document.getElementById('sessions-list');
      if (!list) return;

      const sessions = d.sessions || [];
      if (sessions.length === 0) {
        await this.createNewSession(userId);
        return;
      }

      list.innerHTML = sessions.map(s => {
        const isActive = App.sessionId === s.id;
        const dateStr = App.formatDate(s.updatedAt) + ' ' + App.formatTime(s.updatedAt);
        return `
          <div class="session-item ${isActive ? 'active' : ''}" onclick="Chat.switchSession('${s.id}')">
            <div class="session-title-container">
              <div class="session-title" title="${s.title}">${s.title}</div>
              <div class="session-date">${dateStr}</div>
            </div>
            <button class="session-delete-btn" onclick="event.stopPropagation(); Chat.deleteSession('${s.id}')" title="Delete Session">✕</button>
          </div>
        `;
      }).join('');

      const activeSession = sessions.find(s => s.id === App.sessionId);
      if (!activeSession && sessions[0]) {
        this.switchSession(sessions[0].id);
      }
    } catch (e) {
      console.error('loadSessions error:', e);
    }
  },

  async createNewSession(userId = null) {
    const uid = userId || this.user?.id;
    if (!uid) return;
    try {
      const r = await fetch('/api/chat/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userId: uid, title: 'NEW CHAT' })
      });
      const d = await r.json();
      if (d.success && d.session) {
        App.sessionId = d.session.id;
        await this.loadSessions(uid);
        this.switchSession(d.session.id);
      }
    } catch (e) {
      console.error('createNewSession error:', e);
    }
  },

  async switchSession(sessionId) {
    App.sessionId = sessionId;
    
    document.querySelectorAll('.session-item').forEach(item => {
      item.classList.remove('active');
      if (item.getAttribute('onclick')?.includes(sessionId)) {
        item.classList.add('active');
      }
    });

    try {
      const r = await fetch(`/api/chat/sessions/${sessionId}`);
      const d = await r.json();
      if (d.success && d.session) {
        const session = d.session;
        
        const msgs = document.getElementById('chat-messages');
        if (msgs) {
          msgs.innerHTML = '';
          
          if (session.messages.length === 0) {
            msgs.innerHTML = `
              <div class="chat-welcome">
                <div class="welcome-icon">🤖</div>
                <h2>Your AI Banking Concierge</h2>
                <p>Powered by multi-agent intelligence. I route your requests to specialized agents for transactions, fraud, loans, investments, and compliance.</p>
                <div class="quick-actions">
                  <button class="quick-btn" data-msg="What's my current balance?">💰 Balance</button>
                  <button class="quick-btn" data-msg="Show my recent transactions and flag anything suspicious">📜 Transactions</button>
                  <button class="quick-btn" data-msg="I need to transfer ₹500 to another account">💸 Transfer</button>
                  <button class="quick-btn" data-msg="Analyze my spending patterns this month">📊 Spending</button>
                  <button class="quick-btn" data-msg="I want to apply for a personal loan of ₹10,000">🏦 Loan</button>
                  <button class="quick-btn" data-msg="Is there any suspicious activity on my account?">🛡️ Fraud Check</button>
                  <button class="quick-btn" data-msg="What investment recommendations do you have for me?">📈 Investments</button>
                  <button class="quick-btn" data-msg="Check my KYC and compliance status">📋 Compliance</button>
                </div>
              </div>
            `;
            msgs.querySelectorAll('.quick-btn').forEach(b => b.addEventListener('click', () => {
              const input = document.getElementById('chat-input');
              if(input) input.value = b.dataset.msg||b.textContent.replace(/^[^\s]+\s/,'');
              this.send();
            }));
          } else {
            session.messages.forEach(m => {
              this.appendMsg(m.content, m.role, m);
            });
          }
        }

        const currentDomain = document.getElementById('current-agent-badge');
        if (currentDomain) {
          if (session.lastAgent) {
            const agentMap = {
              'TRANSACTION': { name: 'Transaction Agent', icon: '💸' },
              'FRAUD': { name: 'Fraud Agent', icon: '🛡️' },
              'LOAN': { name: 'Loan Agent', icon: '🏦' },
              'CUSTOMER_SERVICE': { name: 'Customer Service', icon: '🎧' },
              'INVESTMENT': { name: 'Investment Agent', icon: '📈' },
              'COMPLIANCE': { name: 'Compliance Agent', icon: '📋' }
            };
            const info = agentMap[session.lastAgent] || { name: session.lastAgent, icon: '🤖' };
            currentDomain.textContent = `${info.icon} ${info.name}`;
          } else {
            currentDomain.textContent = '🧠 Orchestrator';
          }
        }
      }
    } catch (e) {
      console.error('switchSession error:', e);
    }
  },

  async deleteSession(sessionId) {
    if (!confirm('Are you sure you want to delete this chat session?')) return;
    try {
      const r = await fetch(`/api/chat/sessions/${sessionId}`, { method: 'DELETE' });
      const d = await r.json();
      if (d.success) {
        App.showToast('Session deleted', 'success');
        if (App.sessionId === sessionId) {
          App.sessionId = null;
        }
        await this.loadSessions(this.user.id);
      }
    } catch (e) {
      console.error('deleteSession error:', e);
    }
  },

  isVoiceMode: false,

  toggleVoiceMode() {
    if (!window.AudioService) return;
    this.isVoiceMode = !this.isVoiceMode;
    const btn = document.getElementById('chat-stt-btn');
    if (this.isVoiceMode) {
      if (btn) btn.style.color = 'var(--danger)';
      App.showToast('Voice mode active', 'success');
      this.listenContinuously();
    } else {
      if (btn) btn.style.color = 'var(--text-primary)';
      App.showToast('Voice mode deactivated', 'info');
      window.AudioService.stopListening();
    }
  },

  listenContinuously() {
    if (!this.isVoiceMode || !window.AudioService) return;
    window.AudioService.listen(
      (finalText) => {
        const input = document.getElementById('chat-input');
        if (input) input.value = finalText;
        this.send();
      },
      (interimText) => {
        const input = document.getElementById('chat-input');
        if (input) input.value = interimText;
      },
      (err) => { 
        console.error("STT Error:", err);
        if (err === 'no-speech' && this.isVoiceMode) {
          setTimeout(() => this.listenContinuously(), 100);
        } else {
          this.isVoiceMode = false;
          const btn = document.getElementById('chat-stt-btn');
          if (btn) btn.style.color = 'var(--text-primary)';
          App.showToast('Voice stopped: ' + (err.message || err), 'warning');
        }
      },
      () => { /* onstart */ },
      () => { /* onend */ }
    );
  },

  setupInput() {
    const input = document.getElementById('chat-input');
    const btn = document.getElementById('chat-send-btn');
    if (btn) btn.addEventListener('click', () => this.send());
    if (input) input.addEventListener('keydown', e => { if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();this.send();} });
    document.querySelectorAll('.quick-btn').forEach(b => b.addEventListener('click', () => {
      if(input) input.value = b.dataset.msg||b.textContent.replace(/^[^\s]+\s/,'');
      this.send();
    }));
  },

  async send() {
    const input = document.getElementById('chat-input');
    const text = input?.value?.trim();
    if (!text || !this.user) {
      if (!this.user) App.showToast('Please select a customer first', 'warning');
      return;
    }
    const welcome = document.querySelector('.chat-welcome');
    if (welcome) welcome.style.display = 'none';
    input.value = '';
    this.appendMsg(text, 'user');
    
    // Show thinking bubble with pulse
    this.showThinking();
    App.setAgentState('orchestrator', 'processing');

    try {
      const r = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, userId: this.user.id, sessionId: App.sessionId })
      });
      const d = await r.json();
      
      const thinkingEl = document.getElementById('thinking-el');
      if (thinkingEl) {
        // Freeze the thinking UI: remove dots and ID to prevent conflicts with next message
        const dots = thinkingEl.querySelector('.thinking-dots');
        if (dots) dots.remove();
        const meta = thinkingEl.querySelector('.msg-meta');
        if (meta) meta.innerHTML = `<span style="color:var(--text-muted);font-size:10px">✓ Orchestration Complete</span>`;
        thinkingEl.id = 'frozen-thinking-' + Date.now();
        thinkingEl.classList.remove('pulse-active');
        this.activeLogId = null; // Clear active log reference
      }
      
      const res = d.response;
      if (res) {
        this.appendMsg(res.content || 'No response', 'agent', res);
        const currentDomain = document.getElementById('current-agent-badge');
        if (currentDomain) currentDomain.textContent = `${res.icon || '🤖'} ${res.displayName || 'Agent'}`;
        App.setAgentState(res.domain?.toLowerCase(), 'idle');
        App.setAgentState('orchestrator', 'idle');
        
        // Refresh session sidebar titles
        this.loadSessions(this.user.id);
      }
    } catch (error) {
      const thinkingEl = document.getElementById('thinking-el');
      if (thinkingEl) thinkingEl.remove();
      this.appendMsg('Connection error. Please check the server.', 'agent');
      App.setAgentState('orchestrator', 'idle');
    }
  },

  appendMsg(content, role, meta={}) {
    const msgs = document.getElementById('chat-messages');
    if (!msgs) return;
    const div = document.createElement('div');
    div.className = `msg ${role}`;
    const agentBadge = role === 'agent' && meta.displayName ? `<span class="msg-agent-badge">${meta.icon||'🤖'} ${meta.displayName}</span>` : '';
    const confidence = meta.routingConfidence ? `<span style="font-size:10px;color:var(--text-muted)">confidence: ${(meta.routingConfidence*100).toFixed(0)}%</span>` : '';
    const reqApproval = meta.requiresApproval ? `<div style="margin-top:10px;padding:8px 12px;background:rgba(255,184,0,.1);border:1px solid rgba(255,184,0,.3);border-radius:8px;font-size:12px;color:var(--amber)">⚡ Human approval required · ID: ${meta.approvalId}</div>` : '';
    div.innerHTML = `
      <div class="msg-bubble">${this.formatContent(content)}${reqApproval}</div>
      ${role === 'agent' ? `<div class="msg-meta">${agentBadge}${confidence}<span>${App.formatTime(Date.now())}</span></div>` : `<div class="msg-meta"><span>${App.formatTime(Date.now())}</span></div>`}`;
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
    
    if (role === 'agent' && window.AudioService) {
      window.AudioService.speak(content, () => {
        if (this.isVoiceMode) {
          this.listenContinuously();
        }
      });
    }
  },

  formatContent(text) {
    if (!text) return '';
    
    // 1. Handle Horizontal Rules
    text = text.replace(/^---$/gm, '<hr style="border:0; border-top:1px solid var(--border); margin:15px 0;">');

    // 2. Handle Headers (### Header)
    text = text.replace(/^### (.*$)/gm, '<h3 style="font-family:\'Space Grotesk\'; font-size:16px; font-weight:700; color:var(--electric); margin:15px 0 10px 0;">$1</h3>');

    // 3. Handle Tables
    const lines = text.split('\n');
    let inTable = false;
    let newText = '';
    
    for (let i = 0; i < lines.length; i++) {
      let line = lines[i].trim();
      if (line.startsWith('|') && line.endsWith('|')) {
        const cells = line.split('|').map(c => c.trim()).filter((c, idx, arr) => idx > 0 && idx < arr.length - 1);
        if (line.includes('---')) continue; 
        
        if (!inTable) {
          inTable = true;
          newText += '<div class="transactions-table-wrap" style="margin:15px 0;"><table class="transactions-table" style="width:100%; border:1px solid var(--border); border-radius:8px; overflow:hidden;"><thead><tr>';
          cells.forEach(c => newText += `<th style="background:var(--bg-card2); color:var(--text-secondary); font-size:11px; padding:10px; text-align:left; border-bottom:1px solid var(--border);">${c}</th>`);
          newText += '</tr></thead><tbody>';
        } else {
          newText += '<tr>';
          cells.forEach(c => newText += `<td style="padding:10px; font-size:12px; border-top:1px solid var(--border); color:var(--text-secondary);">${c}</td>`);
          newText += '</tr>';
        }
      } else {
        if (inTable) {
          inTable = false;
          newText += '</tbody></table></div>';
        }
        newText += line + '\n';
      }
    }
    if (inTable) newText += '</tbody></table></div>';
    text = newText;

    // 4. Basic Markdown
    text = text
      .replace(/^### (.*$)/gim, '<h3 style="margin:16px 0 8px 0;font-size:16px;color:var(--text)">$1</h3>')
      .replace(/^## (.*$)/gim, '<h2 style="margin:20px 0 10px 0;font-size:18px;color:var(--text);border-bottom:1px solid var(--border);padding-bottom:5px">$1</h2>')
      .replace(/^# (.*$)/gim, '<h1 style="margin:24px 0 12px 0;font-size:22px;color:var(--electric)">$1</h1>')
      .replace(/^\s*-\s+(.*$)/gim, '<li style="margin-left:20px;margin-bottom:4px">$1</li>')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/`([^`]+)`/g, `<code style="background:rgba(0,212,255,.1); color:var(--electric); padding:1px 5px; border-radius:4px; font-family:var(--mono); font-size:12px">$1</code>`);
      
    // Fix list tags wrapping
    text = text.replace(/(<li.*?>.*?<\/li>)/s, '<ul style="margin:8px 0">$1</ul>');
    
    return text
      .replace(/\n\n/g, '</p><p style="margin-top:10px">')
      .replace(/\n/g, '<br>');
  },

  showThinking() {
    const msgs = document.getElementById('chat-messages');
    if (!msgs) return;
    const d = document.createElement('div');
    d.className = 'msg agent pulse-active';
    d.id = 'thinking-el';
    
    const logId = 'log-' + Date.now();
    this.activeLogId = logId;
    
    d.innerHTML = `
      <div class="msg-bubble thinking-bubble" style="background:var(--bg-surface);border:1px solid var(--border);min-width:320px;padding:15px;position:relative;box-shadow:var(--shadow)">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
          <div style="font-size:10px;text-transform:uppercase;color:var(--violet);letter-spacing:1px;font-weight:700">🧠 Multi-Agent Orchestration Log</div>
          <button onclick="Chat.toggleExpand('${logId}')" style="background:rgba(124,58,237,0.08);border:none;color:var(--violet);font-size:9px;padding:2px 6px;border-radius:4px;cursor:pointer">EXPAND</button>
        </div>
        <div id="${logId}" class="thinking-log-body" style="display:flex;flex-direction:column;gap:10px;max-height:160px;overflow-y:auto;padding-right:8px;scrollbar-width:none;transition:max-height 0.4s ease">
          <div class="agent-pulse" style="margin:0;opacity:1;animation:slideUp 0.3s forwards">
            <div class="pulse-icon" style="width:24px;height:24px;font-size:12px;background:rgba(124,58,237,0.08);color:var(--violet)">🧠</div>
            <div class="pulse-content">
              <div class="pulse-agent" style="font-size:10px;color:var(--text-muted)">Orchestrator</div>
              <div class="pulse-text" style="font-size:11px">Analyzing user intent...</div>
            </div>
          </div>
        </div>
        <div class="thinking-dots" style="margin-top:12px;justify-content:center"><span></span><span></span><span></span></div>
      </div>
      <div class="msg-meta"><span style="color:var(--violet);font-size:10px">Neural Thread Active...</span></div>`;
    msgs.appendChild(d);
    msgs.scrollTop = msgs.scrollHeight;
  },

  toggleExpand(id) {
    const el = document.getElementById(id);
    if (!el) return;
    const isExpanded = el.style.maxHeight === 'none';
    el.style.maxHeight = isExpanded ? '160px' : 'none';
    const btn = el.previousElementSibling.querySelector('button');
    if (btn) btn.textContent = isExpanded ? 'EXPAND' : 'COLLAPSE';
  },

  onTrace(data) {
    // 0. De-duplication check
    const traceHash = `${data.agent}:${data.reasoning || data.content || ''}:${data.toolCalls?.[0]?.name || ''}:${typeof data.toolResult?.result === 'string' ? data.toolResult.result.substring(0,20) : ''}`;
    if (this.lastTraceHash === traceHash) return;
    this.lastTraceHash = traceHash;

    // 1. Log to the ACTIVE in-chat thinking bubble
    const logContainer = this.activeLogId ? document.getElementById(this.activeLogId) : null;
    if (logContainer) {
      const agentId = data.agent?.toLowerCase() || 'agent';
      
      const agentMap = {
        'orchestrator': { name: 'Orchestrator', icon: '🧠' },
        'transaction': { name: 'Transaction Agent', icon: '💸' },
        'fraud': { name: 'Fraud Agent', icon: '🛡️' },
        'loan': { name: 'Loan Agent', icon: '🏦' },
        'customer_service': { name: 'Customer Service', icon: '🎧' },
        'investment': { name: 'Investment Agent', icon: '📈' },
        'compliance': { name: 'Compliance Agent', icon: '📋' }
      };
      const info = agentMap[agentId] || { name: data.agent || 'Agent', icon: '🤖' };
      
      let text = '';
      if (data.toolCalls) {
        let argsPreview = '';
        try {
          let args = typeof data.toolCalls[0].arguments === 'string' ? JSON.parse(data.toolCalls[0].arguments) : data.toolCalls[0].arguments;
          if (args && typeof args === 'object') {
             argsPreview = Object.values(args).join(', ').substring(0, 30);
          }
        } catch(e) {}
        const toolName = data.toolCalls[0].name.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        text = `<div style="color:var(--amber);margin-top:4px;font-weight:600;font-size:10px">⚡ Task: ${toolName}${argsPreview ? ` <span style="opacity:0.7;font-weight:400">(${argsPreview})</span>` : ''}</div>`;
      } else if (data.toolResult) {
        let formattedResult = '';
        try {
          let parsed = typeof data.toolResult.result === 'string' ? JSON.parse(data.toolResult.result) : data.toolResult.result;
          if (Array.isArray(parsed)) {
            if (parsed.length === 0) formattedResult = 'No records found.';
            else if (parsed.length === 1) formattedResult = '1 record retrieved.';
            else formattedResult = `${parsed.length} records retrieved.`;
          } else if (typeof parsed === 'object' && parsed !== null) {
            let keys = Object.keys(parsed).filter(k => parsed[k] !== null && parsed[k] !== '');
            formattedResult = keys.slice(0, 3).map(k => `<span style="color:var(--electric)">${k}:</span> ${parsed[k]}`).join(', ') + (keys.length > 3 ? '...' : '');
          } else {
            formattedResult = String(parsed).substring(0, 40) + '...';
          }
        } catch (e) {
          formattedResult = (data.toolResult.result || '').substring(0, 40) + '...';
        }
        text = `<div style="color:var(--text);margin-top:3px;font-size:10px;background:var(--bg);padding:4px 6px;border-radius:4px;border-left:2px solid var(--neon);">🔭 <span style="font-family:var(--mono)">${formattedResult}</span></div>`;
      } else if (data.reasoning) {
        text = `<div style="margin-top:4px">🤔 ${data.reasoning.substring(0, 100)}${data.reasoning.length > 100 ? '...' : ''}</div>`;
      } else if (data.content) {
        text = `<div style="margin-top:4px;opacity:0.9;font-weight:500">${data.content.replace(/\*\*/g, '').substring(0, 120)}${data.content.length > 120 ? '...' : ''}</div>`;
      }

      // Check if we can append to last entry
      const lastEntry = logContainer.lastElementChild;
      if (this.lastAgentId === agentId && lastEntry && lastEntry.classList.contains('agent-pulse')) {
        const contentArea = lastEntry.querySelector('.pulse-content');
        if (contentArea) {
          const div = document.createElement('div');
          div.innerHTML = text;
          contentArea.appendChild(div);
        }
      } else {
        const entry = document.createElement('div');
        entry.className = 'agent-pulse';
        entry.style.margin = '10px 0 0 0';
        entry.style.animation = 'slideUp 0.3s forwards';
        entry.innerHTML = `
          <div class="pulse-icon" style="width:24px;height:24px;font-size:12px;background:rgba(2,132,199,0.08);color:var(--electric)">${info.icon}</div>
          <div class="pulse-content" style="width:100%">
            <div class="pulse-agent" style="font-size:10px;color:var(--text-muted);font-weight:700">${info.name.toUpperCase()}</div>
            <div class="pulse-text" style="font-size:11px">${text}</div>
          </div>`;
        logContainer.appendChild(entry);
      }
      
      this.lastAgentId = agentId;
      logContainer.scrollTop = logContainer.scrollHeight;
    }

    // 2. Keep the sidebar trace logic intact
    const log = document.getElementById('trace-log');
    if (log) {
      const entry = document.createElement('div');
      const hasTools = data.toolCalls?.length > 0;
      const hasResult = !!data.toolResult;
      const type = data.reasoning ? 'thought' : hasTools ? 'action' : hasResult ? 'observation' : 'response';
      entry.className = `trace-entry ${type}`;
      
      const labels = { thought: '🧠 THINKING', action: '⚡ ACTION', observation: '🔭 OBSERVATION', response: '💬 RESPONSE', system: '⚠️ SYSTEM' };
      let body = `<div class="trace-label">${labels[type] || type.toUpperCase()}<span class="trace-time">${App.formatTime(data.timestamp)}</span></div>`;
      if (data.agent) body += `<div style="font-size:10px;color:var(--text-muted);margin-bottom:4px">AGENT: ${data.agent.toUpperCase()}</div>`;
      if (data.reasoning) body += `<div style="opacity:.8;margin-top:3px">${data.reasoning.substring(0, 180)}${data.reasoning.length > 180 ? '...' : ''}</div>`;
      if (hasTools) data.toolCalls.forEach(t => { body += `<div style="margin-top:4px">▶ ${t.name}(...)</div>`; });
      if (hasResult) body += `<div style="margin-top:4px">◀ ${data.toolResult.name}: ${typeof data.toolResult.result === 'string' ? data.toolResult.result.substring(0, 40) : '...'}</div>`;
      if (data.content && !hasTools && !hasResult) body += `<div style="margin-top:3px;opacity:.9">${data.content.substring(0, 200)}${data.content.length > 200 ? '...' : ''}</div>`;
      
      entry.innerHTML = body;
      log.appendChild(entry);
      log.scrollTop = log.scrollHeight;
      while (log.children.length > 100) log.removeChild(log.firstChild);
    }
  },
};

