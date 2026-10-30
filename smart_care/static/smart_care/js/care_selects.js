/* Custom dropdowns for the Smart Care form. Each one keeps the real value in a
   hidden input, so the form posts exactly like the old native <select> and
   re-renders with the submitted value after a validation error. */
(function () {
  'use strict';

  function all(selector, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(selector));
  }

  function closeAll(except) {
    all('[data-ep-select]').forEach(function (box) {
      if (box === except) return;
      var toggle = box.querySelector('[data-ep-toggle]');
      var menu = box.querySelector('[data-ep-menu]');
      box.classList.remove('is-open');
      if (toggle) toggle.setAttribute('aria-expanded', 'false');
      if (menu) menu.hidden = true;
    });
  }

  function sync(box) {
    var input = box.querySelector('input[type="hidden"]');
    var label = box.querySelector('[data-ep-label]');
    var value = input ? input.value : '';
    var match = null;

    all('[data-ep-value]', box).forEach(function (option) {
      var on = option.getAttribute('data-ep-value') === value;
      option.classList.toggle('active', on);
      option.setAttribute('aria-selected', on ? 'true' : 'false');
      if (on) match = option;
    });

    if (!label) return;
    if (match) {
      label.textContent = match.textContent.trim();
      label.classList.remove('ep-placeholder');
    } else {
      label.textContent = box.getAttribute('data-placeholder') || '';
      label.classList.add('ep-placeholder');
    }
  }

  function init(root) {
    all('[data-ep-select]', root).forEach(function (box) {
      if (box.dataset.epReady === '1') return;
      box.dataset.epReady = '1';
      sync(box);
    });
  }

  document.addEventListener('click', function (event) {
    var toggle = event.target.closest('[data-ep-toggle]');
    if (toggle) {
      var box = toggle.closest('[data-ep-select]');
      var menu = box.querySelector('[data-ep-menu]');
      var open = toggle.getAttribute('aria-expanded') !== 'true';
      closeAll(box);
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      box.classList.toggle('is-open', open);
      if (menu) menu.hidden = !open;
      return;
    }

    var option = event.target.closest('[data-ep-value]');
    if (option) {
      var owner = option.closest('[data-ep-select]');
      var hidden = owner.querySelector('input[type="hidden"]');
      if (hidden) hidden.value = option.getAttribute('data-ep-value');
      sync(owner);
      closeAll();
      var button = owner.querySelector('[data-ep-toggle]');
      if (button) button.focus();
      return;
    }

    if (!event.target.closest('[data-ep-menu]')) closeAll();
  });

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') closeAll();
  });

  if (window.htmx) {
    document.body.addEventListener('htmx:afterSwap', function (event) {
      init(event.target);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { init(document); });
  } else {
    init(document);
  }
})();
