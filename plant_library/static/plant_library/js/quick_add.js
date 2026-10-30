/* Plant Library: the + on a plant card opens a list of the member's EcoPatches and adds the plant to the one picked.
   The list lives in the card as a <template> (server-rendered, so every name is already escaped); it is cloned into
   a popover on <body>, because the card cuts off anything that sticks out. Without JavaScript each row is a plain
   form post that redirects to the EcoPatch. */
(function () {
  'use strict';
  var pop = null, opener = null;

  // A <dialog> opened with showModal() sits in the top layer, above everything on <body>: from inside the plant
  // pop-up the list and the toast have to be put in the dialog itself to be seen.
  function host(from) {
    return (from && from.closest('dialog[open]')) || document.body;
  }

  function close(refocus) {
    if (pop) { pop.remove(); pop = null; }
    if (opener) {
      opener.setAttribute('aria-expanded', 'false');
      if (refocus) opener.focus();
      opener = null;
    }
  }

  function place(button) {
    var r = button.getBoundingClientRect(), w = pop.offsetWidth, h = pop.offsetHeight;
    var left = Math.max(8, Math.min(r.right - w, window.innerWidth - w - 8));
    var top = r.bottom + 8;
    if (top + h > window.innerHeight - 8 && r.top - h - 8 > 8) top = r.top - h - 8;
    pop.style.left = left + 'px';
    pop.style.top = Math.max(8, top) + 'px';
  }

  function open(button) {
    var tpl = button.parentNode.querySelector('template');
    if (!tpl) return;
    pop = document.createElement('div');
    pop.className = 'plant-addpop';
    pop.setAttribute('role', 'dialog');
    pop.setAttribute('aria-label', 'Tambah ke EcoPatch');
    pop.appendChild(tpl.content.cloneNode(true));
    host(button).appendChild(pop);
    opener = button;
    button.setAttribute('aria-expanded', 'true');
    place(button);
    var first = pop.querySelector('button, a');
    if (first) first.focus({ preventScroll: true });
  }

  function toast(message, url, where) {
    var box = document.createElement('div');
    box.className = 'site-toasts';
    box.setAttribute('role', 'status');
    var item = document.createElement('div');
    item.className = 'site-toast';
    var body = document.createElement('div');
    body.className = 'site-toast-body';
    body.textContent = message;
    item.appendChild(body);
    if (url) {
      var link = document.createElement('a');
      link.href = url;
      link.textContent = 'Lihat';
      link.style.cssText = 'color:#8fe3a8;font-weight:800;margin-right:10px;white-space:nowrap';
      item.appendChild(link);
    }
    box.appendChild(item);
    (where || document.body).appendChild(box);
    setTimeout(function () { box.remove(); }, 5200);
  }

  document.addEventListener('click', function (event) {
    var button = event.target.closest('[data-plant-add]');
    if (button) {
      event.preventDefault();
      if (opener === button) close(false); else { close(false); open(button); }
      return;
    }
    if (pop && !pop.contains(event.target)) close(false);
  });

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && pop) { event.preventDefault(); close(true); }
  });

  window.addEventListener('resize', function () { close(false); });
  window.addEventListener('scroll', function () { close(false); }, { passive: true });

  document.addEventListener('submit', function (event) {
    var form = event.target;
    if (!pop || !pop.contains(form)) return;
    event.preventDefault();
    var where = host(pop);
    fetch(form.action, {
      method: 'POST',
      body: new FormData(form),
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest', Accept: 'application/json' }
    }).then(function (response) {
      if (!response.ok) throw new Error('status ' + response.status);
      return response.json();
    }).then(function (data) {
      close(true);
      toast(data.message, data.url, where);
    }).catch(function () {
      close(true);
      toast('Belum tersimpan. Coba lagi, atau buka halaman EcoPatch-nya.', '', where);
    });
  });
}());
