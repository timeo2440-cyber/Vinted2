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

  function build(existing) {
    const f = existing || {};
    const condSelected = f.conditions || [];
    const countryCodes = f.country_codes || [];

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

    // Condition toggle behavior
    div.querySelectorAll('.condition-option').forEach(opt => {
      opt.addEventListener('click', () => {
        opt.classList.toggle('selected');
        opt.querySelector('input').checked = opt.classList.contains('selected');
      });
    });

    return div;
  }

  function read(container) {
    const name = container.querySelector('#ff-name').value.trim();
    if (!name) { toast.show('Le nom du filtre est requis.', 'warn'); return null; }

    const conditions = [...container.querySelectorAll('.condition-option.selected')]
      .map(el => el.dataset.value);

    const countrySelect = container.querySelector('#ff-countries');
    const country_codes = [...countrySelect.selectedOptions].map(o => o.value);

    return {
      name,
      keywords:    container.querySelector('#ff-keywords').value.trim() || null,
      price_min:   parseFloat(container.querySelector('#ff-price-min').value) || null,
      price_max:   parseFloat(container.querySelector('#ff-price-max').value) || null,
      max_budget:  parseFloat(container.querySelector('#ff-budget').value) || null,
      conditions:  conditions.length ? conditions : null,
      country_codes: country_codes.length ? country_codes : null,
      auto_buy:    container.querySelector('#ff-autobuy').checked,
      enabled:     container.querySelector('#ff-enabled').checked,
    };
  }

  function escHtml(s) {
    return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  return { build, read };
})();
