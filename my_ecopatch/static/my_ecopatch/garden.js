/* Forms remain functional when HTMX or JavaScript is unavailable. */
(() => {
  // Keep real selects for POST/no-JS; enhance them with the same Bootstrap
  // dropdown pattern and patch-menu styles used elsewhere in the project.
  function enhanceSelects() {
    if (!window.bootstrap?.Dropdown) return;
    document.querySelectorAll('.mep-module .patch-form select, .mep-module .plant-status-select').forEach(select => {
      if (select.dataset.enhanced) return;
      const wrapper = document.createElement('div');
      wrapper.className = 'dropdown mep-select';
      if (select.classList.contains('plant-status-select')) wrapper.classList.add('mep-select-status');
      const trigger = document.createElement('button');
      trigger.type = 'button';
      trigger.id = select.id + '-control';
      trigger.className = 'patch-select-btn dropdown-toggle';
      trigger.dataset.bsToggle = 'dropdown';
      trigger.setAttribute('aria-expanded', 'false');
      trigger.setAttribute('aria-haspopup', 'menu');
      for (const attr of ['aria-describedby', 'aria-invalid']) {
        if (select.hasAttribute(attr)) trigger.setAttribute(attr, select.getAttribute(attr));
      }
      const label = document.querySelector('label[for="' + select.id + '"]');
      if (label) {
        label.htmlFor = trigger.id;
        label.id ||= select.id + '-label';
        trigger.setAttribute('aria-labelledby', label.id + ' ' + trigger.id);
      }
      const menu = document.createElement('ul');
      menu.className = 'dropdown-menu patch-menu';
      menu.setAttribute('role', 'menu');
      menu.setAttribute('aria-labelledby', trigger.id);
      const sync = () => {
        trigger.textContent = select.selectedOptions[0]?.textContent || 'Pilih…';
        menu.querySelectorAll('button').forEach(option => {
          const active = option.dataset.value === select.value;
          option.classList.toggle('active', active);
          option.setAttribute('aria-checked', String(active));
        });
      };
      for (const option of select.options) {
        const item = document.createElement('li');
        item.setAttribute('role', 'none');
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'dropdown-item patch-menu-item';
        button.setAttribute('role', 'menuitemradio');
        button.dataset.value = option.value;
        button.textContent = option.textContent;
        button.disabled = option.disabled;
        button.addEventListener('click', () => {
          select.value = option.value;
          select.dispatchEvent(new Event('change', {bubbles: true}));
          bootstrap.Dropdown.getOrCreateInstance(trigger).hide();
          trigger.focus();
        });
        item.append(button);
        menu.append(item);
      }
      select.before(wrapper);
      wrapper.append(trigger, menu, select);
      select.hidden = true;
      select.dataset.enhanced = 'true';
      select.addEventListener('change', sync);
      select.form?.addEventListener('reset', () => setTimeout(sync, 0));
      sync();
    });
  }
  enhanceSelects();
  document.body.classList.add('mep-js');

  // The add form is folded away once there are plants; every "add a plant" link opens it and moves there.
  const addPlant = () => document.getElementById('add-plant');
  function openAddPlant(focus) {
    const box = addPlant();
    if (!box) return;
    box.open = true;
    box.scrollIntoView({behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start'});
    if (focus) (document.getElementById('id_plant-control') || box.querySelector('select, input'))?.focus({preventScroll: true});
  }
  document.addEventListener('click', event => {
    const link = event.target.closest('a[href="#add-plant"]');
    if (!link || !addPlant()) return;
    event.preventDefault();
    openAddPlant(true);
  });
  if (location.hash === '#add-plant') openAddPlant(false);

  // HTMX's native confirm is replaced by a themed, focus-trapped dialog.
  const dialog = document.createElement('dialog');
  dialog.className = 'mep-delete-dialog';
  dialog.setAttribute('aria-labelledby', 'mep-delete-title');
  dialog.setAttribute('aria-describedby', 'mep-delete-copy');
  dialog.innerHTML = '<form method="dialog"><span class="mep-delete-icon" aria-hidden="true">×</span><h2 id="mep-delete-title">Hapus tanaman?</h2><p id="mep-delete-copy"></p><p class="patch-help">Tindakan ini tidak bisa dibatalkan.</p><div class="mep-dialog-actions"><button class="btn btn-outline-success" value="cancel" autofocus>Batal</button><button class="btn btn-success patch-btn-danger" value="delete">Ya, hapus tanaman</button></div></form>';
  document.body.append(dialog);
  let pendingDelete = null;
  let deleteTrigger = null;
  document.addEventListener('htmx:confirm', event => {
    const source = event.detail.elt;
    if (!source.matches('.mep-module .plant-remove') || !event.detail.question) return;
    event.preventDefault();
    if (!dialog.showModal) { window.location.assign(source.href); return; }
    if (dialog.open) return;
    deleteTrigger = source;
    pendingDelete = () => event.detail.issueRequest(true);
    dialog.querySelector('#mep-delete-copy').textContent = event.detail.question;
    dialog.returnValue = 'cancel';
    dialog.showModal();
  });
  dialog.addEventListener('close', () => {
    const request = pendingDelete;
    pendingDelete = null;
    if (deleteTrigger?.isConnected) deleteTrigger.focus({preventScroll: true});
    if (dialog.returnValue === 'delete') request?.();
  });
  dialog.addEventListener('cancel', () => { dialog.returnValue = 'cancel'; });
  dialog.addEventListener('click', event => {
    if (event.target !== dialog) return;
    const rect = dialog.getBoundingClientRect();
    if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) dialog.close('cancel');
  });
  let focusId = null;
  const error = () => document.getElementById('mep-network');
  document.addEventListener('htmx:beforeRequest', event => {
    if (!event.detail.elt.closest('#patch-plants')) return;
    focusId = document.activeElement?.id;
    if (error()) error().textContent = '';
  });
  document.addEventListener('htmx:afterSwap', event => {
    if (event.detail.target.id !== 'patch-plants') return;
    enhanceSelects();
    const panel = document.getElementById('patch-plants');
    const invalid = panel.querySelector('[aria-invalid="true"]');
    const target = invalid || (focusId && document.getElementById(focusId));
    if (target) (document.getElementById(target.id + '-control') || target).focus({preventScroll: !invalid});
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
