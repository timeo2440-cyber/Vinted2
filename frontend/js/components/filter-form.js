const filterForm = (() => {
  const CONDITIONS = [
    { value: 'new_with_tags',    label: 'Neuf avec étiquette' },
    { value: 'new_without_tags', label: 'Neuf sans étiquette' },
    { value: 'very_good',        label: 'Très bon état' },
    { value: 'good',             label: 'Bon état' },
    { value: 'satisfactory',     label: 'Satisfaisant' },
  ];

  const COUNTRIES = [
    { code: 'FR', label: 'France' }, { code: 'DE', label: 'Allemagne' },
    { code: 'ES', label: 'Espagne' }, { code: 'IT', label: 'Italie' },
    { code: 'BE', label: 'Belgique' }, { code: 'NL', label: 'Pays-Bas' },
    { code: 'PL', label: 'Pologne' }, { code: 'PT', label: 'Portugal' },
    { code: 'GB', label: 'Royaume-Uni' },
  ];

  // Module-level state — reset on each build()
  let _selectedBrands = [];      // [{id, title}]
  let _categoryCache  = null;    // null until first successful fetch

  function build(existing) {
    const f = existing || {};
    const condSelected = f.conditions || [];
    const countryCodes = f.country_codes || [];

    // Reset brands from existing filter
    _selectedBrands = (f.brand_ids || []).map((id, i) => ({
      id,
      title: (f.brand_names || [])[i] || `#${id}`,
    }));

    const condHtml = CONDITIONS.map(c =>
      `<label class="condition-option ${condSelected.includes(c.value) ? 'selected' : ''}" data-value="${c.value}">
        <input type="checkbox" ${condSelected.includes(c.value) ? 'checked' : ''}>${c.label}
      </label>`
    ).join('');

    const countryOptions = COUNTRIES.map(c =>
      `<option value="${c.code}" ${countryCodes.includes(c.code) ? 'selected' : ''}>${c.label}</option>`
    ).join('');

    const div = document.createElement('div');
    div.className = 'filter-form';
    div.innerHTML = `
      <div class="form-group">
        <label>Nom du filtre *</label>
        <input type="text" id="ff-name" placeholder="Ex: Nike Air Max T42" value="${escHtml(f.name || '')}">
      </div>

      <div class="form-group">
        <label>Mots-clés</label>
        <input type="text" id="ff-keywords" placeholder="nike air max jordan..." value="${escHtml(f.keywords || '')}">
        <small>Séparés par espaces. Utilisez "guillemets" pour des phrases exactes.</small>
      </div>

      <div class="form-group">
        <label>Marques</label>
        <div class="brand-search-wrap">
          <input type="text" id="ff-brand-input" placeholder="Rechercher une marque…" autocomplete="off">
          <div class="brand-dropdown hidden" id="ff-brand-dropdown"></div>
        </div>
        <div class="brand-tags" id="ff-brand-tags"></div>
        <small>Laisser vide = toutes les marques.</small>
      </div>

      <div class="form-group">
        <label>Catégorie</label>
        <select id="ff-category">
          <option value="">Toutes les catégories</option>
        </select>
        <small>Laisser vide = toutes les catégories.</small>
      </div>

      <div class="form-group">
        <label>Fourchette de prix (€)</label>
        <div class="price-row">
          <input type="number" id="ff-price-min" placeholder="Min" min="0" step="0.5" value="${f.price_min ?? ''}">
          <span class="price-sep">—</span>
          <input type="number" id="ff-price-max" placeholder="Max" min="0" step="0.5" value="${f.price_max ?? ''}">
        </div>
      </div>

      <div class="form-group">
        <label>État de l'article</label>
        <div class="checkbox-group" id="ff-conditions">${condHtml}</div>
      </div>

      <div class="form-group">
        <label>Pays vendeur</label>
        <select id="ff-countries" multiple size="4">${countryOptions}</select>
        <small>Ctrl+clic pour sélection multiple. Laisser vide = tous les pays.</small>
      </div>

      <div class="form-group">
        <label>Budget max (€ / 24h)</label>
        <input type="number" id="ff-budget" placeholder="Ex: 150" min="0" step="1" value="${f.max_budget ?? ''}">
        <small>Limite de dépense pour ce filtre sur 24h.</small>
      </div>

      <div class="form-group">
        <div class="switch-row">
          <div>
            <div class="switch-row-label">Auto-achat</div>
            <div class="switch-row-desc">Achète automatiquement les articles matchés</div>
          </div>
          <label class="toggle-switch">
            <input type="checkbox" id="ff-autobuy" ${f.auto_buy ? 'checked' : ''}>
            <span class="slider"></span>
          </label>
        </div>
      </div>

      <div class="form-group">
        <div class="switch-row">
          <div>
            <div class="switch-row-label">Filtre actif</div>
            <div class="switch-row-desc">Active ou désactive ce filtre</div>
          </div>
          <label class="toggle-switch">
            <input type="checkbox" id="ff-enabled" ${f.enabled !== false ? 'checked' : ''}>
            <span class="slider"></span>
          </label>
        </div>
      </div>

      <div class="form-footer">
        <button type="button" class="btn-ghost" id="ff-cancel">Annuler</button>
        <button type="button" class="btn-primary" id="ff-save">
          ${existing ? 'Enregistrer' : 'Créer le filtre'}
        </button>
      </div>
    `;

    // ── Conditions toggle ────────────────────────────────────────────────────
    div.querySelectorAll('.condition-option').forEach(opt => {
      opt.addEventListener('click', () => {
        opt.classList.toggle('selected');
        opt.querySelector('input').checked = opt.classList.contains('selected');
      });
    });

    // ── Brand tags render ────────────────────────────────────────────────────
    function renderBrandTags() {
      const wrap = div.querySelector('#ff-brand-tags');
      if (!wrap) return;
      wrap.innerHTML = _selectedBrands.map(b =>
        `<span class="brand-tag" data-id="${b.id}">
           ${escHtml(b.title)}
           <button type="button" class="brand-tag-remove" data-id="${b.id}" title="Retirer">×</button>
         </span>`
      ).join('');
      wrap.querySelectorAll('.brand-tag-remove').forEach(btn => {
        btn.addEventListener('click', () => {
          _selectedBrands = _selectedBrands.filter(b => String(b.id) !== String(btn.dataset.id));
          renderBrandTags();
        });
      });
    }
    renderBrandTags();

    // ── Brand autocomplete ───────────────────────────────────────────────────
    const brandInput    = div.querySelector('#ff-brand-input');
    const brandDropdown = div.querySelector('#ff-brand-dropdown');
    let _debounce = null;

    brandInput.addEventListener('input', () => {
      clearTimeout(_debounce);
      const q = brandInput.value.trim();
      if (q.length < 2) { brandDropdown.classList.add('hidden'); return; }

      _debounce = setTimeout(async () => {
        try {
          const { brands } = await api.searchBrands(q);
          if (!brands.length) {
            brandDropdown.innerHTML = `<div class="brand-option-empty">Aucun résultat</div>`;
          } else {
            brandDropdown.innerHTML = brands.map(b =>
              `<div class="brand-option" data-id="${b.id}" data-title="${escHtml(b.title)}">${escHtml(b.title)}</div>`
            ).join('');
            brandDropdown.querySelectorAll('.brand-option').forEach(opt => {
              opt.addEventListener('mousedown', e => {
                e.preventDefault();
                const id = parseInt(opt.dataset.id);
                if (!_selectedBrands.find(b => b.id === id)) {
                  _selectedBrands.push({ id, title: opt.dataset.title });
                  renderBrandTags();
                }
                brandInput.value = '';
                brandDropdown.classList.add('hidden');
              });
            });
          }
          brandDropdown.classList.remove('hidden');
        } catch { brandDropdown.classList.add('hidden'); }
      }, 300);
    });

    brandInput.addEventListener('blur', () => {
      setTimeout(() => brandDropdown.classList.add('hidden'), 150);
    });

    // ── Category selector ────────────────────────────────────────────────────
    (async () => {
      const sel = div.querySelector('#ff-category');
      try {
        if (!_categoryCache) {
          const { categories } = await api.getCategories();
          _categoryCache = categories || [];
        }
        const selectedId = (f.category_ids || [])[0];
        _categoryCache.forEach(cat => {
          const opt = document.createElement('option');
          opt.value = cat.id;
          opt.textContent = cat.full_title || cat.title;
          if (selectedId && String(cat.id) === String(selectedId)) opt.selected = true;
          sel.appendChild(opt);
        });
      } catch { /* categories unavailable — select stays with "Toutes" */ }
    })();

    return div;
  }

  function read(container) {
    const name = container.querySelector('#ff-name').value.trim();
    if (!name) { toast.show('Le nom du filtre est requis.', 'warn'); return null; }

    const conditions = [...container.querySelectorAll('.condition-option.selected')]
      .map(el => el.dataset.value);

    const countrySelect = container.querySelector('#ff-countries');
    const country_codes = [...countrySelect.selectedOptions].map(o => o.value);

    const catVal = container.querySelector('#ff-category').value;
    const category_ids = catVal ? [parseInt(catVal)] : null;

    const brand_ids   = _selectedBrands.length ? _selectedBrands.map(b => b.id)    : null;
    const brand_names = _selectedBrands.length ? _selectedBrands.map(b => b.title) : null;

    return {
      name,
      keywords:      container.querySelector('#ff-keywords').value.trim() || null,
      price_min:     parseFloat(container.querySelector('#ff-price-min').value) || null,
      price_max:     parseFloat(container.querySelector('#ff-price-max').value) || null,
      max_budget:    parseFloat(container.querySelector('#ff-budget').value) || null,
      conditions:    conditions.length ? conditions : null,
      country_codes: country_codes.length ? country_codes : null,
      auto_buy:      container.querySelector('#ff-autobuy').checked,
      enabled:       container.querySelector('#ff-enabled').checked,
      brand_ids,
      brand_names,   // display-only, not persisted by backend
      category_ids,
    };
  }

  function escHtml(s) {
    return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  return { build, read };
})();
