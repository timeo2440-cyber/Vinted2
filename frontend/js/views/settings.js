const settingsView = (() => {
  function init() {
    loadSettings();
    bindEvents();
  }

  async function loadSettings() {
    try {
      const s = await api.getSettings();
      const intervalEl = document.getElementById('poll-interval');
      const maxBuyEl   = document.getElementById('max-buy-hour');
      if (intervalEl) {
        intervalEl.value = s.poll_interval_ms || 4000;
        updateIntervalLabel(s.poll_interval_ms || 4000);
      }
      if (maxBuyEl) maxBuyEl.value = s.max_buy_per_hour || 5;
    } catch {}

    // Check auth status
    try {
      const auth = await api.authStatus();
      updateAuthDetail(auth);
      store.set('authenticated', auth.authenticated);
      store.set('username', auth.username);
      updateAuthUI(auth.authenticated, auth.username);
    } catch {}
  }

  function bindEvents() {
    // Poll interval slider
    document.getElementById('poll-interval')?.addEventListener('input', e => {
      updateIntervalLabel(e.target.value);
    });

    // Validate cookies
    document.getElementById('validate-cookies-btn')?.addEventListener('click', async () => {
      const raw = document.getElementById('cookie-input').value.trim();
      if (!raw) { toast.show('Collez vos cookies Vinted d\'abord.', 'warn'); return; }
      const btn = document.getElementById('validate-cookies-btn');
      btn.disabled = true;
      btn.textContent = 'Validation…';
      try {
        const result = await api.submitCookies(raw);
        showAuthResult(result);
        if (result.authenticated) {
          store.set('authenticated', true);
          store.set('username', result.username);
          updateAuthUI(true, result.username);
          toast.show(`Connecté en tant que ${result.username || 'utilisateur'}`, 'success');
        } else {
          toast.show('Cookies invalides ou session expirée.', 'error');
        }
      } catch (e) {
        toast.show('Erreur : ' + e.message, 'error');
      } finally {
        btn.disabled = false;
        btn.textContent = 'Valider les cookies';
      }
    });

    // Check auth
    document.getElementById('check-auth-btn')?.addEventListener('click', async () => {
      try {
        const result = await api.authStatus();
        showAuthResult(result);
        updateAuthUI(result.authenticated, result.username);
      } catch (e) {
        toast.show('Erreur : ' + e.message, 'error');
      }
    });

    // Save settings
    document.getElementById('save-settings-btn')?.addEventListener('click', async () => {
      const intervalEl = document.getElementById('poll-interval');
      const maxBuyEl   = document.getElementById('max-buy-hour');
      try {
        await api.saveSettings({
          poll_interval_ms: parseInt(intervalEl?.value || 4000),
          max_buy_per_hour: parseInt(maxBuyEl?.value || 5),
        });
        toast.show('Paramètres sauvegardés.', 'success');
      } catch (e) {
        toast.show('Erreur : ' + e.message, 'error');
      }
    });
  }

  function updateIntervalLabel(ms) {
    const label = document.getElementById('poll-interval-label');
    if (!label) return;
    const sec = ms / 1000;
    label.textContent = sec % 1 === 0 ? sec + 's' : sec.toFixed(1) + 's';
  }

  function showAuthResult(auth) {
    const el = document.getElementById('auth-result');
    if (!el) return;
    el.classList.remove('hidden', 'success', 'error');
    if (auth.authenticated) {
      el.className = 'auth-result success';
      el.textContent = `Connecté en tant que : ${auth.username || 'utilisateur'}`;
    } else {
      el.className = 'auth-result error';
      el.textContent = 'Non authentifié — vérifiez vos cookies.';
    }
  }

  function updateAuthDetail(auth) {
    const el = document.getElementById('auth-status-detail');
    if (!el) return;
    if (auth.authenticated) {
      el.textContent = `Session active — ${auth.username || ''}`;
      el.style.color = 'var(--green)';
    } else {
      el.textContent = 'Aucune session active.';
      el.style.color = 'var(--text-muted)';
    }
  }

  return { init };
})();
