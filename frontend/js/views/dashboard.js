const dashboardView = (() => {
  let paused = false;
  let matchedOnly = true;  // Par défaut : seulement les articles correspondant aux filtres
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

    const matchedToggle = document.getElementById('matched-only-toggle');
    if (matchedToggle) {
      matchedToggle.checked = true;  // Coché par défaut
      matchedToggle.addEventListener('change', e => {
        matchedOnly = e.target.checked;
        _applyFeedFilter();
      });
    }
  }

  function _applyFeedFilter() {
    const feed = document.getElementById('item-feed');
    feed.querySelectorAll('.item-card').forEach(card => {
      if (matchedOnly) {
        const isRelevant = card.classList.contains('matched')
          || card.classList.contains('buying')
          || card.classList.contains('bought');
        card.style.display = isRelevant ? '' : 'none';
      } else {
        card.style.display = '';
      }
    });
  }

  function prependItem(item) {
    if (paused) return;

    const feed = document.getElementById('item-feed');
    // DOM-level dedup safety net (in case store check was bypassed)
    if (feed.querySelector(`[data-id="${item.id}"]`)) return;
    showEmpty(false);

    const card = itemCard.create(item);

    // Apply matched-only filter immediately
    if (matchedOnly && !['matched', 'buying', 'bought'].includes(item.status)) {
      card.style.display = 'none';
    }

    feed.insertBefore(card, feed.firstChild);

    // Cap number of cards in DOM
    while (feed.children.length > MAX_CARDS) {
      feed.removeChild(feed.lastChild);
    }

    // Observe for status updates
    const unsub = store.on('recentItems', items => {
      const updated = items.find(i => i.id === item.id);
      if (!updated || updated.status === item.status) return;

      const existing = feed.querySelector(`[data-id="${item.id}"]`);
      if (!existing) { unsub(); return; }

      itemCard.updateStatus(existing, updated.status);
      item.status = updated.status;

      // If now matched/bought, show card even in matched-only mode + flash
      if (['matched', 'buying', 'bought'].includes(updated.status)) {
        existing.style.display = '';
        existing.classList.add('flash-match');
        existing.addEventListener('animationend', () => existing.classList.remove('flash-match'), { once: true });
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
