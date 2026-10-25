/* Smart Care page: weather panel, AJAX completion, suggestions (accept / skip / undo), the daily plant
   and the delete / popup modals. All decision rules (suggestions, recommendations, hints, meter
   percentages) come from Django; this file only renders what the JSON says. */
(function () {
  'use strict';

  var page = document.getElementById('care-page');
  if (!page) return;

  var csrf = page.dataset.csrf;
  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

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

  function fail() { window.alert('Belum bisa diperbarui. Coba lagi.'); }

  /* ------------------------------------------------------------------ date picker */
  var jump = $('#care-jump-date');
  if (jump) jump.addEventListener('change', function () { if (jump.value) jump.form.requestSubmit(); });

  /* ------------------------------------------------------------------ weather ribbon + forecast in the date strip */
  var weatherEl = $('#care-weather');
  var errorLine = $('#care-weather-error');
  var currentHints = {};

  function whole(value) {
    return typeof value === 'number' ? String(Math.round(value)) : '--';
  }

  // "sekitar 5 mm"; under 1 mm the number would only say "0"
  function rainAmount(mm) {
    if (typeof mm !== 'number') return '';
    return mm < 1 ? 'kurang dari 1 mm' : 'sekitar ' + Math.round(mm) + ' mm';
  }

  function renderForecast(daily) {
    var byDate = {};
    daily.forEach(function (day) { byDate[day.date] = day; });
    $all('.care-day').forEach(function (cell) {
      var day = byDate[cell.dataset.day];
      var rain = $('[data-rain]', cell);
      cell.classList.toggle('is-rainy', !!(day && day.rainy));
      if (day && typeof day.rain_probability === 'number') {
        $('b', rain).textContent = day.rain_probability + '%';
        rain.classList.add('has-data');
        cell.title = ['Peluang hujan tertinggi ' + day.rain_probability + '%', rainAmount(day.rain_mm)].filter(Boolean).join(', ');
      } else {
        rain.classList.remove('has-data');
        cell.removeAttribute('title');
      }
    });
  }

  function renderWeather(data) {
    errorLine.hidden = true;
    weatherEl.dataset.ambient = data.ambient;
    $('#care-condition').textContent = data.condition;
    $('#care-temp').textContent = whole(data.temperature);
    $('#care-advice').textContent = data.recommendation.message;
    var parts = [];
    if (typeof data.humidity === 'number') parts.push('Kelembapan ' + Math.round(data.humidity) + '%');
    var hasRain = typeof data.rain_probability === 'number';
    if (hasRain) parts.push('Hujan ' + Math.round(data.rain_probability) + '%');
    if (hasRain && rainAmount(data.rain_mm)) parts.push(rainAmount(data.rain_mm));
    $('#care-meta').textContent = parts.join(' \u00b7 ');
    $('#care-meta-note').hidden = !hasRain;
    renderForecast(data.daily || []);
    currentHints = data.hints || {};
    applyHints();
  }

  function showWeatherError() {
    $('#care-condition').textContent = 'Tidak tersedia';
    $('#care-temp').textContent = '--';
    $('#care-advice').textContent = 'Saran sesuai cuaca muncul setelah data berhasil dimuat';
    $('#care-meta').textContent = '';
    $('#care-meta-note').hidden = true;
    renderForecast([]);
    currentHints = {};
    applyHints();
    errorLine.hidden = false;
  }

  function loadWeather() {
    weatherEl.classList.add('is-loading');
    errorLine.hidden = true;
    return fetch(page.dataset.weatherUrl, { headers: { Accept: 'application/json' }, credentials: 'same-origin' })
      .then(function (response) {
        return response.json().then(function (data) { return { ok: response.ok, data: data }; });
      })
      .then(function (result) {
        if (!result.ok || !result.data.available) throw new Error('weather unavailable');
        renderWeather(result.data);
      })
      .catch(showWeatherError)
      .then(function () { weatherEl.classList.remove('is-loading'); });
  }

  // Per-row hints (manual and suggested rows alike): only outdoor rows that are not done yet
  function applyHints() {
    $all('.care-task').forEach(function (row) {
      var hint = $('.care-task-hint', row);
      var text = row.dataset.outdoor === '1' && !row.classList.contains('is-done') ? currentHints[row.dataset.type] : '';
      hint.textContent = text || '';
      hint.hidden = !text;
    });
  }

  $('#care-retry').addEventListener('click', function () { loadWeather(); });
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
    $('.care-pot-btn', el).setAttribute('aria-label', pot.plant_name + ': ' + pot.label + '. Lihat tugasnya');
    $all('.care-pot-dot', el).forEach(function (dot) {
      dot.classList.toggle('is-on', !!pot[dot.dataset.dot + '_ok']);
    });
    if (watered && !reduceMotion) {
      // the water rises (CSS transition) and its surface ripples while it does
      el.classList.add('is-filling');
      setTimeout(function () { el.classList.remove('is-filling'); }, 1200);
    }
  }

  // Clicking a pot jumps to that plant's rows
  function showPlantRows(key) {
    var rows = $all('.care-task').filter(function (row) { return normalize(row.dataset.plant) === key; });
    if (!rows.length) return;
    rows[0].scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'center' });
    rows.forEach(function (row) {
      row.classList.remove('is-highlight');
      void row.offsetWidth; // restart the one-off highlight
      row.classList.add('is-highlight');
      setTimeout(function () { row.classList.remove('is-highlight'); }, 1700);
    });
  }

  /* ------------------------------------------------------------------ progress + daily plant */
  var plant = $('#care-plant');
  var burst = $('#care-burst');
  var lastPercent = Number($('#care-bar').getAttribute('aria-valuenow')) || 0;

  function renderProgress(progress) {
    $('#care-progress-label').textContent = progress.done + ' dari ' + progress.total + ' tugas selesai';
    $('#care-bar-fill').style.width = progress.percent + '%';
    $('#care-bar').setAttribute('aria-valuenow', progress.percent);
    plant.dataset.stage = progress.stage;
    if (progress.percent === 100 && lastPercent < 100 && !reduceMotion) {
      burst.classList.remove('is-active');
      void burst.getBoundingClientRect(); // restart the one-off animation
      burst.classList.add('is-active');
      setTimeout(function () { burst.classList.remove('is-active'); }, 900);
    }
    lastPercent = progress.percent;
  }

  /* ------------------------------------------------------------------ groups, counts, empty states */
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
    $('#care-done-group').hidden = done === 0;
    $('#care-skipped').hidden = skipped === 0;
    var empty = $('#care-empty');
    if (pending + done === 0 && skipped > 0) $('p', empty).textContent = empty.dataset.skipped;
    empty.hidden = pending + done > 0;
    $('#care-allclear').hidden = !(pending === 0 && done > 0);
  }

  function setStripCount(iso, value) {
    var day = $('.care-day[data-day="' + iso + '"] [data-count]');
    if (!day) return;
    day.textContent = Math.max(0, value);
    day.classList.toggle('is-zero', value <= 0);
  }

  function shiftStripCount(iso, delta) {
    var day = $('.care-day[data-day="' + iso + '"] [data-count]');
    if (day) setStripCount(iso, Number(day.textContent) + delta);
  }

  // FLIP: rows slide from where they were to where they are now
  function moveRow(row, target) {
    var rows = $all('.care-task', page);
    var before = rows.map(function (el) { return el.getBoundingClientRect().top; });
    target.appendChild(row);
    refreshGroups();
    if (reduceMotion) return;
    rows.forEach(function (el, index) {
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
  function applyCompletion(row, data) {
    var button = $('.care-check', row);
    row.classList.toggle('is-done', data.is_completed);
    button.setAttribute('aria-pressed', data.is_completed ? 'true' : 'false');
    renderPot(data.pot, data.is_completed && row.dataset.type === 'watering');

    if (row.hasAttribute('data-overdue')) {
      // An overdue task is not part of today's progress; completing it just clears it from "Terlewat"
      shiftStripCount(data.due_date, data.is_completed ? -1 : 1);
      setTimeout(function () { fadeOut(row); }, reduceMotion ? 0 : 650);
    } else {
      setStripCount(data.due_date, data.progress.pending);
      // let the tick finish drawing before the row moves
      setTimeout(function () { moveRow(row, data.is_completed ? lists.done : lists.pending); }, reduceMotion ? 0 : 520);
      renderProgress(data.progress);
    }
    applyHints();
  }

  /* ------------------------------------------------------------------ suggestions */
  function acceptSuggestion(row) {
    return post(page.dataset.acceptUrl, { plant_name: row.dataset.plant, task_type: row.dataset.type }).then(function (data) {
      // The suggestion becomes a real task row (edit / delete included), then plays the usual tick
      var holder = document.createElement('div');
      holder.innerHTML = data.html.trim();
      var fresh = holder.firstElementChild;
      fresh.classList.remove('is-done');
      $('.care-check', fresh).setAttribute('aria-pressed', 'false');
      row.replaceWith(fresh);
      if (window.htmx) window.htmx.process(fresh);
      requestAnimationFrame(function () { requestAnimationFrame(function () { applyCompletion(fresh, data); }); });
    });
  }

  function skipSuggestion(row) {
    return post(page.dataset.skipUrl, { plant_name: row.dataset.plant, task_type: row.dataset.type }).then(function (data) {
      var li = document.createElement('li');
      var label = document.createElement('span');
      label.textContent = data.skipped.plant_name + ' ';
      var type = document.createElement('small');
      type.textContent = data.skipped.label;
      label.appendChild(type);
      var undo = document.createElement('button');
      undo.type = 'button';
      undo.className = 'care-restore';
      undo.dataset.plant = data.skipped.plant_name;
      undo.dataset.type = data.skipped.task_type;
      undo.textContent = 'Batalkan';
      li.appendChild(label);
      li.appendChild(undo);
      lists.skipped.appendChild(li);
      renderProgress(data.progress);
      setStripCount(data.due_date, data.progress.pending);
      fadeOut(row);
      applyHints();
    });
  }

  function restoreSuggestion(button) {
    return post(page.dataset.restoreUrl, { plant_name: button.dataset.plant, task_type: button.dataset.type }).then(function () {
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

    if (potButton) {
      showPlantRows(potButton.closest('.care-pot').dataset.key);
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
