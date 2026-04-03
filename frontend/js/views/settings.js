const settingsView = (() => {
  function init() {
    loadSettings();
    loadPlanInfo();
    bindEvents();
  }

  async function loadSettings() {
    try {
      const s = await api.getSettings();
      const maxBuyEl = document.getElementById('max-buy-hour');
      if (maxBuyEl) maxBuyEl.value = s.max_buy_per_hour || 5;
    } catch {}
  }

  async function loadPlanInfo() {
    try {
      const user = auth.getUser();
      if (!user) return;
      const planEl = document.getElementById('plan-info');
      if (!planEl) return;
      const planColors = { free: '#64748b', pro: '#38bdf8', unlimited: '#a78bfa' };
      const color = planColors[user.plan] || '#64748b';
      const limits = user.limits || {};
      planEl.innerHTML = `
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
          <span class="plan-badge ${user.plan}">${user.plan.toUpperCase()}</span>
          ${user.plan_expires_at
            ? `<span style="font-size:12px;color:#64748b">expire le ${new Date(user.plan_expires_at).toLocaleDateString('fr-FR')}</span>`
            : ''}
        </div>
        <ul style="font-size:13px;color:#94a3b8;list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:4px">
          <li>✓ ${limits.max_accounts ?? '?'} compte${limits.max_accounts !== 1 ? 's' : ''} Vinted</li>
          <li>✓ ${limits.max_filters ?? '?'} filtre${limits.max_filters !== 1 ? 's' : ''}</li>
          <li>${limits.auto_buy ? '✓ Autocop activé' : '✗ Autocop désactivé (plan Free)'}</li>
        </ul>`;
    } catch {}
  }

  function bindEvents() {
    // Validate cookies
    document.getElementById('validate-cookies-btn')?.addEventListener('click', async () => {
      const raw = document.getElementById('cookie-input').value.trim();
      if (!raw) { toast.show('Collez vos cookies Vinted d\'abord.', 'warn'); return; }
      const btn = document.getElementById('validate-cookies-btn');
      btn.disabled = true; btn.textContent = 'Validation…';
      try {
        const result = await api.submitCookies(raw);
        if (result.authenticated) {
          toast.show(`Session Vinted validée — ${result.username || ''}`, 'success');
        } else {
          toast.show('Cookies invalides ou session expirée.', 'error');
        }
      } catch (e) {
        toast.show('Erreur : ' + e.message, 'error');
      } finally {
        btn.disabled = false; btn.textContent = 'Valider les cookies';
      }
    });

    // Check auth
    document.getElementById('check-auth-btn')?.addEventListener('click', async () => {
      try {
        const result = await api.authStatus();
        toast.show(
          result.authenticated ? `Session active — ${result.username || ''}` : 'Aucune session active.',
          result.authenticated ? 'success' : 'warn'
        );
      } catch (e) { toast.show('Erreur : ' + e.message, 'error'); }
    });

    // Save settings
    document.getElementById('save-settings-btn')?.addEventListener('click', async () => {
      const maxBuyEl = document.getElementById('max-buy-hour');
      try {
        await api.saveSettings({ max_buy_per_hour: parseInt(maxBuyEl?.value || 5) });
        toast.show('Paramètres sauvegardés.', 'success');
      } catch (e) { toast.show('Erreur : ' + e.message, 'error'); }
    });

    // Activate license
    document.getElementById('activate-license-btn')?.addEventListener('click', async () => {
      const key = document.getElementById('license-key-input').value.trim();
      if (!key) { toast.show('Entrez votre clé de licence.', 'warn'); return; }
      try {
        const res = await api.activateLicense(key);
        toast.show(`Plan activé : ${res.plan.toUpperCase()} — expire le ${new Date(res.expires_at).toLocaleDateString('fr-FR')}`, 'success');
        document.getElementById('license-key-input').value = '';
        // Refresh user info
        const me = await api.me();
        auth.save(auth.getToken(), me);
        await loadPlanInfo();
      } catch (e) { toast.show('Erreur : ' + e.message, 'error'); }
    });

    // Change password
    document.getElementById('change-pw-btn')?.addEventListener('click', async () => {
      const old_pw = document.getElementById('old-pw').value;
      const new_pw = document.getElementById('new-pw').value;
      if (!old_pw || !new_pw) { toast.show('Remplissez les deux champs.', 'warn'); return; }
      try {
        await api.changePassword(old_pw, new_pw);
        toast.show('Mot de passe mis à jour.', 'success');
        document.getElementById('old-pw').value = '';
        document.getElementById('new-pw').value = '';
      } catch (e) { toast.show('Erreur : ' + e.message, 'error'); }
    });
  }

  return { init };
})();
