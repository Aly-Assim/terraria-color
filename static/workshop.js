/* Local comparison state. Only IDs and actual paint IDs are persisted. */
(() => {
    const panel = document.querySelector('[data-workshop]');
    if (!panel) return;
    const {t, render} = window.TerrariaUI;
    const key = 'terraria-color-workshop-v1';
    const grid = document.getElementById('workshopGrid');
    const form = document.getElementById('workshopSearch');
    const query = document.getElementById('workshopQuery');
    const suggestions = document.getElementById('workshopSuggestions');
    const status = document.getElementById('workshopSearchStatus');
    const notice = document.getElementById('workshopNotice');
    const warning = document.getElementById('workshopStorageWarning');
    const commonPaint = document.getElementById('workshopPaint');
    const clear = document.getElementById('workshopClear');
    const apply = document.getElementById('workshopApply');
    const paints = new Set([...commonPaint.options].map(option => Number(option.value)));
    const cache = new Map();
    let entries = [], nextKey = 0, searchRequest = null, debounce;

    function text(el, source) { el.dataset.i18n = source; el.textContent = t(source); }
    function button(source, action) {
        const el = document.createElement('button'); el.type = 'button'; el.className = 'quiet-button';
        text(el, source); el.addEventListener('click', action); return el;
    }
    function save() {
        try {
            localStorage.setItem(key, JSON.stringify({version: 1, items: entries.map(({local_id, paint_id}) => ({local_id, paint_id}))}));
        } catch (_) {
            warning.hidden = false; text(warning, 'Sauvegarde locale indisponible : cette sélection reste dans cet onglet.');
        }
    }
    function summary() {
        document.getElementById('workshopCount').textContent = entries.length;
        document.getElementById('workshopEmpty').hidden = entries.length > 0;
        clear.disabled = apply.disabled = entries.length === 0;
    }
    function closeDetails(entry) {
        if (entry.slot.querySelector('.is-selected')) document.getElementById('inspector').close();
    }
    function remove(entry) {
        closeDetails(entry); entries = entries.filter(other => other !== entry); entry.slot.remove(); save(); summary();
        text(notice, 'Matériau retiré.'); query.focus({preventScroll: true});
    }
    async function cardHTML(entry, paint) {
        const url = panel.dataset.itemBase.replace(/0\/0$/, `${entry.local_id}/${paint}`);
        if (!cache.has(url)) {
            cache.set(url, fetch(url).then(response => {
                if (!response.ok) throw new Error('Unavailable material');
                return response.text();
            }).catch(error => { cache.delete(url); throw error; }));
        }
        return cache.get(url);
    }
    function imageFailure(image) {
        image.hidden = true;
        const message = document.createElement('span'); message.className = 'preview-error';
        text(message, 'Aperçu peint indisponible.'); image.parentElement.append(message);
    }
    async function load(entry) {
        const paint = entry.paint_id;
        const version = ++entry.version;
        entry.slot.setAttribute('aria-busy', 'true');
        closeDetails(entry);
        // Do not allow inspection of stale measurements while a paint is loading.
        entry.slot.querySelector('[data-inspect]')?.setAttribute('disabled', '');
        try {
            const html = await cardHTML(entry, paint);
            if (!entries.includes(entry) || entry.version !== version) return;
            const focused = entry.slot.contains(document.activeElement);
            const template = document.createElement('template'); template.innerHTML = html;
            const card = template.content.querySelector('.card');
            const controls = document.createElement('div'); controls.className = 'workshop-item-controls';
            const label = document.createElement('label'); const caption = document.createElement('span'); text(caption, 'Peinture');
            const select = commonPaint.cloneNode(true); select.removeAttribute('id'); select.value = String(paint);
            select.addEventListener('change', () => { entry.paint_id = Number(select.value); save(); load(entry); });
            label.append(caption, select); controls.append(label, button('Retirer', () => remove(entry)));
            card.insertBefore(controls, card.querySelector('.card-body'));
            entry.slot.replaceChildren(card); render(entry.slot);
            const image = card.querySelector('.world-img');
            if (image) { image.addEventListener('error', () => imageFailure(image), {once: true}); if (image.complete && !image.naturalWidth) imageFailure(image); }
            if (focused) select.focus({preventScroll: true});
        } catch (_) {
            if (!entries.includes(entry) || entry.version !== version) return;
            const box = document.createElement('div'); box.className = 'workshop-unavailable';
            const name = document.createElement('strong'); name.textContent = `#${entry.local_id}`;
            const message = document.createElement('p'); text(message, 'Matériau indisponible. Réessayez ou retirez-le de la sélection.');
            box.append(name, message, button('Réessayer', () => load(entry)), button('Retirer', () => remove(entry)));
            entry.slot.replaceChildren(box);
        } finally {
            if (entry.version === version) entry.slot.setAttribute('aria-busy', 'false');
        }
    }
    function add(local_id, paint_id = 0, persist = true) {
        if (entries.length >= 64) { text(notice, 'Limite de 64 matériaux atteinte.'); return; }
        const slot = document.createElement('div'); slot.className = 'workshop-slot';
        const entry = {local_id, paint_id, slot, version: 0, key: ++nextKey};
        const loading = document.createElement('p'); text(loading, 'Chargement…'); slot.append(loading);
        entries.push(entry); grid.append(slot); summary(); if (persist) save(); load(entry);
        if (persist) text(notice, 'Matériau ajouté au Workshop.');
    }
    async function search() {
        clearTimeout(debounce); searchRequest?.abort();
        const controller = new AbortController(); searchRequest = controller;
        suggestions.replaceChildren();
        if (!query.value.trim()) { text(status, 'Saisissez un nom pour trouver des matériaux.'); return; }
        text(status, 'Recherche en cours…');
        try {
            const response = await fetch(form.action + '?' + new URLSearchParams(new FormData(form)), {signal: controller.signal});
            if (!response.ok) throw new Error('Search failed');
            const results = await response.json();
            if (controller.signal.aborted) return;
            text(status, results.length ? 'Ajoutez les matériaux à comparer (40 résultats maximum).' : 'Aucun matériau trouvé');
            for (const item of results) {
                const row = document.createElement('li');
                const image = document.createElement('img'); image.alt = ''; image.loading = 'lazy';
                const src = item.inventory_image_url || item.world_image_url;
                if (src) image.src = src;
                const info = document.createElement('div'); const name = document.createElement('strong'); name.textContent = item.name;
                const type = document.createElement('small'); text(type, item.object_type === 'wall' ? 'Mur' : 'Bloc'); info.append(name, type);
                row.append(image, info, button('Ajouter', () => add(item.local_id))); suggestions.append(row);
            }
        } catch (error) { if (error.name !== 'AbortError') text(status, 'Recherche indisponible. Réessayez.'); }
    }
    form.addEventListener('submit', event => { event.preventDefault(); search(); });
    query.addEventListener('input', () => { searchRequest?.abort(); clearTimeout(debounce); debounce = setTimeout(search, 200); });
    form.elements.object_type.addEventListener('change', search);
    clear.addEventListener('click', () => {
        entries.forEach(closeDetails); entries = []; grid.replaceChildren(); save(); summary(); text(notice, 'Workshop vidé.');
    });
    apply.addEventListener('click', () => {
        entries.forEach(entry => { entry.paint_id = Number(commonPaint.value); load(entry); }); save(); text(notice, 'Peinture appliquée à tous les matériaux.');
    });
    document.getElementById('workshopFind').addEventListener('click', () => {
        if (matchMedia('(max-width: 800px)').matches) {
            document.documentElement.classList.add('filters-open'); document.getElementById('filterToggle').setAttribute('aria-expanded', 'true');
        }
        query.focus();
    });
    try {
        const stored = JSON.parse(localStorage.getItem(key) || 'null');
        if (stored) {
            if (stored.version !== 1 || !Array.isArray(stored.items)) throw new Error('Unsupported saved state');
            stored.items.slice(0, 64).forEach(item => {
                if (item && Number.isSafeInteger(item.local_id) && item.local_id >= 0 && paints.has(item.paint_id)) add(item.local_id, item.paint_id, false);
            });
        }
    } catch (_) {
        warning.hidden = false; text(warning, 'Sélection sauvegardée illisible ou stockage inaccessible. Vous pouvez créer une nouvelle sélection.');
    }
    summary();
    const initialQuery = new URLSearchParams(location.search).get('q');
    if (initialQuery) { query.value = initialQuery; search(); }
})();
