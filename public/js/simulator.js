// AgenticBank AI — Simulator + MCP Invoker
const Simulator = {
  mcpTools: [],

  init() {
    this.setupSimForms();
    this.setupScenarios();
    this.loadMCPTools();
    App.on('userChanged', () => this.refreshAccounts());
  },

  refreshAccounts() {
    const accounts = App.accounts || [];
    const fills = ['sim-account','sim-from'];
    fills.forEach(id => {
      const el = document.getElementById(id);
      if (el) el.innerHTML = accounts.map(a => `<option value="${a.id}">${a.name||a.type} · ${App.formatCurrency(a.balance)}</option>`).join('');
    });
    this.populateRecipients(accounts);
  },

  populateRecipients(accounts) {
    const sugg = document.getElementById('recipient-suggestions');
    if (!sugg) return;
    const allRecs = [
      {icon:'👤',name:'John Doe',id:'EXT-JOHN'},
      {icon:'👤',name:'Sarah Smith',id:'EXT-SARAH'},
      {icon:'🏢',name:'Netflix',id:'EXT-NETFLIX'},
      ...accounts.map(a => ({icon:'💳',name:a.name||a.type,id:a.id}))
    ];
    sugg.innerHTML = allRecs.map(r => `<div class="recipient-item" onclick="document.getElementById('sim-to').value='${r.id}';document.getElementById('recipient-suggestions').style.display='none'"><span class="recipient-item-icon">${r.icon}</span><span>${r.name}</span><span style="font-family:var(--mono);font-size:11px;color:var(--text-muted);margin-left:auto">${r.id}</span></div>`).join('');
    const toInput = document.getElementById('sim-to');
    if (toInput) {
      toInput.addEventListener('focus', () => sugg.style.display = 'block');
      document.addEventListener('click', e => { if (!toInput.contains(e.target) && !sugg.contains(e.target)) sugg.style.display = 'none'; });
    }
  },

  setupSimForms() {
    const txnForm = document.getElementById('sim-transaction-form');
    if (txnForm) txnForm.addEventListener('submit', async e => {
      e.preventDefault();
      const accountId = document.getElementById('sim-account')?.value;
      const amount = parseFloat(document.getElementById('sim-amount')?.value);
      const type = document.getElementById('sim-type')?.value;
      const merchant = document.getElementById('sim-merchant')?.value;
      const category = document.getElementById('sim-category')?.value;
      if (!accountId || !amount) return App.showToast('Please fill all fields', 'warning');
      try {
        const r = await fetch('/api/banking/transactions/simulate', {
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({ accountId, amount: type==='debit'?-Math.abs(amount):Math.abs(amount), merchant, category })
        });
        const d = await r.json();
        if (d.success) {
          App.showToast(`Transaction created: ${App.formatCurrency(d.transaction.amount)}`, 'success');
          this.updateRiskGauge(d.transaction.riskScore);
          txnForm.reset();
        }
      } catch(e) { App.showToast('Transaction failed', 'error'); }
    });

    const xferForm = document.getElementById('sim-transfer-form');
    if (xferForm) xferForm.addEventListener('submit', async e => {
      e.preventDefault();
      const fromAccountId = document.getElementById('sim-from')?.value;
      const toAccountId = document.getElementById('sim-to')?.value;
      const amount = parseFloat(document.getElementById('sim-transfer-amount')?.value);
      const description = document.getElementById('sim-transfer-desc')?.value;
      if (!fromAccountId || !toAccountId || !amount) return App.showToast('Fill all transfer fields', 'warning');
      try {
        const r = await fetch('/api/banking/transactions/transfer', {
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({ fromAccountId, toAccountId, amount, description })
        });
        const d = await r.json();
        if (d.success) {
          App.showToast(d.requiresApproval ? `⚡ Large transfer: needs approval (${d.message})` : `Transfer complete: ${App.formatCurrency(amount)}`, d.requiresApproval?'warning':'success');
          xferForm.reset();
        } else { App.showToast(d.error||'Transfer failed','error'); }
      } catch(e) { App.showToast('Transfer error','error'); }
    });
  },

  updateRiskGauge(score) {
    const fill = document.getElementById('risk-gauge-fill');
    if (!fill) return;
    fill.style.width = `${(score||0)*100}%`;
    fill.style.background = score>0.6?'var(--danger)':score>0.3?'var(--amber)':'var(--neon)';
    const label = document.getElementById('risk-gauge-label');
    if (label) label.textContent = `Risk: ${((score||0)*100).toFixed(0)}% — ${score>0.6?'HIGH RISK':score>0.3?'MEDIUM':'LOW'}`;
  },

  setupScenarios() {
    document.querySelectorAll('.btn-scenario').forEach(btn => {
      btn.addEventListener('click', () => this.runScenario(btn.dataset.scenario));
    });
  },

  async runScenario(type) {
    const uid = App.currentUser?.id;
    if (!uid) return App.showToast('Select a customer first','warning');
    const accounts = App.accounts;
    if (!accounts.length) return;
    const acct = accounts[0].id;
    const log = document.getElementById('scenario-log');
    if (log) log.innerHTML = '';
    const logEntry = (msg, cls='ok') => { if(log){ const d=document.createElement('div'); d.className=`scenario-log-entry ${cls}`; d.textContent=`> ${msg}`; log.appendChild(d); log.scrollTop=log.scrollHeight; } };

    const scenarios = {
      normal: [
        {merchant:'Starbucks Coffee',category:'Food',amount:-6.50},{merchant:'Amazon.com',category:'Shopping',amount:-89.99},
        {merchant:'Uber Eats',category:'Food',amount:-32.00},{merchant:'Shell Gas Station',category:'Fuel',amount:-65.00},
        {merchant:'Netflix',category:'Entertainment',amount:-15.99},{merchant:'Whole Foods',category:'Grocery',amount:-145.20},
        {merchant:'Zara',category:'Shopping',amount:-120.00},{merchant:'Parking Meter',category:'Transport',amount:-8.00},
        {merchant:'Apple Store',category:'Electronics',amount:-29.99},{merchant:'Pharmacy',category:'Health',amount:-24.50}
      ],
      payday: [
        {merchant:'Employer Direct Deposit',category:'Income',amount:4200.00},{merchant:'Rent Payment',category:'Housing',amount:-1850.00},
        {merchant:'Electric Bill',category:'Utilities',amount:-180.00},{merchant:'Internet Provider',category:'Utilities',amount:-79.99},
        {merchant:'Insurance Premium',category:'Insurance',amount:-220.00},{merchant:'Savings Transfer',category:'Transfer',amount:-500.00}
      ],
      fraud: [
        {merchant:'BITCOIN ATM - URGENT',category:'Crypto',amount:-500,desc:'URGENT: crypto fees required for prize claim'},
        {merchant:'IRS IMMEDIATE PAYMENT',category:'Government',amount:-1200,desc:'WARNING: pay immediately to avoid arrest'},
        {merchant:'Tech Support Services',category:'Tech',amount:-350,desc:'Computer virus removal - urgent fee'},
        {merchant:'Nigerian Prince Corp',category:'International',amount:-2000,desc:'Processing fee for ₹5M inheritance transfer'},
        {merchant:'Lottery Commission',category:'Gambling',amount:-800,desc:'Release fee for ₹100,000 lottery winnings'}
      ]
    };

    const txns = scenarios[type] || [];
    logEntry(`Running: ${type.toUpperCase()} scenario (${txns.length} transactions)...`,'ok');
    for (const t of txns) {
      await new Promise(r=>setTimeout(r,400));
      try {
        const r = await fetch('/api/banking/transactions/simulate', {
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({ accountId: acct, amount: t.amount, merchant: t.merchant, category: t.category, description: t.desc||'' })
        });
        const d = await r.json();
        logEntry(`${t.merchant}: ${App.formatCurrency(t.amount)}`, t.amount<0&&Math.abs(t.amount)>200?'warn':'ok');
        this.updateRiskGauge(d.transaction?.riskScore||0);
      } catch(e) { logEntry(`Failed: ${t.merchant}`,'err'); }
    }
    logEntry('Scenario complete. Check AI Alerts on banker dashboard.', type==='fraud'?'err':'ok');
  },

  async loadMCPTools() {
    try {
      const r = await fetch('/api/mcp/tools');
      const d = await r.json();
      this.mcpTools = d.tools || [];
      this.renderMCPTools();
    } catch(e) {}
  },

  renderMCPTools() {
    const grid = document.getElementById('mcp-tools-grid');
    if (!grid) return;
    grid.innerHTML = this.mcpTools.map(t => `
      <div class="mcp-tool-card" data-tool="${t.name}" onclick="Simulator.selectMCPTool('${t.name}')">
        <div class="mcp-tool-icon">${t.icon}</div>
        <div class="mcp-tool-name">${t.name}</div>
        <div class="mcp-tool-desc">${t.description}</div>
        <span class="mcp-tool-cat ${t.category}">${t.category}</span>
      </div>`).join('');
  },

  selectMCPTool(name) {
    document.querySelectorAll('.mcp-tool-card').forEach(c => c.classList.toggle('selected', c.dataset.tool===name));
    const tool = this.mcpTools.find(t=>t.name===name);
    if (!tool) return;
    const paramsEl = document.getElementById('mcp-params');
    if (!paramsEl) return;
    const required = tool.parameters?.required || [];
    const props = tool.parameters?.properties || {};
    paramsEl.innerHTML = Object.entries(props).map(([key,prop]) => `
      <div class="form-group">
        <label>${key}${required.includes(key)?' *':''} <span style="color:var(--text-muted);font-size:10px">${prop.type}</span></label>
        <input class="input-premium" id="mcp-param-${key}" placeholder="${prop.description||key}" type="${prop.type==='number'?'number':'text'}">
      </div>`).join('');
    document.getElementById('mcp-invoke-btn')?.removeAttribute('disabled');
    document.getElementById('mcp-selected-name').textContent = `${tool.icon} ${tool.name}`;
  },

  async invokeMCPTool() {
    const selectedCard = document.querySelector('.mcp-tool-card.selected');
    if (!selectedCard) return App.showToast('Select a tool first','warning');
    const toolName = selectedCard.dataset.tool;
    const tool = this.mcpTools.find(t=>t.name===toolName);
    if (!tool) return;
    const params = {};
    const props = tool.parameters?.properties || {};
    Object.keys(props).forEach(key => {
      const el = document.getElementById(`mcp-param-${key}`);
      if (el?.value) params[key] = props[key].type==='number' ? parseFloat(el.value) : el.value;
    });
    // Auto-fill userId if empty
    if (props.userId && !params.userId && App.currentUser) params.userId = App.currentUser.id;
    if (props.accountId && !params.accountId && App.accounts[0]) params.accountId = App.accounts[0].id;

    const resultEl = document.getElementById('mcp-result');
    if (resultEl) { resultEl.textContent = 'Invoking...'; resultEl.className = 'mcp-result'; }
    try {
      const r = await fetch('/api/mcp/invoke', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({ tool: toolName, parameters: params })
      });
      const d = await r.json();
      if (resultEl) {
        resultEl.textContent = JSON.stringify(d.result, null, 2);
        resultEl.className = `mcp-result ${d.result?.success===false?'error':''}`;
      }
      App.showToast(`MCP: ${toolName} executed`, d.result?.success!==false?'success':'error');
    } catch(e) {
      if (resultEl) { resultEl.textContent = `Error: ${e.message}`; resultEl.className = 'mcp-result error'; }
    }
  },
};
