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

  // ── Arbre de catégories (accordéon, style Vinted) ──────────────────────────
  const CATEGORY_TREE = [
    { title: 'Femmes', children: [
      { title: 'Hauts', children: [
        {id:1904,title:'T-shirts'},{id:2050,title:'Chemises'},{id:4,title:'Pulls & sweats'},
        {id:3,title:'Hoodies'},{id:1913,title:'Cardigans'},{id:1912,title:'Blouses'},
        {id:1906,title:'Débardeurs & tops'},{id:1914,title:'Crop tops'},
      ]},
      { title: 'Robes', children: [
        {id:1607,title:'Toutes les robes'},{id:1916,title:'Robes courtes'},
        {id:1917,title:'Robes longues'},{id:1918,title:'Robes mi-longues'},
      ]},
      { title: 'Bas', children: [
        {id:1609,title:'Jeans'},{id:1608,title:'Pantalons'},{id:1610,title:'Jupes'},
        {id:1617,title:'Shorts'},{id:1920,title:'Leggings'},{id:1921,title:'Joggings'},
      ]},
      { title: 'Manteaux & Vestes', children: [
        {id:6,title:'Vestes'},{id:7,title:'Manteaux'},{id:1925,title:'Doudounes'},
        {id:1926,title:'Trench-coats'},{id:1927,title:'Blazers'},{id:1928,title:'Parkas'},
        {id:2072,title:'Bombers'},
      ]},
      { title: 'Combinaisons & Maillots', children: [
        {id:1619,title:'Combinaisons'},{id:1621,title:'Maillots de bain'},{id:1622,title:'Lingerie'},
      ]},
      { title: 'Chaussures', children: [
        {id:16,title:'Baskets'},{id:1634,title:'Escarpins'},{id:1635,title:'Bottes & bottines'},
        {id:1636,title:'Sandales'},{id:1637,title:'Ballerines'},{id:1638,title:'Mocassins'},
        {id:1940,title:'Mules & sabots'},{id:1941,title:'Sport'},
      ]},
      { title: 'Sacs', children: [
        {id:1624,title:'Sacs à main'},{id:1625,title:'Sacs à dos'},
        {id:1626,title:'Sacs bandoulière'},{id:1945,title:'Pochettes'},{id:1946,title:'Tote bags'},
      ]},
      { title: 'Accessoires', children: [
        {id:1630,title:'Bijoux'},{id:1628,title:'Lunettes'},{id:1629,title:'Ceintures'},
        {id:1631,title:'Chapeaux & casquettes'},{id:1633,title:'Écharpes & foulards'},
        {id:1950,title:'Montres'},{id:1951,title:'Gants'},
      ]},
    ]},
    { title: 'Hommes', children: [
      { title: 'Hauts', children: [
        {id:1206,title:'T-shirts'},{id:2,title:'Chemises'},{id:1207,title:'Pulls & sweats'},
        {id:1208,title:'Hoodies'},{id:2060,title:'Débardeurs'},{id:2061,title:'Polos'},
      ]},
      { title: 'Bas', children: [
        {id:1212,title:'Jeans'},{id:1213,title:'Pantalons'},{id:1214,title:'Shorts'},
        {id:1215,title:'Joggings'},
      ]},
      { title: 'Manteaux & Vestes', children: [
        {id:1209,title:'Vestes'},{id:1210,title:'Manteaux'},{id:1211,title:'Doudounes'},
        {id:2070,title:'Parkas'},{id:2071,title:'Blazers'},{id:2072,title:'Bombers'},
        {id:2073,title:'Trench-coats'},
      ]},
      { title: 'Costumes', children: [{id:1216,title:'Costumes & smokings'}]},
      { title: 'Chaussures', children: [
        {id:1217,title:'Baskets'},{id:1218,title:'Bottines & boots'},{id:1219,title:'Mocassins'},
        {id:1220,title:'Sandales'},{id:2080,title:'Sport'},{id:2081,title:'Derbies & richelieus'},
      ]},
      { title: 'Sacs & Accessoires', children: [
        {id:2085,title:'Sacs à dos'},{id:2086,title:'Bananes'},{id:1221,title:'Sacs'},
        {id:1222,title:'Ceintures'},{id:1223,title:'Lunettes'},{id:1224,title:'Montres'},
        {id:1225,title:'Casquettes & chapeaux'},{id:1226,title:'Écharpes'},{id:2090,title:'Bijoux'},
      ]},
      { title: 'Sous-vêtements', children: [
        {id:2095,title:'Sous-vêtements'},{id:2096,title:'Chaussettes'},{id:2097,title:'Maillots de bain'},
      ]},
    ]},
    { title: 'Enfants', children: [
      { title: 'Bébé (0-24 mois)', children: [
        {id:1231,title:'Vêtements'},{id:1232,title:'Chaussures'},{id:2101,title:'Accessoires'},
      ]},
      { title: 'Garçons', children: [
        {id:1233,title:'T-shirts'},{id:2102,title:'Pantalons'},{id:2103,title:'Vestes'},{id:2104,title:'Chaussures'},
      ]},
      { title: 'Filles', children: [
        {id:1234,title:'Robes'},{id:2105,title:'T-shirts'},{id:2106,title:'Pantalons'},{id:2107,title:'Chaussures'},
      ]},
      { title: 'Autres', children: [
        {id:1236,title:'Chaussures enfant'},{id:1237,title:'Jouets & Jeux'},{id:1238,title:'Livres'},{id:2110,title:'Puériculture'},
      ]},
    ]},
    { title: 'Maison', children: [
      { title: 'Décoration', children: [
        {id:1781,title:'Décoration'},{id:2120,title:'Bougies & senteurs'},{id:2121,title:'Tableaux & art'},{id:2122,title:'Textiles déco'},
      ]},
      { title: 'Mobilier & Cuisine', children: [
        {id:1785,title:'Meubles'},{id:1786,title:'Luminaires'},{id:1782,title:'Linge de maison'},
        {id:1783,title:'Vaisselle'},{id:1784,title:'Électroménager'},{id:1787,title:'Jardin & Plantes'},
      ]},
    ]},
    { title: 'Sport', children: [
      { title: 'Vêtements & Chaussures', children: [
        {id:2390,title:'Vêtements sport'},{id:2391,title:'Chaussures sport'},
      ]},
      { title: 'Équipements & Sports', children: [
        {id:2392,title:'Équipement'},{id:2393,title:'Vélos'},{id:2394,title:'Ski & Snowboard'},
        {id:2395,title:'Football'},{id:2396,title:'Running'},{id:2398,title:'Tennis'},
        {id:2399,title:'Yoga & Fitness'},{id:2400,title:'Randonnée'},
      ]},
    ]},
    { title: 'Divertissement', children: [
      { title: 'Médias', children: [
        {id:1901,title:'Livres'},{id:1902,title:'Musique (CD, vinyles)'},{id:1903,title:'Films & Séries'},
        {id:2131,title:'BD & Manga'},
      ]},
      { title: 'Jeux', children: [
        {id:1905,title:'Jeux vidéo'},{id:1906,title:'Consoles'},{id:2130,title:'Jeux de société'},
      ]},
    ]},
    { title: 'Électronique', children: [
      { title: 'Appareils', children: [
        {id:2640,title:'Téléphones'},{id:2641,title:'Tablettes'},{id:2642,title:'Ordinateurs'},
        {id:2643,title:'Appareils photo'},
      ]},
      { title: 'Audio & Accessoires', children: [
        {id:2644,title:'Casques & écouteurs'},{id:2645,title:'Enceintes'},{id:2646,title:'Accessoires tech'},
      ]},
    ]},
    { title: 'Beauté', children: [
      { title: 'Soins & Maquillage', children: [
        {id:2200,title:'Parfums'},{id:2201,title:'Soins visage'},{id:2202,title:'Soins corps'},
        {id:2203,title:'Maquillage'},{id:2204,title:'Soins cheveux'},
      ]},
    ]},
  ];

  // ── Flat list (pour la recherche texte) ────────────────────────────────────
  function _flattenTree(nodes, parent = '') {
    const result = [];
    for (const node of nodes) {
      const full = parent ? `${parent} > ${node.title}` : node.title;
      if (node.id) result.push({ id: node.id, title: node.title, full_title: full });
      if (node.children) result.push(..._flattenTree(node.children, full));
    }
    return result;
  }
  const CATEGORY_FLAT = _flattenTree(CATEGORY_TREE);

  // ── Module-level state — reset on each build() ────────────────────────────
  let _selectedBrands     = [];
  let _selectedCategories = [];

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
        <div class="cat-wrap" id="ff-cat-wrap">
          <input type="text" id="ff-cat-input" placeholder="Cliquez pour parcourir ou tapez pour chercher…" autocomplete="off" readonly>
          <div class="cat-panel hidden" id="ff-cat-panel">
            <div class="cat-search-row">
              <input type="text" id="ff-cat-search" placeholder="🔍 Rechercher une catégorie…" autocomplete="off">
            </div>
            <div class="cat-tree" id="ff-cat-tree"></div>
          </div>
        </div>
        <div class="brand-tags" id="ff-cat-tags"></div>
        <small>Plusieurs catégories possibles.</small>
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
      wrap.innerHTML = _selectedBrands.map((b, i) =>
        `<span class="brand-tag" data-idx="${i}">
           ${escHtml(b.title)}${b.id === null ? ' <small style="opacity:.6">(texte)</small>' : ''}
           <button type="button" class="brand-tag-remove" data-idx="${i}" title="Retirer">×</button>
         </span>`
      ).join('');
      wrap.querySelectorAll('.brand-tag-remove').forEach(btn => {
        btn.addEventListener('click', () => {
          const idx = parseInt(btn.dataset.idx);
          _selectedBrands.splice(idx, 1);
          renderBrandTags();
        });
      });
    }
    renderBrandTags();

    // ── Brand autocomplete ────────────────────────────────────────────────────
    const brandInput    = div.querySelector('#ff-brand-input');
    const brandDropdown = div.querySelector('#ff-brand-dropdown');
    let _brandDebounce  = null;

    function _positionBrandDropdown() {
      const rect = brandInput.getBoundingClientRect();
      brandDropdown.style.position = 'fixed';
      brandDropdown.style.top   = (rect.bottom + 2) + 'px';
      brandDropdown.style.left  = rect.left + 'px';
      brandDropdown.style.width = rect.width + 'px';
    }

    function _renderBrandOptions(brands, query) {
      let html = brands.map(b =>
        `<div class="brand-option" data-id="${b.id}" data-title="${escHtml(b.title)}">${escHtml(b.title)}</div>`
      ).join('');
      // Allow adding any brand by name (for niche brands not in the list)
      if (query && query.trim().length > 1) {
        html += `<div class="brand-option brand-option-manual" data-id="" data-title="${escHtml(query.trim())}">
          ➕ Ajouter "${escHtml(query.trim())}" manuellement
        </div>`;
      }
      brandDropdown.innerHTML = html;
      brandDropdown.querySelectorAll('.brand-option').forEach(opt => {
        opt.addEventListener('mousedown', e => {
          e.preventDefault();
          const rawId = opt.dataset.id;
          const title = opt.dataset.title;
          const id = rawId ? parseInt(rawId) : null;
          const key = id !== null ? id : title;
          if (!_selectedBrands.find(b => (b.id !== null ? b.id : b.title) === key)) {
            _selectedBrands.push({ id, title });
            renderBrandTags();
          }
          brandInput.value = '';
          brandDropdown.classList.add('hidden');
        });
      });
      _positionBrandDropdown();
      brandDropdown.classList.remove('hidden');
    }

    brandInput.addEventListener('focus', () => {
      if (!brandInput.value.trim()) {
        _renderBrandOptions(POPULAR_BRANDS, '');
      }
    });

    brandInput.addEventListener('input', () => {
      clearTimeout(_brandDebounce);
      const q = brandInput.value.trim();
      if (q.length < 1) {
        _renderBrandOptions(POPULAR_BRANDS, '');
        return;
      }
      // Filter popular brands locally first for instant feedback
      const qLow = q.toLowerCase();
      const localMatches = POPULAR_BRANDS.filter(b => b.title.toLowerCase().includes(qLow));
      _renderBrandOptions(localMatches.length ? localMatches : [], q);

      _brandDebounce = setTimeout(async () => {
        try {
          const { brands } = await api.searchBrands(q);
          if (brands && brands.length) {
            _renderBrandOptions(brands, q);
          }
        } catch { /* keep local results */ }
      }, 300);
    });

    brandInput.addEventListener('keydown', e => {
      if (e.key === 'Enter') {
        e.preventDefault();
        const q = brandInput.value.trim();
        if (q.length > 1 && !_selectedBrands.find(b => b.title.toLowerCase() === q.toLowerCase())) {
          _selectedBrands.push({ id: null, title: q });
          renderBrandTags();
          brandInput.value = '';
          brandDropdown.classList.add('hidden');
        }
      }
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

    // ── Category accordion panel ──────────────────────────────────────────────
    const catWrap  = div.querySelector('#ff-cat-wrap');
    const catInput = div.querySelector('#ff-cat-input');
    const catPanel = div.querySelector('#ff-cat-panel');
    const catSearch= div.querySelector('#ff-cat-search');
    const catTree  = div.querySelector('#ff-cat-tree');

    function _selectCategory(id, title, full) {
      if (!_selectedCategories.find(c => c.id === id)) {
        _selectedCategories.push({ id, title, full_title: full });
        renderCategoryTags();
      }
      // Panel stays open so user can select multiple categories
      _updateCatInput();
    }

    function _updateCatInput() {
      const n = _selectedCategories.length;
      catInput.placeholder = n ? `${n} catégorie(s) — cliquez pour en ajouter` : 'Cliquez pour parcourir ou tapez pour chercher…';
    }

    function _openCatPanel() {
      // Position fixed so it's not clipped by the modal's overflow-y:auto
      const rect = catInput.getBoundingClientRect();
      catPanel.style.position = 'fixed';
      catPanel.style.top   = (rect.bottom + 4) + 'px';
      catPanel.style.left  = rect.left + 'px';
      catPanel.style.width = rect.width + 'px';
      catPanel.classList.remove('hidden');
      catSearch.focus();
      _renderTree(CATEGORY_TREE);
    }

    function _closeCatPanel() {
      catPanel.classList.add('hidden');
      catSearch.value = '';
    }

    // Build accordion tree
    function _renderTree(nodes, parent = '') {
      catTree.innerHTML = '';
      nodes.forEach(node => {
        const full = parent ? `${parent} > ${node.title}` : node.title;
        const hasChildren = node.children && node.children.length;

        const section = document.createElement('div');
        section.className = 'cat-section';

        const header = document.createElement('div');
        header.className = 'cat-section-header';

        if (hasChildren) {
          const arrow = document.createElement('span');
          arrow.className = 'cat-arrow';
          arrow.innerHTML = '&#9654;'; // ▶
          header.appendChild(arrow);
        } else {
          header.style.paddingLeft = '26px';
        }

        const label = document.createElement('span');
        label.textContent = node.title;
        header.appendChild(label);

        // Leaf node or parent (both selectable)
        if (node.id) {
          header.classList.add('cat-selectable');
          header.addEventListener('click', () => _selectCategory(node.id, node.title, full));
        }

        if (hasChildren) {
          const childWrap = document.createElement('div');
          childWrap.className = 'cat-children hidden';

          node.children.forEach(child => {
            const childFull = `${full} > ${child.title}`;
            if (child.children && child.children.length) {
              // Sub-section
              const subSection = document.createElement('div');
              subSection.className = 'cat-section';

              const subHeader = document.createElement('div');
              subHeader.className = 'cat-section-header cat-sub-header';
              const subArrow = document.createElement('span');
              subArrow.className = 'cat-arrow';
              subArrow.innerHTML = '&#9654;';
              subHeader.appendChild(subArrow);
              subHeader.appendChild(Object.assign(document.createElement('span'), {textContent: child.title}));

              const subChildren = document.createElement('div');
              subChildren.className = 'cat-children hidden';

              child.children.forEach(leaf => {
                const leafFull = `${childFull} > ${leaf.title}`;
                const leafEl = document.createElement('div');
                leafEl.className = 'cat-item';
                leafEl.textContent = leaf.title;
                leafEl.addEventListener('click', () => _selectCategory(leaf.id, leaf.title, leafFull));
                subChildren.appendChild(leafEl);
              });

              subHeader.addEventListener('click', () => {
                const open = !subChildren.classList.contains('hidden');
                subChildren.classList.toggle('hidden', open);
                subArrow.classList.toggle('open', !open);
              });

              subSection.appendChild(subHeader);
              subSection.appendChild(subChildren);
              childWrap.appendChild(subSection);
            } else {
              // Leaf
              const leafEl = document.createElement('div');
              leafEl.className = 'cat-item';
              leafEl.textContent = child.title;
              leafEl.addEventListener('click', () => _selectCategory(child.id, child.title, childFull));
              childWrap.appendChild(leafEl);
            }
          });

          header.addEventListener('click', (e) => {
            if (node.id) return; // selectable nodes don't expand on click
            const open = !childWrap.classList.contains('hidden');
            childWrap.classList.toggle('hidden', open);
            header.querySelector('.cat-arrow').classList.toggle('open', !open);
          });

          // For non-leaf sections, clicking arrow expands
          const arrow = header.querySelector('.cat-arrow');
          if (arrow && !node.id) {
            arrow.addEventListener('click', (e) => {
              e.stopPropagation();
              const open = !childWrap.classList.contains('hidden');
              childWrap.classList.toggle('hidden', open);
              arrow.classList.toggle('open', !open);
            });
          } else if (arrow && node.id) {
            // Parent that is also selectable: arrow expands, label selects
            header.addEventListener('click', (e) => {});
            arrow.addEventListener('click', (e) => {
              e.stopPropagation();
              const open = !childWrap.classList.contains('hidden');
              childWrap.classList.toggle('hidden', open);
              arrow.classList.toggle('open', !open);
            });
            label.addEventListener('click', (e) => {
              e.stopPropagation();
              _selectCategory(node.id, node.title, full);
            });
          }

          section.appendChild(header);
          section.appendChild(childWrap);
        } else {
          section.appendChild(header);
        }

        catTree.appendChild(section);
      });
    }

    // Search in flat list
    function _renderSearch(q) {
      catTree.innerHTML = '';
      const qLow = q.toLowerCase();
      const matches = CATEGORY_FLAT.filter(c =>
        (c.full_title || c.title || '').toLowerCase().includes(qLow)
      ).slice(0, 50);

      if (!matches.length) {
        catTree.innerHTML = `<div style="padding:10px 14px;color:var(--text-muted);font-size:13px">Aucun résultat</div>`;
        return;
      }
      matches.forEach(c => {
        const el = document.createElement('div');
        el.className = 'cat-item cat-search-result';
        el.innerHTML = `<span style="color:var(--text-muted);font-size:11px">${escHtml((c.full_title||'').split(' > ').slice(0,-1).join(' > '))}</span>
          <span style="margin-left:4px">${escHtml(c.title)}</span>`;
        el.addEventListener('click', () => _selectCategory(c.id, c.title, c.full_title));
        catTree.appendChild(el);
      });
    }

    catInput.addEventListener('click', () => {
      if (catPanel.classList.contains('hidden')) _openCatPanel();
      else _closeCatPanel();
    });

    catSearch.addEventListener('input', () => {
      const q = catSearch.value.trim();
      if (q.length >= 1) _renderSearch(q);
      else _renderTree(CATEGORY_TREE);
    });

    // Close on outside click
    document.addEventListener('mousedown', function onOutside(e) {
      if (!catWrap.contains(e.target)) {
        _closeCatPanel();
        document.removeEventListener('mousedown', onOutside);
      }
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

    // Brands with id=null are text-only (niche brands added manually)
    const brandsWithId    = _selectedBrands.filter(b => b.id !== null);
    const brand_ids   = brandsWithId.length       ? brandsWithId.map(b => b.id)   : null;
    const brand_names = _selectedBrands.length    ? _selectedBrands.map(b => b.title) : null;

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
