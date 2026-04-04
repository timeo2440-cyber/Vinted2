/**
 * REST API wrapper — all calls go through here.
 * Automatically attaches the JWT Authorization header.
 */
const api = (() => {
  const BASE = '';

  async function request(method, path, body) {
    const headers = { 'Content-Type': 'application/json' };
    const token = auth.getToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const opts = { method, headers };
    if (body !== undefined) opts.body = JSON.stringify(body);

    const res = await fetch(BASE + path, opts);

    // Token expired or revoked → force re-login
    if (res.status === 401) {
      auth.clear();
      location.reload();
      return;
    }

    if (!res.ok) {
      let msg = `HTTP ${res.status}`;
      try { const j = await res.json(); msg = j.detail || j.message || msg; } catch {}
      throw new Error(msg);
    }
    if (res.status === 204) return null;
    return res.json();
  }

  return {
    // Auth
    me:               ()     => request('GET',  '/api/auth/me'),
    activateLicense:  (key)  => request('POST', '/api/auth/activate-license', { key }),
    changePassword:   (o, n) => request('POST', '/api/auth/change-password', { old_password: o, new_password: n }),

    // Bot control
    botStart:      () => request('POST', '/api/bot/start'),
    botStop:       () => request('POST', '/api/bot/stop'),
    botStatus:     () => request('GET',  '/api/bot/status'),
    getAutocop:    () => request('GET',  '/api/bot/autocop'),
    setAutocop:    (enabled) => request('POST', '/api/bot/autocop', { enabled }),
    manualBuy:     (item)    => request('POST', '/api/bot/manual-buy', item),

    // Filters
    getFilters:    ()           => request('GET',    '/api/filters'),
    createFilter:  (data)       => request('POST',   '/api/filters', data),
    updateFilter:  (id, data)   => request('PATCH',  `/api/filters/${id}`, data),
    replaceFilter: (id, data)   => request('PUT',    `/api/filters/${id}`, data),
    deleteFilter:  (id)         => request('DELETE', `/api/filters/${id}`),
    testFilter:    (id)         => request('POST',   `/api/filters/${id}/test`),
    debugFilter:   (id)         => request('GET',    `/api/filters/${id}/debug`),

    // Settings
    getSettings:    ()     => request('GET', '/api/settings'),
    saveSettings:   (data) => request('PUT', '/api/settings', data),
    submitCookies:  (c)    => request('POST', '/api/settings/cookies', { cookies: c }),
    authStatus:     ()     => request('GET',  '/api/settings/auth-status'),

    // History
    getPurchases:  (page=1) => request('GET', `/api/history/purchases?page=${page}`),
    getSeenItems:  (page=1) => request('GET', `/api/history/seen-items?page=${page}`),

    // Stats
    getStats:    () => request('GET', '/api/stats/summary'),
    getTimeline: () => request('GET', '/api/stats/timeline'),

    // Logs
    getLogs:   (page=1) => request('GET', `/api/logs?page=${page}&per_page=200`),
    clearLogs: ()       => request('DELETE', '/api/logs'),

    // Vinted meta
    searchBrands:   (q)  => request('GET', `/api/vinted/brands?q=${encodeURIComponent(q)}`),
    getCategories:  ()   => request('GET', '/api/vinted/categories'),

    // Accounts
    getAccounts:         ()              => request('GET',    '/api/accounts'),
    createAccount:       (data)          => request('POST',   '/api/accounts', data),
    updateAccount:       (id, data)      => request('PUT',    `/api/accounts/${id}`, data),
    deleteAccount:       (id)            => request('DELETE', `/api/accounts/${id}`),
    reloginAccount:      (id)            => request('POST',   `/api/accounts/${id}/login`),
    setAccountCookies:   (id, cookies)   => request('POST',   `/api/accounts/${id}/cookies`, { cookies }),
    checkAccountStatus:  (id)            => request('GET',    `/api/accounts/${id}/status`),

    // Admin
    adminGetUsers:      ()          => request('GET',    '/api/admin/users'),
    adminUpdateUser:    (id, data)  => request('PUT',    `/api/admin/users/${id}`, data),
    adminDeleteUser:    (id)        => request('DELETE', `/api/admin/users/${id}`),
    adminGetLicenses:   ()          => request('GET',    '/api/admin/licenses'),
    adminCreateLicense: (data)      => request('POST',   '/api/admin/licenses', data),
    adminDeleteLicense: (key)       => request('DELETE', `/api/admin/licenses/${key}`),
    adminGetStats:      ()          => request('GET',    '/api/admin/stats'),
  };
})();
