// AgenticBank AI — Dashboard Module
const Dashboard = {
  charts: {},

  init() { App.on('userChanged', u => this.loadDashboard(u.id)); },

  async loadDashboard(uid) {
    if (!uid) return;
    try {
      const r = await fetch(`/api/banking/dashboard/${uid}`);
      const d = await r.json();
      this.renderStats(d.stats, d.user);
      this.renderRecentTxns(d.stats?.recentTransactions || []);
      this.renderLoans(d.loans || [], 'active-loans');
      this.renderLoans(d.loans || [], 'loans-grid');
      if (d.portfolio) this.renderPortfolio(d.portfolio, d.market);
    } catch(e) { console.error('Dashboard load:', e); }
    try {
      const r2 = await fetch(`/api/banking/accounts/${uid}`);
      const d2 = await r2.json();
      this.renderAccounts(d2.accounts || []);
      this.populateTxnFilter(d2.accounts || []);
    } catch(e) {}
    this.loadApprovals();
  },

  renderStats(stats, user) {
    const grid = document.getElementById('stats-grid');
    if (!grid || !stats) return;
    const creditScore = user?.creditScore || 0;
    const scoreColor = creditScore >= 750 ? 'green' : creditScore >= 700 ? 'blue' : creditScore >= 650 ? 'amber' : 'red';
    grid.innerHTML = `
      <div class="stat-card"><div class="stat-label">Total Balance</div><div class="stat-value blue">${App.formatCurrency(stats.totalBalance)}</div><div class="stat-change pos">↑ Across all accounts</div><div class="stat-icon">💰</div></div>
      <div class="stat-card"><div class="stat-label">Net Worth</div><div class="stat-value green">${App.formatCurrency(stats.netWorth)}</div><div class="stat-change ${stats.netWorth>=0?'pos':'neg'}">${stats.netWorth>=0?'▲ Positive':'▼ Negative'} equity</div><div class="stat-icon">📈</div></div>
      <div class="stat-card"><div class="stat-label">Monthly Spending</div><div class="stat-value amber">${App.formatCurrency(stats.monthlySpending)}</div><div class="stat-change">Last 30 days</div><div class="stat-icon">💸</div></div>
      <div class="stat-card"><div class="stat-label">Credit Score</div><div class="stat-value ${scoreColor}">${creditScore}</div><div class="stat-change ${scoreColor === 'green'?'pos':scoreColor === 'red'?'neg':''}">${creditScore>=750?'Excellent':creditScore>=700?'Good':creditScore>=650?'Fair':'Poor'}</div><div class="stat-icon">🏅</div></div>
      <div class="stat-card">
        <div class="stat-label">Financial Health</div>
        <div style="margin-top:8px;font-size:12px;color:var(--text-secondary)">
          <div style="display:flex;justify-content:space-between;margin-bottom:4px"><span>DTI Ratio</span><strong style="color:${user.dtiRatio > 40 ? 'var(--danger)' : 'var(--neon)'}">${user.dtiRatio}%</strong></div>
          <div style="display:flex;justify-content:space-between;margin-bottom:4px"><span>Monthly Inc.</span><strong>₹${Math.round(user.monthlyIncome).toLocaleString('en-IN')}</strong></div>
          <div style="display:flex;justify-content:space-between;margin-bottom:4px"><span>Mortgage</span><strong>${user.existingMortgage ? 'Active' : 'None'}</strong></div>
          <div style="display:flex;justify-content:space-between"><span>KYC Status</span><strong style="color:${user.kycStatus === 'verified' ? 'var(--neon)' : user.kycStatus === 'pending' ? 'var(--amber)' : 'var(--danger)'}">${user.kycStatus?.toUpperCase()}</strong></div>
        </div>
        <div class="stat-icon" style="opacity:.15">⚖️</div>
      </div>
    `;
  },

  renderRecentTxns(txns) {
    const el = document.getElementById('recent-transactions');
    if (!el) return;
    if (!txns.length) { el.innerHTML = '<div class="empty-state"><div class="empty-icon">📭</div><p>No recent transactions</p></div>'; return; }
    el.innerHTML = txns.slice(0,8).map(t => `
      <div class="txn-mini">
        <div class="txn-mini-left">
          <div class="txn-mini-icon">${t.category==='Shopping'?'🛍':t.category==='Food'?'🍔':t.category==='Transfer'?'↔️':t.category==='Travel'?'✈️':'💳'}</div>
          <div><div class="txn-mini-name">${t.merchant}</div><div class="txn-mini-date">${App.formatDate(t.date)} · ${t.category}</div></div>
        </div>
        <div>
          <div class="txn-amount ${t.amount>=0?'pos':'neg'}">${t.amount>=0?'+':''}${App.formatCurrency(t.amount)}</div>
          <div class="risk-bar-wrap" title="Risk: ${(t.riskScore*100).toFixed(0)}%"><div class="risk-bar ${t.riskScore>0.6?'risk-high':t.riskScore>0.3?'risk-med':'risk-low'}" style="width:${t.riskScore*100}%"></div></div>
        </div>
      </div>`).join('');
  },

  renderLoans(loans, containerId) {
    const el = document.getElementById(containerId);
    if (!el) return;
    const active = loans.filter(l => l.status === 'active' || l.status === 'pending_approval');
    if (!active.length) { el.innerHTML = '<div class="empty-state"><div class="empty-icon">🏦</div><h3>No active loans</h3><p>Apply via the AI Assistant</p></div>'; return; }
    el.innerHTML = active.map(l => `
      <div class="account-card">
        <div class="acc-type">${l.type?.toUpperCase()||'LOAN'} · <span class="acc-status ${l.status==='active'?'active':'pending'}">${l.status}</span></div>
        <div class="acc-name">${l.purpose||'Personal Loan'}</div>
        <div class="acc-balance" style="font-size:20px">${App.formatCurrency(l.remainingBalance||l.amount)}</div>
        <div class="acc-meta"><span>Rate: ${l.interestRate}% APR</span><span>EMI: ${App.formatCurrency(l.monthlyPayment)}/mo</span></div>
      </div>`).join('');
  },

  renderAccounts(accounts) {
    const el = document.getElementById('accounts-grid');
    if (!el) return;
    el.innerHTML = accounts.map(a => `
      <div class="account-card">
        <div class="acc-type">${a.type?.toUpperCase()}</div>
        <div class="acc-name">${a.name||a.type}</div>
        <div class="acc-number">${a.accountNumber||a.id}</div>
        <div class="acc-balance ${a.balance<0?'negative':''}">${App.formatCurrency(a.balance)}</div>
        <div class="acc-meta"><span class="acc-status ${a.status==='active'?'active':'frozen'}">${a.status||'active'}</span><span>Since ${App.formatDate(a.openDate||Date.now())}</span></div>
      </div>`).join('');
  },

  populateTxnFilter(accounts) {
    const sel = document.getElementById('txn-account-filter');
    if (!sel) return;
    sel.innerHTML = '<option value="">All Accounts</option>' + accounts.map(a => `<option value="${a.id}">${a.name} (${a.id})</option>`).join('');
    sel.addEventListener('change', () => this.loadTransactions(sel.value, App.currentUser?.id));
    this.loadTransactions('', App.currentUser?.id);
  },

  async loadTransactions(accountId, userId) {
    const tbody = document.getElementById('transactions-tbody');
    if (!tbody) return;
    try {
      const url = accountId ? `/api/banking/transactions/${accountId}?limit=50` : `/api/banking/user-transactions/${userId}?limit=50`;
      const r = await fetch(url);
      const d = await r.json();
      const txns = d.transactions || [];
      tbody.innerHTML = txns.map(t => `<tr>
        <td>${App.formatDate(t.date)}</td>
        <td>${t.merchant}</td>
        <td><span style="background:rgba(0,212,255,.08);color:var(--electric);padding:2px 8px;border-radius:10px;font-size:11px">${t.category}</span></td>
        <td class="txn-amount ${t.amount>=0?'pos':'neg'}">${t.amount>=0?'+':''}${App.formatCurrency(t.amount)}</td>
        <td><div class="risk-bar-wrap"><div class="risk-bar ${t.riskScore>0.6?'risk-high':t.riskScore>0.3?'risk-med':'risk-low'}" style="width:${(t.riskScore||0)*100}%"></div></div><div style="font-size:10px;color:var(--text-muted);margin-top:3px">${((t.riskScore||0)*100).toFixed(0)}%</div></td>
        <td><span class="txn-status ${t.riskScore>0.6?'flagged':'completed'}">${t.riskScore>0.6?'FLAGGED':'OK'}</span></td>
      </tr>`).join('');
    } catch(e) {}
  },

  renderPortfolio(portfolio, market) {
    const holdingsEl = document.getElementById('holdings-table');
    if (holdingsEl && portfolio.holdings) {
      holdingsEl.innerHTML = portfolio.holdings.map(h => `
        <div class="holding-row">
          <div><div class="holding-symbol">${h.symbol}</div><div class="holding-name">${h.name||h.symbol}</div></div>
          <div style="text-align:right"><div class="holding-price">${App.formatCurrency(h.currentPrice||h.avgCost)}</div><div class="holding-change ${h.change&&h.change.startsWith('-')?'neg':'pos'}">${h.change||'+0.0%'}</div></div>
          <div style="text-align:right;min-width:60px"><div style="font-size:13px;color:var(--text-primary)">${h.shares} shares</div><div style="font-size:11px;color:var(--text-muted)">${App.formatCurrency((h.shares*h.currentPrice)||0)}</div></div>
        </div>`).join('');
    }
    const totalEl = document.getElementById('portfolio-value');
    if (totalEl) totalEl.textContent = App.formatCurrency(portfolio.totalValue||0);
    this.drawMarketTicker(market);
  },

  drawMarketTicker(market) {
    const el = document.getElementById('market-ticker');
    if (!el || !market?.indices) return;
    el.innerHTML = market.indices.map(idx => `
      <div style="display:inline-flex;align-items:center;gap:8px;background:var(--bg-card2);border:1px solid var(--border);border-radius:8px;padding:8px 14px;margin:4px">
        <span style="font-size:12px;font-weight:700;color:var(--text-primary)">${idx.name||idx.symbol}</span>
        <span style="font-family:var(--mono);font-size:13px;color:var(--electric)">${App.formatCurrency(idx.price||idx.value,'')}</span>
        <span style="font-size:11px;color:${idx.change>=0?'var(--neon)':'var(--danger)'}">${idx.change>=0?'+':''}${idx.change?.toFixed(2)||0}%</span>
      </div>`).join('');
  },

  async loadApprovals() {
    try {
      const r = await fetch('/api/approvals');
      const d = await r.json();
      const list = document.getElementById('approvals-list');
      const empty = document.getElementById('approvals-empty');
      const badge = document.getElementById('approval-badge');
      const pending = (d.approvals||[]).filter(a=>a.status==='pending');
      if (badge) { badge.textContent = pending.length; badge.style.display = pending.length ? 'inline' : 'none'; }
      if (!list) return;
      if (!pending.length) { if(empty) empty.style.display='flex'; list.innerHTML=''; return; }
      if(empty) empty.style.display='none';
      list.innerHTML = pending.map(a => `
        <div class="approval-card">
          <div class="approval-header">
            <div><div class="approval-type">${a.type?.replace(/_/g,' ')}</div><div class="approval-id">ID: ${a.id}</div></div>
            <div style="font-size:11px;color:var(--text-muted)">${App.formatTime(a.createdAt)}</div>
          </div>
          <div class="approval-detail">Agent: <strong>${a.agentName}</strong><br>Reason: ${a.reason}<br>
          ${a.details?.amount?`Amount: <strong style="color:var(--amber)">${App.formatCurrency(a.details.amount)}</strong>`:''}</div>
          <div class="approval-actions">
            <input class="input-premium approval-note" placeholder="Reviewer note (optional)" id="note-${a.id}" style="height:36px;font-size:12px">
            <button class="btn-success" onclick="Dashboard.resolveApproval('${a.id}','approved')">✓ Approve</button>
            <button class="btn-danger" onclick="Dashboard.resolveApproval('${a.id}','rejected')">✗ Reject</button>
          </div>
        </div>`).join('');
    } catch(e) {}
  },

  async resolveApproval(id, decision) {
    const note = document.getElementById(`note-${id}`)?.value||'';
    try {
      const r = await fetch(`/api/approvals/${id}/${decision}`, { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({reviewerNote:note}) });
      const d = await r.json();
      if (d.success) { App.showToast(`Approval ${decision}!`, decision==='approved'?'success':'error'); this.loadApprovals(); }
    } catch(e) {}
  },

  onTransaction(data) { if (App.currentUser && data.userId === App.currentUser.id) this.loadDashboard(App.currentUser.id); },
  onApprovalPending() { this.loadApprovals(); },
  onApprovalResolved() { this.loadApprovals(); },
};
