const activityLog = (() => {
  const MAX = 300;
  let autoScroll = true;
  let entries = [];

  function append(level, message, category) {
    const container = document.getElementById('activity-log');
    if (!container) return;

    const now = new Date();
    const time = now.toTimeString().slice(0, 8);

    entries.push({ level, message, category, time });
    if (entries.length > MAX) entries.shift();

    const empty = document.getElementById('feed-empty');
    // Remove empty state hint only for actual log container

    const el = document.createElement('div');
    el.className = `log-entry ${level}`;
    el.innerHTML = `<span class="log-time">${time}</span><span class="log-msg">${escapeHtml(message)}</span>`;
    container.appendChild(el);

    // Cap DOM nodes
    while (container.children.length > MAX) {
      container.removeChild(container.firstChild);
    }

    if (autoScroll) {
      container.scrollTop = container.scrollHeight;
    }
  }

  function clear() {
    const container = document.getElementById('activity-log');
    if (container) container.innerHTML = '';
    entries = [];
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  // Setup auto-scroll detection
  document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('activity-log');
    if (container) {
      container.addEventListener('scroll', () => {
        const threshold = 40;
        autoScroll = container.scrollTop + container.clientHeight >= container.scrollHeight - threshold;
      });
    }

    document.getElementById('clear-logs-btn')?.addEventListener('click', async () => {
      try { await api.clearLogs(); } catch {}
      clear();
    });
  });

  return { append, clear };
})();
