/* Smart Care page: the weather scene, the week strip, the garden, AJAX completion with undo, suggestions
   (accept / skip / undo), the pots and the popups. Every rule (rainy day, headline, advice, suggestions, pot
   levels) comes from Django; this file only renders what the JSON says. */
/* Peta alur file ini:
     loadWeather()        GET  smart_care:weather        -> renderScene / renderWeek / renderHints
     applyCompletion()    POST /<pk>/complete/           -> centang tugas, geser baris, perbarui pot, kebun, dan titik minggu
     acceptSuggestion()   POST suggestions/accept/       -> baris saran diganti baris tugas hasil render server (data.html);
                                                            yang dikirim adalah ID baris tanaman (data-pp), bukan namanya
     skipSuggestion()     POST suggestions/skip/         -> saran hilang, toast "Saran dilewati" dengan tombol batal
     restoreSuggestion()  POST suggestions/restore/      -> batalkan lewati
   Semua POST lewat post(), yang menyertakan header X-CSRFToken. Tokennya diambil dari data-csrf di #care-page karena
   cookie CSRF berstatus HttpOnly dan tidak bisa dibaca JavaScript. URL endpoint juga dibaca dari atribut data-* halaman,
   bukan ditulis ulang di sini, sehingga perubahan di urls.py tidak perlu menyentuh file ini.
   Form tambah/ubah tugas tidak ada di sini: itu ditangani HTMX (hx-get / hx-post) dan modal Bootstrap di template. */
(function () {
  'use strict';

  var page = document.getElementById('care-page');
  if (!page) return;

  var csrf = page.dataset.csrf;
  var TODAY = page.dataset.today;
  var SELECTED = page.dataset.selected;
  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // What the page knows about the weather: undefined while loading, null when it could not be loaded
  var weather;
  var garden = { done: Number($('#care-garden').dataset.done) || 0, total: Number($('#care-garden').dataset.total) || 0 };

  function $(selector, root) { return (root || document).querySelector(selector); }
  function $all(selector, root) { return Array.prototype.slice.call((root || document).querySelectorAll(selector)); }

  function post(url, data) {
    var body = null;
    if (data) {
      body = new FormData();
      Object.keys(data).forEach(function (key) { body.append(key, data[key]); });
    }
    return fetch(url, {
      method: 'POST',
      body: body,
      headers: { 'X-CSRFToken': csrf, Accept: 'application/json' },
      credentials: 'same-origin',
    }).then(function (response) {
      if (!response.ok) throw new Error('request failed');
      return response.json();
    });
  }

  function fail() { toast('Belum bisa diperbarui. Coba lagi.'); }

  /* ------------------------------------------------------------------ small message with undo */
  var toastTimer = 0;
  var undoAction = null;

  function toast(message, undo) {
    var box = $('#care-toast');
    $('#care-toast-text').textContent = message;
    $('#care-toast-undo').hidden = !undo;
    undoAction = undo || null;
    box.classList.add('is-on');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { box.classList.remove('is-on'); undoAction = null; }, 4500);
  }

  $('#care-toast-undo').addEventListener('click', function () {
    var action = undoAction;
    undoAction = null;
    $('#care-toast').classList.remove('is-on');
    if (action) action();
  });

  /* ------------------------------------------------------------------ icons for what the script draws */
  var ICONS = {
    rain: '<path d="M7 15a4 4 0 0 1-.6-7.96A5.5 5.5 0 0 1 17 6.5 4.3 4.3 0 0 1 17 15H7z"/><path d="M8 18l-1 2.5M12 18l-1 2.5M16 18l-1 2.5"/>',
    cloud: '<path d="M7 18a4 4 0 0 1-.6-7.96A5.5 5.5 0 0 1 17 9.5 4.3 4.3 0 0 1 17 18H7z"/>',
    cloudsun: '<path d="M12 3v1.5M5 6l1 1M19 6l-1 1M3.5 12H5"/><path d="M8 11a4 4 0 0 1 7.5-1"/><path d="M8 20a3.5 3.5 0 0 1-.4-7A5 5 0 0 1 17.5 13 3.7 3.7 0 0 1 17 20H8z"/>',
    sun: '<circle cx="12" cy="12" r="4"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M5.6 18.4L7 17M17 7l1.4-1.4"/>',
  };

  function icon(name) { return '<svg viewBox="0 0 24 24" aria-hidden="true">' + (ICONS[name] || '') + '</svg>'; }

  // 5,5 in Indonesian notation; "5" instead of "5,0"
  function mm(value) { return value.toFixed(1).replace('.', ',').replace(',0', ''); }

  function dayData(iso) {
    var list = (weather && weather.daily) || [];
    for (var i = 0; i < list.length; i++) if (list[i].date === iso) return list[i];
    return null;
  }

  /* ------------------------------------------------------------------ date picker: the calendar button opens it */
  var jump = $('#care-jump-date');
  var calendarButton = $('#care-cal-btn');
  if (jump && calendarButton) {
    calendarButton.addEventListener('click', function () {
      try { jump.showPicker(); } catch (error) { jump.focus(); jump.click(); }
    });
    jump.addEventListener('change', function () { if (jump.value) jump.form.requestSubmit(); });
  }

  /* ------------------------------------------------------------------ the scene: sky, Petak, headline */
  var scene = $('#care-scene');
  var PILL = { rain: 'is-rain', drizzle: 'is-soft', heat: 'is-heat', humid: 'is-soft', ok: 'is-ok' };

  function setBubble(tone, pill, text) {
    if ($('#care-bubble').hasAttribute('data-petak')) return; // Petak is asking for plants: keep his words
    var chip = $('#care-pill');
    chip.className = 'care-pill ' + tone;
    chip.textContent = pill;
    $('#care-bubble-text').textContent = text;
  }

  function renderScene() {
    var proud = garden.total > 0 && garden.done === garden.total;
    var isToday = SELECTED === TODAY;
    var errorLine = $('#care-weather-error');
    errorLine.hidden = weather !== null;

    if (weather === undefined) return; // still loading: the first paint stays as the page was rendered

    var day = dayData(SELECTED);
    var sky = 'soft';
    var pet = 'curious';

    if (weather === null) {
      $('#care-temp').textContent = '--°';
      $('#care-condition').textContent = 'Tidak tersedia';
      $('#care-mini').textContent = '';
      setBubble('is-soft', 'Cuaca tidak tersedia', 'Saran sesuai cuaca muncul setelah data berhasil dimuat');
    } else if (!day) {
      $('#care-temp').textContent = '--°';
      $('#care-condition').textContent = 'Tanpa prakiraan';
      $('#care-mini').textContent = '';
      setBubble('is-soft', 'Tanpa prakiraan', 'Prakiraan cuaca hanya tersedia untuk 7 hari ke depan.');
    } else {
      sky = day.outlook.sky;
      pet = sky === 'rain' ? 'curious' : sky === 'soft' ? 'happy' : 'cheer';
      var temperature = isToday ? weather.temperature : day.temperature_max;
      $('#care-temp').textContent = (typeof temperature === 'number' ? Math.round(temperature) : '--') + '°';
      $('#care-condition').textContent = isToday ? weather.condition : day.outlook.label;
      var parts = [];
      if (isToday && typeof weather.humidity === 'number') parts.push('Kelembapan <b>' + Math.round(weather.humidity) + '%</b>');
      // the chance is the highest of the day's hours, which is why it can read 99% on a day with a few drops
      if (typeof day.rain_probability === 'number') parts.push('Peluang hujan tertinggi <b>' + Math.round(day.rain_probability) + '%</b>');
      if (typeof day.rain_mm === 'number') parts.push('Curah hujan <b>' + mm(day.rain_mm) + ' mm</b>');
      $('#care-mini').innerHTML = parts.map(function (part) { return '<span>' + part + '</span>'; }).join('');
      setBubble(PILL[day.recommendation.tone] || 'is-ok', day.recommendation.pill, day.recommendation.message);
    }

    if (proud) {
      pet = 'proud';
      setBubble('is-proud', 'Semua beres', isToday ? 'Kebun hari ini terawat. Petak bangga padamu!' : 'Semua tugas di hari itu sudah beres.');
    }
    scene.dataset.sky = sky;
    scene.dataset.pet = pet;
    // the empty-day card shows the same Petak (proud is for finished days, so an empty one is just happy)
    var card = $('#care-empty');
    card.dataset.mood = pet === 'proud' ? 'happy' : pet;
  }

  /* ------------------------------------------------------------------ the week strip: forecast per day */
  function renderWeek() {
    $all('.care-day').forEach(function (cell) {
      var day = dayData(cell.dataset.day);
      var slot = $('[data-weather]', cell);
      if (!cell.dataset.label) cell.dataset.label = cell.getAttribute('aria-label');
      if (!day) {
        slot.className = 'care-day-w';
        slot.innerHTML = '';
        cell.removeAttribute('title');
        cell.setAttribute('aria-label', cell.dataset.label);
        return;
      }
      var amount = typeof day.rain_mm === 'number' && day.rain_mm >= 0.5 ? mm(day.rain_mm) : '';
      slot.className = 'care-day-w' + (day.rainy ? ' is-heavy' : '');
      slot.innerHTML = icon(day.outlook.icon) + (amount ? amount + '<span>mm</span>' : '');
      cell.title = 'Peluang hujan tertinggi ' + Math.round(day.rain_probability) + '%' + (amount ? ', sekitar ' + amount + ' mm' : '');
      cell.setAttribute('aria-label', cell.dataset.label + (day.rainy ? '. Hujan ' + amount + ' milimeter' : ''));
    });
  }

  // A dot of a day changes state (pending, late, done) when one of its tasks is ticked or unticked
  function moveDot(iso, from, to) {
    var cell = $('.care-day[data-day="' + iso + '"]');
    var dot = cell && $('.care-dot.is-' + from, cell);
    if (dot) dot.className = 'care-dot is-' + to;
  }

  // A dot disappears (a skipped suggestion no longer counts); the "+N" of a busy day shrinks instead when the dot is hidden in it
  function removeDot(iso, state) {
    var cell = $('.care-day[data-day="' + iso + '"]');
    if (!cell) return;
    var dot = $('.care-dot.is-' + state, cell);
    if (dot) { dot.remove(); return; }
    var more = $('.care-dots small', cell);
    if (!more) return;
    var left = Number(more.textContent.replace('+', '')) - 1;
    if (left > 0) more.textContent = '+' + left;
    else more.remove();
  }

  function pendingState(iso) { return iso < TODAY ? 'late' : 'pending'; }

  /* ------------------------------------------------------------------ advice on the rows: only outdoor, not done */
  function renderHints() {
    $all('.care-task', page).forEach(function (row) {
      var hint = $('.care-hint', row);
      var day = dayData(row.dataset.due);
      var text = day && row.dataset.outdoor === '1' && !row.classList.contains('is-done') ? (day.hints || {})[row.dataset.type] : '';
      if (!text) {
        hint.hidden = true;
        hint.textContent = '';
        return;
      }
      var watering = row.dataset.type === 'watering';
      hint.className = 'care-hint ' + (day.rainy && watering ? 'is-rain' : 'is-warn');
      hint.innerHTML = icon(day.rainy ? (watering ? 'rain' : 'cloud') : 'sun') + '<span></span>';
      $('span', hint).textContent = text;
      hint.hidden = false;
    });
  }

  function loadWeather() {
    scene.classList.add('is-loading');
    return fetch(page.dataset.weatherUrl, { headers: { Accept: 'application/json' }, credentials: 'same-origin' })
      .then(function (response) {
        return response.json().then(function (data) { return { ok: response.ok, data: data }; });
      })
      .then(function (result) {
        if (!result.ok || !result.data.available) throw new Error('weather unavailable');
        weather = result.data;
      })
      .catch(function () { weather = null; })
      .then(function () {
        scene.classList.remove('is-loading');
        renderScene();
        renderWeek();
        renderHints();
      });
  }

  $('#care-retry').addEventListener('click', function () { weather = undefined; loadWeather(); });
  loadWeather();

  /* ------------------------------------------------------------------ pots (one per plant) */
  function normalize(name) { return (name || '').trim().replace(/\s+/g, ' ').toLowerCase(); }

  function renderPot(pot, watered) {
    if (!pot) return;
    var el = $('.care-pot[data-key="' + pot.key.replace(/"/g, '\\"') + '"]');
    if (!el) return;
    el.style.setProperty('--water', pot.water);
    el.classList.toggle('is-due', pot.watering_due);
    el.classList.toggle('is-empty', pot.never_recorded);
    $('.care-pot-label', el).textContent = pot.label;
    $('.care-pot-btn', el).setAttribute('aria-label', pot.plant_name + (pot.place ? ' (' + pot.place + ')' : '') + ': ' + pot.label + '. Lihat tugasnya');
    $all('.care-pot-dot', el).forEach(function (dot) {
      dot.classList.toggle('is-on', !!pot[dot.dataset.dot + '_ok']);
    });
    if (watered && !reduceMotion) {
      // the water rises (CSS transition) and its surface ripples while it does
      el.classList.add('is-filling');
      setTimeout(function () { el.classList.remove('is-filling'); }, 1200);
    }
  }

  // Clicking a pot jumps to that plant's rows. A task points at its plant by id (data-pp); one from before tasks were
  // linked to plants has no id and is matched by the name instead.
  function showPlantRows(key, name) {
    var rows = $all('.care-task').filter(function (row) {
      return row.dataset.pp ? row.dataset.pp === key : normalize(row.dataset.plant) === normalize(name);
    });
    if (!rows.length) return;
    var visible = rows.filter(function (row) { return row.offsetParent !== null; });
    var target = visible.length ? visible : rows;
    target[0].scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'center' });
    target.forEach(function (row) {
      row.classList.remove('is-highlight');
      void row.offsetWidth; // restart the one-off highlight
      row.classList.add('is-highlight');
      setTimeout(function () { row.classList.remove('is-highlight'); }, 1700);
    });
  }

  /* ------------------------------------------------------------------ garden: the plant, the label and the bar */
  function renderGarden(progress) {
    garden.done = progress.done;
    garden.total = progress.total;
    $('#care-plant').dataset.s = progress.stage;
    $('#care-garden').classList.toggle('is-empty', !progress.total);
    $('#care-progress-label').textContent = !progress.total
      ? 'Belum ada tugas yang dijadwalkan.'
      : progress.done === progress.total ? 'Semua beres. Kebunmu terawat.' : progress.done + ' dari ' + progress.total + ' tugas selesai';
    $('#care-bar-fill').style.width = progress.percent + '%';
    $('#care-bar').setAttribute('aria-valuenow', progress.percent);
    renderScene(); // Petak is proud when everything is done
  }

  /* ------------------------------------------------------------------ groups, counts, empty state */
  var lists = {
    overdue: $('#care-overdue-list'),
    pending: $('#care-pending-list'),
    done: $('#care-done-list'),
    skipped: $('#care-skipped-list'),
  };

  function refreshGroups() {
    var pending = lists.pending.children.length;
    var done = lists.done.children.length;
    var overdue = lists.overdue.children.length;
    var skipped = lists.skipped.children.length;
    $('#care-pending-count').textContent = pending;
    $('#care-done-count').textContent = done;
    $('#care-overdue-count').textContent = overdue;
    $('#care-skipped-count').textContent = skipped;
    $('#care-overdue').hidden = overdue === 0;
    $('#care-pending-group').hidden = pending === 0;
    $('#care-done-group').hidden = done === 0;
    $('#care-skipped').hidden = skipped === 0;
    var empty = $('#care-empty');
    var allSkipped = pending + done === 0 && skipped > 0;
    $('b', empty).textContent = allSkipped ? 'Semua saran hari ini dilewati' : empty.dataset.default;
    $('p', empty).textContent = allSkipped
      ? 'Buka "Dilewati hari ini" di bawah kalau mau mengembalikannya.'
      : 'Hari yang santai untuk kebunmu. Tambah Care Task kalau ada yang perlu dijadwalkan.';
    empty.hidden = pending + done > 0;
  }

  // FLIP: rows slide from where they were to where they are now
  function moveRow(row, target) {
    var rows = $all('.care-task', page);
    var before = rows.map(function (el) { return el.getBoundingClientRect().top; });
    target.appendChild(row);
    refreshGroups();
    if (reduceMotion) return;
    rows.forEach(function (el, index) {
      if (el.offsetParent === null) return; // inside a collapsed list: nothing to see
      var delta = before[index] - el.getBoundingClientRect().top;
      if (delta) {
        el.animate(
          [{ transform: 'translateY(' + delta + 'px)' }, { transform: 'none' }],
          { duration: 420, easing: 'cubic-bezier(.2,.8,.2,1)' }
        );
      }
    });
  }

  function fadeOut(row, then) {
    var finish = function () { row.remove(); if (then) then(); refreshGroups(); };
    if (reduceMotion) return finish();
    row.style.transition = 'opacity .3s ease, transform .3s ease';
    row.style.opacity = '0';
    row.style.transform = 'translateX(16px)';
    setTimeout(finish, 320);
  }

  /* ------------------------------------------------------------------ complete / reopen a task */
  function applyCompletion(row, data, silent) {
    var button = $('.care-check', row);
    var overdue = row.hasAttribute('data-overdue');
    row.classList.toggle('is-done', data.is_completed);
    button.setAttribute('aria-checked', data.is_completed ? 'true' : 'false');
    renderPot(data.pot, data.is_completed && row.dataset.type === 'watering');
    if (data.is_completed) moveDot(data.due_date, pendingState(data.due_date), 'done');
    else moveDot(data.due_date, 'done', pendingState(data.due_date));

    if (overdue) {
      // An overdue task is not part of today's progress; completing it just clears it from "Terlewat"
      setTimeout(function () { fadeOut(row); }, reduceMotion ? 0 : 650);
    } else {
      // let the tick finish drawing before the row moves
      setTimeout(function () { moveRow(row, data.is_completed ? lists.done : lists.pending); }, reduceMotion ? 0 : 520);
      renderGarden(data.progress);
    }
    renderHints();

    if (silent) return;
    var undo = overdue
      ? function () { post(row.dataset.completeUrl).then(function () { window.location.reload(); }).catch(fail); }
      : function () { post(row.dataset.completeUrl).then(function (back) { applyCompletion(row, back, true); }).catch(fail); };
    toast(data.is_completed ? 'Selesai. Kerja bagus!' : 'Dikembalikan ke belum selesai.', undo);
  }

  /* ------------------------------------------------------------------ suggestions */
  function acceptSuggestion(row) {
    return post(page.dataset.acceptUrl, { patch_plant: row.dataset.pp, task_type: row.dataset.type }).then(function (data) {
      // The suggestion becomes a real task row (edit / delete included), then plays the usual tick
      var holder = document.createElement('div');
      holder.innerHTML = data.html.trim();
      var fresh = holder.firstElementChild;
      fresh.classList.remove('is-done');
      $('.care-check', fresh).setAttribute('aria-checked', 'false');
      row.replaceWith(fresh);
      if (window.htmx) window.htmx.process(fresh);
      requestAnimationFrame(function () { requestAnimationFrame(function () { applyCompletion(fresh, data); }); });
    });
  }

  function skipSuggestion(row) {
    return post(page.dataset.skipUrl, { patch_plant: row.dataset.pp, task_type: row.dataset.type }).then(function (data) {
      var li = document.createElement('li');
      var label = document.createElement('span');
      label.textContent = data.skipped.plant_name + (data.skipped.place ? ' (' + data.skipped.place + ')' : '') + ' ';
      var type = document.createElement('small');
      type.textContent = data.skipped.label;
      label.appendChild(type);
      var undo = document.createElement('button');
      undo.type = 'button';
      undo.className = 'care-restore';
      undo.dataset.pp = data.skipped.patch_plant;
      undo.dataset.plant = data.skipped.plant_name;
      undo.dataset.type = data.skipped.task_type;
      undo.textContent = 'Batalkan';
      li.appendChild(label);
      li.appendChild(undo);
      lists.skipped.appendChild(li);
      renderGarden(data.progress);
      removeDot(data.due_date, 'pending'); // a skipped suggestion no longer waits for you
      fadeOut(row);
      renderHints();
      toast('Saran dilewati.', function () { restoreSuggestion(undo).catch(fail); });
    });
  }

  function restoreSuggestion(button) {
    return post(page.dataset.restoreUrl, { patch_plant: button.dataset.pp, task_type: button.dataset.type }).then(function () {
      window.location.reload(); // the suggestion is rebuilt on the server, so just reload
    });
  }

  /* ------------------------------------------------------------------ click handling */
  page.addEventListener('click', function (event) {
    var check = event.target.closest('.care-check');
    var skip = event.target.closest('.care-skip');
    var restore = event.target.closest('.care-restore');
    var remove = event.target.closest('[data-delete-url]');
    var potButton = event.target.closest('.care-pot-btn');
    var fold = event.target.closest('.care-fold');

    if (fold) {
      var open = fold.getAttribute('aria-expanded') !== 'true';
      fold.setAttribute('aria-expanded', open ? 'true' : 'false');
      document.getElementById(fold.getAttribute('aria-controls')).hidden = !open;
      return;
    }

    if (potButton) {
      var pot = potButton.closest('.care-pot');
      showPlantRows(pot.dataset.key, pot.dataset.name);
      return;
    }

    if (check) {
      var row = check.closest('.care-task');
      if (row.dataset.busy) return;
      row.dataset.busy = '1';
      var request = row.hasAttribute('data-suggestion')
        ? acceptSuggestion(row)
        : post(row.dataset.completeUrl).then(function (data) { applyCompletion(row, data); });
      request.catch(fail).then(function () { delete row.dataset.busy; });
    } else if (skip) {
      var skipRow = skip.closest('.care-task');
      if (skipRow.dataset.busy) return;
      skipRow.dataset.busy = '1';
      skipSuggestion(skipRow).catch(fail).then(function () { delete skipRow.dataset.busy; });
    } else if (restore) {
      restore.disabled = true;
      restoreSuggestion(restore).catch(function () { restore.disabled = false; fail(); });
    } else if (remove) {
      $('#care-delete-form').action = remove.dataset.deleteUrl;
      $('#care-delete-name').textContent = remove.dataset.deleteName;
      bootstrap.Modal.getOrCreateInstance(document.getElementById('care-delete-modal')).show();
    }
  });

  /* ------------------------------------------------------------------ add / edit popup (HTMX loads the form) */
  var formModal = document.getElementById('care-modal');
  formModal.addEventListener('hidden.bs.modal', function () {
    $('#care-modal-content').innerHTML = '<div class="modal-body care-modal-loading">Memuat</div>';
  });
})();
