/* Plant Library: clicking a plant card opens its sheet in a pop-up instead of leaving the list.
   The sheet is the same server-rendered markup as the detail page (asked for with X-Requested-With, so it comes without
   the page around it), which keeps every name escaped. The links still work as plain pages: with Ctrl/Cmd/Shift-click, a
   middle click, without <dialog>, or when the request fails. */
(function () {
  'use strict';
  var dialog = null, opener = null, requestId = 0;

  function build() {
    dialog = document.createElement('dialog');
    dialog.className = 'plant-modal';
    dialog.setAttribute('aria-labelledby', 'plant-modal-title');
    dialog.innerHTML = '<button type="button" class="plant-modal-x" data-plant-close aria-label="Tutup">&times;</button><div class="plant-modal-body"></div>';
    // inside .plant-page so the page's colour variables reach the sheet
    (document.querySelector('.plant-page') || document.body).appendChild(dialog);
    dialog.addEventListener('click', function (event) {
      if (event.target === dialog || event.target.closest('[data-plant-close]')) dialog.close();
    });
    dialog.addEventListener('close', function () {
      requestId++;
      if (opener && opener.isConnected) opener.focus({ preventScroll: true });
    });
  }

  function show(url) {
    var body = dialog.querySelector('.plant-modal-body');
    if (!dialog.open) dialog.showModal();
    body.innerHTML = '<p class="plant-modal-loading">Memuat tanaman&hellip;</p>';
    var mine = ++requestId;
    fetch(url, { credentials: 'same-origin', headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function (response) {
        if (!response.ok) throw new Error('status ' + response.status);
        return response.text();
      })
      .then(function (html) {
        if (mine !== requestId) return;
        body.innerHTML = html;
        var title = body.querySelector('#plant-modal-title');
        if (title) { title.tabIndex = -1; title.focus({ preventScroll: true }); }
      })
      .catch(function () {
        if (mine === requestId) window.location.assign(url);
      });
  }

  document.addEventListener('click', function (event) {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    if (typeof HTMLDialogElement !== 'function') return;
    var link = event.target.closest('[data-plant-open]');
    var card = event.target.closest('.plant-card');
    // anywhere on the card opens it, except its own buttons and links (the + and the staff tools)
    if (!link && card && !event.target.closest('a, button, .plant-add, .plant-card-tools')) link = card.querySelector('[data-plant-open]');
    if (!link) return;
    event.preventDefault();
    if (!dialog) build();
    opener = link;
    show(link.href);
  });
}());
