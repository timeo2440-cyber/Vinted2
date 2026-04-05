const itemCard = (() => {
  const CONDITIONS = {
    new_with_tags:    'Neuf avec étiquette',
    new_without_tags: 'Neuf sans étiquette',
    very_good:        'Très bon état',
    good:             'Bon état',
    satisfactory:     'Satisfaisant',
  };

  function timeAgo(ts) {
    if (!ts) return '';
    const diff = Math.floor((Date.now() - ts) / 1000);
    if (diff < 5)    return 'à l\'instant';
    if (diff < 60)   return `${diff}s`;
    if (diff < 3600) return `${Math.floor(diff / 60)} min`;
    return `${Math.floor(diff / 3600)}h`;
  }

  function conditionLabel(c) {
    return CONDITIONS[c] || c || '';
  }

  function create(item) {
    const el = document.createElement('div');
    el.className = `item-card ${item.status || 'new'}`;
    el.dataset.id = item.id;

    const photo = item.photo_url
      ? `<img class="item-photo" src="${item.photo_url}" alt="" loading="lazy"
             onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">`
        + `<div class="item-photo-placeholder" style="display:none"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg></div>`
      : `<div class="item-photo-placeholder"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg></div>`;

    const filterTag = item.filter_name
      ? `<span class="item-filter-tag">⚡ ${escHtml(item.filter_name)}</span>` : '';

    const condition = item.condition
      ? `<span class="condition-badge">${conditionLabel(item.condition)}</span>` : '';

    const price = item.price != null ? `${parseFloat(item.price).toFixed(2)} €` : '—';

    // Use Vinted's publication timestamp if available, otherwise fall back to received time
    const pubTs = item.created_at_ts ? item.created_at_ts * 1000 : item._ts;

    el.innerHTML = `
      <a class="item-photo-wrap" href="${item.item_url || '#'}" target="_blank" rel="noopener">
        ${photo}
      </a>
      <div class="item-info">
        <div class="item-header-row">
          <span class="item-price">${price}</span>
          <span class="item-time-badge">🕒 ${timeAgo(pubTs)}</span>
        </div>
        <div class="item-title">${escHtml(item.title || 'Article sans titre')}</div>
        <div class="item-meta">
          ${item.brand ? `<span class="item-brand">${escHtml(item.brand)}</span>` : ''}
          ${item.size  ? `<span class="item-size">T.${escHtml(item.size)}</span>` : ''}
          ${condition}
          ${filterTag}
        </div>
        <div class="item-footer-row">
          <div class="item-actions">
            ${item.item_url ? `<a class="btn-item-view" href="${item.item_url}" target="_blank" rel="noopener">Voir</a>` : ''}
            <button class="btn-item-buy" data-id="${escHtml(item.id)}" data-title="${escHtml(item.title||'')}" data-price="${item.price||''}" data-url="${escHtml(item.item_url||'')}">
              🛒 Acheter
            </button>
          </div>
        </div>
      </div>
    `;

    // Buy button handler
    const buyBtn = el.querySelector('.btn-item-buy');
    buyBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      if (buyBtn.disabled) return;

      buyBtn.disabled = true;
      buyBtn.textContent = '⏳ Achat…';
      buyBtn.classList.add('loading');

      try {
        const result = await api.manualBuy({
          id:       item.id,
          title:    item.title,
          price:    item.price,
          item_url: item.item_url,
        });

        if (result.success) {
          buyBtn.textContent = '✅ Acheté';
          buyBtn.classList.remove('loading');
          buyBtn.classList.add('done');
          updateStatus(el, 'bought');
          toast.show(`Acheté : ${item.title} — ${item.price}€`, 'success');
        } else {
          buyBtn.disabled = false;
          buyBtn.textContent = '🛒 Acheter';
          buyBtn.classList.remove('loading');
          toast.show(`Échec : ${result.error || 'Erreur inconnue'}`, 'error');
        }
      } catch (err) {
        buyBtn.disabled = false;
        buyBtn.textContent = '🛒 Acheter';
        buyBtn.classList.remove('loading');
        toast.show(`Erreur : ${err.message}`, 'error');
      }
    });

    return el;
  }

  function statusBadgeHtml(status) {
    const map = {
      new:     ['new',     'Nouveau'],
      matched: ['matched', '⚡ Matché'],
      buying:  ['buying',  '⏳ Achat...'],
      bought:  ['bought',  '✅ Acheté'],
      failed:  ['failed',  '✗ Échec'],
    };
    const [cls, label] = map[status] || ['new', 'Nouveau'];
    return `<span class="badge-status ${cls}">${label}</span>`;
  }

  function updateStatus(cardEl, status) {
    if (!cardEl) return;
    cardEl.className = `item-card ${status}`;
  }

  function escHtml(s) {
    return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  return { create, updateStatus };
})();
