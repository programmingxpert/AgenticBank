/* ============================================================
   Payment Hub — Frontend Controller
   AgenticBank AI | Autonomous Payment Processing
   ============================================================ */

const PaymentHub = {
  ws: null,
  payments: [],
  analytics: {},
  pipelineSessionId: null,
  chatSessionId: `pay-chat-${Date.now()}`,
  pollingInterval: null,

  /* ─── Init ─────────────────────────────────────────────── */
  init() {
    this.initWebSocket();
    this.loadPayments();
    this.loadAnalytics();
    this.setupNavigation();
    this.setupForm();
    this.setupChat();
    this.renderPolicies();
    this.pollingInterval = setInterval(() => this.loadPayments(), 10000);
    App.showToast('Payment Hub connected', 'success');
  },

  /* ─── WebSocket ─────────────────────────────────────────── */
  initWebSocket() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    // Connect to the same broadcast WS used by banker/customer pages
    this.ws = new WebSocket(`${proto}//${location.host}/`);
    this.wsRetryDelay = this.wsRetryDelay || 2000;
    this.ws.onopen = () => {
      this.wsRetryDelay = 2000; // reset backoff on success
      const ind = document.getElementById('ws-indicator');
      if (ind) ind.style.background = 'var(--neon)';
    };
    this.ws.onclose = () => {
      const ind = document.getElementById('ws-indicator');
      if (ind) ind.style.background = 'var(--danger)';
      // Exponential backoff: 2s → 4s → 8s → max 30s
      this.wsRetryDelay = Math.min(this.wsRetryDelay * 1.5, 30000);
      setTimeout(() => this.initWebSocket(), this.wsRetryDelay);
    };
    this.ws.onmessage = (evt) => {
      try {
        const { event, data } = JSON.parse(evt.data);
        if (event === 'agent:trace') this.appendPipelineTrace(data);
        if (event === 'payment:created' || event === 'payment:updated') this.loadPayments();
        if (event === 'approval:pending') this.showApprovalToast(data);
      } catch {}
    };
    this.ws.onerror = () => {}; // suppress console noise
  },

  /* ─── Navigation ────────────────────────────────────────── */
  setupNavigation() {
    document.querySelectorAll('.pay-nav-item').forEach(item => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        const view = item.dataset.view;
        document.querySelectorAll('.pay-nav-item').forEach(i => i.classList.remove('active'));
        item.classList.add('active');
        document.querySelectorAll('.pay-view').forEach(v => v.classList.remove('active'));
        const el = document.getElementById(`view-${view}`);
        if (el) el.classList.add('active');
        if (view === 'analytics') this.loadAnalytics();
        if (view === 'reconciliation') this.loadReconciliation();
      });
    });
  },

  /* ─── Payment Form ──────────────────────────────────────── */
  setupForm() {
    const form = document.getElementById('payment-form');
    if (form) form.addEventListener('submit', (e) => { e.preventDefault(); this.submitPayment(); });
    
    // Auto-select rail based on amount
    const amountInput = document.getElementById('pay-amount');
    const railSelect = document.getElementById('pay-rail');
    if (amountInput && railSelect) {
      amountInput.addEventListener('input', () => {
        const amt = parseFloat(amountInput.value) || 0;
        if (amt < 100000) railSelect.value = 'UPI';
        else if (amt < 500000) railSelect.value = 'IMPS';
        else if (amt >= 200000 && amt < 5000000) railSelect.value = 'RTGS';
        else if (amt >= 5000000) railSelect.value = 'SWIFT';
        else railSelect.value = 'NEFT';
        this.updateFeeEstimate(amt, railSelect.value);
      });
      railSelect.addEventListener('change', () => {
        this.updateFeeEstimate(parseFloat(amountInput.value) || 0, railSelect.value);
      });
    }
  },

  updateFeeEstimate(amount, rail) {
    const feeMap = { UPI: 0, Internal: 0, IMPS: 17.7, NEFT: Math.min(25, Math.max(2, amount * 0.00005)), RTGS: 37.5, SWIFT: 1500 };
    const timeMap = { UPI: 'Instant (<10s)', IMPS: 'Instant (<30s)', NEFT: '30 min batch', RTGS: 'Real-time (30 min cutoff)', SWIFT: '1–3 business days', Internal: 'Instant' };
    const fee = feeMap[rail] || 0;
    const el = document.getElementById('fee-estimate');
    if (el) el.innerHTML = `<span>Est. Fee: ₹${fee.toFixed(2)} + GST</span><span class="sep">·</span><span>Settlement: ${timeMap[rail] || 'N/A'}</span>`;
    
    const hitlWarning = document.getElementById('hitl-warning');
    if (hitlWarning) {
      if (amount > 500000 || rail === 'SWIFT') {
        hitlWarning.style.display = 'flex';
        hitlWarning.querySelector('span').textContent = rail === 'SWIFT' ? '⚠️ International SWIFT payments require banker approval' : '⚠️ Payments above ₹5,00,000 require human approval';
      } else {
        hitlWarning.style.display = 'none';
      }
    }
  },

  async submitPayment() {
    const userId = document.getElementById('pay-user-id')?.value?.trim();
    const fromAccId = document.getElementById('pay-from-account')?.value?.trim();
    const benefName = document.getElementById('pay-benef-name')?.value?.trim();
    const benefAcc = document.getElementById('pay-benef-account')?.value?.trim();
    const amount = parseFloat(document.getElementById('pay-amount')?.value);
    const rail = document.getElementById('pay-rail')?.value;
    const urgency = document.getElementById('pay-urgency')?.value || 'standard';
    const ref = document.getElementById('pay-reference')?.value?.trim();
    const desc = document.getElementById('pay-desc')?.value?.trim();
    const currency = document.getElementById('pay-currency')?.value || 'INR';

    if (!userId || !fromAccId || !benefName || !benefAcc || !amount) {
      App.showToast('Please fill in all required fields', 'warning'); return;
    }

    // Switch to pipeline view and clear it
    document.querySelectorAll('.pay-nav-item').forEach(i => i.classList.remove('active'));
    document.querySelector('[data-view="pipeline"]')?.classList.add('active');
    document.querySelectorAll('.pay-view').forEach(v => v.classList.remove('active'));
    document.getElementById('view-pipeline')?.classList.add('active');

    this.clearPipeline();
    this.appendPipelineTrace({ agent: 'orchestrator', content: '🚀 Payment instruction received — starting autonomous pipeline...', timestamp: new Date().toISOString() });

    const btn = document.getElementById('pay-submit-btn');
    if (btn) { btn.disabled = true; btn.textContent = 'Processing...'; }

    try {
      const token = localStorage.getItem('agentToken');
      const res = await fetch('/api/payments/initiate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ userId, fromAccountId: fromAccId, beneficiaryName: benefName, beneficiaryAccount: benefAcc, amount, currency, paymentType: rail === 'SWIFT' ? 'international' : 'domestic', urgency, rail, reference: ref, description: desc })
      });
      const d = await res.json();
      if (d.success) {
        App.showToast('Payment pipeline executed!', 'success');
        this.loadPayments();
        this.loadAnalytics();
      } else {
        App.showToast('Pipeline error: ' + (d.detail || 'Unknown'), 'error');
      }
    } catch (e) {
      App.showToast('Network error: ' + e.message, 'error');
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = '⚡ Execute Payment'; }
    }
  },

  /* ─── Pipeline Trace ────────────────────────────────────── */
  clearPipeline() {
    const panel = document.getElementById('pipeline-trace');
    if (panel) panel.innerHTML = `<div class="pipeline-empty">Pipeline ready — submit a payment to watch agents work in real-time</div>`;
    this.updateStages('idle');
  },

  appendPipelineTrace(data) {
    const panel = document.getElementById('pipeline-trace');
    if (!panel) return;
    const empty = panel.querySelector('.pipeline-empty');
    if (empty) empty.remove();

    const agent = data.agent || 'system';
    const content = data.content || '';
    const time = new Date(data.timestamp || Date.now()).toLocaleTimeString('en-IN');
    
    const div = document.createElement('div');
    div.className = 'trace-entry';
    
    const icons = { orchestrator: '🧠', payment_orchestrator: '💳', payment_validation: '✅', payment_routing: '🔀', payment_reconciliation: '🔁', fraud: '🛡️', compliance: '📋' };
    const icon = icons[agent] || '⚙️';
    
    // Detect stage transitions
    const lower = content.toLowerCase();
    if (lower.includes('validat')) this.updateStages('validation');
    if (lower.includes('rout') || lower.includes('rail')) this.updateStages('routing');
    if (lower.includes('execut') || lower.includes('processing')) this.updateStages('execution');
    if (lower.includes('complet') || lower.includes('success')) this.updateStages('complete');
    if (lower.includes('hold') || lower.includes('approval')) this.updateStages('hold');
    if (lower.includes('reject') || lower.includes('fail') || lower.includes('block')) this.updateStages('failed');

    div.innerHTML = `
      <div class="trace-icon">${icon}</div>
      <div class="trace-body">
        <div class="trace-agent">${agent.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase())}</div>
        <div class="trace-content">${this.formatTrace(content)}</div>
        ${data.toolResult ? `<div class="trace-tool-result"><span>🔧 Tool: ${data.toolResult.name}</span></div>` : ''}
      </div>
      <div class="trace-time">${time}</div>
    `;
    panel.appendChild(div);
    panel.scrollTop = panel.scrollHeight;
  },

  formatTrace(text) {
    return text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/`(.*?)`/g, '<code>$1</code>');
  },

  updateStages(stage) {
    const stages = ['validation', 'routing', 'execution', 'settlement'];
    const stageMap = { idle: -1, validation: 0, routing: 1, execution: 2, settlement: 3, complete: 3, hold: 1, failed: -1 };
    const idx = stageMap[stage] ?? -1;
    stages.forEach((s, i) => {
      const el = document.getElementById(`stage-${s}`);
      if (!el) return;
      el.className = 'pipeline-stage';
      if (stage === 'hold' && i === 1) { el.classList.add('stage-hold'); return; }
      if (stage === 'failed' && i === stageMap.failed + 1) { el.classList.add('stage-failed'); return; }
      if (stage === 'complete') { el.classList.add('stage-complete'); return; }
      if (i < idx) el.classList.add('stage-complete');
      else if (i === idx) el.classList.add('stage-active');
    });
  },

  /* ─── Queue ─────────────────────────────────────────────── */
  async loadPayments() {
    try {
      const token = localStorage.getItem('agentToken');
      const res = await fetch('/api/payments/queue', { headers: { 'Authorization': `Bearer ${token}` } });
      const d = await res.json();
      this.payments = d.payments || [];
      this.renderQueue();
      this.updateBadge();
    } catch {}
  },

  renderQueue() {
    const table = document.getElementById('payment-queue-body');
    if (!table) return;
    let list = this.payments;
    if (typeof App !== 'undefined' && App.currentUser) {
      list = list.filter(p => p.userId === App.currentUser.id);
    }
    if (!list.length) {
      table.innerHTML = `<tr><td colspan="8" class="empty-row"><div class="queue-empty">No payments yet — submit one using the form</div></td></tr>`;
      return;
    }
    table.innerHTML = list.map(p => {
      const statusClass = { completed: 'badge-success', processing: 'badge-info badge-pulse', held: 'badge-warning', failed: 'badge-danger', cancelled: 'badge-muted', reconciled: 'badge-violet' }[p.status] || 'badge-muted';
      const railIcon = { UPI: '📱', IMPS: '⚡', NEFT: '🏦', RTGS: '💰', SWIFT: '🌐', Internal: '🔄' }[p.rail] || '💳';
      const amt = p.amount ? `₹${parseFloat(p.amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}` : '—';
      const date = p.createdAt ? new Date(p.createdAt).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' }) : '—';
      return `
        <tr class="queue-row" onclick="PaymentHub.showPaymentDetail('${p.id}')">
          <td><code class="pay-id">${p.id}</code></td>
          <td>${p.beneficiaryName || '—'}</td>
          <td><strong>${amt}</strong></td>
          <td>${railIcon} ${p.rail || 'Auto'}</td>
          <td><span class="status-badge ${statusClass}">${p.status}</span></td>
          <td>${p.userId || '—'}</td>
          <td>${date}</td>
          <td>
            ${p.status === 'processing' || p.status === 'pending' ? `<button class="btn-sm btn-danger" onclick="event.stopPropagation();PaymentHub.cancelPayment('${p.id}')">Cancel</button>` : ''}
          </td>
        </tr>`;
    }).join('');
  },

  updateBadge() {
    let list = this.payments;
    if (typeof App !== 'undefined' && App.currentUser) {
      list = list.filter(p => p.userId === App.currentUser.id);
    }
    const processing = list.filter(p => p.status === 'processing').length;
    const badge = document.getElementById('queue-badge');
    if (badge) { badge.textContent = processing; badge.style.display = processing ? 'inline' : 'none'; }
  },

  async cancelPayment(id) {
    if (!confirm('Cancel this payment?')) return;
    const token = localStorage.getItem('agentToken');
    await fetch(`/api/payments/${id}/cancel`, { method: 'POST', headers: { 'Authorization': `Bearer ${token}` } });
    App.showToast('Payment cancelled', 'info');
    this.loadPayments();
  },

  showPaymentDetail(id) {
    const pay = this.payments.find(p => p.id === id);
    if (!pay) return;
    const modal = document.getElementById('payment-detail-modal');
    const body = document.getElementById('payment-detail-body');
    if (body) {
      body.innerHTML = `
        <div class="detail-grid">
          <div class="detail-row"><span>ID</span><code>${pay.id}</code></div>
          <div class="detail-row"><span>Status</span><span class="status-badge badge-${pay.status === 'completed' ? 'success' : pay.status === 'held' ? 'warning' : pay.status === 'failed' ? 'danger' : 'info'}">${pay.status}</span></div>
          <div class="detail-row"><span>Beneficiary</span><strong>${pay.beneficiaryName || '—'}</strong></div>
          <div class="detail-row"><span>Account</span><code>${pay.beneficiaryAccount || '—'}</code></div>
          <div class="detail-row"><span>Amount</span><strong>₹${parseFloat(pay.amount || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong></div>
          <div class="detail-row"><span>Rail</span>${pay.rail || 'Auto-selected'}</div>
          <div class="detail-row"><span>Reference</span>${pay.reference || '—'}</div>
          <div class="detail-row"><span>Description</span>${pay.description || '—'}</div>
          <div class="detail-row"><span>Validation</span><span class="val-status">${pay.validationStatus || '—'}</span></div>
          <div class="detail-row"><span>Est. Fee</span>₹${pay.estimatedFee || '0.00'}</div>
          <div class="detail-row"><span>Est. Settlement</span>${pay.estimatedSettlement || '—'}</div>
          <div class="detail-row"><span>Created</span>${pay.createdAt ? new Date(pay.createdAt).toLocaleString('en-IN') : '—'}</div>
          <div class="detail-row"><span>Updated</span>${pay.updatedAt ? new Date(pay.updatedAt).toLocaleString('en-IN') : '—'}</div>
          ${pay.approvalId ? `<div class="detail-row"><span>Approval</span><code>${pay.approvalId}</code></div>` : ''}
          ${pay.rejectionReason ? `<div class="detail-row"><span>Rejection Reason</span><span class="danger-text">${pay.rejectionReason}</span></div>` : ''}
        </div>`;
    }
    if (modal) modal.style.display = 'flex';
  },

  closeModal() {
    const modal = document.getElementById('payment-detail-modal');
    if (modal) modal.style.display = 'none';
  },

  /* ─── Analytics ─────────────────────────────────────────── */
  async loadAnalytics() {
    try {
      const token = localStorage.getItem('agentToken');
      const res = await fetch('/api/payments/analytics', { headers: { 'Authorization': `Bearer ${token}` } });
      this.analytics = await res.json();
      this.renderAnalytics();
    } catch {}
  },

  renderAnalytics() {
    const a = this.analytics;
    const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
    const total = a.total || 0;
    const vol = a.totalVolume || 0;
    set('stat-total', total.toLocaleString('en-IN'));
    set('stat-volume', `₹${vol.toLocaleString('en-IN', { maximumFractionDigits: 0 })}`);
    set('stat-success', `${a.successRate || 0}%`);
    const byStatus = a.byStatus || {};
    set('stat-processing', (byStatus.processing || 0).toString());
    set('stat-held', (byStatus.held || 0).toString());
    set('stat-failed', (byStatus.failed || 0).toString());

    // Render rail breakdown
    const railDiv = document.getElementById('rail-breakdown');
    if (railDiv && a.byRail) {
      const total_rails = Object.values(a.byRail).reduce((s, v) => s + v, 0) || 1;
      railDiv.innerHTML = Object.entries(a.byRail).map(([rail, cnt]) => {
        const pct = Math.round(cnt / total_rails * 100);
        const colors = { UPI: '#0284c7', IMPS: '#059669', NEFT: '#d97706', RTGS: '#7c3aed', SWIFT: '#dc2626', Internal: '#475569' };
        return `<div class="rail-bar-row">
          <span class="rail-label">${rail}</span>
          <div class="rail-bar-bg"><div class="rail-bar-fill" style="width:${pct}%;background:${colors[rail]||'#475569'}"></div></div>
          <span class="rail-count">${cnt}</span>
        </div>`;
      }).join('');
    }
  },

  /* ─── Reconciliation ─────────────────────────────────────── */
  loadReconciliation() {
    let pays = this.payments;
    if (typeof App !== 'undefined' && App.currentUser) {
      pays = pays.filter(p => p.userId === App.currentUser.id);
    }
    const matched = pays.filter(p => p.status === 'completed' || p.status === 'reconciled').length;
    const unmatched = pays.filter(p => p.status === 'failed').length;
    const pending = pays.filter(p => p.status === 'processing').length;
    const held = pays.filter(p => p.status === 'held').length;

    const set = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
    set('recon-matched', matched);
    set('recon-unmatched', unmatched);
    set('recon-pending', pending);
    set('recon-held', held);

    const tbody = document.getElementById('recon-table-body');
    if (tbody) {
      tbody.innerHTML = pays.slice(0, 20).map(p => {
        const reconStatus = p.status === 'completed' ? '✅ Matched' : p.status === 'failed' ? '❌ Exception' : p.status === 'held' ? '⏸ On Hold' : '⏳ Pending';
        const amt = `₹${parseFloat(p.amount || 0).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
        return `<tr>
          <td><code>${p.id}</code></td>
          <td>${p.beneficiaryName || '—'}</td>
          <td>${amt}</td>
          <td>${p.rail || '—'}</td>
          <td>${reconStatus}</td>
          <td>${p.createdAt ? new Date(p.createdAt).toLocaleDateString('en-IN') : '—'}</td>
        </tr>`;
      }).join('');
    }
  },

  /* ─── Policies ───────────────────────────────────────────── */
  renderPolicies() {
    const policies = [
      { name: 'Per Transaction Limit', value: '₹50,00,000', status: 'active', icon: '💰' },
      { name: 'Daily Volume Limit', value: '₹2,00,00,000', status: 'active', icon: '📅' },
      { name: 'Daily Payment Count', value: '10 payments/day', status: 'active', icon: '🔢' },
      { name: 'Duplicate Window', value: '60 seconds', status: 'active', icon: '🔁' },
      { name: 'SWIFT Approval Gate', value: 'Always Required', status: 'enforced', icon: '🌐' },
      { name: 'Large Payment Gate', value: '>₹5,00,000 → HITL', status: 'enforced', icon: '✋' },
      { name: 'First-Time Payee Hold', value: 'Enabled', status: 'active', icon: '👤' },
      { name: 'Sanctions Screening', value: 'Real-time, pre-payment', status: 'enforced', icon: '🛡️' },
      { name: 'UPI Rail Limit', value: '₹1,00,000 max', status: 'active', icon: '📱' },
      { name: 'RTGS Min Amount', value: '₹2,00,000 min', status: 'active', icon: '🏦' },
    ];
    const grid = document.getElementById('policy-grid');
    if (grid) {
      grid.innerHTML = policies.map(p => `
        <div class="policy-card">
          <div class="policy-icon">${p.icon}</div>
          <div class="policy-info">
            <div class="policy-name">${p.name}</div>
            <div class="policy-value">${p.value}</div>
          </div>
          <div class="policy-badge policy-${p.status}">${p.status}</div>
        </div>`).join('');
    }
  },

  /* ─── AI Chat ────────────────────────────────────────────── */
  setupChat() {
    const input = document.getElementById('pay-chat-input');
    const btn = document.getElementById('pay-chat-send');
    if (btn) btn.addEventListener('click', () => this.sendChat());
    if (input) input.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this.sendChat(); } });
    
    document.querySelectorAll('.pay-quick-btn').forEach(b => {
      b.addEventListener('click', () => {
        if (input) input.value = b.dataset.msg;
        this.sendChat();
      });
    });
  },

  async sendChat() {
    const input = document.getElementById('pay-chat-input');
    const text = input?.value?.trim();
    if (!text) return;
    input.value = '';

    this.appendChatMsg('user', text);

    const thinking = this.appendChatMsg('agent', null, true);
    
    try {
      const token = localStorage.getItem('agentToken');
      const res = await fetch('/api/chat/payment', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ message: text, sessionId: this.chatSessionId })
      });
      const d = await res.json();
      if (thinking) thinking.remove();
      if (d.success) {
        this.appendChatMsg('agent', d.response);
      } else {
        this.appendChatMsg('agent', 'Sorry, I encountered an error processing that request.');
      }
    } catch {
      if (thinking) thinking.remove();
      this.appendChatMsg('agent', 'Connection error. Please try again.');
    }
  },

  appendChatMsg(role, content, isThinking = false) {
    const msgs = document.getElementById('pay-chat-messages');
    if (!msgs) return null;
    const welcome = msgs.querySelector('.chat-welcome');
    if (welcome) welcome.style.display = 'none';
    const div = document.createElement('div');
    div.className = `msg ${role === 'user' ? 'user' : 'agent'}`;
    if (isThinking) {
      div.innerHTML = `<div class="msg-bubble thinking"><div class="dot-pulse"><span></span><span></span><span></span></div></div>`;
    } else {
      const text = this.formatChatContent(content || '');
      div.innerHTML = `
        <div class="msg-bubble">${text}</div>
        <div class="msg-meta">
          <span>${role === 'user' ? '👤 You' : '💳 Payment AI'}</span>
          <span>·</span>
          <span>${new Date().toLocaleTimeString('en-IN', { timeStyle: 'short' })}</span>
        </div>`;
    }
    msgs.appendChild(div);
    msgs.scrollTop = msgs.scrollHeight;
    return div;
  },

  formatChatContent(text) {
    return text
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/`(.*?)`/g, '<code>$1</code>')
      .replace(/\n/g, '<br>');
  },

  /* ─── Utils ─────────────────────────────────────────────── */
  updateUserContext() {
    const userIdInput = document.getElementById('pay-user-id');
    if (userIdInput && typeof App !== 'undefined' && App.currentUser) {
      userIdInput.value = App.currentUser.id;
      userIdInput.disabled = true;
    }
    const fromAccSelect = document.getElementById('pay-from-account');
    if (fromAccSelect && typeof App !== 'undefined' && App.accounts) {
      const currentVal = fromAccSelect.value;
      fromAccSelect.innerHTML = App.accounts.map(a => `<option value="${a.id}">${a.name} (${a.id}) — ₹${parseFloat(a.balance||0).toLocaleString('en-IN', {minimumFractionDigits: 2})}</option>`).join('');
      if (currentVal && App.accounts.some(a => a.id === currentVal)) {
        fromAccSelect.value = currentVal;
      }
    }
  },

  showApprovalToast(data) {
    App.showToast(`✋ Payment held for approval: ${data.id || ''}`, 'warning');
  }
};

document.addEventListener('DOMContentLoaded', () => {
  const isPaymentHubPage = window.location.pathname.includes('payment-hub');
  if (isPaymentHubPage) {
    const token = localStorage.getItem('agentToken');
    if (!token) { window.location.replace('/login.html'); return; }
  }
  if (typeof App !== 'undefined') PaymentHub.init();
  else window.addEventListener('app:ready', () => PaymentHub.init());
});
