/**
 * Accounts view — manage multiple Vinted accounts.
 */
const accountsView = (() => {
  let _accounts = [];
  let _inited = false;

  async function init() {
    if (_inited) return;
    _inited = true;
    document.getElementById('add-account-btn').addEventListener('click', _openAddModal);
    await reload();
  }

  async function reload() {
    try {
      _accounts = await api.getAccounts();
      _renderCards();
    } catch (e) {
      toast.show('Erreur chargement comptes : ' + e.message, 'error');
    }
  }

  function _renderCards() {
    const list   = document.getElementById('accounts-list');
    const empty  = document.getElementById('accounts-empty');
    if (!_accounts.length) {
      list.innerHTML = '';
      empty.classList.remove('hidden');
      return;
    }
    empty.classList.add('hidden');
    list.innerHTML = _accounts.map(_buildCard).join('');

    list.querySelectorAll('[data-action]').forEach(el => {
      el.addEventListener('change', e => {
        if (el.dataset.action === 'toggle') _toggleActive(+el.dataset.id, el.checked);
      });
      el.addEventListener('click', e => {
        const { action, id } = el.dataset;
        if (action === 'delete')   _deleteAccount(+id);
        if (action === 'relogin')  _reloginAccount(+id);
        if (action === 'edit')     _openEditModal(+id);
        if (action === 'verify')   _verifyAccount(+id, el);
      });
    });
  }

  function _statusBadge(is_authenticated) {
    if (is_authenticated === true)  return ['connected', 'Connecté'];
    if (is_authenticated === false) return ['expired',   'Expiré'];
    return ['unknown', 'Non vérifié'];
  }

  function _buildCard(a) {
    const initial = ((a.vinted_username || a.name || a.email)[0] || '?').toUpperCase();
    const [statusCls, statusLabel] = _statusBadge(a.is_authenticated);
    const inactiveCls = !a.is_active ? 'inactive' : '';
    const bannedBadge = a.ban_suspected ? '<span class="account-ban-badge">⚠ Suspecté banni</span>' : '';
    const lastLogin   = a.last_login
      ? new Date(a.last_login).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' })
      : 'Jamais';

    return `
    <div class="account-card ${inactiveCls}" data-id="${a.id}">
      <div class="account-avatar" style="background:${_avatarColor(a.email)}">${_esc(initial)}</div>
      <div class="account-info">
        <div class="account-name">${_esc(a.vinted_username || a.name)}</div>
        <div class="account-email">${_esc(a.email)}</div>
        <div class="account-meta">
          <span class="account-status ${statusCls}" id="status-badge-${a.id}">${statusLabel}</span>
          <button class="btn-verify btn-xs" data-action="verify" data-id="${a.id}" title="Vérifier la connexion">✓ Vérifier</button>
          <span class="account-purchases">${a.purchases_count} achat${a.purchases_count !== 1 ? 's' : ''}</span>
          <span class="account-lastlogin">Dernier login : ${lastLogin}</span>
        </div>
        ${bannedBadge}
      </div>
      <div class="account-actions">
        <label class="toggle-switch" title="Activer / D\u00e9sactiver">
          <input type="checkbox" data-action="toggle" data-id="${a.id}" ${a.is_active ? 'checked' : ''}>
          <span class="slider"></span>
        </label>
        <button class="btn-ghost btn-xs" data-action="relogin" data-id="${a.id}" title="Re-connecter">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13"><path d="M23 4v6h-6"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
        </button>
        <button class="btn-ghost btn-xs" data-action="edit" data-id="${a.id}" title="Modifier">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
        </button>
        <button class="btn-danger btn-xs" data-action="delete" data-id="${a.id}" title="Supprimer">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/></svg>
        </button>
      </div>
    </div>`;
  }

  // ── Add account modal ──────────────────────────────────────────────────────
  function _openAddModal() {
    const body = document.createElement('div');
    body.innerHTML = `
      <div class="form-group">
        <label>Email Vinted *</label>
        <input type="email" id="af-email" class="input-field" placeholder="votre@email.com">
      </div>
      <div class="form-group">
        <label>Mot de passe *</label>
        <input type="password" id="af-password" class="input-field" placeholder="\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022">
      </div>
      <div class="form-group">
        <label>Nom du compte (optionnel)</label>
        <input type="text" id="af-name" class="input-field" placeholder="Ex: Compte principal">
      </div>
      <p class="help-text" style="margin-top:8px">Si la connexion automatique échoue, le compte sera quand même sauvegardé et vous pourrez entrer vos cookies manuellement.</p>
      <div id="af-result" class="auth-result hidden" style="margin:10px 0"></div>
      <div class="form-footer">
        <button class="btn-ghost" id="af-cancel">Annuler</button>
        <button class="btn-primary" id="af-submit">Se connecter</button>
      </div>`;

    modal.open('Ajouter un compte Vinted', body);

    document.getElementById('af-cancel').onclick = () => modal.close();
    document.getElementById('af-submit').onclick  = async () => {
      const email    = document.getElementById('af-email').value.trim();
      const password = document.getElementById('af-password').value;
      const name     = document.getElementById('af-name').value.trim();
      const resultEl = document.getElementById('af-result');

      if (!email || !password) { toast.show('Email et mot de passe requis', 'warn'); return; }

      const btn = document.getElementById('af-submit');
      btn.disabled = true;
      btn.textContent = 'Connexion...';
      resultEl.className = 'auth-result hidden';

      try {
        const account = await api.createAccount({ email, password, name: name || undefined });
        if (account.login_error) {
          resultEl.className = 'auth-result warn';
          resultEl.textContent = '⚠ ' + account.login_error + ' — Compte sauvegardé, entrez les cookies manuellement.';
          resultEl.classList.remove('hidden');
          btn.disabled = false;
          btn.textContent = 'Se connecter';
        } else {
          toast.show('Compte connecté : ' + (account.vinted_username || account.email), 'success');
          modal.close();
        }
        await reload();
      } catch (e) {
        resultEl.className = 'auth-result error';
        resultEl.textContent = 'Erreur : ' + e.message;
        resultEl.classList.remove('hidden');
        btn.disabled = false;
        btn.textContent = 'Se connecter';
      }
    };
  }

  // ── Edit modal ─────────────────────────────────────────────────────────────
  function _openEditModal(id) {
    const a = _accounts.find(x => x.id === id);
    if (!a) return;

    const addr = a.default_address || {};
    const pickups = (a.preferred_pickup_points || []).join('\n');
    const card = a.payment_card || {};

    const body = document.createElement('div');
    body.innerHTML = `
      <div class="form-group">
        <label>Nom du compte</label>
        <input type="text" id="ef-name" class="input-field" value="${_esc(a.name)}">
      </div>

      <div class="form-group">
        <label>Numéro de téléphone</label>
        <input type="tel" id="ef-phone" class="input-field" placeholder="+33 6 12 34 56 78" value="${_esc(a.phone_number || '')}">
        <small>Utilisé pour le suivi des colis.</small>
      </div>

      <div class="form-group">
        <label>Carte bancaire</label>
        <input type="text" id="ef-card-number" class="input-field" placeholder="1234 5678 9012 3456" value="${_esc(card.number || '')}" style="margin-bottom:6px" maxlength="19">
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px">
          <input type="text" id="ef-card-expiry" class="input-field" placeholder="MM/AA" value="${_esc(card.expiry || '')}" maxlength="5">
          <input type="text" id="ef-card-cvv" class="input-field" placeholder="CVV" value="${_esc(card.cvv || '')}" maxlength="4">
          <input type="text" id="ef-card-holder" class="input-field" placeholder="Titulaire" value="${_esc(card.holder || '')}">
        </div>
        <small>Stockée localement, utilisée pour les achats automatiques.</small>
      </div>

      <div class="form-group">
        <label>Adresse de livraison par défaut</label>
        <input type="text" id="ef-street" class="input-field" placeholder="Rue et numéro" value="${_esc(addr.street || '')}" style="margin-bottom:6px">
        <div style="display:grid;grid-template-columns:1fr 2fr;gap:6px">
          <input type="text" id="ef-zip" class="input-field" placeholder="Code postal" value="${_esc(addr.zip || '')}">
          <input type="text" id="ef-city" class="input-field" placeholder="Ville" value="${_esc(addr.city || '')}">
        </div>
        <input type="text" id="ef-country" class="input-field" placeholder="Pays (ex: France)" value="${_esc(addr.country || '')}" style="margin-top:6px">
      </div>

      <div class="form-group">
        <label>Points relais préférés</label>
        <textarea id="ef-pickups" class="cookie-textarea" rows="3" placeholder="Un point relais par ligne\nEx: Relay Point Paris 11 - 15 rue de la Roquette">${_esc(pickups)}</textarea>
        <small>Un par ligne. Le bot choisira automatiquement parmi ces points.</small>
      </div>

      <div class="form-group">
        <div class="switch-row">
          <div><div class="switch-row-label">Compte actif</div><div class="switch-row-desc">Le bot utilisera ce compte pour les achats</div></div>
          <label class="toggle-switch"><input type="checkbox" id="ef-active" ${a.is_active ? 'checked' : ''}><span class="slider"></span></label>
        </div>
      </div>

      <div class="form-group">
        <div class="switch-row">
          <div><div class="switch-row-label">Compte suspecté banni</div><div class="switch-row-desc">Exclut ce compte des achats automatiques</div></div>
          <label class="toggle-switch"><input type="checkbox" id="ef-banned" ${a.ban_suspected ? 'checked' : ''}><span class="slider"></span></label>
        </div>
      </div>

      <div class="form-footer">
        <button class="btn-ghost" id="ef-cancel">Annuler</button>
        <button class="btn-primary" id="ef-save">Enregistrer</button>
      </div>`;

    modal.open('Modifier le compte', body);

    document.getElementById('ef-cancel').onclick = () => modal.close();
    document.getElementById('ef-save').onclick = async () => {
      const name       = document.getElementById('ef-name').value.trim();
      const phone      = document.getElementById('ef-phone').value.trim();
      const cardNumber = document.getElementById('ef-card-number').value.replace(/\s/g, '').trim();
      const cardExpiry = document.getElementById('ef-card-expiry').value.trim();
      const cardCvv    = document.getElementById('ef-card-cvv').value.trim();
      const cardHolder = document.getElementById('ef-card-holder').value.trim();
      const street     = document.getElementById('ef-street').value.trim();
      const zip        = document.getElementById('ef-zip').value.trim();
      const city       = document.getElementById('ef-city').value.trim();
      const country    = document.getElementById('ef-country').value.trim();
      const active     = document.getElementById('ef-active').checked;
      const banned     = document.getElementById('ef-banned').checked;
      const pickupsRaw = document.getElementById('ef-pickups').value;
      const pickups    = pickupsRaw.split('\n').map(s => s.trim()).filter(Boolean);

      const default_address = (street || city || zip)
        ? { street, zip, city, country }
        : null;

      const payment_card = cardNumber
        ? { number: cardNumber, expiry: cardExpiry, cvv: cardCvv, holder: cardHolder }
        : null;

      try {
        await api.updateAccount(id, {
          name: name || undefined,
          phone_number: phone || null,
          payment_card,
          is_active: active,
          ban_suspected: banned,
          default_address,
          preferred_pickup_points: pickups.length ? pickups : [],
        });
        toast.show('Compte mis à jour', 'success');
        modal.close();
        await reload();
      } catch (e) {
        toast.show('Erreur : ' + e.message, 'error');
      }
    };
  }

  // ── Cookies modal ──────────────────────────────────────────────────────────
  function _openCookiesModal(id) {
    const a = _accounts.find(x => x.id === id);
    if (!a) return;

    const body = document.createElement('div');
    body.innerHTML = `
      <p class="help-text">Copiez vos cookies depuis les outils de développement (F12 → Réseau → En-têtes → Cookie) et collez-les ci-dessous.</p>
      <textarea id="ck-input" class="cookie-textarea" placeholder="_vinted_fr_session=...; auth_t=..."></textarea>
      <div class="form-footer">
        <button class="btn-ghost" id="ck-cancel">Annuler</button>
        <button class="btn-primary" id="ck-save">Valider les cookies</button>
      </div>`;

    modal.open('Cookies manuels — ' + _esc(a.email), body);

    document.getElementById('ck-cancel').onclick = () => modal.close();
    document.getElementById('ck-save').onclick = async () => {
      const cookies = document.getElementById('ck-input').value.trim();
      if (!cookies) { toast.show('Collez vos cookies', 'warn'); return; }
      try {
        const result = await api.setAccountCookies(id, cookies);
        const msg = result.is_authenticated
          ? `✅ Connecté — ${result.vinted_username || result.email}`
          : result.validation_reason === 'network_error'
            ? '⚠ Cookies sauvegardés — impossible de vérifier (réseau). Cliquez "Vérifier" plus tard.'
            : '❌ Cookies invalides — session expirée sur Vinted';
        toast.show(msg, result.is_authenticated ? 'success' : result.validation_reason === 'network_error' ? 'warn' : 'error');
        modal.close();
        await reload();
      } catch (e) {
        toast.show('Erreur : ' + e.message, 'error');
      }
    };
  }

  // ── Actions ────────────────────────────────────────────────────────────────
  async function _toggleActive(id, active) {
    try {
      await api.updateAccount(id, { is_active: active });
      const a = _accounts.find(x => x.id === id);
      if (a) a.is_active = active;
      _renderCards();
    } catch (e) {
      toast.show('Erreur : ' + e.message, 'error');
    }
  }

  async function _reloginAccount(id) {
    const a = _accounts.find(x => x.id === id);
    if (!a) return;
    toast.show('Reconnexion en cours...', 'info');
    try {
      const result = await api.reloginAccount(id);
      if (result.error) {
        toast.show('Échec : ' + result.error, 'error');
        _openCookiesModal(id);
      } else {
        toast.show('Reconnecté : ' + (result.vinted_username || result.email), 'success');
      }
      await reload();
    } catch (e) {
      toast.show('Erreur : ' + e.message, 'error');
    }
  }

  async function _verifyAccount(id, btn) {
    const badge = document.getElementById(`status-badge-${id}`);
    if (badge) { badge.className = 'account-status verifying'; badge.textContent = 'Vérification…'; }
    if (btn) { btn.disabled = true; }
    try {
      const result = await api.checkAccountStatus(id);
      const auth = result.authenticated;
      const [cls, label] = auth === true  ? ['connected', 'Connecté']
                         : auth === false ? ['expired',   'Expiré']
                         :                  ['unknown',   'Non vérifié'];
      if (badge) { badge.className = `account-status ${cls}`; badge.textContent = label; }
      const msg = auth === true  ? `Compte connecté — ${result.username || ''}`.trim()
                : auth === false ? 'Session expirée — recollez vos cookies'
                :                  'Impossible de vérifier (réseau). Cookies conservés.';
      toast.show(msg, auth === true ? 'success' : auth === false ? 'error' : 'warn');
      if (auth !== null) await reload();
    } catch (e) {
      if (badge) { badge.className = 'account-status unknown'; badge.textContent = 'Non vérifié'; }
      toast.show('Erreur vérification : ' + e.message, 'error');
    } finally {
      if (btn) { btn.disabled = false; }
    }
  }

  async function _deleteAccount(id) {
    const a = _accounts.find(x => x.id === id);
    if (!a) return;
    if (!confirm(`Supprimer le compte ${a.vinted_username || a.email} ?`)) return;
    try {
      await api.deleteAccount(id);
      toast.show('Compte supprimé', 'success');
      await reload();
    } catch (e) {
      toast.show('Erreur : ' + e.message, 'error');
    }
  }

  // ── Helpers ────────────────────────────────────────────────────────────────
  function _avatarColor(email) {
    const colors = ['#6366f1','#8b5cf6','#ec4899','#f59e0b','#10b981','#3b82f6','#ef4444'];
    let hash = 0;
    for (const c of email) hash = (hash * 31 + c.charCodeAt(0)) & 0xffffffff;
    return colors[Math.abs(hash) % colors.length];
  }

  function _esc(s) {
    return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  return { init, reload };
})();
