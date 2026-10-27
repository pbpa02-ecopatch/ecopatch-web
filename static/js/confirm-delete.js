/* One themed confirmation pop-up for every delete button.
   Mark a link or a form with data-confirm-delete (and, if you like, data-confirm-title / -name / -note / -yes):
     <a href="/x/delete/" data-confirm-delete data-confirm-name="Balkon">   opens the pop-up, then POSTs to the href
     <form method="post" data-confirm-delete ...>                           opens the pop-up, then submits the form
   Code that builds its own buttons can call window.siteConfirmDelete({title, name, note, yes}, onYes).
   Everything shown is put in with textContent. Without <dialog>/JavaScript a link still opens its confirmation page
   and a form falls back to the browser's own confirm() (see the onsubmit on those forms). */
(function () {
  'use strict';
  if (typeof HTMLDialogElement !== 'function') return;

  var dialog = null, opener = null, onYes = null;

  function build() {
    dialog = document.createElement('dialog');
    dialog.className = 'confirm-dialog';
    dialog.setAttribute('aria-labelledby', 'confirm-dialog-title');
    dialog.setAttribute('aria-describedby', 'confirm-dialog-text');
    dialog.innerHTML =
      '<form method="dialog">' +
      '<span class="confirm-dialog-icon" aria-hidden="true">&times;</span>' +
      '<h2 id="confirm-dialog-title"></h2>' +
      '<div id="confirm-dialog-text"><p class="confirm-dialog-name"></p><p class="confirm-dialog-note"></p></div>' +
      '<div class="confirm-dialog-actions">' +
      '<button type="submit" value="cancel" class="confirm-btn confirm-btn--ghost" autofocus>Batal</button>' +
      '<button type="submit" value="delete" class="confirm-btn confirm-btn--danger"></button>' +
      '</div></form>';
    document.body.appendChild(dialog);
    dialog.addEventListener('cancel', function () { dialog.returnValue = 'cancel'; });
    dialog.addEventListener('click', function (event) {
      if (event.target !== dialog) return;
      var r = dialog.getBoundingClientRect();
      if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) dialog.close('cancel');
    });
    dialog.addEventListener('close', function () {
      var run = dialog.returnValue === 'delete' ? onYes : null;
      onYes = null;
      if (!run && opener && opener.isConnected) opener.focus({ preventScroll: true });
      if (run) run();
    });
  }

  function show(options, yes) {
    if (!dialog) build();
    if (dialog.open) return;
    var name = dialog.querySelector('.confirm-dialog-name');
    var note = dialog.querySelector('.confirm-dialog-note');
    dialog.querySelector('h2').textContent = options.title || 'Hapus?';
    name.textContent = options.name ? '“' + options.name + '”' : '';
    name.hidden = !options.name;
    note.textContent = options.note || 'Tindakan ini tidak bisa dibatalkan.';
    dialog.querySelector('.confirm-btn--danger').textContent = options.yes || 'Ya, hapus';
    dialog.returnValue = 'cancel';
    onYes = yes;
    dialog.showModal();
  }

  function optionsOf(element) {
    var d = element.dataset;
    return { title: d.confirmTitle, name: d.confirmName, note: d.confirmNote, yes: d.confirmYes };
  }

  window.siteConfirmDelete = function (options, yes) {
    opener = document.activeElement;
    show(options || {}, yes);
  };

  document.addEventListener('click', function (event) {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    var link = event.target.closest('a[data-confirm-delete]');
    if (!link) return;
    var shared = document.getElementById('site-delete-form');
    if (!shared) return; // no way to post from here: let the link open its confirmation page
    event.preventDefault();
    opener = link;
    show(optionsOf(link), function () {
      shared.action = link.href;
      shared.submit();
    });
  });

  document.addEventListener('submit', function (event) {
    var form = event.target.closest('form[data-confirm-delete]');
    if (!form || form.dataset.confirmed === '1') return;
    event.preventDefault();
    opener = event.submitter || document.activeElement;
    show(optionsOf(form), function () {
      form.dataset.confirmed = '1';
      if (form.requestSubmit) form.requestSubmit(); else form.submit();
    });
  });
}());
