const filtersView = (() => {
  // Cache display names locally (not persisted in DB) keyed by filter id
  const _brandNamesCache    = new Map();
  const _categoryNamesCache = new Map();

  function init() {
    document.getElementById('add-filter-btn').addEventListener('click', () => openFilterModal(null));
    loadFilters();
  }

  async function loadFilters() {
    try {
      const filters = await api.getFilters();
      store.set('filters', filters);
      renderFilters(filters);
      // Update badge
      const active = filters.filter(f => f.enabled).length;
      const badge = document.getElementById('filter-badge');
      if (badge) {
        badge.textContent = active;
        badge.classList.toggle('hidden', active === 0);
      }
    } catch (e) {
      toast.show('Erreur chargement filtres : ' + e.message, 'error');
    }
  }

  function renderFilters(filters) {
    const list = document.getElementById('filter-list');
    const empty = document.getElementById('filters-empty');

    // Remove existing cards (keep empty state)
    list.querySelectorAll('.filter-card').forEach(el => el.remove());

    if (!filters.length) {
      empty.style.display = 'flex';
      return;
    }
    empty.style.display = 'none';

    filters.forEach(f => list.appendChild(buildFilterCard(f)));
  }

  function buildFilterCard(f) {
    const card = document.createElement('div');
    card.className = `filter-card${f.enabled ? '' : ' disabled'}`;
    card.dataset.id = f.id;

    const chips = buildChips(f);

    card.innerHTML = `
      <div class="filter-card-header">
        <span class="filter-name">${escHtml(f.name)}</span>
        <div class="filter-toggles">
          <label class="nano-toggle" title="Activer/désactiver">
            <input type="checkbox" class="toggle-enabled" ${f.enabled ? 'checked' : ''}>
            <span class="nano-slider"></span>
          </label>
          <label class="nano-toggle orange" title="Auto-achat">
            <input type="checkbox" class="toggle-autobuy" ${f.auto_buy ? 'checked' : ''}>
            <span class="nano-slider"></span>
          </label>
        </div>
      </div>
      <div class="filter-chip-row">${chips}</div>
      <div class="filter-card-actions">
        <button class="btn-ghost btn-sm btn-edit">Modifier</button>
        <button class="btn-ghost btn-sm btn-test">Tester</button>
        <button class="btn-ghost btn-sm btn-debug" title="Voir pourquoi les articles matchent ou non">🔍 Debug</button>
        <button class="btn-danger btn-sm btn-delete">Supprimer</button>
      </div>
    `;

    // Enable toggle
    card.querySelector('.toggle-enabled').addEventListener('change', async e => {
      try {
        await api.updateFilter(f.id, { enabled: e.target.checked });
        card.classList.toggle('disabled', !e.target.checked);
        f.enabled = e.target.checked;
        updateBadgeCount();
      } catch (err) {
        toast.show('Erreur : ' + err.message, 'error');
        e.target.checked = !e.target.checked;
      }
    });

    // Auto-buy toggle
    card.querySelector('.toggle-autobuy').addEventListener('change', async e => {
      if (e.target.checked) {
        const ok = confirm('Activer l\'auto-achat pour ce filtre ? Les articles correspondants seront achetés automatiquement.');
        if (!ok) { e.target.checked = false; return; }
      }
      try {
        await api.updateFilter(f.id, { auto_buy: e.target.checked });
        f.auto_buy = e.target.checked;
      } catch (err) {
        toast.show('Erreur : ' + err.message, 'error');
        e.target.checked = !e.target.checked;
      }
    });

    // Edit
    card.querySelector('.btn-edit').addEventListener('click', () => openFilterModal(f));

    // Test
    card.querySelector('.btn-test').addEventListener('click', () => testFilter(f));

    // Debug
    card.querySelector('.btn-debug').addEventListener('click', () => debugFilter(f));

    // Delete
    card.querySelector('.btn-delete').addEventListener('click', () => deleteFilter(f, card));

    return card;
  }

  function buildChips(f) {
    const chips = [];
    if (f.keywords)   chips.push(`<span class="filter-chip keyword">🔍 ${escHtml(f.keywords)}</span>`);
    if (f.price_min != null || f.price_max != null) {
      const min = f.price_min != null ? f.price_min + '€' : '0€';
      const max = f.price_max != null ? f.price_max + '€' : '∞';
      chips.push(`<span class="filter-chip price">💶 ${min} – ${max}</span>`);
    }
    // Brand chips
    if (f.brand_ids?.length) {
      const names = _brandNamesCache.get(f.id);
      const label = names
        ? names.slice(0, 3).join(', ') + (names.length > 3 ? '…' : '')
        : `${f.brand_ids.length} marque${f.brand_ids.length > 1 ? 's' : ''}`;
      chips.push(`<span class="filter-chip brand">🏷 ${escHtml(label)}</span>`);
    }
    // Category chips
    if (f.category_ids?.length) {
      const catNames = _categoryNamesCache.get(f.id);
      const catLabel = catNames
        ? catNames.slice(0, 2).join(', ') + (catNames.length > 2 ? '…' : '')
        : `${f.category_ids.length} catégorie${f.category_ids.length > 1 ? 's' : ''}`;
      chips.push(`<span class="filter-chip category">📂 ${escHtml(catLabel)}</span>`);
    }
    if (f.auto_buy)   chips.push(`<span class="filter-chip autobuy">⚡ Auto-achat</span>`);
    if (f.conditions?.length) chips.push(`<span class="filter-chip">${f.conditions.length} état(s)</span>`);
    if (f.country_codes?.length) chips.push(`<span class="filter-chip">${f.country_codes.join(', ')}</span>`);
    if (f.max_budget) chips.push(`<span class="filter-chip price">Budget max ${f.max_budget}€</span>`);
    if (!chips.length) chips.push(`<span class="filter-chip">Tous articles</span>`);
    return chips.join('');
  }

  function openFilterModal(existing) {
    // Enrich with display names (API now returns brand_names; fallback to local cache)
    const enriched = existing ? {
      ...existing,
      brand_names:    existing.brand_names?.length ? existing.brand_names : (_brandNamesCache.get(existing.id) || []),
      category_names: _categoryNamesCache.get(existing.id) || [],
    } : null;

    const formEl = filterForm.build(enriched);
    modal.open(existing ? 'Modifier le filtre' : 'Nouveau filtre', formEl);

    formEl.querySelector('#ff-cancel').addEventListener('click', () => modal.close());

    formEl.querySelector('#ff-save').addEventListener('click', async () => {
      const data = filterForm.read(formEl);
      if (!data) return;

      // category_names is display-only; brand_names is now saved to DB for matching
      const payload = { ...data };
      delete payload.category_names;

      try {
        let savedFilter;
        if (existing) {
          savedFilter = await api.replaceFilter(existing.id, payload);
          if (payload.brand_names?.length) _brandNamesCache.set(existing.id, payload.brand_names);
          toast.show('Filtre mis à jour.', 'success');
        } else {
          savedFilter = await api.createFilter(payload);
          if (savedFilter?.id && payload.brand_names?.length) {
            _brandNamesCache.set(savedFilter.id, payload.brand_names);
          }
          toast.show('Filtre créé.', 'success');
        }
        modal.close();
        await loadFilters();
      } catch (e) {
        toast.show('Erreur : ' + e.message, 'error');
      }
    });
  }

  async function testFilter(f) {
    toast.show('Test du filtre en cours…', 'info', 2000);
    try {
      const result = await api.testFilter(f.id);
      const count = result.matched_count;
      const items = result.items || [];

      const html = `
        <p style="margin-bottom:14px;color:var(--text-secondary)">
          <strong style="color:var(--accent)">${count}</strong> article(s) trouvé(s) parmi les 200 derniers vus.
        </p>
        <div style="display:flex;flex-direction:column;gap:8px;max-height:360px;overflow-y:auto">
          ${items.slice(0, 20).map(it => `
            <div style="display:flex;align-items:center;gap:10px;padding:8px;background:var(--bg-1);border-radius:8px;border:1px solid var(--border)">
              ${it.photo_url ? `<img src="${it.photo_url}" style="width:48px;height:48px;object-fit:cover;border-radius:6px">` : '<div style="width:48px;height:48px;background:var(--bg-3);border-radius:6px"></div>'}
              <div style="min-width:0;flex:1">
                <div style="font-size:13px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${escHtml(it.title || '')}</div>
                <div style="font-size:12px;color:var(--text-muted)">${it.price != null ? it.price + '€' : ''} ${it.brand || ''}</div>
              </div>
              ${it.item_url ? `<a href="${it.item_url}" target="_blank" style="font-size:11px;color:var(--accent);flex-shrink:0">Voir →</a>` : ''}
            </div>
          `).join('')}
          ${count > 20 ? `<p style="text-align:center;color:var(--text-muted);font-size:12px">+${count - 20} autres…</p>` : ''}
        </div>
      `;
      modal.open(`Résultats du test — ${escHtml(f.name)}`, html);
    } catch (e) {
      toast.show('Erreur test : ' + e.message, 'error');
    }
  }

  async function debugFilter(f) {
    toast.show('Debug en cours — fetch Vinted live…', 'info', 3000);
    try {
      const result = await api.debugFilter(f.id);

      if (result.error) {
        modal.open('Debug — Erreur', `<pre style="font-size:12px;color:#f87171">${escHtml(result.error)}</pre>`);
        return;
      }

      const rows = (result.items || []).map(it => {
        const icon = it.match ? '✅' : '❌';
        const passes = it.why_pass.map(p => `<span style="color:#10b981">✓ ${escHtml(p)}</span>`).join('<br>');
        const fails  = it.why_fail.map(p => `<span style="color:#f87171">✗ ${escHtml(p)}</span>`).join('<br>');
        return `
          <div style="padding:10px 0;border-bottom:1px solid var(--border)">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
              <span style="font-size:16px">${icon}</span>
              <span style="font-size:13px;font-weight:600">${escHtml(it.title)}</span>
              <span style="font-size:12px;color:var(--text-muted)">${it.price != null ? it.price + '€' : ''}</span>
            </div>
            <div style="font-size:11px;color:var(--text-muted);margin-bottom:4px">
              brand=${escHtml(String(it.brand||'?'))} brand_id=${it.brand_id??'—'} category_id=${it.category_id??'—'}
            </div>
            <div style="font-size:12px;line-height:1.7">${passes}${fails ? (passes?'<br>':'') + fails : ''}</div>
          </div>`;
      }).join('');

      const html = `
        <div style="font-size:12px;background:var(--bg-1);border-radius:8px;padding:10px;margin-bottom:14px;font-family:monospace">
          <div>Méthode : <b>${escHtml(result.fetch_method)}</b></div>
          <div>Articles récupérés : <b>${result.total_fetched}</b> &nbsp;|&nbsp; Matchés : <b style="color:${result.matched>0?'#10b981':'#f87171'}">${result.matched}</b></div>
        </div>
        ${result.total_fetched === 0
          ? `<p style="color:#f87171;font-size:13px">⚠ Vinted n'a renvoyé aucun article.<br>Causes possibles : IP bloquée (Cloudflare), cookies expirés, ou les IDs de marque/catégorie n'existent pas sur Vinted.</p>`
          : `<div style="max-height:420px;overflow-y:auto">${rows}</div>`
        }`;

      modal.open(`🔍 Debug — ${escHtml(f.name)}`, html);
    } catch(e) {
      toast.show('Erreur debug : ' + e.message, 'error');
    }
  }

  async function deleteFilter(f, card) {
    if (!confirm(`Supprimer le filtre "${f.name}" ?`)) return;
    try {
      await api.deleteFilter(f.id);
      _brandNamesCache.delete(f.id);
      _categoryNamesCache.delete(f.id);
      card.remove();
      toast.show('Filtre supprimé.', 'success');
      updateBadgeCount();
      const list = document.getElementById('filter-list');
      if (!list.querySelector('.filter-card')) {
        document.getElementById('filters-empty').style.display = 'flex';
      }
    } catch (e) {
      toast.show('Erreur : ' + e.message, 'error');
    }
  }

  function updateBadgeCount() {
    const cards = document.querySelectorAll('.filter-card:not(.disabled)');
    const badge = document.getElementById('filter-badge');
    if (badge) {
      badge.textContent = cards.length;
      badge.classList.toggle('hidden', cards.length === 0);
    }
  }

  function escHtml(s) {
    return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  return { init, loadFilters };
})();
