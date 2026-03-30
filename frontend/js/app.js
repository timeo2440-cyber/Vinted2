/**
 * App entry point — routing, bot toggle, initial data load.
 */
(async function init() {
  // ── Router ──────────────────────────────────────────────────────────────
  const VIEWS = {
    dashboard: { el: 'view-dashboard', title: 'Dashboard',       init: () => dashboardView.init() },
    filters:   { el: 'view-filters',   title: 'Filtres',         init: () => filtersView.init()   },
    history:   { el: 'view-history',   title: 'Historique',      init: () => historyView.init()   },
    stats:     { el: 'view-stats',     title: 'Statistiques',    init: () => statsView.init()     },
    settings:  { el: 'view-settings',  title: 'Paramètres',      init: () => settingsView.init()  },
  };

  const initialised = new Set();

  function navigate(viewKey) {
    const view = VIEWS[viewKey];
    if (!view) return;

    // Hide all views
    Object.values(VIEWS).forEach(v => {
      document.getElementById(v.el)?.classList.remove('active');
    });

    // Show target
    document.getElementById(view.el)?.classList.add('active');

    // Update nav links
    document.querySelectorAll('.nav-link').forEach(link => {
      link.classList.toggle('active', link.dataset.view === viewKey);
    });

    // Update page title
    document.getElementById('page-title').textContent = view.title;

    // Init once
    if (!initialised.has(viewKey)) {
      initialised.add(viewKey);
      view.init();
    }

    // Reload stats/history when navigating to them
    if (viewKey === 'stats' && initialised.has('stats'))    statsView.reload();
    if (viewKey === 'history' && initialised.has('history')) historyView.reload();

    location.hash = viewKey;
  }

  // Nav click handlers
  document.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', e => {
      e.preventDefault();
      navigate(link.dataset.view);
    });
  });

  // Hash-based routing on load
  const hash = location.hash.replace('#', '') || 'dashboard';
  navigate(VIEWS[hash] ? hash : 'dashboard');

  // ── Bot toggle ───────────────────────────────────────────────────────────
  const botToggle = document.getElementById('bot-toggle');
  const botLabel  = document.getElementById('bot-status-label');

  botToggle.addEventListener('change', async () => {
    botToggle.disabled = true;
    botLabel.textContent = '…';
    botLabel.className = 'bot-label loading';
    try {
      if (botToggle.checked) {
        await api.botStart();
      } else {
        await api.botStop();
      }
    } catch (e) {
      toast.show('Erreur bot : ' + e.message, 'error');
      botToggle.checked = !botToggle.checked;
      updateBotUI(botToggle.checked);
    } finally {
      botToggle.disabled = false;
    }
  });

  // ── Initial state from REST ──────────────────────────────────────────────
  try {
    const status = await api.botStatus();
    store.set('botRunning', status.running);
    store.set('itemsSeen', status.items_seen || 0);
    store.set('itemsMatched', status.items_matched || 0);
    document.getElementById('stat-seen').textContent    = status.items_seen    || 0;
    document.getElementById('stat-matched').textContent = status.items_matched || 0;
    updateBotUI(status.running);
    updateAuthUI(status.authenticated, status.username);
    store.set('authenticated', status.authenticated);
    store.set('username', status.username);
  } catch {}

  // Load filters for badge
  try {
    const filters = await api.getFilters();
    store.set('filters', filters);
    const active = filters.filter(f => f.enabled).length;
    const badge = document.getElementById('filter-badge');
    if (badge && active > 0) {
      badge.textContent = active;
      badge.classList.remove('hidden');
    }
  } catch {}

  // Load recent logs into activity log panel
  try {
    const logs = await api.getLogs();
    logs.reverse().forEach(log => {
      activityLog.append(log.level, log.message, log.category);
    });
  } catch {}

  // ── Connect WebSocket ────────────────────────────────────────────────────
  wsClient.connect();

  // ── Keyboard shortcut: Escape closes modal ───────────────────────────────
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') modal.close();
  });
})();
