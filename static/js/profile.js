/* Profil Saya: bagian atas halaman adalah pratinjau langsung dari isian di bawahnya.
   Foto (unggahan atau wajah Petak), nama, kota, deskripsi dan kontak diubah di draf; tidak ada yang tersimpan
   sampai tombol Simpan (form biasa, dengan server yang memeriksa semuanya). "Buang" mengembalikan ke yang tersimpan. */
(function () {
  'use strict';
  var form = document.getElementById('pf-form');
  if (!form) return;

  function $(selector, root) { return (root || document).querySelector(selector); }
  function esc(text) {
    return String(text).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; });
  }

  var MAX_BYTES = 2 * 1024 * 1024;
  var TYPES = /^image\/(jpeg|png|webp)$/;
  var F = {
    first: $('#id_first_name'), last: $('#id_last_name'), city: $('#id_city'), bio: $('#id_bio'),
    wa: $('#id_whatsapp'), ig: $('#id_instagram'), em: $('#id_email'),
  };
  var fileInput = $('#id_avatar');
  var petakInput = $('#id_avatar_petak');
  var removeFlag = $('#id_remove_avatar');
  var avatarBtn = $('#avatar-btn');
  var avatarImg = $('#pf-avimg');
  var removeBtn = $('#avatar-remove');
  var photoErr = $('#pf-photo-err');
  var menu = $('#pf-menu');
  var veil = $('#pf-veil');
  var saveBar = $('#pf-savebar');
  var toastEl = $('#pf-toast');
  var sub = $('#pf-sub');
  var nameEl = $('#pf-name');
  var USERNAME = sub.dataset.user;
  var SINCE = sub.dataset.since;
  var FALLBACK = nameEl.dataset.fallback;

  // wajah Petak (empat suasana) diambil dari <template>, supaya tidak ditulis berulang di halaman
  var PETS = {};
  var LABELS = {};
  [].forEach.call($('#pf-pets').content.children, function (box) {
    PETS[box.dataset.v] = box.innerHTML;
    LABELS[box.dataset.v] = box.dataset.label;
  });

  /* ------------------------------------------------------------------ keadaan: yang tersimpan dan draf */
  function readFields() {
    var values = {};
    Object.keys(F).forEach(function (key) { values[key] = F[key].value; });
    return values;
  }
  var existingPhotoUrl = (function () { var img = $('img', avatarImg); return img ? img.getAttribute('src') : null; })();
  var savedAvatar = petakInput.value ? { kind: 'petak', petak: petakInput.value }
    : existingPhotoUrl ? { kind: 'photo', url: existingPhotoUrl, fresh: false } : { kind: 'none' };
  var savedFields = readFields();
  var avatar = JSON.parse(JSON.stringify(savedAvatar));
  var pickedFile = null;
  // setelah kiriman yang ditolak server, isian terisi ulang dari kiriman itu: tetap dianggap belum disimpan
  var forceDirty = !!form.querySelector('.pf-err');
  var submitting = false;

  function copyAvatar(a) { return JSON.parse(JSON.stringify(a)); }

  function initialLetter() {
    var name = ((F.first.value + ' ' + F.last.value).trim() || FALLBACK);
    return name.charAt(0).toUpperCase();
  }

  /* ------------------------------------------------------------------ pratinjau */
  function renderAvatar() {
    avatarImg.classList.toggle('is-none', avatar.kind === 'none');
    if (avatar.kind === 'photo') avatarImg.innerHTML = '<img src="' + esc(avatar.url) + '" alt="">';
    else if (avatar.kind === 'petak') avatarImg.innerHTML = PETS[avatar.petak];
    else avatarImg.innerHTML = '<span aria-hidden="true">' + esc(initialLetter()) + '</span>';
    removeBtn.hidden = avatar.kind === 'none';
  }

  function renderIdentity() {
    var full = (F.first.value + ' ' + F.last.value).trim();
    nameEl.textContent = full || FALLBACK;
    var city = F.city.value ? F.city.options[F.city.selectedIndex].text : '';
    sub.innerHTML = '<span class="pf-h">' + esc(USERNAME) + '</span>' + (city ? '<span class="pf-h">' + esc(city) + '</span>' : '') +
      '<span class="pf-h">' + esc(SINCE) + '</span>';
    var bio = F.bio.value.trim();
    $('#pf-bio').innerHTML = bio ? esc(bio).replace(/\n/g, '<br>') : '<button type="button" class="pf-lnk" data-focus="id_bio">Tambahkan deskripsi singkat</button>';
    var icons = {
      wa: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 19l1.2-3.8A7.5 7.5 0 1 1 9 18z"/><path d="M9.5 9.5c.3 2 2 3.7 4 4.2l1.2-1.2-1.8-1-.8.6c-.6-.3-1.2-.9-1.5-1.5l.6-.8-1-1.8z"/></svg>',
      ig: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="4" width="16" height="16" rx="5"/><circle cx="12" cy="12" r="3.6"/><circle cx="16.8" cy="7.2" r=".6" fill="currentColor"/></svg>',
      em: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3.5" y="5.5" width="17" height="13" rx="3"/><path d="M4 8l8 5.5L20 8"/></svg>',
    };
    var links = [];
    if (F.wa.value.trim()) links.push(icons.wa + esc(F.wa.value.trim()));
    var ig = F.ig.value.trim().replace(/^(https?:\/\/)?(www\.)?instagram\.com\//i, '').replace(/^@/, '').replace(/[/?].*$/, '');
    if (ig) links.push(icons.ig + '@' + esc(ig));
    if (F.em.value.trim()) links.push(icons.em + esc(F.em.value.trim()));
    var list = $('#pf-links');
    list.innerHTML = links.map(function (html) { return '<li>' + html + '</li>'; }).join('');
    list.hidden = !links.length;
  }

  function steps() {
    return [
      ['Foto', avatar.kind !== 'none', 'avatar-btn'],
      ['Nama', !!F.first.value.trim(), 'id_first_name'],
      ['Kota', !!F.city.value, 'id_city'],
      ['Deskripsi', !!F.bio.value.trim(), 'id_bio'],
      ['Kontak', !!(F.wa.value.trim() || F.ig.value.trim()), 'id_whatsapp'],
    ];
  }

  function renderProgress() {
    var list = steps();
    var done = list.filter(function (s) { return s[1]; }).length;
    var next = list.filter(function (s) { return !s[1]; })[0];
    var comp = $('#pf-comp');
    if (done === list.length) {
      comp.innerHTML = '<span class="pf-ok"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>Profil lengkap</span>';
    } else {
      var label = next[0] === 'Foto' ? 'Tambah foto' : next[0] === 'Kontak' ? 'Tambah kontak' : 'Isi ' + next[0].toLowerCase();
      comp.innerHTML = '<span class="pf-sqs" aria-hidden="true">' + list.map(function (s) { return '<i class="pf-sq' + (s[1] ? ' on' : '') + '"></i>'; }).join('') + '</span>' +
        '<span>' + done + ' dari 5 terisi</span><button type="button" class="pf-lnk" data-focus="' + next[2] + '">' + label + '</button>';
    }
    // Petak: bangga kalau lengkap, kalau belum penasaran dan menunjuk langkah berikutnya
    var mood = done === list.length ? 'proud' : 'curious';
    $('#pf-pet').innerHTML = PETS[mood];
    $('#pf-bubble').textContent = done === list.length ? 'Profilmu sudah lengkap. Mantap!'
      : 'Hai! Profilmu baru ' + done + ' dari 5 terisi. Yuk lengkapi ' + next[0].toLowerCase() + '.';
  }

  function renderHelp() {
    var help = $('#pf-city-help');
    if (help) {
      help.textContent = F.city.value ? 'Smart Care akan memakai cuaca ' + F.city.options[F.city.selectedIndex].text + '.'
        : 'Pilih kota supaya Smart Care menampilkan cuaca yang pas.';
    }
    $('#pf-bio-count').textContent = F.bio.value.length + ' / 300';
  }

  /* ------------------------------------------------------------------ yang dikirim ke server */
  function syncAvatarInputs() {
    petakInput.value = avatar.kind === 'petak' ? avatar.petak : '';
    // foto lama dihapus hanya kalau tadinya ada foto dan sekarang tidak ada foto sama sekali
    removeFlag.checked = savedAvatar.kind === 'photo' && avatar.kind === 'none';
  }

  function dirty() {
    if (forceDirty) return true;
    var now = readFields();
    var changed = Object.keys(now).some(function (key) { return now[key] !== savedFields[key]; });
    var avatarChanged = avatar.kind !== savedAvatar.kind || avatar.petak !== savedAvatar.petak || !!pickedFile;
    return changed || avatarChanged;
  }

  function render() {
    renderAvatar();
    renderIdentity();
    renderProgress();
    renderHelp();
    syncAvatarInputs();
    saveBar.classList.toggle('on', dirty());
  }

  /* ------------------------------------------------------------------ pesan singkat */
  var toastTimer = 0;
  var undoAction = null;
  function toast(message, undo) {
    $('#pf-toast-txt').textContent = message;
    $('#pf-toast-btn').hidden = !undo;
    undoAction = undo || null;
    toastEl.classList.add('on');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toastEl.classList.remove('on'); undoAction = null; }, 3800);
  }
  $('#pf-toast-btn').addEventListener('click', function () {
    if (undoAction) undoAction();
    undoAction = null;
    toastEl.classList.remove('on');
  });

  /* ------------------------------------------------------------------ isian */
  form.addEventListener('input', function (event) {
    if (!event.target.matches('input, textarea, select')) return;
    forceDirty = false;
    render();
  });
  form.addEventListener('change', render);

  function focusTarget(id) {
    if (id === 'avatar-btn') { openMenu(avatarBtn); return; }
    var el = document.getElementById(id);
    if (!el) return;
    try { el.scrollIntoView({ block: 'center', behavior: 'smooth' }); } catch (error) { /* browser lama */ }
    setTimeout(function () { el.focus({ preventScroll: true }); }, 250);
  }
  document.addEventListener('click', function (event) {
    var target = event.target.closest('[data-focus]');
    if (target) focusTarget(target.dataset.focus);
  });

  $('#pf-discard').addEventListener('click', function () {
    Object.keys(F).forEach(function (key) { F[key].value = savedFields[key]; });
    avatar = copyAvatar(savedAvatar);
    pickedFile = null;
    fileInput.value = '';
    photoErr.hidden = true;
    forceDirty = false;
    render();
    toast('Perubahan dibuang.');
  });

  form.addEventListener('submit', function () { submitting = true; });
  window.addEventListener('beforeunload', function (event) {
    if (!submitting && dirty()) { event.preventDefault(); event.returnValue = ''; }
  });

  /* ------------------------------------------------------------------ foto: unggah, pilih Petak, atau hapus */
  var menuOpen = false;
  function closeMenu(restoreFocus) {
    if (!menuOpen) return;
    menu.hidden = true;
    veil.hidden = true;
    menuOpen = false;
    avatarBtn.setAttribute('aria-expanded', 'false');
    if (restoreFocus) avatarBtn.focus();
  }

  function openMenu(button) {
    closeMenu();
    menuOpen = true;
    button.setAttribute('aria-expanded', 'true');
    var up = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 16V5M7.5 9.5L12 5l4.5 4.5M5 19h14"/></svg>';
    var grid = Object.keys(PETS).map(function (code) {
      return '<button type="button" role="menuitem" data-m="petak" data-v="' + code + '" aria-label="Petak ' + esc(LABELS[code].toLowerCase()) + '"' +
        (avatar.kind === 'petak' && avatar.petak === code ? ' aria-current="true"' : '') + '>' + PETS[code] + '</button>';
    }).join('');
    menu.innerHTML = '<button type="button" role="menuitem" data-m="upload">' + up + 'Unggah foto…</button>' +
      '<small class="pf-pnote">JPG, PNG, atau WebP. Maksimal 2 MB.</small><h3>Atau pilih Petak</h3><div class="pf-mkgrid">' + grid + '</div>';
    menu.hidden = false;
    veil.hidden = false;
    if (!window.matchMedia('(max-width: 767.98px)').matches) {
      var r = button.getBoundingClientRect();
      var left = Math.max(12, Math.min(r.left, window.innerWidth - menu.offsetWidth - 12));
      var top = r.bottom + 10;
      if (top + menu.offsetHeight > window.innerHeight - 12 && r.top - menu.offsetHeight - 10 > 12) top = r.top - menu.offsetHeight - 10;
      menu.style.left = left + 'px';
      menu.style.top = Math.max(12, top) + 'px';
    }
    menu.querySelector('button').focus({ preventScroll: true });
  }

  avatarBtn.addEventListener('click', function () { menuOpen ? closeMenu(true) : openMenu(avatarBtn); });
  veil.addEventListener('mousedown', function () { closeMenu(true); });
  window.addEventListener('resize', function () { closeMenu(false); });
  document.addEventListener('keydown', function (event) { if (event.key === 'Escape' && menuOpen) closeMenu(true); });
  menu.addEventListener('keydown', function (event) {
    var items = [].slice.call(menu.querySelectorAll('button'));
    var index = items.indexOf(document.activeElement);
    if (event.key === 'ArrowDown' || event.key === 'ArrowRight') { items[Math.min(items.length - 1, index + 1)].focus(); event.preventDefault(); }
    else if (event.key === 'ArrowUp' || event.key === 'ArrowLeft') { items[Math.max(0, index - 1)].focus(); event.preventDefault(); }
    else if (event.key === 'Tab') { event.preventDefault(); closeMenu(true); }
  });
  menu.addEventListener('click', function (event) {
    var item = event.target.closest('[data-m]');
    if (!item) return;
    if (item.dataset.m === 'upload') { closeMenu(false); fileInput.click(); return; }
    avatar = { kind: 'petak', petak: item.dataset.v };
    pickedFile = null;
    fileInput.value = '';
    photoErr.hidden = true;
    forceDirty = false;
    closeMenu(false);
    render();
    avatarBtn.focus();
  });

  fileInput.addEventListener('change', function () {
    var file = fileInput.files && fileInput.files[0];
    if (!file) return;
    if (!TYPES.test(file.type)) { return rejectFile('Format foto harus JPG, PNG, atau WebP.'); }
    if (file.size > MAX_BYTES) { return rejectFile('Ukuran foto maksimal 2 MB. Fotomu ' + (file.size / 1048576).toFixed(1) + ' MB.'); }
    photoErr.hidden = true;
    var reader = new FileReader();
    reader.onload = function () {
      pickedFile = file;
      avatar = { kind: 'photo', url: reader.result, fresh: true };
      forceDirty = false;
      render();
    };
    reader.readAsDataURL(file);
  });
  function rejectFile(message) {
    fileInput.value = '';
    photoErr.textContent = message;
    photoErr.hidden = false;
  }

  removeBtn.addEventListener('click', function () {
    var before = copyAvatar(avatar);
    var beforeFile = pickedFile;
    avatar = { kind: 'none' };
    pickedFile = null;
    fileInput.value = '';
    forceDirty = false;
    render();
    avatarBtn.focus();
    toast('Foto dihapus.', function () {
      avatar = before;
      pickedFile = beforeFile;
      if (beforeFile) {
        try { var data = new DataTransfer(); data.items.add(beforeFile); fileInput.files = data.files; } catch (error) { /* browser lama */ }
      }
      render();
    });
  });

  render();
})();
