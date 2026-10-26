/* Forms remain functional when HTMX or JavaScript is unavailable. */
(() => {
  let focusId = null;
  const error = () => document.getElementById('mep-network');
  document.addEventListener('htmx:beforeRequest', event => {
    if (!event.detail.elt.closest('#patch-plants')) return;
    focusId = document.activeElement?.id;
    if (error()) error().textContent = '';
  });
  document.addEventListener('htmx:afterSwap', event => {
    if (event.detail.target.id !== 'patch-plants') return;
    const panel = document.getElementById('patch-plants');
    const invalid = panel.querySelector('[aria-invalid="true"]');
    const target = invalid || (focusId && document.getElementById(focusId));
    if (target) target.focus({preventScroll: !invalid});
    else {
      const message = panel.querySelector('[role="status"]');
      message.tabIndex = -1;
      message.focus({preventScroll: true});
    }
  });
  ['htmx:responseError', 'htmx:sendError', 'htmx:timeout'].forEach(name => {
    document.addEventListener(name, event => {
      if (!event.detail.elt.closest('#patch-plants') || !error()) return;
      error().textContent = 'Perubahan belum tersimpan. Periksa koneksi, lalu coba lagi. Jika sesi berakhir, muat ulang halaman untuk masuk kembali.';
      error().focus();
    });
  });
})();
