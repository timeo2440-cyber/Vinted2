const modal = (() => {
  const overlay = () => document.getElementById('modal-overlay');
  const box     = () => document.getElementById('modal-box');
  const title   = () => document.getElementById('modal-title');
  const body    = () => document.getElementById('modal-body');

  function open(titleText, content) {
    title().textContent = titleText;
    if (typeof content === 'string') {
      body().innerHTML = content;
    } else {
      body().innerHTML = '';
      body().appendChild(content);
    }
    overlay().classList.remove('hidden');
  }

  function close() {
    overlay().classList.add('hidden');
    body().innerHTML = '';
  }

  function onConfirm(selector, cb) {
    const btn = body().querySelector(selector);
    if (btn) btn.addEventListener('click', cb);
  }

  // Init close button
  document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('modal-close').addEventListener('click', close);
    overlay().addEventListener('click', e => {
      if (e.target === overlay()) close();
    });
  });

  return { open, close, onConfirm };
})();
