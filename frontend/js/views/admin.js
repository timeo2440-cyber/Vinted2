/**
 * Admin panel view — manage users, licenses, global stats.
 * Only accessible to users with role='admin'.
 */
const adminView = (() => {
  let _inited = false;
  let _tab = 'users';

  async function init() {
    if (_inited) return;
    _inited = true;
    _renderTabs();
    await _loadTab('users');
  }

  function _renderTabs() {
    const container = document.getElementById('admin-tabs');
    if (!container) return;
    container.querySelectorAll('[data-admin-tab]').forEach(btn => {
      btn.addEventListener('click', () => {
        container.querySelectorAll('[data-admin-tab]').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        _tab = btn.dataset.adminTab;
        _loadTab(_tab);
      });
    });
  }

  async function _loadTab(tab) {
    const body = document.getElementById('admin-body');
    if (!body) return;
    body.innerHTML = '<div class="loading-spinner"></div>';
    if (tab === 'users')    await _renderUsers(body);
    if (tab === 'licenses') await _renderLicenses(body);
    if (tab === 'stats')    await _renderStats(body);
    if (tab === 'backup')   _renderBackup(body);
  }

  // ── Users ──────────────────────────────────────────────────────────────────

  async function _renderUsers(body) {
    let users;
    try { users = await api.adminGetUsers(); }
    catch (e) { body.innerHTML = `<p class="error-text">${e.message}</p>`; return; }

    const planColors = { free: '#475569', pro: '#38bdf8', unlimited: '#a78bfa' };

    body.innerHTML = `
      <div class="admin-toolbar">
        <span class="admin-count">${users.length} utilisateur${users.length !== 1 ? 's' : ''}</span>
      </div>
      <div class="table-wrap">
        <table class="data-table admin-table">
          <thead><tr>
            <th>Email</th><th>Plan</th><th>Rôle</th>
            <th>Filtres</th><th>Comptes</th><th>Achats</th>
            <th>Inscrit</th><th>Actions</th>
          </tr></thead>
          <tbody>
            ${users.map(u => `
              <tr data-user-id="${u.id}">
                <td><span class="user-email-cell">${_esc(u.email)}</span></td>
                <td>
                  <select class="plan-select input-field-xs" data-uid="${u.id}">
                    ${['free','pro','unlimited'].map(p =>
                      `<option value="${p}" ${u.plan===p?'selected':''}>${p}</option>`
                    ).join('')}
                  </select>
                </td>
                <td>
                  <select class="role-select input-field-xs" data-uid="${u.id}">
                    ${['user','admin'].map(r =>
                      `<option value="${r}" ${u.role===r?'selected':''}>${r}</option>`
                    ).join('')}
                  </select>
                </td>
                <td class="center">${u.filter_count}</td>
                <td class="center">${u.account_count}</td>
                <td class="center">${u.purchase_count}</td>
                <td class="muted">${u.created_at ? new Date(u.created_at).toLocaleDateString('fr-FR') : '—'}</td>
                <td>
                  <div class="admin-actions">
                    <button class="btn-ghost btn-xs save-user-btn" data-uid="${u.id}">Sauver</button>
                    <button class="btn-danger btn-xs del-user-btn" data-uid="${u.id}">✕</button>
                  </div>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>`;

    body.querySelectorAll('.save-user-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const uid = +btn.dataset.uid;
        const row = body.querySelector(`tr[data-user-id="${uid}"]`);
        const plan = row.querySelector('.plan-select').value;
        const role = row.querySelector('.role-select').value;
        try {
          await api.adminUpdateUser(uid, { plan, role });
          toast.show('Mis à jour', 'success');
        } catch (e) { toast.show(e.message, 'error'); }
      });
    });

    body.querySelectorAll('.del-user-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        if (!confirm('Supprimer cet utilisateur et toutes ses données ?')) return;
        try {
          await api.adminDeleteUser(+btn.dataset.uid);
          toast.show('Utilisateur supprimé', 'success');
          await _loadTab('users');
        } catch (e) { toast.show(e.message, 'error'); }
      });
    });
  }

  // ── Licenses ───────────────────────────────────────────────────────────────

  async function _renderLicenses(body) {
    let keys;
    try { keys = await api.adminGetLicenses(); }
    catch (e) { body.innerHTML = `<p class="error-text">${e.message}</p>`; return; }

    body.innerHTML = `
      <div class="admin-toolbar">
        <div class="license-gen-row">
          <select id="lic-plan" class="input-field-xs">
            <option value="pro">Pro</option>
            <option value="unlimited">Unlimited</option>
          </select>
          <select id="lic-days" class="input-field-xs">
            <option value="30">30 jours</option>
            <option value="90">90 jours</option>
            <option value="365">1 an</option>
            <option value="3650">À vie</option>
          </select>
          <button id="gen-license-btn" class="btn-primary btn-sm">Générer une clé</button>
        </div>
      </div>
      <div class="table-wrap">
        <table class="data-table admin-table">
          <thead><tr>
            <th>Clé</th><th>Plan</th><th>Durée</th><th>Utilisée par</th><th>Créée le</th><th></th>
          </tr></thead>
          <tbody>
            ${keys.length === 0 ? '<tr><td colspan="6" class="muted center">Aucune clé</td></tr>' : ''}
            ${keys.map(k => `
              <tr>
                <td><code class="license-key-cell">${k.key}</code></td>
                <td><span class="plan-badge ${k.plan}">${k.plan}</span></td>
                <td>${k.duration_days}j</td>
                <td>${k.used_by_user_id ? `User #${k.used_by_user_id}` : '<span class="muted">Disponible</span>'}</td>
                <td class="muted">${k.created_at ? new Date(k.created_at).toLocaleDateString('fr-FR') : '—'}</td>
                <td>
                  ${!k.used_by_user_id
                    ? `<button class="btn-danger btn-xs del-key-btn" data-key="${k.key}">✕</button>`
                    : ''}
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>`;

    document.getElementById('gen-license-btn').addEventListener('click', async () => {
      const plan = document.getElementById('lic-plan').value;
      const days = +document.getElementById('lic-days').value;
      try {
        const res = await api.adminCreateLicense({ plan, duration_days: days });
        toast.show(`Clé créée : ${res.key}`, 'success');
        await navigator.clipboard.writeText(res.key).catch(() => {});
        await _loadTab('licenses');
      } catch (e) { toast.show(e.message, 'error'); }
    });

    body.querySelectorAll('.del-key-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        try {
          await api.adminDeleteLicense(btn.dataset.key);
          toast.show('Clé supprimée', 'success');
          await _loadTab('licenses');
        } catch (e) { toast.show(e.message, 'error'); }
      });
    });
  }

  // ── Stats ──────────────────────────────────────────────────────────────────

  async function _renderStats(body) {
    let stats;
    try { stats = await api.adminGetStats(); }
    catch (e) { body.innerHTML = `<p class="error-text">${e.message}</p>`; return; }

    const u = stats.users;
    body.innerHTML = `
      <div class="stats-grid admin-stats-grid">
        <div class="stat-card">
          <div class="stat-icon blue"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/></svg></div>
          <div><div class="stat-value">${u.total}</div><div class="stat-label">Utilisateurs</div></div>
        </div>
        <div class="stat-card">
          <div class="stat-icon purple"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg></div>
          <div>
            <div class="stat-value">${u.pro + u.unlimited}</div>
            <div class="stat-label">Abonnés payants</div>
            <div class="muted" style="font-size:11px">Pro: ${u.pro} · Unlimited: ${u.unlimited} · Free: ${u.free}</div>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon orange"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg></div>
          <div><div class="stat-value">${stats.filters}</div><div class="stat-label">Filtres actifs</div></div>
        </div>
        <div class="stat-card">
          <div class="stat-icon green"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg></div>
          <div><div class="stat-value">${stats.purchases}</div><div class="stat-label">Achats total</div></div>
        </div>
        <div class="stat-card">
          <div class="stat-icon blue"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg></div>
          <div><div class="stat-value">${stats.seen_items.toLocaleString()}</div><div class="stat-label">Articles vus</div></div>
        </div>
        <div class="stat-card">
          <div class="stat-icon orange"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="5" y="2" width="14" height="20" rx="2"/></svg></div>
          <div><div class="stat-value">${stats.accounts}</div><div class="stat-label">Comptes Vinted</div></div>
        </div>
      </div>`;
  }

  function _renderBackup(container) {
    container.innerHTML = `
      <div style="padding:24px;max-width:500px">
        <h3 style="color:#e2e8f0;margin-bottom:16px">Sauvegarde des données</h3>
        <p style="color:#9ca3af;margin-bottom:24px;font-size:14px">
          Exporte toutes les données (utilisateurs, filtres, comptes, achats) en fichier JSON.
        </p>
        <button id="btn-export" style="background:#6c63ff;color:#fff;border:none;padding:12px 24px;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer">
          Télécharger la sauvegarde
        </button>
        <p id="backup-msg" style="color:#10b981;margin-top:12px;font-size:14px;display:none">Sauvegarde téléchargée !</p>
      </div>`;
    container.querySelector('#btn-export').addEventListener('click', async () => {
      const token = localStorage.getItem('vbot_token');
      const res = await fetch('/api/admin/backup/export', {
        headers: { 'Authorization': 'Bearer ' + token }
      });
      if (!res.ok) { alert('Erreur export'); return; }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `flashcop_backup_${new Date().toISOString().slice(0,10)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      container.querySelector('#backup-msg').style.display = 'block';
    });
  }

  function _esc(s) {
    return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  return { init };
})();
