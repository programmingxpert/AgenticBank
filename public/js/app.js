// AgenticBank AI — Core App Module v2.0
const App = {
  ws: null, wsReady: false,
  currentUser: null, sessionId: null,
  users: [], accounts: [],

  async init() {
    this.sessionId = 'sess-' + Date.now().toString(36);
    await this.loadUsers();
    this.setupWS();
    this.setupNavigation();
    if (typeof Dashboard !== 'undefined') Dashboard.init();
    if (typeof Chat !== 'undefined') Chat.init();
    if (typeof Simulator !== 'undefined') Simulator.init();
    if (typeof Memory !== 'undefined') Memory.init();
    if (typeof Banker !== 'undefined') Banker.init();
    this.renderAgentHub();
  },

  agents: [
    { id: 'orchestrator', name: 'Orchestrator', icon: '🧠', role: 'Management', desc: 'Central reasoning engine and handoff coordinator.', tools: ['route_intent', 'session_manager', 'handoff_coordinator'] },
    { id: 'memory', name: 'Memory Agent', icon: '🧠', role: 'Core', desc: 'Manages episodic and semantic memory pools.', tools: ['episodic_retrieval', 'semantic_indexing', 'working_memory_sync'] },
    { id: 'transaction', name: 'Transaction Agent', icon: '💸', role: 'Domain', desc: 'Executes payments and account transfers.', tools: ['execute_transfer', 'get_balance', 'list_transactions'] },
    { id: 'fraud', name: 'Fraud Agent', icon: '🛡️', role: 'Domain', desc: 'Detects suspicious patterns and social engineering.', tools: ['risk_score_calculation', 'pattern_detection', 'lock_account'] },
    { id: 'loan', name: 'Loan Agent', icon: '🏦', role: 'Domain', desc: 'Manages personal and business loan inquiries.', tools: ['credit_assessment', 'loan_eligibility', 'repayment_projection'] },
    { id: 'customer_service', name: 'Customer Service', icon: '🎧', role: 'Domain', desc: 'Handles complaints and general support.', tools: ['file_complaint', 'escalate_to_human', 'faq_search'] },
    { id: 'investment', name: 'Investment Agent', icon: '📈', role: 'Domain', desc: 'Portfolio rebalancing and market analysis.', tools: ['portfolio_rebalancing', 'trend_analysis', 'trade_execution'] },
    { id: 'compliance', name: 'Compliance Agent', icon: '📋', role: 'Domain', desc: 'KYC verification and AML screening.', tools: ['kyc_verification', 'aml_screening', 'sar_filing'] },
    { id: 'extractor', name: 'Extractor Node', icon: '📄', role: 'Pipeline', desc: 'Extracts entities from loan applications.', tools: ['entity_recognition', 'document_parsing'] },
    { id: 'db_lookup', name: 'DB Lookup Node', icon: '🗄️', role: 'Pipeline', desc: 'Cross-references internal credit records.', tools: ['vector_search', 'sql_generation'] },
    { id: 'analyst', name: 'Credit Analyst', icon: '📊', role: 'Pipeline', desc: 'Analyzes income and debt-to-income ratios.', tools: ['income_verification', 'debt_analysis'] },
    { id: 'risk_node', name: 'Risk Assessment', icon: '⚖️', role: 'Pipeline', desc: 'Simulates default scenarios and risk modeling.', tools: ['probabilistic_modeling', 'scenario_sim'] },
    { id: 'underwriter', name: 'Underwriter', icon: '🔍', role: 'Pipeline', desc: 'Optimizes loan terms and policy enforcement.', tools: ['policy_enforcement', 'terms_optimization'] },
    { id: 'decision', name: 'Decision Node', icon: '⚡', role: 'Pipeline', desc: 'Final routing and audit trail generation.', tools: ['final_routing', 'audit_trail_gen'] }
  ],

  toggleAgentHub() {
    const panel = document.getElementById('agent-hub-panel');
    if (panel) panel.classList.toggle('active');
  },

  renderAgentHub() {
    const grid = document.getElementById('agent-hub-grid');
    if (!grid) return;
    grid.innerHTML = this.agents.map(a => `
      <div class="agent-card-mini">
        <div class="agent-card-header">
          <span class="agent-card-icon">${a.icon}</span>
          <span class="agent-card-name">${a.name}</span>
        </div>
        <div class="agent-card-desc">${a.desc}</div>
        <div class="agent-tools-trigger">Tools: ${a.tools.length}</div>
        <div class="agent-tools-list">
          ${a.tools.map(t => `<span class="tool-tag">${t}</span>`).join('')}
        </div>
      </div>
    `).join('');
  },

  async loadUsers() {
    try {
      const r = await fetch('/api/banking/users');
      const d = await r.json();
      this.users = d.users || [];
      const sel = document.getElementById('user-select');
      if (sel) {
        sel.innerHTML = this.users.map(u => `<option value="${u.id}">${u.firstName} ${u.lastName} — ${u.occupation}</option>`).join('');
        sel.addEventListener('change', () => this.setUser(sel.value));
        if (this.users[0]) this.setUser(this.users[0].id);
      }
    } catch(e) { console.error('loadUsers:', e); }
  },

  async setUser(uid) {
    this.currentUser = this.users.find(u => u.id === uid) || null;
    if (!this.currentUser) return;
    try {
      const r = await fetch(`/api/banking/accounts/${uid}`);
      const d = await r.json();
      this.accounts = d.accounts || [];
    } catch(e) {}
    this.emit('userChanged', this.currentUser);
    if (typeof Dashboard !== 'undefined') Dashboard.loadDashboard(uid);
    if (typeof Chat !== 'undefined') Chat.setUser(this.currentUser);
    if (typeof Simulator !== 'undefined') Simulator.refreshAccounts();
    if (typeof Memory !== 'undefined') Memory.loadMemory(uid);
    if (typeof PaymentHub !== 'undefined') {
      PaymentHub.updateUserContext();
      PaymentHub.loadPayments();
    }
    this.updateAgentList();
  },

  setupWS() {
    const wsUrl = `ws://${location.host}`;
    this.ws = new WebSocket(wsUrl);
    this.ws.onopen = () => {
      this.wsReady = true;
      this.setApiStatus('connected');
    };
    this.ws.onclose = () => { this.wsReady = false; this.setApiStatus('error'); setTimeout(() => this.setupWS(), 3000); };
    this.ws.onmessage = (e) => {
      try {
        const { event, data } = JSON.parse(e.data);
        this.handleWSEvent(event, data);
      } catch(err) {}
    };
  },

  handleWSEvent(event, data) {
    switch(event) {
      case 'transaction':
      case 'transfer':
        if (typeof Dashboard !== 'undefined') Dashboard.onTransaction(data);
        this.showToast(`New ${event}: ${data.merchant || ''}`, 'info');
        break;
      case 'approval:pending':
        this.showToast(`⚡ Approval needed: ${data.type}`, 'warning');
        if (typeof Dashboard !== 'undefined') Dashboard.onApprovalPending(data);
        if (typeof Banker !== 'undefined') {
          Banker.loadApprovals();
          if (Banker.addAlert) Banker.addAlert({
            agent: data.agentName || 'System',
            message: `High-value ${data.type} requires review: ${data.id}`,
            severity: 'high',
            timestamp: new Date().toISOString()
          });
        }
        break;
      case 'approval:resolved':
        this.showToast(`✓ Approval ${data.decision}: ${data.type}`, data.decision === 'approved' ? 'success' : 'error');
        if (typeof Dashboard !== 'undefined') Dashboard.onApprovalResolved(data);
        if (typeof Banker !== 'undefined') Banker.loadApprovals();
        break;
      case 'agent:trace':
        if (typeof Chat !== 'undefined') Chat.onTrace(data);
        break;
      case 'agent:alert':
        this.showToast(`🚨 ${data.agent}: ${data.message?.substring(0,60)}...`, 'error');
        break;
      case 'memory:update':
        if (data.userId === this.currentUser?.id && typeof Memory !== 'undefined') Memory.onUpdate(data);
        break;
      case 'loan':
        this.showToast(`Loan created: ${data.id}`, 'info');
        break;
    }
  },

  setupNavigation() {
    document.querySelectorAll('.nav-item[data-view]').forEach(item => {
      item.addEventListener('click', e => {
        e.preventDefault();
        this.switchView(item.dataset.view);
        document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
        item.classList.add('active');
        const titleEl = document.getElementById('page-title');
        if (titleEl) titleEl.textContent = item.querySelector('span:not(.nav-icon):not(.nav-badge)')?.textContent?.trim() || item.textContent.trim().replace(/[0-9]/g,'').trim();
      });
    });
  },

  switchView(viewId) {
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    const target = document.getElementById(`view-${viewId}`);
    if (target) target.classList.add('active');
    if (viewId === 'memory' && this.currentUser && typeof Memory !== 'undefined') Memory.loadMemory(this.currentUser.id);
    if (viewId === 'investments' && this.currentUser && typeof Dashboard !== 'undefined') Dashboard.loadPortfolio(this.currentUser.id);
  },

  setApiStatus(state) {
    document.querySelectorAll('.status-dot').forEach(d => {
      d.className = 'status-dot ' + (state === 'connected' ? '' : state === 'error' ? 'error' : 'simulation');
    });
    document.querySelectorAll('.status-text').forEach(t => {
      t.textContent = state === 'connected' ? 'Connected' : state === 'error' ? 'Reconnecting...' : 'Simulation Mode';
    });
  },

  async updateAgentList() {
    const list = document.getElementById('agent-status-list');
    if (!list) return;
    try {
      const r = await fetch('/api/agents');
      const d = await r.json();
      list.innerHTML = (d.agents || []).map(a => `
        <div class="agent-chip">
          <span class="agent-dot" id="dot-${a.id.toLowerCase()}"></span>
          <span>${a.icon} ${a.name.replace(' Agent','')}</span>
        </div>`).join('');
    } catch(e) {}
  },

  setAgentState(agentId, state) {
    const dot = document.getElementById(`dot-${agentId?.toLowerCase()}`);
    if (dot) { dot.className = `agent-dot ${state}`; }
  },

  showToast(message, type = 'info', duration = 4000) {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const icons = { success:'✅', error:'🚨', warning:'⚡', info:'💡' };
    const t = document.createElement('div');
    t.className = `toast ${type}`;
    t.innerHTML = `<span>${icons[type]||'ℹ'}</span><span>${message}</span>`;
    container.appendChild(t);
    setTimeout(() => { t.style.opacity='0'; t.style.transform='translateX(40px)'; t.style.transition='all .3s'; setTimeout(()=>t.remove(),300); }, duration);
  },

  formatCurrency(n, sym='₹') { if(n==null)return sym+'0.00'; return sym+Math.abs(n).toLocaleString('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2}); },
  formatDate(d) { return new Date(d).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}); },
  formatTime(d) { return new Date(d).toLocaleTimeString('en-US',{hour:'2-digit',minute:'2-digit'}); },
  riskColor(s) { return s>0.6?'var(--danger)':s>0.3?'var(--amber)':'var(--neon)'; },

  _listeners: {},
  on(event, fn) { (this._listeners[event]=this._listeners[event]||[]).push(fn); },
  emit(event, data) { (this._listeners[event]||[]).forEach(fn=>fn(data)); },
};

document.addEventListener('DOMContentLoaded', () => App.init());
