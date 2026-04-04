/**
 * App entry point — auth gate, routing, bot toggle, initial data load.
 */
(async function init() {

  // ── 1. Auth gate ─────────────────────────────────────────────────────────
  auth.initOverlay();

  const isAuthed = await auth.verify();
  if (!isAuthed) {
    await auth.showLoginOverlay();
  }

  // Render user menu in sidebar
  _renderUserMenu();

  // Show admin nav if admin
  if (auth.isAdmin()) {
    document.getElementById('admin-nav-link').classList.remove('hidden');
  }

  // ── 2. Router ─────────────────────────────────────────────────────────────
  const VIEWS = {
    dashboard: { el: 'view-dashboard', title: 'Dashboard',      init: () => dashboardView.init()  },
    filters:   { el: 'view-filters',   title: 'Filtres',        init: () => filtersView.init()    },
    accounts:  { el: 'view-accounts',  title: 'Comptes Vinted', init: () => accountsView.init()   },
    history:   { el: 'view-history',   title: 'Historique',     init: () => historyView.init()    },
    stats:     { el: 'view-stats',     title: 'Statistiques',   init: () => statsView.init()      },
    settings:  { el: 'view-settings',  title: 'Paramètres',    init: () => settingsView.init()   },
    admin:     { el: 'view-admin',     title: 'Administration', init: () => adminView.init()      },
  };

  const initialised = new Set();

  function navigate(viewKey) {
    const view = VIEWS[viewKey];
    if (!view) return;
    if (viewKey === 'admin' && !auth.isAdmin()) return;

    Object.values(VIEWS).forEach(v => document.getElementById(v.el)?.classList.remove('active'));
    document.getElementById(view.el)?.classList.add('active');
    document.querySelectorAll('.nav-link').forEach(link =>
      link.classList.toggle('active', link.dataset.view === viewKey)
    );
    document.getElementById('page-title').textContent = view.title;

    if (!initialised.has(viewKey)) { initialised.add(viewKey); view.init(); }

    if (viewKey === 'stats'    && initialised.has('stats'))    statsView.reload();
    if (viewKey === 'history'  && initialised.has('history'))  historyView.reload();
    if (viewKey === 'accounts' && initialised.has('accounts')) accountsView.reload();

    location.hash = viewKey;
  }

  document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', e => { e.preventDefault(); navigate(link.dataset.view); });
  });

  const hash = location.hash.replace('#', '') || 'dashboard';
  navigate(VIEWS[hash] ? hash : 'dashboard');

  // ── 3. Autocop toggle ─────────────────────────────────────────────────────
  const autocopToggle = document.getElementById('autocop-toggle');
  const autocopLabel  = document.getElementById('autocop-label');

  function updateAutocop(enabled) {
    autocopToggle.checked = enabled;
    autocopLabel.textContent = enabled ? 'Autocop ON' : 'Autocop OFF';
    autocopLabel.className = 'autocop-label ' + (enabled ? 'on' : 'off');
  }

  autocopToggle.addEventListener('change', async () => {
    const enabled = autocopToggle.checked;
    autocopToggle.disabled = true;
    try {
      await api.setAutocop(enabled);
      updateAutocop(enabled);
      toast.show(enabled ? 'Autocop activé !' : 'Autocop désactivé.', enabled ? 'success' : 'info');
    } catch (e) {
      toast.show('Erreur : ' + e.message, 'error');
      updateAutocop(!enabled);
    } finally { autocopToggle.disabled = false; }
  });

  // ── 4. Initial REST state ─────────────────────────────────────────────────
  try {
    const status = await api.botStatus();
    store.set('itemsSeen', status.items_seen || 0);
    store.set('itemsMatched', status.items_matched || 0);
    document.getElementById('stat-seen').textContent    = status.items_seen    || 0;
    document.getElementById('stat-matched').textContent = status.items_matched || 0;
    updateAutocop(status.autocop_enabled || false);
  } catch {}

  try {
    const filters = await api.getFilters();
    store.set('filters', filters);
    const active = filters.filter(f => f.enabled).length;
    const badge = document.getElementById('filter-badge');
    if (badge && active > 0) { badge.textContent = active; badge.classList.remove('hidden'); }
  } catch {}

  try {
    const accounts = await api.getAccounts();
    const badge = document.getElementById('accounts-badge');
    if (badge && accounts.length > 0) { badge.textContent = accounts.length; badge.classList.remove('hidden'); }
  } catch {}

  try {
    const logs = await api.getLogs();
    logs.reverse().forEach(log => activityLog.append(log.level, log.message, log.category));
  } catch {}

  // ── 5. WebSocket ──────────────────────────────────────────────────────────
  wsClient.connect();
  wsClient.initSoundToggle();

  // ── 6. Items/min rate ─────────────────────────────────────────────────────
  let _rateLastCount = store.get('itemsSeen') || 0;
  let _rateLastTime  = Date.now();
  setInterval(() => {
    const elapsed = (Date.now() - _rateLastTime) / 60000;
    const current = store.get('itemsSeen') || 0;
    const rate = elapsed > 0 ? Math.round((current - _rateLastCount) / elapsed) : 0;
    const el = document.getElementById('stat-rate');
    if (el) el.textContent = rate;
    _rateLastCount = current;
    _rateLastTime  = Date.now();
  }, 30000);

  document.addEventListener('keydown', e => { if (e.key === 'Escape') modal.close(); });

  // ── Diagnostic global ─────────────────────────────────────────────────────
  window.diagTest = async function() {
    try {
      // 1. Check diagnostic stats
      const stats = await fetch('/api/bot/seen-count', {
        headers: { 'Authorization': 'Bearer ' + auth.getToken() }
      }).then(r => r.json());

      // 2. Send WS ping test
      const ping = await fetch('/api/bot/ping-ws', {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + auth.getToken() }
      }).then(r => r.json());

      const lines = [
        `<b>Diagnostic Flashcop</b>`,
        ``,
        `Articles scannés en DB : <b>${stats.seen_items_in_db}</b>`,
        `Articles vus cette session : <b>${stats.items_seen_this_session}</b>`,
        `Correspondances cette session : <b>${stats.items_matched_this_session}</b>`,
        `Bot actif : <b>${stats.bot_running ? '✓ OUI' : '✗ NON'}</b>`,
        ``,
        `Connexions WS totales : <b>${stats.ws_connections_total}</b>`,
        `Connexions WS pour toi : <b>${stats.ws_connections_for_you}</b>`,
        ``,
        ping.ws_connections > 0
          ? `<span style="color:#10b981">✓ WS OK — un article test a été envoyé, vérifie le feed !</span>`
          : `<span style="color:#f87171">✗ WS non authentifié — déconnecte-toi et reconnecte-toi</span>`,
      ];

      modal.open('Diagnostic', `<div style="font-size:14px;line-height:2;font-family:monospace">${lines.join('<br>')}</div>`);
    } catch(e) {
      toast.show('Erreur diagnostic : ' + e.message, 'error');
    }
  };

  // ── Helpers ───────────────────────────────────────────────────────────────
  function _renderUserMenu() {
    const user = auth.getUser();
    if (!user) return;
    const slot = document.getElementById('user-menu-slot');
    if (!slot) return;
    const initial = (user.email[0] || '?').toUpperCase();
    const planColors = { free: '#475569', pro: '#38bdf8', unlimited: '#a78bfa' };
    slot.innerHTML = `
      <div class="user-menu">
        <div class="user-avatar">${initial}</div>
        <div class="user-info">
          <div class="user-email">${user.email}</div>
          <div class="user-plan" style="color:${planColors[user.plan]||'#475569'}">${user.plan.toUpperCase()}</div>
        </div>
        <button class="user-logout" id="logout-btn" title="Déconnexion">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
        </button>
      </div>`;
    document.getElementById('logout-btn').addEventListener('click', () => {
      if (confirm('Se déconnecter ?')) auth.logout();
    });
  }
})();
