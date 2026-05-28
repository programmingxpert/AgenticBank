// AgenticBank AI — Banker Dashboard Module
const Banker = {
  alertCount: 0,
  complaintCount: 0,
  systemStats: {},

  init() {
    // Render banker profile details
    try {
      const profile = JSON.parse(localStorage.getItem('agentProfile'));
      if (profile) {
        const nameEl = document.getElementById('banker-display-name');
        if (nameEl) {
          nameEl.innerHTML = `💼 <strong>${profile.name}</strong> (${profile.role})`;
        }
      }
    } catch (e) {
      console.error('Error rendering agent profile:', e);
    }

    // Attach logout button handler
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', () => {
        localStorage.removeItem('agentToken');
        localStorage.removeItem('agentProfile');
        window.location.replace('/login.html');
      });
    }

    // Apply UI role filtering
    let userRole = '';
    try {
      const profile = JSON.parse(localStorage.getItem('agentProfile'));
      if (profile) {
        userRole = profile.role;
        if (userRole === 'Compliance Officer') {
          const fraudNav = document.getElementById('nav-fraud');
          if (fraudNav) fraudNav.style.display = 'none';
        } else if (userRole === 'Fraud Analyst') {
          const approvalsNav = document.getElementById('nav-approvals');
          if (approvalsNav) approvalsNav.style.display = 'none';
          const complaintsNav = document.getElementById('nav-complaints');
          if (complaintsNav) complaintsNav.style.display = 'none';
        }
      }
    } catch (e) {
      console.error('Error applying UI role filters:', e);
    }

    this.loadSystemStats();
    this.renderAgentGrid();
    this.loadUserDirectory();
    this.loadApprovals();
    this.loadAllLoans();
    this.loadAlerts();
    
    // Only load complaints for Compliance Officer
    if (userRole === 'Compliance Officer') {
      this.loadComplaints();
    }
    
    this.loadAuditLog();
    this.setupUserSearch();
    setInterval(() => this.loadSystemStats(), 15000);
  },

  async loadSystemStats() {
    try {
      const r = await fetch('/api/banking/system-stats');
      const d = await r.json();
      this.systemStats = d;
      this.renderSystemStats(d);
    } catch(e) {}
    // Also check payment HITL queue
    try {
      const pr = await fetch('/api/payments/analytics');
      const pd = await pr.json();
      const held = (pd.byStatus||{}).held || 0;
      const badge = document.getElementById('pay-hitl-badge');
      if (badge) badge.style.display = held > 0 ? 'inline' : 'none';
    } catch(e) {}
  },

  renderSystemStats(s) {
    const grid = document.getElementById('system-stats-grid');
    if (!grid) return;
    grid.innerHTML = `
      <div class="stat-card"><div class="stat-label">Total Customers</div><div class="stat-value blue">${s.totalUsers||0}</div><div class="stat-icon">👥</div></div>
      <div class="stat-card"><div class="stat-label">Total Deposits</div><div class="stat-value green">${App.formatCurrency(s.totalDeposits||0)}</div><div class="stat-icon">🏦</div></div>
      <div class="stat-card"><div class="stat-label">Active Loans</div><div class="stat-value amber">${App.formatCurrency(s.activeLoans||0)}</div><div class="stat-icon">📄</div></div>
      <div class="stat-card"><div class="stat-label">Pending Approvals</div><div class="stat-value ${(s.pendingApprovals||0)>0?'red amber':''}">${s.pendingApprovals||0}</div><div class="stat-icon">⚡</div></div>
      <div class="stat-card"><div class="stat-label">Fraud Alerts</div><div class="stat-value ${(s.fraudAlerts||0)>0?'red':''}">${s.fraudAlerts||0}</div><div class="stat-icon">🛡️</div></div>
      <div class="stat-card"><div class="stat-label">Open Complaints</div><div class="stat-value ${(s.openComplaints||0)>0?'amber':''}">${s.openComplaints||0}</div><div class="stat-icon">📢</div></div>
      <div class="stat-card"><div class="stat-label">Agents Online</div><div class="stat-value green">${s.agentsActive||6}</div><div class="stat-icon">🤖</div></div>
    `;
  },

  renderAgentGrid() {
    const grid = document.getElementById('agent-status-grid');
    if (!grid) return;
    const agents = [
      {id:'TRANSACTION',name:'Transaction',icon:'💸'},{id:'FRAUD',name:'Fraud',icon:'🛡️'},
      {id:'LOAN',name:'Loan',icon:'🏦'},{id:'CUSTOMER_SERVICE',name:'Customer Svc',icon:'🎧'},
      {id:'INVESTMENT',name:'Investment',icon:'📈'},{id:'COMPLIANCE',name:'Compliance',icon:'📋'}
    ];
    grid.innerHTML = agents.map(a => `
      <div class="agent-status-card active" id="asc-${a.id}">
        <div class="agent-status-icon">${a.icon}</div>
        <div class="agent-status-name">${a.name}</div>
        <div class="agent-status-state active" id="astate-${a.id}">ACTIVE</div>
      </div>`).join('');
  },

  setAgentState(id, state) {
    const card = document.getElementById(`asc-${id?.toUpperCase()}`);
    const stateEl = document.getElementById(`astate-${id?.toUpperCase()}`);
    if (!card || !stateEl) return;
    card.className = `agent-status-card ${state}`;
    stateEl.className = `agent-status-state ${state}`;
    stateEl.textContent = state.toUpperCase();
  },

  addTrace(data) {
    const log = document.getElementById('ai-trace-log');
    if (!log) return;
    const entry = document.createElement('div');
    const hasTools = data.toolCalls?.length > 0;
    const hasResult = !!data.toolResult;
    const isReasoning = !!data.reasoning;
    const type = isReasoning ? 'thought' : hasTools ? 'action' : hasResult ? 'observation' : 'response';
    entry.className = `trace-entry ${type}`;
    const labels = {thought:'🧠 THINKING',action:'⚡ TOOL CALL',observation:'🔭 OBSERVATION',response:'💬 RESPONSE',system:'⚠️ SYSTEM'};
    let body = `<div class="trace-label">${labels[type]||type.toUpperCase()}<span class="trace-time">${App.formatTime(data.timestamp)}</span></div>`;
    body += `<div style="font-size:10px;margin-bottom:4px;color:var(--electric)">${data.agent||'System'}</div>`;
    if (data.reasoning) body += `<div style="opacity:.75;margin-top:3px;font-size:10px">${data.reasoning.substring(0,250)}${data.reasoning.length>250?'...':''}</div>`;
    if (hasTools) data.toolCalls.forEach(t => { body += `<div style="margin-top:4px">▶ <strong>${t.name}</strong>(${(t.args||'').substring(0,80)})</div>`; });
    if (hasResult) body += `<div style="margin-top:4px;color:var(--electric)">◀ ${data.toolResult.name}: ${(data.toolResult.result||'').substring(0,120)}</div>`;
    if (data.content && !hasTools && !hasResult) body += `<div style="margin-top:3px;opacity:.9">${data.content.substring(0,250)}${data.content.length>250?'...':''}</div>`;
    entry.innerHTML = body;
    log.appendChild(entry);
    log.scrollTop = log.scrollHeight;
    while (log.children.length > 150) log.removeChild(log.firstChild);
  },

  addAlert(data) {
    const list = document.getElementById('alerts-list');
    const empty = document.getElementById('alerts-empty');
    if (empty) empty.style.display = 'none';
    const el = document.createElement('div');
    el.className = 'alert-card';
    el.innerHTML = `
      <div class="alert-header"><span>⚠️ ${(data.severity||'').toUpperCase()} ALERT</span><span>${App.formatTime(data.timestamp)}</span></div>
      <div class="alert-body"><strong>${data.agent}:</strong> ${data.message}</div>
      <div class="alert-meta" style="display:flex;justify-content:space-between;align-items:center;margin-top:10px;font-size:11px">
        <span>User: ${data.userId}</span>
        <button class="btn-primary" style="padding:4px 8px;font-size:10px;height:auto;cursor:pointer" onclick="Banker.investigateUserInChat('${data.userId}', '${(data.message || '').replace(/'/g, "\\'")}')">🔍 Investigate in Chat</button>
      </div>`;
    if (list) list.prepend(el);
    this.alertCount++;
    const badge = document.getElementById('alert-badge');
    if (badge && !document.getElementById('view-alerts')?.classList.contains('active')) {
      badge.textContent = this.alertCount;
      badge.style.display = 'inline';
    }
  },

  async loadApprovals() {
    try {
      const r = await fetch('/api/approvals');
      const d = await r.json();
      const pending = (d.approvals||[]).filter(a=>a.status==='pending');
      const badge = document.getElementById('approval-badge');
      if (badge) { badge.textContent = pending.length; badge.style.display = pending.length?'inline':'none'; }
      const list = document.getElementById('approvals-list');
      const empty = document.getElementById('approvals-empty');
      if (!list) return;
      if (!pending.length) { if(empty)empty.style.display='flex'; list.innerHTML=''; return; }
      if(empty)empty.style.display='none';

      // Separate payment holds from regular approvals
      const paymentHolds = pending.filter(a => a.type === 'payment_hold');
      const otherApprovals = pending.filter(a => a.type !== 'payment_hold');

      let html = '';

      // ── Payment HITL section ──
      if (paymentHolds.length) {
        html += `<div style="margin-bottom:16px">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">
            <div style="flex:1;height:1px;background:rgba(220,38,38,0.2)"></div>
            <span style="font-size:11px;font-weight:700;color:var(--danger);text-transform:uppercase;letter-spacing:1px;white-space:nowrap">💳 Payment HITL Queue (${paymentHolds.length})</span>
            <div style="flex:1;height:1px;background:rgba(220,38,38,0.2)"></div>
          </div>
          ${paymentHolds.map(a => {
            const det = a.details || {};
            const amt = det.amount ? App.formatCurrency(det.amount) : '—';
            const rail = det.rail || 'Auto';
            const railIcon = {UPI:'📱',IMPS:'⚡',NEFT:'🏦',RTGS:'💰',SWIFT:'🌐',Internal:'🔄'}[rail] || '💳';
            const isSwift = rail === 'SWIFT';
            const isHighValue = det.amount > 500000;
            return `<div class="approval-card" style="border-color:rgba(220,38,38,0.25);background:rgba(220,38,38,0.02)">
              <div style="display:flex;align-items:center;gap:10px;padding:12px 16px;border-bottom:1px solid rgba(220,38,38,0.1)">
                <div style="width:40px;height:40px;border-radius:10px;background:linear-gradient(135deg,#7c3aed,#0284c7);display:flex;align-items:center;justify-content:center;font-size:20px;flex-shrink:0">💳</div>
                <div style="flex:1;min-width:0">
                  <div style="font-size:13px;font-weight:700;color:var(--text-primary)">Payment Hold — ${det.beneficiaryName || 'Unknown Beneficiary'}</div>
                  <div style="font-size:11px;color:var(--text-muted);margin-top:2px">ID: ${a.id} · Payment: ${det.paymentId || '—'} · ${App.formatTime(a.createdAt)}</div>
                </div>
                <div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px">
                  <span style="font-size:15px;font-weight:700;color:var(--amber)">${amt}</span>
                  <span style="font-size:10px;background:rgba(2,132,199,0.1);color:var(--electric);padding:2px 8px;border-radius:8px">${railIcon} ${rail}</span>
                </div>
              </div>
              <div style="padding:12px 16px;display:flex;gap:8px;flex-wrap:wrap">
                ${isSwift ? `<span style="font-size:10px;font-weight:700;background:rgba(220,38,38,0.1);color:var(--danger);padding:3px 10px;border-radius:10px;border:1px solid rgba(220,38,38,0.2)">🌐 SWIFT — Compliance Required</span>` : ''}
                ${isHighValue ? `<span style="font-size:10px;font-weight:700;background:rgba(217,119,6,0.1);color:var(--amber);padding:3px 10px;border-radius:10px;border:1px solid rgba(217,119,6,0.2)">⚠️ High-Value > ₹5L</span>` : ''}
                <span style="font-size:10px;color:var(--text-secondary)">Ref: ${det.reference || '—'}</span>
              </div>
              <div style="padding:8px 16px;font-size:12px;color:var(--text-secondary);background:var(--bg-card2);border-top:1px solid var(--border)">
                <strong>Hold Reason:</strong> ${a.reason}
              </div>
              <div class="approval-actions" style="border-top:1px solid var(--border)">
                <input class="input-premium approval-note" id="bnote-${a.id}" placeholder="Add compliance note (required for SWIFT)..." style="height:34px;font-size:12px">
                <button class="btn-success" onclick="Banker.resolveApproval('${a.id}','approved')">✓ Approve Payment</button>
                <button class="btn-danger" onclick="Banker.resolveApproval('${a.id}','rejected')">✗ Reject Payment</button>
              </div>
            </div>`;
          }).join('')}
        </div>`;
      }

      // ── Regular approvals ──
      if (otherApprovals.length) {
        if (paymentHolds.length) {
          html += `<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">
            <div style="flex:1;height:1px;background:var(--border)"></div>
            <span style="font-size:11px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:1px;white-space:nowrap">Other Approvals (${otherApprovals.length})</span>
            <div style="flex:1;height:1px;background:var(--border)"></div>
          </div>`;
        }
        html += otherApprovals.map(a => `
          <div class="approval-card">
            <div class="approval-header">
              <div><div class="approval-type">${(a.type||'').replace(/_/g,' ')}</div><div class="approval-id">ID: ${a.id} · Agent: ${a.agentName}</div></div>
              <div style="font-size:11px;color:var(--text-muted)">${App.formatTime(a.createdAt)}</div>
            </div>
            <div class="approval-detail">${a.reason}<br>
            ${a.details?.amount?`<strong style="color:var(--amber)">Amount: ${App.formatCurrency(a.details.amount)}</strong>`:''}</div>
            <div class="approval-actions">
              <input class="input-premium approval-note" id="bnote-${a.id}" placeholder="Reviewer note" style="height:34px;font-size:12px">
              <button class="btn-success" onclick="Banker.resolveApproval('${a.id}','approved')">✓ Approve</button>
              <button class="btn-danger" onclick="Banker.resolveApproval('${a.id}','rejected')">✗ Reject</button>
            </div>
          </div>`).join('');
      }

      list.innerHTML = html;
    } catch(e) { console.error('loadApprovals error:', e); }
  },

  async resolveApproval(id, decision) {
    const note = document.getElementById(`bnote-${id}`)?.value||'';
    try {
      const r = await fetch(`/api/approvals/${id}/${decision}`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({reviewerNote:note})});
      const d = await r.json();
      if (d.success) {
        App.showToast(`Payment ${decision} successfully!`, decision==='approved'?'success':'error');
        this.loadApprovals();
        // Refresh payment queue badge in banker stats
        this.loadSystemStats();
      }
    } catch(e) {}
  },

  async loadAllLoans() {
    try {
      const r = await fetch('/api/banking/loans/all');
      const d = await r.json();
      const el = document.getElementById('banker-loans-list');
      if (!el) return;
      const loans = d.loans||[];
      if (!loans.length) { el.innerHTML='<div class="empty-state"><div class="empty-icon">🏦</div><p>No loans in system</p></div>'; return; }
      el.innerHTML = `<table class="transactions-table"><thead><tr><th>Loan ID</th><th>User</th><th>Purpose</th><th>Amount</th><th>Rate</th><th>EMI</th><th>Status</th></tr></thead><tbody>${
        loans.map(l=>`<tr><td style="font-family:var(--mono);font-size:12px">${l.id}</td><td>${l.userId}</td><td>${l.purpose||'—'}</td><td class="txn-amount neg">${App.formatCurrency(l.remainingBalance||l.amount)}</td><td>${l.interestRate||'—'}%</td><td>${App.formatCurrency(l.monthlyPayment)}/mo</td><td><span class="txn-status ${l.status==='active'?'completed':l.status==='pending_approval'?'pending':'flagged'}">${l.status}</span></td></tr>`).join('')
      }</tbody></table>`;
    } catch(e) {}
  },

  async loadAlerts() {
    // Alerts arrive via WebSocket — this just ensures empty state is correct
    const list = document.getElementById('alerts-list');
    const empty = document.getElementById('alerts-empty');
    if (list && !list.children.length && empty) empty.style.display = 'flex';
  },

  async loadAuditLog() {
    try {
      const r = await fetch('/api/banking/audit?limit=30');
      const d = await r.json();
      const el = document.getElementById('audit-log');
      if (!el) return;
      const logs = d.auditLog || [];
      el.innerHTML = `<table class="transactions-table"><thead><tr><th>Time</th><th>Action</th><th>Details</th></tr></thead><tbody>${
        logs.slice().reverse().map(l=>`<tr><td style="font-family:var(--mono);font-size:11px">${App.formatTime(l.timestamp)}</td><td><span class="txn-status completed" style="font-size:10px">${l.action}</span></td><td style="font-size:12px;color:var(--text-secondary)">${JSON.stringify(l.data).substring(0,80)}...</td></tr>`).join('')
      }</tbody></table>`;
    } catch(e) {}
  },

  async loadUserIntel(userId) {
    if (this.currentIntelUser === userId) return;
    this.currentIntelUser = userId;
    try {
      const r = await fetch(`/api/banking/users/${userId}`);
      const d = await r.json();
      const u = d.user;
      const el = document.getElementById('intel-content');
      if (!el || !u) return;
      
      const scoreColor = u.creditScore >= 750 ? 'var(--neon)' : u.creditScore >= 700 ? 'var(--electric)' : u.creditScore >= 650 ? 'var(--amber)' : 'var(--danger)';
      
      el.innerHTML = `
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">
          <div style="width:40px;height:40px;border-radius:50%;background:rgba(2,132,199,0.08);display:flex;align-items:center;justify-content:center;font-size:20px">👤</div>
          <div><div style="font-weight:700;font-size:14px;color:var(--text-primary)">${u.firstName} ${u.lastName}</div><div style="font-size:11px;color:var(--text-muted)">${u.occupation} @ ${u.employer}</div></div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
          <div style="background:var(--bg-surface);padding:10px;border-radius:8px;border:1px solid var(--border)">
            <div style="font-size:9px;color:var(--text-muted);text-transform:uppercase;margin-bottom:4px">Credit Score</div>
            <div style="font-size:20px;font-weight:700;color:${scoreColor};font-family:'Space Grotesk'">${u.creditScore}</div>
          </div>
          <div style="background:var(--bg-surface);padding:10px;border-radius:8px;border:1px solid var(--border)">
            <div style="font-size:9px;color:var(--text-muted);text-transform:uppercase;margin-bottom:4px">Risk Profile</div>
            <div style="font-size:14px;font-weight:600;color:var(--text-primary);margin-top:4px">${u.riskProfile.toUpperCase()}</div>
          </div>
        </div>
        <div style="margin-top:10px;font-size:11px;color:var(--text-secondary);display:grid;grid-template-columns:1fr 1fr;gap:8px">
          <div>💰 Annual: ₹${u.annualIncome.toLocaleString('en-IN')}</div>
          <div>💵 Monthly: ₹${Math.round(u.monthlyIncome).toLocaleString('en-IN')}</div>
          <div style="color:${u.dtiRatio > 40 ? 'var(--danger)' : 'var(--neon)'}">📉 DTI: ${u.dtiRatio}%</div>
          <div>🏠 Mortgage: ${u.existingMortgage ? 'YES' : 'NONE'}</div>
        </div>
        ${u.existingMortgage ? `
          <div style="margin-top:10px;padding:8px;background:var(--bg-deep);border-radius:4px;font-size:10px">
            <strong style="color:var(--amber)">Active Mortgage Snapshot</strong><br>
            Balance: ₹${u.existingMortgage.balance.toLocaleString('en-IN')}<br>
            Payment: ₹${u.existingMortgage.payment.toLocaleString('en-IN')}/mo
          </div>
        ` : ''}
        <div style="margin-top:15px;display:grid;grid-template-columns:1fr 1fr;gap:8px">
          <button id="btn-edit-profile" class="btn-primary" style="font-size:11px;padding:8px">⚙️ Edit Profile</button>
          <button id="btn-manage-accounts" class="btn-secondary" style="font-size:11px;padding:8px">💳 Manage Accounts</button>
        </div>
        <button id="btn-consult-copilot" class="btn-ghost" style="width:100%;margin-top:8px;font-size:11px;padding:8px;border:1px solid var(--border);color:var(--electric);cursor:pointer">💬 Consult AI Copilot</button>
        <div id="intel-accounts-list" style="margin-top:15px"></div>
      `;

      // Use event listeners for better reliability
      setTimeout(() => {
          const editBtn = document.getElementById('btn-edit-profile');
          if (editBtn) editBtn.onclick = () => {
              console.log('Banker: Edit Profile clicked for', u.id);
              this.openEditUserModal(u.id);
          };
          
          const manageBtn = document.getElementById('btn-manage-accounts');
          if (manageBtn) manageBtn.onclick = () => {
              console.log('Banker: Manage Accounts clicked for', u.id);
              this.loadUserAccounts(u.id);
          };

          const consultBtn = document.getElementById('btn-consult-copilot');
          if (consultBtn) consultBtn.onclick = () => {
              console.log('Banker: Consult AI Copilot clicked for', u.id);
              this.consultCopilotForUser(u.id);
          };
      }, 50);
    } catch(e) {}
  },

  async loadUserAccounts(userId) {
    try {
      const r = await fetch(`/api/banking/accounts/${userId}`);
      const d = await r.json();
      const el = document.getElementById('intel-accounts-list');
      if (!el) return;
      el.innerHTML = `<div style="font-size:11px;font-weight:700;margin-bottom:8px;color:var(--text-muted)">MANAGEMENT: ACCOUNTS</div>` + d.accounts.map(a => `
        <div class="account-card-mini" style="background:var(--bg-surface);margin-bottom:8px;border:1px solid var(--border)">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <div style="font-size:11px;font-weight:600">${a.name}</div>
            <div style="font-size:10px;color:var(--neon)">${App.formatCurrency(a.balance)}</div>
          </div>
          <div style="display:flex;gap:5px;margin-top:8px">
            <input type="number" id="bal-${a.id}" placeholder="New Bal" style="width:70px;background:var(--bg-card2);border:1px solid var(--border2);color:var(--text-primary);font-size:10px;padding:2px 5px;border-radius:4px">
            <button class="btn-success" onclick="Banker.updateBalance('${a.id}')" style="font-size:9px;padding:2px 8px">Set</button>
            <button class="btn-danger" onclick="Banker.deleteAccount('${a.id}','${userId}')" style="font-size:9px;padding:2px 8px">Del</button>
          </div>
        </div>
      `).join('');
    } catch(e) {}
  },

  async updateBalance(accountId) {
    const bal = document.getElementById(`bal-${accountId}`)?.value;
    if (!bal) return;
    try {
      await fetch(`/api/banking/accounts/${accountId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ balance: parseFloat(bal) })
      });
      App.showToast('Balance updated', 'success');
      if (this.currentIntelUser) this.loadUserAccounts(this.currentIntelUser);
    } catch(e) {}
  },

  async deleteAccount(accountId, userId) {
    if (!confirm('Permanently delete this account?')) return;
    try {
      await fetch(`/api/banking/accounts/${accountId}`, { method: 'DELETE' });
      App.showToast('Account terminated', 'warning');
      this.loadUserAccounts(userId);
    } catch(e) {}
  },

  openEditUserModal(userId) {
    const u = App.users.find(u => u.id === userId);
    if (!u) return;
    const modal = document.createElement('div');
    modal.className = 'modal-overlay';
    modal.id = 'edit-user-modal';
    modal.innerHTML = `
      <div class="modal-content glass" style="max-width:450px">
        <h3 style="margin-top:0">Edit Customer: ${u.firstName}</h3>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin-top:15px">
          <div class="input-group">
            <label>Credit Score</label>
            <input type="number" id="edit-score" value="${u.creditScore || 0}" class="input-premium">
          </div>
          <div class="input-group">
            <label>Annual Income (₹)</label>
            <input type="number" id="edit-income" value="${u.annualIncome || 0}" class="input-premium">
          </div>
          <div class="input-group">
            <label>KYC Status</label>
            <select id="edit-kyc" class="input-premium">
              <option value="verified" ${(u.kycStatus||'').toLowerCase()==='verified'?'selected':''}>Verified</option>
              <option value="pending" ${(u.kycStatus||'').toLowerCase()==='pending'?'selected':''}>Pending</option>
              <option value="flagged" ${(u.kycStatus||'').toLowerCase()==='flagged'?'selected':''}>Flagged</option>
            </select>
          </div>
          <div class="input-group">
            <label>Risk Profile</label>
            <select id="edit-risk" class="input-premium">
              <option value="low" ${(u.riskProfile||'').toLowerCase()==='low'?'selected':''}>Low</option>
              <option value="medium" ${(u.riskProfile||'').toLowerCase()==='medium'?'selected':''}>Medium</option>
              <option value="high" ${(u.riskProfile||'').toLowerCase()==='high'?'selected':''}>High</option>
            </select>
          </div>
        </div>
        <div style="margin-top:20px;display:flex;gap:10px;justify-content:flex-end">
          <button class="btn-secondary" onclick="document.getElementById('edit-user-modal').remove()">Cancel</button>
          <button class="btn-primary" onclick="Banker.saveUserEdits('${userId}')">Save Changes</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);
  },

  async saveUserEdits(userId) {
    const data = {
      creditScore: parseInt(document.getElementById('edit-score').value),
      annualIncome: parseFloat(document.getElementById('edit-income').value),
      kycStatus: document.getElementById('edit-kyc').value,
      riskProfile: document.getElementById('edit-risk').value,
    };
    try {
      await fetch(`/api/banking/users/${userId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      App.showToast('Profile updated!', 'success');
      document.getElementById('edit-user-modal').remove();
      this.currentIntelUser = null; // Force reload
      this.loadUserIntel(userId);
    } catch(e) {}
  },

  async loadUserDirectory() {
    console.log('Banker: Loading user directory...');
    const grid = document.getElementById('user-directory-grid');
    if (!grid) {
        console.warn('Banker: user-directory-grid not found in DOM');
        return;
    }

    try {
      // Use App.users if already loaded, otherwise fetch
      if (App.users && App.users.length > 0) {
        console.log(`Banker: Using ${App.users.length} pre-loaded users from App context`);
        this.allUsers = App.users;
      } else {
        console.log('Banker: App.users empty, fetching from API...');
        const r = await fetch('/api/banking/users');
        const d = await r.json();
        this.allUsers = d.users || [];
      }
      
      this.renderUserDirectory(this.allUsers);
    } catch(e) {
      console.error('Banker: Failed to load user directory:', e);
      grid.innerHTML = '<div style="color:var(--danger);grid-column:1/-1;text-align:center">Error loading directory. Check console.</div>';
    }
  },

  renderUserDirectory(users) {
    const grid = document.getElementById('user-directory-grid');
    if (!grid) return;
    
    if (!users || !users.length) {
      grid.innerHTML = '<div style="opacity:.4;grid-column:1/-1;text-align:center;padding:20px">No users found in system</div>';
      return;
    }
    
    console.log(`Banker: Rendering directory with ${users.length} users`);
    grid.innerHTML = users.map(u => `
      <div class="agent-status-card" style="cursor:pointer;padding:12px;display:flex;flex-direction:column;gap:5px;${this.currentIntelUser===u.id?'border-color:var(--electric);background:rgba(0,212,255,0.05)':''}" onclick="Banker.selectUser('${u.id}')">
        <div style="font-size:12px;font-weight:700;color:var(--text-primary)">${u.firstName} ${u.lastName}</div>
        <div style="font-size:10px;color:var(--text-muted)">${u.occupation}</div>
        <div style="display:flex;justify-content:space-between;align-items:center;margin-top:5px">
          <span style="font-size:9px;color:var(--text-muted)">Score</span>
          <span style="font-size:11px;font-weight:700;color:${App.riskColor(1 - (u.creditScore/850))}">${u.creditScore}</span>
        </div>
      </div>
    `).join('');
  },

  selectUser(userId) {
    console.log(`Banker: Selected user ${userId}`);
    this.loadUserIntel(userId);
    this.renderUserDirectory(this.allUsers); // Re-render to show active state
  },

  setupUserSearch() {
    const input = document.getElementById('user-search');
    if (!input) return;
    input.addEventListener('input', (e) => {
      const q = e.target.value.toLowerCase();
      if (!this.allUsers) return;
      const filtered = this.allUsers.filter(u => 
        u.firstName.toLowerCase().includes(q) || 
        u.lastName.toLowerCase().includes(q) || 
        u.occupation.toLowerCase().includes(q)
      );
      this.renderUserDirectory(filtered);
    });
  },

  async loadComplaints() {
    try {
      const r = await fetch('/api/banking/complaints/all');
      const d = await r.json();
      const list = document.getElementById('complaints-list');
      const empty = document.getElementById('complaints-empty');
      const table = document.getElementById('complaints-table');
      if (!list) return;
      const complaints = d.complaints || [];
      if (!complaints.length) {
          if (empty) empty.style.display = 'flex';
          if (table) table.style.display = 'none';
          return;
      }
      if (empty) empty.style.display = 'none';
      if (table) table.style.display = 'table';
      list.innerHTML = complaints.slice().reverse().map(c => `
        <tr>
          <td style="font-family:var(--mono);font-size:11px">${c.id}</td>
          <td>${c.userId}</td>
          <td><strong>${c.subject}</strong><br><small style="color:var(--text-muted)">${c.description}</small></td>
          <td><span class="txn-status" style="background:${c.priority==='high'?'rgba(255,59,78,.1)':c.priority==='medium'?'rgba(255,184,0,.1)':'rgba(0,212,255,.1)'};color:${c.priority==='high'?'var(--danger)':c.priority==='medium'?'var(--amber)':'var(--electric)'}">${c.priority}</span></td>
          <td><span class="txn-status ${c.status==='resolved'?'completed':'pending'}">${c.status}</span></td>
          <td style="font-size:11px;color:var(--text-muted)">${c.date}</td>
          <td>
            ${c.status !== 'resolved' ? `<button class="btn-ghost" onclick="Banker.investigateComplaint('${c.id}', '${c.userId}', '${c.subject.replace(/'/g, "\\'")}')" style="font-size:10px;padding:4px 8px;border:1px solid var(--border)">🔍 Consult Copilot</button>` : `<span style="color:var(--text-muted);font-size:11px">Resolved</span>`}
          </td>
        </tr>`).join('');
    } catch(e) {}
  },

  onComplaint(data) {
    this.loadComplaints();
    this.complaintCount++;
    const badge = document.getElementById('complaint-badge');
    if (badge && !document.getElementById('view-complaints')?.classList.contains('active')) {
      badge.textContent = this.complaintCount;
      badge.style.display = 'inline';
    }
  },

  // ─── AI Copilot ───────────────────────────────────────────────────────────
  copilotSessionId: null,

  getBankerUsername() {
    try {
      const profile = JSON.parse(localStorage.getItem('agentProfile'));
      return profile ? profile.username : 'banker';
    } catch (e) {
      return 'banker';
    }
  },

  async loadCopilotSessions() {
    const userId = `banker_${this.getBankerUsername()}`;
    try {
      const r = await fetch(`/api/chat/sessions?userId=${userId}`);
      const d = await r.json();
      const list = document.getElementById('copilot-sessions-list');
      if (!list) return;

      const sessions = d.sessions || [];
      if (sessions.length === 0) {
        await this.createNewCopilotSession();
        return;
      }

      list.innerHTML = sessions.map(s => {
        const isActive = this.copilotSessionId === s.id;
        const dateStr = App.formatDate(s.updatedAt) + ' ' + App.formatTime(s.updatedAt);
        return `
          <div class="session-item ${isActive ? 'active' : ''}" onclick="Banker.switchCopilotSession('${s.id}')">
            <div class="session-title-container">
              <div class="session-title" title="${s.title}">${s.title}</div>
              <div class="session-date">${dateStr}</div>
            </div>
            <button class="session-delete-btn" onclick="event.stopPropagation(); Banker.deleteCopilotSession('${s.id}')" title="Delete Session">✕</button>
          </div>
        `;
      }).join('');

      const activeSession = sessions.find(s => s.id === this.copilotSessionId);
      if (!activeSession && sessions[0]) {
        await this.switchCopilotSession(sessions[0].id);
      }
    } catch (e) {
      console.error('loadCopilotSessions error:', e);
    }
  },

  async createNewCopilotSession() {
    const userId = `banker_${this.getBankerUsername()}`;
    try {
      const r = await fetch('/api/chat/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ userId: userId, title: 'New Chat' })
      });
      const d = await r.json();
      if (d.success && d.session) {
        this.copilotSessionId = d.session.id;
        await this.loadCopilotSessions();
        await this.switchCopilotSession(d.session.id);
      }
    } catch (e) {
      console.error('createNewCopilotSession error:', e);
    }
  },

  async switchCopilotSession(sessionId) {
    if (window.AudioService && window.AudioService.synth) {
      window.AudioService.synth.cancel();
    }
    
    this.copilotSessionId = sessionId;
    
    document.querySelectorAll('#copilot-sessions-list .session-item').forEach(item => {
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
        const titleEl = document.getElementById('copilot-chat-title');
        if (titleEl) titleEl.textContent = session.title || '🤖 AI Banker Copilot';
        
        const msgs = document.getElementById('copilot-chat-messages');
        if (msgs) {
          msgs.innerHTML = '';
          if (session.messages.length === 0) {
            msgs.innerHTML = `
              <div class="chat-welcome" style="text-align:center;padding:40px 20px">
                <div class="welcome-icon" style="font-size:48px;margin-bottom:16px">🤖</div>
                <h2 style="font-size:20px;margin-bottom:8px">AI Banker Assistant</h2>
                <p style="color:var(--text-secondary);max-width:500px;margin:0 auto 20px">Hello! I am your AI Banking Copilot. I have access to system accounts, compliance statuses, transaction history, and complaints.</p>
                <p style="font-size:12px;color:var(--text-muted);margin-bottom:12px">You can ask me to take direct actions, such as:</p>
                <div class="quick-actions" style="display:grid;grid-template-columns:1fr 1fr;gap:10px;max-width:500px;margin:0 auto">
                  <button class="btn-ghost" style="text-align:left;font-size:11px;padding:8px 12px;border:1px solid var(--border)" onclick="Banker.quickCopilotMsg('Explain why user USR-003 was flagged')">❓ Why was USR-003 flagged?</button>
                  <button class="btn-ghost" style="text-align:left;font-size:11px;padding:8px 12px;border:1px solid var(--border)" onclick="Banker.quickCopilotMsg('Freeze all accounts of user USR-003')">❄️ Freeze user USR-003</button>
                  <button class="btn-ghost" style="text-align:left;font-size:11px;padding:8px 12px;border:1px solid var(--border)" onclick="Banker.quickCopilotMsg('Check recent transactions for USR-001')">📜 Get recent txns USR-001</button>
                  <button class="btn-ghost" style="text-align:left;font-size:11px;padding:8px 12px;border:1px solid var(--border)" onclick="Banker.quickCopilotMsg('Resolve complaint CMP-001')">📢 Resolve complaint CMP-001</button>
                </div>
              </div>
            `;
          } else {
            session.messages.forEach(m => {
              this.appendCopilotMsg(m.role === 'user' ? 'user' : 'agent', m.content, m);
            });
          }
        }
      }
    } catch (e) {
      console.error('switchCopilotSession error:', e);
    }
  },

  async deleteCopilotSession(sessionId) {
    if (!confirm('Are you sure you want to delete this Copilot chat session?')) return;
    try {
      const r = await fetch(`/api/chat/sessions/${sessionId}`, { method: 'DELETE' });
      const d = await r.json();
      if (d.success) {
        if (this.copilotSessionId === sessionId) {
          this.copilotSessionId = null;
        }
        await this.loadCopilotSessions();
      }
    } catch (e) {
      console.error('deleteCopilotSession error:', e);
    }
  },

  async initCopilotView() {
    console.log("Banker: Initializing AI Copilot view...");
    if (!this.copilotSessionId) {
      await this.loadCopilotSessions();
    }

    const select = document.getElementById('copilot-user-select');
    if (!select) return;

    const currentVal = select.value;

    if (!this.allUsers || this.allUsers.length === 0) {
      await this.loadUserDirectory();
    }

    select.innerHTML = '<option value="">-- No customer selected --</option>' + 
      (this.allUsers || []).map(u => `<option value="${u.id}">${u.firstName} ${u.lastName} (${u.id})</option>`).join('');

    if (currentVal && (this.allUsers || []).some(u => u.id === currentVal)) {
      select.value = currentVal;
    } else if (this.currentIntelUser) {
      select.value = this.currentIntelUser;
    }

    this.onCopilotUserChange();
  },

  async onCopilotUserChange() {
    const select = document.getElementById('copilot-user-select');
    const detail = document.getElementById('copilot-context-detail');
    if (!select || !detail) return;

    const userId = select.value;
    if (!userId) {
      detail.innerHTML = `<div style="text-align:center;color:var(--text-muted);padding-top:40px">
        Select a customer to load real-time intelligence into the AI context window.
      </div>`;
      return;
    }

    this.currentIntelUser = userId;

    try {
      detail.innerHTML = '<div style="opacity:.6;text-align:center;padding-top:40px">Loading financials...</div>';
      
      const r = await fetch(`/api/banking/users/${userId}`);
      const d = await r.json();
      const u = d.user;
      if (!u) {
        detail.innerHTML = '<div style="color:var(--danger)">Failed to load user info.</div>';
        return;
      }

      const accRes = await fetch(`/api/banking/accounts/${userId}`);
      const accData = await accRes.json();
      const accounts = accData.accounts || [];

      const scoreColor = u.creditScore >= 750 ? 'var(--neon)' : u.creditScore >= 700 ? 'var(--electric)' : u.creditScore >= 650 ? 'var(--amber)' : 'var(--danger)';

      detail.innerHTML = `
        <div style="font-weight:700;font-size:14px;color:var(--text-primary);margin-bottom:4px">${u.firstName} ${u.lastName}</div>
        <div style="font-size:11px;color:var(--text-muted);margin-bottom:12px">${u.occupation} @ ${u.employer}</div>
        
        <div style="display:flex;gap:8px;margin-bottom:16px">
          <div style="flex:1;background:var(--bg-surface);padding:6px;border-radius:4px;border:1px solid var(--border);text-align:center">
            <div style="font-size:8px;color:var(--text-muted);text-transform:uppercase">Credit Score</div>
            <div style="font-size:14px;font-weight:700;color:${scoreColor}">${u.creditScore}</div>
          </div>
          <div style="flex:1;background:var(--bg-surface);padding:6px;border-radius:4px;border:1px solid var(--border);text-align:center">
            <div style="font-size:8px;color:var(--text-muted);text-transform:uppercase">KYC Status</div>
            <div style="font-size:11px;font-weight:700;color:${u.kycStatus==='verified'?'var(--neon)':u.kycStatus==='flagged'?'var(--danger)':'var(--amber)'}">${(u.kycStatus||'').toUpperCase()}</div>
          </div>
        </div>

        <div style="font-size:11px;font-weight:600;color:var(--text-primary);margin-bottom:6px;text-transform:uppercase;letter-spacing:0.5px">Accounts</div>
        <div style="display:flex;flex-direction:column;gap:6px;margin-bottom:16px">
          ${accounts.map(a => `
            <div style="display:flex;justify-content:space-between;align-items:center;background:var(--bg-surface);padding:6px 8px;border-radius:4px;border:1px solid var(--border)">
              <div>
                <div style="font-weight:600;font-size:11px">${a.name}</div>
                <div style="font-size:9px;color:var(--text-muted)">ID: ${a.id} · <span style="color:${a.status==='active'?'var(--neon)':'var(--danger)'}">${a.status}</span></div>
              </div>
              <div style="font-weight:700;font-family:var(--mono);font-size:11px">${App.formatCurrency(a.balance)}</div>
            </div>
          `).join('')}
        </div>
        
        <div style="font-size:11px;font-weight:600;color:var(--text-primary);margin-bottom:6px;text-transform:uppercase;letter-spacing:0.5px">Direct Actions</div>
        <div style="display:flex;gap:6px">
          <button class="btn-danger" style="flex:1;font-size:10px;padding:6px;height:auto" onclick="Banker.freezeUserAccounts('${u.id}')">❄️ Freeze Accounts</button>
          <button class="btn-success" style="flex:1;font-size:10px;padding:6px;height:auto" onclick="Banker.unfreezeUserAccounts('${u.id}')">🔥 Unfreeze</button>
        </div>
      `;
    } catch (e) {
      detail.innerHTML = `<div style="color:var(--danger)">Error loading context: ${e.message}</div>`;
    }
  },

  async freezeUserAccounts(userId) {
    if (!confirm(`Are you sure you want to freeze all accounts for user ${userId}?`)) return;
    try {
      const r = await fetch(`/api/banking/users/${userId}/freeze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('agentToken')}`
        },
        body: JSON.stringify({ reason: 'Manual banker action' })
      });
      const d = await r.json();
      if (d.success) {
        App.showToast(d.message, 'success');
        this.onCopilotUserChange();
        this.loadUserDirectory();
      } else {
        App.showToast(d.error || 'Failed to freeze accounts', 'error');
      }
    } catch (e) {
      App.showToast('Network error freezing accounts', 'error');
    }
  },

  async unfreezeUserAccounts(userId) {
    if (!confirm(`Are you sure you want to unfreeze all accounts for user ${userId}?`)) return;
    try {
      const accountsRes = await fetch(`/api/banking/accounts/${userId}`);
      const accountsData = await accountsRes.json();
      const accounts = accountsData.accounts || [];
      if (!accounts.length) {
        App.showToast('No accounts found to unfreeze', 'error');
        return;
      }
      
      let successCount = 0;
      for (const acc of accounts) {
        const r = await fetch(`/api/banking/accounts/${acc.id}`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${localStorage.getItem('agentToken')}`
          },
          body: JSON.stringify({ status: 'active' })
        });
        const d = await r.json();
        if (d.success) successCount++;
      }

      if (successCount > 0) {
        App.showToast(`Successfully activated ${successCount} account(s) for user ${userId}`, 'success');
        this.onCopilotUserChange();
        this.loadUserDirectory();
      } else {
        App.showToast('Failed to unfreeze accounts', 'error');
      }
    } catch (e) {
      App.showToast('Network error unfreezing accounts', 'error');
    }
  },

  quickCopilotMsg(text) {
    const input = document.getElementById('copilot-chat-input');
    if (input) {
      input.value = text;
      this.sendCopilotMessage();
    }
  },

  isVoiceMode: false,

  toggleVoiceMode() {
    if (!window.AudioService) return;
    this.isVoiceMode = !this.isVoiceMode;
    const btn = document.getElementById('banker-stt-btn');
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
        const input = document.getElementById('copilot-chat-input');
        if (input) input.value = finalText;
        this.sendCopilotMessage();
      },
      (interimText) => {
        const input = document.getElementById('copilot-chat-input');
        if (input) input.value = interimText;
      },
      (err) => { 
        console.error("STT Error:", err);
        if (err === 'no-speech' && this.isVoiceMode) {
          setTimeout(() => this.listenContinuously(), 100);
        } else {
          this.isVoiceMode = false;
          const btn = document.getElementById('banker-stt-btn');
          if (btn) btn.style.color = 'var(--text-primary)';
          App.showToast('Voice stopped: ' + (err.message || err), 'warning');
        }
      },
      () => { /* onstart */ },
      () => { /* onend */ }
    );
  },

  async sendCopilotMessage() {
    const input = document.getElementById('copilot-chat-input');
    if (!input) return;

    const text = input.value.trim();
    if (!text) return;

    input.value = '';
    this.appendCopilotMsg('user', text);

    const messages = document.getElementById('copilot-chat-messages');
    if (!messages) return;

    const thinkingEl = document.createElement('div');
    thinkingEl.className = 'msg agent pulse-active';
    thinkingEl.innerHTML = `
      <div class="msg-bubble thinking-bubble" style="background:var(--bg-surface);border:1px solid var(--border);min-width:320px;padding:15px;position:relative">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
          <div style="font-size:10px;text-transform:uppercase;color:var(--violet);letter-spacing:1px;font-weight:700">🧠 Banker Copilot Reasoning</div>
          <div class="thinking-dots" style="display:flex;gap:4px">
            <span style="width:6px;height:6px;border-radius:50%;background:var(--violet);animation:pulse 1s infinite alternate"></span>
            <span style="width:6px;height:6px;border-radius:50%;background:var(--violet);animation:pulse 1s infinite alternate;animation-delay:0.2s"></span>
            <span style="width:6px;height:6px;border-radius:50%;background:var(--violet);animation:pulse 1s infinite alternate;animation-delay:0.4s"></span>
          </div>
        </div>
        <div style="font-size:12px;color:var(--text-secondary);font-family:var(--mono)">Analyzing credentials and active queues...</div>
      </div>
      <div class="msg-meta"><span style="color:var(--violet);font-size:10px">Neural Thread Active...</span></div>`;
    messages.appendChild(thinkingEl);
    messages.scrollTop = messages.scrollHeight;

    const targetUser = document.getElementById('copilot-user-select')?.value || '';

    try {
      const response = await fetch('/api/chat/banker', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('agentToken')}`
        },
        body: JSON.stringify({
          message: text,
          userId: targetUser,
          sessionId: this.copilotSessionId
        })
      });

      thinkingEl.remove();

      if (!response.ok) {
        const errData = await response.json();
        this.appendCopilotMsg('agent', `Failed to get response: ${errData.error || response.statusText}`);
        return;
      }

      const d = await response.json();
      if (d.success && d.response) {
        const res = d.response;
        this.appendCopilotMsg('agent', res.content || 'No response details available.', res);
        
        this.loadApprovals();
        this.loadComplaints();
        this.loadAllLoans();
        this.loadAuditLog();
        if (targetUser) {
          this.onCopilotUserChange();
        }
      } else {
        this.appendCopilotMsg('agent', 'Sorry, I couldn\'t process that message.');
      }
    } catch (e) {
      if (thinkingEl) thinkingEl.remove();
      this.appendCopilotMsg('agent', `Connection error: ${e.message}`);
    }
  },

  appendCopilotMsg(role, content, meta={}) {
    const msgs = document.getElementById('copilot-chat-messages');
    if (!msgs) return;

    const welcome = msgs.querySelector('.chat-welcome');
    if (welcome && role === 'user') welcome.style.display = 'none';

    const div = document.createElement('div');
    div.className = `msg ${role==='user'?'user':'agent'}`;
    
    const formatted = this.formatCopilotContent(content);
    
    div.innerHTML = `
      <div class="msg-bubble" style="${role==='user'?'margin-left:auto;background:var(--electric);color:white;border-radius:12px 12px 0 12px':'background:var(--bg-surface);border:1px solid var(--border);border-radius:12px 12px 12px 0'}">${formatted}</div>
      <div class="msg-meta" style="display:flex;justify-content:${role==='user'?'flex-end':'flex-start'};gap:10px;font-size:10px;color:var(--text-muted);margin-top:4px">
        ${role==='user'?'👤 You':`🤖 ${meta.displayName || 'AI Copilot'}`}
        <span>·</span>
        <span>${App.formatTime(Date.now())}</span>
      </div>
    `;

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

  formatCopilotContent(text) {
    if (!text) return '';
    
    text = text.replace(/^---$/gm, '<hr style="border:0; border-top:1px solid var(--border); margin:15px 0;">');
    text = text.replace(/^### (.*$)/gm, '<h3 style="font-family:\'Space Grotesk\'; font-size:14px; font-weight:700; color:var(--electric); margin:12px 0 6px 0;">$1</h3>');

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
          newText += '<div class="transactions-table-wrap" style="margin:12px 0;"><table class="transactions-table" style="width:100%; border:1px solid var(--border); border-radius:6px; overflow:hidden;"><thead><tr>';
          cells.forEach(c => newText += `<th style="background:var(--bg-card2); color:var(--text-secondary); font-size:10px; padding:6px; text-align:left; border-bottom:1px solid var(--border);">${c}</th>`);
          newText += '</tr></thead><tbody>';
        } else {
          newText += '<tr>';
          cells.forEach(c => newText += `<td style="padding:6px; font-size:11px; border-top:1px solid var(--border); color:var(--text-secondary);">${c}</td>`);
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

    return text
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/`(.+?)`/g, `<code style="background:rgba(2,132,199,0.06); color:var(--electric); padding:2px 6px; border-radius:4px; font-family:var(--mono); font-size:11px">$1</code>`)
      .replace(/\n\n/g, '</p><p style="margin-top:8px">')
      .replace(/\n/g, '<br>');
  },

  async investigateUserInChat(userId, alertMessage) {
    const item = document.querySelector(`.nav-item[data-view="copilot"]`);
    if (item) {
      document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'));
      item.classList.add('active');
      document.querySelectorAll('.view').forEach(v=>v.classList.remove('active'));
      document.getElementById('view-copilot')?.classList.add('active');
      const titleEl = document.getElementById('page-title');
      if (titleEl) titleEl.textContent = 'AI Copilot';
      
      await this.initCopilotView();
      
      const select = document.getElementById('copilot-user-select');
      if (select) {
        select.value = userId;
        this.onCopilotUserChange();
      }
      
      const input = document.getElementById('copilot-chat-input');
      if (input) {
        input.value = `I'm investigating a security alert: "${alertMessage}". Can you analyze this user's accounts, recent transactions, and compliance records, and recommend what action to take?`;
        this.sendCopilotMessage();
      }
    }
  },

  async investigateComplaint(complaintId, userId, subject) {
    const item = document.querySelector(`.nav-item[data-view="copilot"]`);
    if (item) {
      document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'));
      item.classList.add('active');
      document.querySelectorAll('.view').forEach(v=>v.classList.remove('active'));
      document.getElementById('view-copilot')?.classList.add('active');
      const titleEl = document.getElementById('page-title');
      if (titleEl) titleEl.textContent = 'AI Copilot';
      
      await this.initCopilotView();
      
      const select = document.getElementById('copilot-user-select');
      if (select) {
        select.value = userId;
        this.onCopilotUserChange();
      }
      
      const input = document.getElementById('copilot-chat-input');
      if (input) {
        input.value = `I want to resolve complaint ${complaintId} for user ${userId}. Subject: "${subject}". Can you review this and resolve it?`;
        this.sendCopilotMessage();
      }
    }
  },

  consultCopilotForUser(userId) {
    const item = document.querySelector(`.nav-item[data-view="copilot"]`);
    if (item) {
      document.querySelectorAll('.nav-item').forEach(n=>n.classList.remove('active'));
      item.classList.add('active');
      document.querySelectorAll('.view').forEach(v=>v.classList.remove('active'));
      document.getElementById('view-copilot')?.classList.add('active');
      const titleEl = document.getElementById('page-title');
      if (titleEl) titleEl.textContent = 'AI Copilot';
      
      this.initCopilotView();
      
      const select = document.getElementById('copilot-user-select');
      if (select) {
        select.value = userId;
        this.onCopilotUserChange();
      }
      
      const input = document.getElementById('copilot-chat-input');
      if (input) {
        input.value = `Please analyze customer ${userId}'s recent standing, accounts, and any active tasks.`;
        input.focus();
      }
    }
  },
};
