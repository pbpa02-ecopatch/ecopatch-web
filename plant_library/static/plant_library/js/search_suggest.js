(function () {
    'use strict';

    var KEYWORD_SUGGESTIONS = [
        'tanaman yang mudah dirawat',
        'tanaman yang teduh',
        'cahaya penuh',
        'perawatan sedang',
        'tanaman indoor',
        'tanaman outdoor',
        'jarang disiram',
        'sering disiram',
        'tahan lupa disiram'
    ];

    function getPlantNames() {
        var el = document.getElementById('plant-names-data');
        if (el) {
            try {
                return JSON.parse(el.textContent) || [];
            } catch (e) {
                return [];
            }
        }
        var titles = document.querySelectorAll('.plant-card-name, .plant-card-title, .plant-name');
        var names = [];
        for (var i = 0; i < titles.length; i++) {
            var t = titles[i].textContent.trim();
            if (t && names.indexOf(t) === -1) names.push(t);
        }
        return names;
    }

    function initSuggest() {
        var input = document.getElementById('plant-q');
        if (!input) return;

        var container = input.closest('.plant-search-row') || input.parentElement;
        if (!container) return;

        // Avoid duplicate initialization
        var existing = container.querySelector('.plant-suggest');
        if (existing) existing.remove();

        var listEl = document.createElement('ul');
        listEl.className = 'plant-suggest';
        listEl.setAttribute('role', 'listbox');
        listEl.setAttribute('aria-label', 'Saran pencarian');
        listEl.hidden = true;
        container.appendChild(listEl);

        var plantNames = getPlantNames();
        var selectedIdx = -1;
        var currentItems = [];

        function hide() {
            listEl.hidden = true;
            listEl.innerHTML = '';
            selectedIdx = -1;
            currentItems = [];
        }

        function highlightMatch(text, query) {
            var idx = text.toLowerCase().indexOf(query.toLowerCase());
            if (idx === -1) return escapeHtml(text);
            var before = text.slice(0, idx);
            var match = text.slice(idx, idx + query.length);
            var after = text.slice(idx + query.length);
            return escapeHtml(before) + '<mark style="background:transparent;color:var(--pl-brand-strong);font-weight:800;padding:0;">' + escapeHtml(match) + '</mark>' + escapeHtml(after);
        }

        function escapeHtml(str) {
            return String(str)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }

        function selectItem(text) {
            input.value = text;
            hide();
            if (window.htmx) {
                input.dispatchEvent(new Event('search', { bubbles: true }));
            } else if (input.form) {
                if (input.form.requestSubmit) {
                    input.form.requestSubmit();
                } else {
                    input.form.submit();
                }
            }
        }

        function renderSuggestions(query) {
            var q = query.trim().toLowerCase();
            if (!q) {
                hide();
                return;
            }

            var matchedPlants = [];
            for (var i = 0; i < plantNames.length; i++) {
                var name = plantNames[i];
                if (name.toLowerCase().indexOf(q) !== -1) {
                    matchedPlants.push({ text: name, type: 'plant' });
                }
            }

            var matchedKeywords = [];
            for (var k = 0; k < KEYWORD_SUGGESTIONS.length; k++) {
                var kw = KEYWORD_SUGGESTIONS[k];
                if (kw.toLowerCase().indexOf(q) !== -1) {
                    matchedKeywords.push({ text: kw, type: 'keyword' });
                }
            }

            // Sort: items starting with q first
            function score(item) {
                return item.text.toLowerCase().indexOf(q) === 0 ? 0 : 1;
            }
            matchedPlants.sort(function (a, b) { return score(a) - score(b); });
            matchedKeywords.sort(function (a, b) { return score(a) - score(b); });

            currentItems = matchedPlants.slice(0, 5).concat(matchedKeywords.slice(0, 3)).slice(0, 7);

            if (currentItems.length === 0) {
                hide();
                return;
            }

            selectedIdx = -1;
            listEl.innerHTML = '';

            currentItems.forEach(function (item, idx) {
                var li = document.createElement('li');
                li.className = 'plant-suggest-item';
                li.setAttribute('role', 'option');
                li.id = 'plant-suggest-opt-' + idx;

                var icon = item.type === 'plant' ? '🪴' : '🔍';
                var tagLabel = item.type === 'plant' ? 'Tanaman' : 'Kriteria';

                li.innerHTML = '<span class="plant-suggest-main">' +
                    '<span class="plant-suggest-icon" aria-hidden="true">' + icon + '</span>' +
                    '<span>' + highlightMatch(item.text, q) + '</span>' +
                    '</span>' +
                    '<span class="plant-suggest-tag">' + tagLabel + '</span>';

                li.addEventListener('mousedown', function (e) {
                    e.preventDefault();
                    selectItem(item.text);
                });

                listEl.appendChild(li);
            });

            listEl.hidden = false;
        }

        function updateSelection() {
            var items = listEl.querySelectorAll('.plant-suggest-item');
            items.forEach(function (el, idx) {
                var isSel = idx === selectedIdx;
                el.classList.toggle('is-selected', isSel);
                if (isSel) {
                    el.scrollIntoView({ block: 'nearest' });
                    input.setAttribute('aria-activedescendant', el.id);
                }
            });
            if (selectedIdx === -1) {
                input.removeAttribute('aria-activedescendant');
            }
        }

        input.addEventListener('input', function () {
            renderSuggestions(input.value);
        });

        input.addEventListener('keydown', function (e) {
            if (listEl.hidden || currentItems.length === 0) return;

            if (e.key === 'ArrowDown') {
                e.preventDefault();
                selectedIdx = (selectedIdx + 1) % currentItems.length;
                updateSelection();
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                selectedIdx = (selectedIdx - 1 + currentItems.length) % currentItems.length;
                updateSelection();
            } else if (e.key === 'Enter') {
                if (selectedIdx >= 0 && selectedIdx < currentItems.length) {
                    e.preventDefault();
                    selectItem(currentItems[selectedIdx].text);
                }
            } else if (e.key === 'Escape') {
                hide();
            }
        });

        document.addEventListener('click', function (e) {
            if (!container.contains(e.target)) {
                hide();
            }
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initSuggest);
    } else {
        initSuggest();
    }

    if (window.htmx) {
        document.body.addEventListener('htmx:afterSwap', function (e) {
            if (e.detail && e.detail.target && e.detail.target.id === 'plant-library-body') {
                initSuggest();
            }
        });
    }
})();
