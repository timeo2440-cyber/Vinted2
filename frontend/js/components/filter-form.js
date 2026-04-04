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

  // 100+ marques populaires affichées dès le focus
  const POPULAR_BRANDS = [
    // Sportswear
    {id:53,  title:'Nike'},          {id:14,  title:'Adidas'},
    {id:27,  title:'Puma'},          {id:25,  title:'New Balance'},
    {id:23,  title:'Converse'},      {id:24,  title:'Vans'},
    {id:28,  title:'Reebok'},        {id:29,  title:'Under Armour'},
    {id:131, title:'ASICS'},         {id:134, title:'On Running'},
    {id:133, title:'Hoka'},          {id:128, title:'Arc\'teryx'},
    {id:129, title:'Salomon'},       {id:18,  title:'The North Face'},
    {id:19,  title:'Carhartt'},      {id:22,  title:'Champion'},
    {id:116, title:'Y-3'},
    // Streetwear / Hype
    {id:16,  title:'Supreme'},       {id:17,  title:'Stone Island'},
    {id:118, title:'Stüssy'},        {id:119, title:'Palace'},
    {id:120, title:'Kith'},          {id:124, title:'CP Company'},
    {id:122, title:'Amiri'},         {id:123, title:'Represent'},
    {id:117, title:'Fear of God'},   {id:15,  title:'Off-White'},
    // Luxe
    {id:88,  title:'Gucci'},         {id:99,  title:'Louis Vuitton'},
    {id:475, title:'Balenciaga'},    {id:125, title:'Moncler'},
    {id:126, title:'Canada Goose'},  {id:1,   title:'Prada'},
    {id:2,   title:'Chanel'},        {id:4,   title:'Dior'},
    {id:5,   title:'Versace'},       {id:6,   title:'Givenchy'},
    {id:7,   title:'Burberry'},      {id:8,   title:'Hermès'},
    {id:9,   title:'Saint Laurent'}, {id:10,  title:'Valentino'},
    {id:11,  title:'Bottega Veneta'},{id:12,  title:'Celine'},
    {id:13,  title:'Fendi'},         {id:89,  title:'Miu Miu'},
    {id:90,  title:'Alexander McQueen'},{id:91, title:'Moschino'},
    {id:92,  title:'Kenzo'},         {id:93,  title:'Acne Studios'},
    {id:94,  title:'Maison Margiela'},{id:95, title:'Rick Owens'},
    {id:96,  title:'Comme des Garçons'},{id:97,title:'A.P.C.'},
    {id:98,  title:'Isabel Marant'}, {id:115, title:'Jacquemus'},
    // Casual / Fast fashion
    {id:3,   title:'Zara'},          {id:26,  title:'H&M'},
    {id:65,  title:'Mango'},         {id:54,  title:'Uniqlo'},
    {id:49,  title:'Massimo Dutti'}, {id:50,  title:'COS'},
    {id:51,  title:'& Other Stories'},{id:52, title:'Arket'},
    {id:41,  title:'Pull&Bear'},     {id:43,  title:'Bershka'},
    {id:42,  title:'Stradivarius'},  {id:39,  title:'ASOS'},
    {id:55,  title:'Primark'},       {id:58,  title:'Gap'},
    {id:64,  title:'Urban Outfitters'},{id:66,title:'Free People'},
    // Denim / Classics
    {id:304, title:'Levi\'s'},       {id:81,  title:'G-Star RAW'},
    {id:82,  title:'Pepe Jeans'},    {id:83,  title:'Wrangler'},
    {id:84,  title:'Lee'},           {id:85,  title:'Replay'},
    {id:80,  title:'Diesel'},
    // Lifestyle / Preppy
    {id:1341,title:'Tommy Hilfiger'},{id:302, title:'Lacoste'},
    {id:308, title:'Calvin Klein'},  {id:109, title:'Ralph Lauren'},
    {id:36,  title:'BOSS'},          {id:37,  title:'Paul Smith'},
    {id:38,  title:'Ted Baker'},     {id:71,  title:'Barbour'},
    {id:69,  title:'Reiss'},         {id:70,  title:'AllSaints'},
    // Chaussures
    {id:33,  title:'Dr. Martens'},   {id:34,  title:'UGG'},
    {id:35,  title:'Birkenstock'},   {id:32,  title:'Timberland'},
    // Maroquinerie / Sacs
    {id:72,  title:'Mulberry'},      {id:73,  title:'Longchamp'},
    {id:74,  title:'Coach'},         {id:75,  title:'Michael Kors'},
    {id:76,  title:'Kate Spade'},    {id:78,  title:'Marc Jacobs'},
    // Français
    {id:100, title:'Sandro'},        {id:101, title:'Maje'},
    {id:102, title:'Ba&sh'},         {id:103, title:'The Kooples'},
    {id:104, title:'IRO'},           {id:105, title:'Claudie Pierlot'},
    {id:106, title:'Zadig & Voltaire'},{id:108,title:'Petit Bateau'},
    {id:107, title:'Aigle'},         {id:114, title:'agnès b.'},
    {id:113, title:'Comptoir des Cotonniers'},
  ];

  // Module-level state — reset on each build()
  let _selectedBrands     = [];
  let _selectedCategories = [];
  let _categoryCache      = null;

  function build(existing) {
    const f = existing || {};
    const condSelected = f.conditions    || [];
    const countryCodes = f.country_codes || [];

    _selectedBrands = (f.brand_ids || []).map((id, i) => ({
      id,
      title: (f.brand_names || [])[i] || `#${id}`,
    }));

    _selectedCategories = (f.category_ids || []).map((id, i) => ({
      id,
      title:      (f.category_names || [])[i] || `#${id}`,
      full_title: (f.category_names || [])[i] || `#${id}`,
    }));

    const condHtml = CONDITIONS.map(c =>
      `<div class="condition-option${condSelected.includes(c.value) ? ' selected' : ''}" data-value="${c.value}">
        ${c.label}
       </div>`
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
          <input type="text" id="ff-brand-input" placeholder="Rechercher une marque… (cliquez pour voir les populaires)" autocomplete="off">
          <div class="brand-dropdown hidden" id="ff-brand-dropdown"></div>
        </div>
        <div class="brand-tags" id="ff-brand-tags"></div>
        <small>Laisser vide = toutes les marques.</small>
      </div>

      <div class="form-group">
        <label>Catégories</label>
        <div class="brand-search-wrap">
          <input type="text" id="ff-cat-input" placeholder="Rechercher (ex: Pulls, Baskets, Robes…)" autocomplete="off">
          <div class="brand-dropdown hidden" id="ff-cat-dropdown"></div>
        </div>
        <div class="brand-tags" id="ff-cat-tags"></div>
        <small>Cliquez pour parcourir. Plusieurs catégories possibles.</small>
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
        <label>État de l'article <small style="font-weight:400;color:var(--text-muted)">(cliquez pour sélectionner, plusieurs possibles)</small></label>
        <div class="checkbox-group" id="ff-conditions">${condHtml}</div>
        <small>Laisser vide = tous les états.</small>
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

    // ── Conditions toggle (multi-select) ──────────────────────────────────────
    div.querySelectorAll('.condition-option').forEach(opt => {
      opt.addEventListener('click', () => {
        opt.classList.toggle('selected');
      });
    });

    // ── Brand tags ────────────────────────────────────────────────────────────
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

    // ── Brand autocomplete ────────────────────────────────────────────────────
    const brandInput    = div.querySelector('#ff-brand-input');
    const brandDropdown = div.querySelector('#ff-brand-dropdown');
    let _brandDebounce  = null;

    function _renderBrandOptions(brands) {
      if (!brands || !brands.length) return;
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
      brandDropdown.classList.remove('hidden');
    }

    brandInput.addEventListener('focus', () => {
      if (!brandInput.value.trim()) {
        _renderBrandOptions(POPULAR_BRANDS);
      }
    });

    brandInput.addEventListener('input', () => {
      clearTimeout(_brandDebounce);
      const q = brandInput.value.trim();
      if (q.length < 1) {
        _renderBrandOptions(POPULAR_BRANDS);
        return;
      }
      // Filter popular brands locally first for instant feedback
      const qLow = q.toLowerCase();
      const localMatches = POPULAR_BRANDS.filter(b => b.title.toLowerCase().includes(qLow));
      if (localMatches.length) _renderBrandOptions(localMatches);

      _brandDebounce = setTimeout(async () => {
        try {
          const { brands } = await api.searchBrands(q);
          if (brands && brands.length) {
            _renderBrandOptions(brands);
          } else if (!localMatches.length) {
            brandDropdown.innerHTML = `<div class="brand-option-empty">Aucun résultat pour "${escHtml(q)}"</div>`;
            brandDropdown.classList.remove('hidden');
          }
        } catch { /* keep local results */ }
      }, 300);
    });

    brandInput.addEventListener('blur', () => {
      setTimeout(() => brandDropdown.classList.add('hidden'), 200);
    });

    // ── Category tags ─────────────────────────────────────────────────────────
    function renderCategoryTags() {
      const wrap = div.querySelector('#ff-cat-tags');
      if (!wrap) return;
      wrap.innerHTML = _selectedCategories.map(c =>
        `<span class="brand-tag cat-tag" data-id="${c.id}">
           ${escHtml(c.full_title || c.title)}
           <button type="button" class="brand-tag-remove" data-id="${c.id}" title="Retirer">×</button>
         </span>`
      ).join('');
      wrap.querySelectorAll('.brand-tag-remove').forEach(btn => {
        btn.addEventListener('click', () => {
          _selectedCategories = _selectedCategories.filter(c => String(c.id) !== String(btn.dataset.id));
          renderCategoryTags();
        });
      });
    }
    renderCategoryTags();

    // ── Category autocomplete ─────────────────────────────────────────────────
    const catInput    = div.querySelector('#ff-cat-input');
    const catDropdown = div.querySelector('#ff-cat-dropdown');

    (async () => {
      try {
        if (!_categoryCache) {
          const { categories } = await api.getCategories();
          _categoryCache = categories || [];
        }
      } catch { _categoryCache = []; }
    })();

    function _addCategoryOption(catDropdown, cat) {
      const opt = document.createElement('div');
      opt.className = 'brand-option';
      opt.dataset.id    = cat.id;
      opt.dataset.title = cat.title;
      opt.dataset.full  = cat.full_title || cat.title;
      opt.textContent   = cat.full_title || cat.title;
      opt.addEventListener('mousedown', e => {
        e.preventDefault();
        const id = parseInt(opt.dataset.id);
        if (!_selectedCategories.find(c => c.id === id)) {
          _selectedCategories.push({ id, title: opt.dataset.title, full_title: opt.dataset.full });
          renderCategoryTags();
        }
        catInput.value = '';
        catDropdown.classList.add('hidden');
      });
      return opt;
    }

    function _showCategoryDropdown(q) {
      if (!_categoryCache) { catDropdown.classList.add('hidden'); return; }

      catDropdown.innerHTML = '';

      if (q.length >= 1) {
        // Search mode: flat results
        const qLow = q.toLowerCase();
        const filtered = _categoryCache
          .filter(c => (c.full_title || c.title || '').toLowerCase().includes(qLow))
          .slice(0, 40);
        if (!filtered.length) {
          catDropdown.innerHTML = `<div class="brand-option-empty">Aucune catégorie pour "${escHtml(q)}"</div>`;
        } else {
          filtered.forEach(c => catDropdown.appendChild(_addCategoryOption(catDropdown, c)));
        }
        catDropdown.classList.remove('hidden');
        return;
      }

      // Browse mode: grouped by top-level section
      const groups = {};
      const order  = [];
      for (const cat of _categoryCache) {
        const parts  = (cat.full_title || cat.title || '').split(' > ');
        const group  = parts[0] || 'Autre';
        if (!groups[group]) { groups[group] = []; order.push(group); }
        groups[group].push(cat);
      }

      for (const group of order) {
        // Section header
        const header = document.createElement('div');
        header.className = 'brand-option-header';
        header.textContent = group.toUpperCase();
        catDropdown.appendChild(header);

        for (const cat of groups[group]) {
          const opt = _addCategoryOption(catDropdown, cat);
          // Visual indentation based on depth
          const depth = (cat.full_title || '').split(' > ').length - 1;
          opt.style.paddingLeft = `${8 + depth * 12}px`;
          // Sub-categories in lighter color
          if (depth > 1) opt.style.color = 'var(--text-muted)';
          catDropdown.appendChild(opt);
        }
      }

      if (!catDropdown.children.length) {
        catDropdown.innerHTML = `<div class="brand-option-empty">Aucune catégorie disponible</div>`;
      }
      catDropdown.classList.remove('hidden');
    }

    catInput.addEventListener('focus', () => {
      _showCategoryDropdown(catInput.value.trim());
    });

    catInput.addEventListener('input', () => {
      _showCategoryDropdown(catInput.value.trim());
    });

    catInput.addEventListener('blur', () => {
      setTimeout(() => catDropdown.classList.add('hidden'), 200);
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

    const brand_ids   = _selectedBrands.length     ? _selectedBrands.map(b => b.id)             : null;
    const brand_names = _selectedBrands.length     ? _selectedBrands.map(b => b.title)           : null;

    const category_ids   = _selectedCategories.length ? _selectedCategories.map(c => c.id)       : null;
    const category_names = _selectedCategories.length ? _selectedCategories.map(c => c.full_title || c.title) : null;

    return {
      name,
      keywords:      container.querySelector('#ff-keywords').value.trim() || null,
      price_min:     parseFloat(container.querySelector('#ff-price-min').value) || null,
      price_max:     parseFloat(container.querySelector('#ff-price-max').value) || null,
      max_budget:    parseFloat(container.querySelector('#ff-budget').value)    || null,
      conditions:    conditions.length    ? conditions    : null,
      country_codes: country_codes.length ? country_codes : null,
      auto_buy:      container.querySelector('#ff-autobuy').checked,
      enabled:       container.querySelector('#ff-enabled').checked,
      brand_ids,
      brand_names,
      category_ids,
      category_names,
    };
  }

  function escHtml(s) {
    return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  return { build, read };
})();
