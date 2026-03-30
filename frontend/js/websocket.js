/**
 * WebSocket client with auto-reconnect and event dispatching.
 */
const wsClient = (() => {
  let ws = null;
  let reconnectTimer = null;
  let reconnectDelay = 1000;
  let pingTimer = null;

  function connect() {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const url = `${proto}://${location.host}/ws`;

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
        handleNewItem(data);
        break;

      case 'item_match':
        store.updateItem(data.id, {
          status: 'matched',
          matched_filter_ids: [...(data.matched_filter_ids || []), data.filter_id].filter(Boolean),
          filter_name: data.filter_name,
        });
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
        } else {
          store.updateItem(data.item_id, { status: 'failed' });
          toast.show(`Échec d'achat : ${data.error || 'Erreur inconnue'}`, 'error');
        }
        break;

      case 'bot_status':
        store.set('botRunning', data.running);
        store.set('itemsSeen', data.items_seen || 0);
        store.set('itemsMatched', data.items_matched || 0);
        updateBotUI(data.running);
        document.getElementById('stat-seen').textContent = data.items_seen || 0;
        document.getElementById('stat-matched').textContent = data.items_matched || 0;
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

  function handleNewItem(data) {
    const item = { ...data, status: data.matched_filter_ids?.length ? 'matched' : 'new', _ts: Date.now() };
    store.pushItem(item);

    const seen = store.get('itemsSeen') + 1;
    store.set('itemsSeen', seen);
    document.getElementById('stat-seen').textContent = seen;

    // Render in feed
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

  return { connect, send };
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
