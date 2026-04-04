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

      const plans = [
        { key: 'starter', label: 'Starter', price: '10€/mois', accounts: 2,  filters: 5,  autocop: false, color: '#38bdf8' },
        { key: 'pro',     label: 'Pro',     price: '30€/mois', accounts: 5,  filters: 15, autocop: false, color: '#a78bfa' },
        { key: 'premium', label: 'Premium', price: '80€/mois', accounts: 20, filters: 50, autocop: true,  color: '#f59e0b' },
      ];

      const planColors = { free: '#64748b', starter: '#38bdf8', pro: '#a78bfa', premium: '#f59e0b', unlimited: '#10b981' };
      const color = planColors[user.plan] || '#64748b';
      const limits = user.limits || {};

      planEl.innerHTML = `
        <div style="margin-bottom:20px">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
            <span class="plan-badge ${user.plan}" style="background:${color}20;color:${color};padding:4px 12px;border-radius:20px;font-size:12px;font-weight:700;border:1px solid ${color}40">
              ${user.plan.toUpperCase()}
            </span>
            ${user.plan_expires_at
              ? `<span style="font-size:12px;color:#64748b">expire le ${new Date(user.plan_expires_at).toLocaleDateString('fr-FR')}</span>`
              : ''}
          </div>
          <ul style="font-size:13px;color:#94a3b8;list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:4px">
            <li>✓ ${limits.max_accounts ?? '?'} compte${(limits.max_accounts||0) !== 1 ? 's' : ''} Vinted</li>
            <li>✓ ${limits.max_filters ?? '?'} filtre${(limits.max_filters||0) !== 1 ? 's' : ''}</li>
            <li>${limits.auto_buy ? '✓ Autocop activé' : '✗ Autocop non disponible'}</li>
          </ul>
        </div>

        <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:16px">
          ${plans.map(p => {
            const isCurrent = user.plan === p.key;
            return `<div style="background:${isCurrent ? p.color+'20' : '#0f1117'};border:2px solid ${isCurrent ? p.color : '#2a2d3e'};border-radius:12px;padding:16px;text-align:center;position:relative">
              ${isCurrent ? `<div style="position:absolute;top:-10px;left:50%;transform:translateX(-50%);background:${p.color};color:#000;font-size:10px;font-weight:700;padding:2px 10px;border-radius:20px">ACTUEL</div>` : ''}
              <div style="color:${p.color};font-weight:700;font-size:15px;margin-bottom:4px">${p.label}</div>
              <div style="color:#e2e8f0;font-size:20px;font-weight:800;margin-bottom:8px">${p.price}</div>
              <ul style="list-style:none;padding:0;margin:0;font-size:12px;color:#94a3b8;text-align:left">
                <li>✓ ${p.accounts} comptes Vinted</li>
                <li>✓ ${p.filters} filtres</li>
                <li>${p.autocop ? '✓ <b style="color:#10b981">Autocop</b>' : '✗ Pas d\'autocop'}</li>
              </ul>
            </div>`;
          }).join('')}
        </div>`;
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
