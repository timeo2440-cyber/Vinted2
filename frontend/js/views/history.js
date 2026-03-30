const historyView = (() => {
  let currentPage = 1;
  let loading = false;

  function init() {
    loadHistory();
  }

  async function loadHistory(page = 1) {
    if (loading) return;
    loading = true;
    currentPage = page;
    try {
      const purchases = await api.getPurchases(page);
      renderTable(purchases, page);
    } catch (e) {
      toast.show('Erreur historique : ' + e.message, 'error');
    } finally {
      loading = false;
    }
  }

  function renderTable(purchases, page) {
    const tbody  = document.getElementById('history-tbody');
    const empty  = document.getElementById('history-empty');
    const table  = document.getElementById('history-table');

    if (!purchases.length && page === 1) {
      table.style.display = 'none';
      empty.style.display = 'flex';
      return;
    }
    table.style.display = '';
    empty.style.display = 'none';

    if (page === 1) tbody.innerHTML = '';

    const filters = store.get('filters') || [];
    const filterMap = Object.fromEntries(filters.map(f => [f.id, f.name]));

    purchases.forEach(p => {
      const tr = document.createElement('tr');
      const date = p.attempted_at ? new Date(p.attempted_at).toLocaleString('fr-FR') : '—';
      const statusHtml = statusCell(p.status);
      const filterName = p.filter_id ? (filterMap[p.filter_id] || `Filtre #${p.filter_id}`) : '—';

      tr.innerHTML = `
        <td style="max-width:220px" class="truncate">${escHtml(p.item_title || '—')}</td>
        <td style="font-weight:600;white-space:nowrap">${p.price != null ? p.price.toFixed(2) + ' €' : '—'}</td>
        <td style="color:var(--text-muted)">${escHtml(filterName)}</td>
        <td>${statusHtml}</td>
        <td style="color:var(--text-muted);white-space:nowrap;font-size:12px">${date}</td>
      `;
      tbody.appendChild(tr);
    });

    // Pagination hint
    let pager = document.getElementById('history-pager');
    if (!pager) {
      pager = document.createElement('div');
      pager.id = 'history-pager';
      pager.style.cssText = 'display:flex;justify-content:center;gap:10px;padding:16px';
      document.getElementById('history-table-wrap').appendChild(pager);
    }
    pager.innerHTML = purchases.length === 50
      ? `<button class="btn-ghost btn-sm" id="history-more">Charger plus</button>` : '';
    pager.querySelector('#history-more')?.addEventListener('click', () => loadHistory(currentPage + 1));
  }

  function statusCell(status) {
    const map = {
      success:  ['bought', 'Acheté'],
      failed:   ['failed', 'Échec'],
      pending:  ['buying', 'En cours'],
      skipped:  ['new',    'Ignoré'],
    };
    const [cls, label] = map[status] || ['new', status];
    return `<span class="badge-status ${cls}">${label}</span>`;
  }

  function escHtml(s) {
    return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  return { init, reload: () => loadHistory(1) };
})();
