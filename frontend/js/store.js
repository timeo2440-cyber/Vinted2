/**
 * Lightweight reactive state store with pub/sub.
 * Usage: store.on('filters', cb) / store.set('filters', []) / store.get('filters')
 */
const store = (() => {
  const state = {
    botRunning: false,
    authenticated: false,
    username: null,
    filters: [],
    recentItems: [],       // ring buffer, max 300
    purchases: [],
    stats: {},
    wsConnected: false,
    itemsSeen: 0,
    itemsMatched: 0,
    itemsBought: 0,
    pollIntervalMs: 4000,
  };

  const listeners = {};

  function on(key, cb) {
    if (!listeners[key]) listeners[key] = [];
    listeners[key].push(cb);
    return () => { listeners[key] = listeners[key].filter(f => f !== cb); };
  }

  function emit(key, value) {
    (listeners[key] || []).forEach(cb => cb(value));
  }

  function set(key, value) {
    state[key] = value;
    emit(key, value);
  }

  function get(key) {
    return state[key];
  }

  function pushItem(item) {
    const items = [item, ...state.recentItems].slice(0, 300);
    state.recentItems = items;
    emit('recentItems', items);
  }

  function updateItem(itemId, patch) {
    state.recentItems = state.recentItems.map(it =>
      it.id === itemId ? { ...it, ...patch } : it
    );
    emit('recentItems', state.recentItems);
  }

  return { on, set, get, emit, pushItem, updateItem, state };
})();
