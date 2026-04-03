/**
 * Authentication manager — handles JWT storage, login overlay, user state.
 */
const auth = (() => {
  const TOKEN_KEY = 'vbot_token';
  const USER_KEY  = 'vbot_user';

  let _token = localStorage.getItem(TOKEN_KEY) || null;
  let _user  = JSON.parse(localStorage.getItem(USER_KEY) || 'null');
  let _onLogin = null;

  function getToken() { return _token; }
  function getUser()  { return _user; }
  function isAdmin()  { return _user && _user.role === 'admin'; }

  function save(token, user) {
    _token = token;
    _user  = user;
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  }

  function clear() {
    _token = null;
    _user  = null;
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }

  function logout() {
    clear();
    location.reload();
  }

  /** Show login overlay; resolves when user is authenticated. */
  function showLoginOverlay() {
    return new Promise(resolve => {
      _onLogin = resolve;
      document.getElementById('login-overlay').classList.remove('hidden');
    });
  }

  function hideLoginOverlay() {
    document.getElementById('login-overlay').classList.add('hidden');
  }

  function _switchTab(tab) {
    document.querySelectorAll('.login-tab').forEach(t =>
      t.classList.toggle('active', t.dataset.tab === tab)
    );
    document.getElementById('login-form-login').classList.toggle('hidden', tab !== 'login');
    document.getElementById('login-form-register').classList.toggle('hidden', tab !== 'register');
    document.querySelectorAll('.login-error').forEach(e => e.classList.remove('visible'));
  }

  async function _doLogin(email, password, errEl, btn) {
    btn.disabled = true;
    btn.textContent = 'Connexion…';
    errEl.classList.remove('visible');
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Erreur connexion');
      save(data.token, data.user);
      hideLoginOverlay();
      if (_onLogin) { _onLogin(); _onLogin = null; }
    } catch (e) {
      errEl.textContent = e.message;
      errEl.classList.add('visible');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Se connecter';
    }
  }

  async function _doRegister(email, password, errEl, btn) {
    btn.disabled = true;
    btn.textContent = 'Création…';
    errEl.classList.remove('visible');
    try {
      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Erreur inscription');
      save(data.token, data.user);
      hideLoginOverlay();
      if (_onLogin) { _onLogin(); _onLogin = null; }
    } catch (e) {
      errEl.textContent = e.message;
      errEl.classList.add('visible');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Créer le compte';
    }
  }

  function initOverlay() {
    // Tab switching
    document.querySelectorAll('.login-tab').forEach(tab => {
      tab.addEventListener('click', () => _switchTab(tab.dataset.tab));
    });

    // Login form
    document.getElementById('login-btn').addEventListener('click', () => {
      const email = document.getElementById('login-email').value.trim();
      const pw    = document.getElementById('login-password').value;
      _doLogin(email, pw,
        document.getElementById('login-error'),
        document.getElementById('login-btn')
      );
    });

    ['login-email', 'login-password'].forEach(id => {
      document.getElementById(id).addEventListener('keydown', e => {
        if (e.key === 'Enter') document.getElementById('login-btn').click();
      });
    });

    // Register form
    document.getElementById('register-btn').addEventListener('click', () => {
      const email = document.getElementById('register-email').value.trim();
      const pw    = document.getElementById('register-password').value;
      _doRegister(email, pw,
        document.getElementById('register-error'),
        document.getElementById('register-btn')
      );
    });

    ['register-email', 'register-password'].forEach(id => {
      document.getElementById(id).addEventListener('keydown', e => {
        if (e.key === 'Enter') document.getElementById('register-btn').click();
      });
    });
  }

  /** Verify stored token is still valid; clear if not. */
  async function verify() {
    if (!_token) return false;
    try {
      const res = await fetch('/api/auth/me', {
        headers: { Authorization: `Bearer ${_token}` },
      });
      if (!res.ok) { clear(); return false; }
      const user = await res.json();
      save(_token, user); // refresh user data
      return true;
    } catch {
      return false;
    }
  }

  return { getToken, getUser, isAdmin, save, clear, logout, showLoginOverlay, initOverlay, verify };
})();
