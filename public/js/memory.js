// AgenticBank AI — Memory Inspector Module (4-Type Memory Visualization)
const Memory = {
  activeTab: 'working',
  data: null,

  init() {
    this.setupTabs();
    App.on('userChanged', u => this.loadMemory(u.id));
  },

  setupTabs() {
    document.querySelectorAll('.mem-tab').forEach(tab => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('.mem-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        this.activeTab = tab.dataset.tab;
        this.render();
      });
    });
  },

  async loadMemory(uid) {
    if (!uid) return;
    try {
      const r = await fetch(`/api/banking/memory/${uid}`);
      const d = await r.json();
      this.data = d.memory;
      this.render();
      this.updateMetrics();
    } catch(e) {}
  },

  render() {
    if (!this.data) return;
    const viewer = document.getElementById('memory-viewer');
    if (!viewer) return;
    switch(this.activeTab) {
      case 'working': viewer.innerHTML = this.renderWorking(); break;
      case 'semantic': viewer.innerHTML = this.renderSemantic(); break;
      case 'episodic': viewer.innerHTML = this.renderEpisodic(); break;
      case 'procedural': viewer.innerHTML = this.renderProcedural(); break;
    }
    this.updateCount();
  },

  renderWorking() {
    const w = this.data.working || {};
    const load = w.cognitiveLoad || 5;
    return `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px">
        <div class="memory-item"><div class="meta">ACTIVE INTENT</div><div class="content"><strong>${w.intent||'IDLE'}</strong></div></div>
        <div class="memory-item"><div class="meta">ACTIVE AGENT</div><div class="content">${w.activeAgent||'—'}</div></div>
        <div class="memory-item"><div class="meta">LAST QUERY</div><div class="content">${(w.lastQuery||'—').substring(0,80)}</div></div>
        <div class="memory-item"><div class="meta">SESSION LOAD</div>
          <div class="content"><strong style="color:${load>60?'var(--danger)':load>30?'var(--amber)':'var(--neon)'}">${load}%</strong>
          <div class="cognitive-bar-wrap" style="margin-top:6px"><div class="cognitive-bar" style="width:${load}%;background:${load>60?'var(--danger)':load>30?'var(--amber)':'linear-gradient(90deg,var(--electric),var(--neon))'}"></div></div></div></div>
      </div>
      <div class="memory-item"><div class="meta">LAST UPDATED</div><div class="content" style="font-family:var(--mono)">${w.lastUpdated?App.formatTime(w.lastUpdated):'—'}</div></div>`;
  },

  renderSemantic() {
    const s = this.data.semantic || {};
    if (!Object.keys(s).length) return '<div class="empty-state" style="padding:30px"><div class="empty-icon">🧠</div><p>No semantic facts yet. Use the AI assistant to populate.</p></div>';
    return Object.entries(s).map(([key,fact]) => `
      <div class="memory-item">
        <div class="meta"><span>CERTAINTY: ${((fact.certainty||1)*100).toFixed(0)}%</span><span>UPDATED: ${fact.updated||'—'}</span></div>
        <div class="content"><strong>${key}:</strong> ${JSON.stringify(fact.value)}</div>
      </div>`).join('');
  },

  renderEpisodic() {
    const eps = (this.data.episodic || []).slice(0,20);
    if (!eps.length) return '<div class="empty-state" style="padding:30px"><div class="empty-icon">📖</div><p>No episodic memories yet.</p></div>';
    return eps.map(ep => `
      <div class="memory-item episodic-item ${ep.valence||'neutral'}">
        <div class="meta">
          <span>IMPORTANCE: ${ep.importance||5}/10</span>
          <span style="color:${ep.valence==='positive'?'var(--neon)':ep.valence==='negative'?'var(--danger)':'var(--text-muted)'}">${(ep.valence||'neutral').toUpperCase()}</span>
        </div>
        <div class="content"><strong style="font-family:var(--mono);font-size:11px">${App.formatTime(ep.timestamp)}:</strong> ${ep.event}</div>
      </div>`).join('');
  },

  renderProcedural() {
    const p = this.data.procedural || {};
    const progress = p.totalSteps > 0 ? (p.step/p.totalSteps)*100 : 0;
    const history = (p.history||[]).slice(-5).reverse();
    return `
      <div class="memory-item" style="margin-bottom:16px">
        <div class="meta">CURRENT WORKFLOW</div>
        <div class="content"><strong style="color:${p.currentWorkflow!=='IDLE'?'var(--amber)':'var(--neon)'}">${p.currentWorkflow||'IDLE'}</strong></div>
        ${p.totalSteps>0?`<div style="margin-top:10px"><div style="font-size:11px;color:var(--text-muted);margin-bottom:4px">Step ${p.step}/${p.totalSteps}</div><div class="cognitive-bar-wrap"><div class="cognitive-bar" style="width:${progress}%"></div></div></div>`:''}
      </div>
      ${history.length?`<div class="meta" style="padding:4px 0 10px;font-size:10px;text-transform:uppercase;letter-spacing:1px;color:var(--text-muted)">Workflow History</div>`:''}
      ${history.map(h=>`<div class="memory-item"><div class="meta"><span>${h.workflow}</span><span style="color:${h.outcome==='completed'?'var(--neon)':'var(--amber)'}">${(h.outcome||'').toUpperCase()}</span></div><div class="content" style="font-family:var(--mono);font-size:11px">${h.completedAt?App.formatTime(h.completedAt):'—'}</div></div>`).join('')}`;
  },

  updateCount() {
    const countEl = document.getElementById('memory-count');
    if (!countEl || !this.data) return;
    const counts = { working: Object.keys(this.data.working||{}).length, semantic: Object.keys(this.data.semantic||{}).length, episodic: (this.data.episodic||[]).length, procedural: (this.data.procedural?.history||[]).length };
    countEl.textContent = counts[this.activeTab] || 0;
  },

  updateMetrics() {
    if (!this.data) return;
    const stats = this.data.stats || {};
    const semCount = document.getElementById('semantic-count');
    const epCount = document.getElementById('episodic-count');
    const wfCount = document.getElementById('workflow-count');
    if (semCount) semCount.textContent = stats.semanticCount || 0;
    if (epCount) epCount.textContent = stats.episodicCount || 0;
    if (wfCount) wfCount.textContent = stats.workflowsCompleted || 0;
  },

  onUpdate(data) {
    if (App.currentUser && data.userId === App.currentUser.id) {
      this.loadMemory(App.currentUser.id);
    }
  },
};
