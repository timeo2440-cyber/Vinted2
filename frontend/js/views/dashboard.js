const dashboardView = (() => {
  let paused = false;
  const MAX_CARDS = 150;

  function init() {
    document.getElementById('pause-feed').addEventListener('change', e => {
      paused = e.target.checked;
    });

    document.getElementById('clear-feed').addEventListener('click', () => {
      const feed = document.getElementById('item-feed');
      feed.innerHTML = '';
      showEmpty(true);
    });
  }

  function prependItem(item) {
    if (paused) return;

    const feed = document.getElementById('item-feed');
    showEmpty(false);

    const card = itemCard.create(item);
    feed.insertBefore(card, feed.firstChild);

    // Cap number of cards in DOM
    while (feed.children.length > MAX_CARDS) {
      feed.removeChild(feed.lastChild);
    }

    // Observe for status updates
    store.on('recentItems', items => {
      const updated = items.find(i => i.id === item.id);
      if (updated && updated.status !== item.status) {
        const existing = feed.querySelector(`[data-id="${item.id}"]`);
        if (existing) itemCard.updateStatus(existing, updated.status);
      }
    });
  }

  function showEmpty(show) {
    const empty = document.getElementById('feed-empty');
    if (!empty) return;
    empty.style.display = show ? 'flex' : 'none';
  }

  return { init, prependItem };
})();
