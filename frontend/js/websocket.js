/**
 * WebSocket client with auto-reconnect and event dispatching.
 */
const wsClient = (() => {
  let ws = null;
  let reconnectTimer = null;
  let reconnectDelay = 1000;
  let pingTimer = null;

  // ── Sound helpers ──────────────────────────────────────────────────────────

  function playBeep() {
    if (!store.get('soundEnabled')) return;
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc  = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.type = 'sine';
      osc.frequency.setValueAtTime(880, ctx.currentTime);
      gain.gain.setValueAtTime(0.25, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
      osc.start(ctx.currentTime);
      osc.stop(ctx.currentTime + 0.3);
      osc.onended = () => ctx.close();
    } catch {}
  }

  function playSuccessChime() {
    if (!store.get('soundEnabled')) return;
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      [1047, 1319].forEach((freq, i) => {
        const osc  = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.frequency.value = freq;
        gain.gain.setValueAtTime(0.2,   ctx.currentTime + i * 0.15);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + i * 0.15 + 0.3);
        osc.start(ctx.currentTime + i * 0.15);
        osc.stop(ctx.currentTime  + i * 0.15 + 0.35);
      });
      setTimeout(() => ctx.close(), 800);
    } catch {}
  }

  // ── Connection ─────────────────────────────────────────────────────────────

  function connect() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const token = auth.getToken ? auth.getToken() : '';
    const url = `${proto}://${location.host}/ws${token ? `?token=${encodeURIComponent(token)}` : ''}`;

    try { ws = new WebSocket(url); } catch { scheduleReconnect(); return; }

    ws.onopen = () => {
      store.set('wsConnected', true);
      reconnectDelay = 1000;
      document.getElementById('ws-indicator').className = 'ws-dot connected';
      startPing();
    };

    ws.onclose = () => {
      store.set('wsConnected', false);
      document.getElementById('ws-indicator').className = 'ws-dot disconnected';
      stopPing();
      scheduleReconnect();
    };

    ws.onerror = () => {
      ws.close();
    };

    ws.onmessage = (e) => {
      let msg;
      try { msg = JSON.parse(e.data); } catch { return; }
      dispatch(msg);
    };
  }

  function dispatch(msg) {
    const { type, data } = msg;

    switch (type) {
      case 'new_item':
        // Compter les articles vus mais NE PAS les afficher dans le feed
        // (on n'affiche que les articles qui correspondent aux filtres)
        store.set('itemsSeen', store.get('itemsSeen') + 1);
        document.getElementById('stat-seen').textContent = store.get('itemsSeen');
        break;

      case 'item_match':
        // Article correspondant à un filtre → l'ajouter au feed
        handleMatchedItem(data);
        store.set('itemsMatched', store.get('itemsMatched') + 1);
        document.getElementById('stat-matched').textContent = store.get('itemsMatched');
        break;

      case 'buy_attempt':
        store.updateItem(data.item_id, { status: 'buying' });
        break;

      case 'buy_result':
        if (data.status === 'success') {
          store.updateItem(data.item_id, { status: 'bought' });
          const bought = store.get('itemsBought') + 1;
          store.set('itemsBought', bought);
          document.getElementById('stat-bought').textContent = bought;
          toast.show(`Acheté avec succès ! ${data.price ? data.price + '€' : ''}`, 'success');
          playSuccessChime();
        } else {
          store.updateItem(data.item_id, { status: 'failed' });
          toast.show(`Échec d'achat : ${data.error || 'Erreur inconnue'}`, 'error');
        }
        break;

      case 'bot_status':
        store.set('botRunning', data.running);
        store.set('itemsSeen', data.items_seen || 0);
        store.set('itemsMatched', data.items_matched || 0);
        document.getElementById('stat-seen').textContent = data.items_seen || 0;
        document.getElementById('stat-matched').textContent = data.items_matched || 0;
        // Keep live badge in sync
        const liveBadge = document.getElementById('bot-live-badge');
        if (liveBadge) liveBadge.classList.toggle('offline', !data.running);
        break;

      case 'log':
        activityLog.append(data.level, data.message, data.category);
        break;

      case 'auth_error':
        toast.show('Session Vinted expirée. Mettez à jour vos cookies.', 'error');
        store.set('authenticated', false);
        updateAuthUI(false, null);
        break;

      case 'pong':
        break;
    }
  }

  function handleMatchedItem(data) {
    // Deduplicate: skip if this item is already in the store (replay + poller can both fire)
    if (store.get('recentItems').some(i => i.id === data.id)) return;
    const item = { ...data, status: 'matched', _ts: Date.now() };
    store.pushItem(item);
    dashboardView.prependItem(item);
  }

  function startPing() {
    stopPing();
    pingTimer = setInterval(() => {
      if (ws && ws.readyState === WebSocket.OPEN) ws.send('ping');
    }, 25000);
  }

  function stopPing() {
    if (pingTimer) { clearInterval(pingTimer); pingTimer = null; }
  }

  function scheduleReconnect() {
    if (reconnectTimer) return;
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      reconnectDelay = Math.min(reconnectDelay * 2, 16000);
      connect();
    }, reconnectDelay);
  }

  function send(msg) {
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg));
  }

  function initSoundToggle() {
    const btn = document.getElementById('sound-toggle');
    if (!btn) return;
    btn.addEventListener('click', () => {
      const enabled = !store.get('soundEnabled');
      store.set('soundEnabled', enabled);
      btn.classList.toggle('active', enabled);
      btn.title = enabled ? 'Son activé (cliquez pour désactiver)' : 'Son désactivé (cliquez pour activer)';
    });
  }

  return { connect, send, initSoundToggle };
})();

// Helpers used by wsClient — defined later but hoisted via function scope
function updateBotUI(running) {
  const toggle = document.getElementById('bot-toggle');
  const label  = document.getElementById('bot-status-label');
  if (toggle) toggle.checked = running;
  if (label) {
    label.textContent = running ? 'En cours' : 'Arrêté';
    label.className = 'bot-label ' + (running ? 'running' : 'stopped');
  }
}

function updateAuthUI(authenticated, username) {
  const badge = document.getElementById('auth-status-badge');
  const label = document.getElementById('auth-label');
  if (!badge || !label) return;
  if (authenticated) {
    badge.className = 'auth-badge online';
    label.textContent = username || 'Connecté';
  } else {
    badge.className = 'auth-badge offline';
    label.textContent = 'Non connecté';
  }
}
