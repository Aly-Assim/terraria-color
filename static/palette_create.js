/* Palette Create draft and UI; generation and color ranking stay server-owned. */
(() => {
    const {t, render} = window.TerrariaUI;
    const key = 'terraria-palette-create-draft-v1';
    const share = window.PaletteShareCode;
    const expiry = window.PaletteExpiry;
    const $ = id => document.getElementById(id);
    const generateForm = $('generateForm'), augmentForm = $('augmentForm'), colorForm = $('colorForm');
    // The selected swatch owns the target color; the existing Color Search form owns its filters.
    $('colorInput').disabled = true; $('colorPicker').disabled = true;
    const swatches = $('paletteSwatches'), results = $('paletteResults'), selected = $('paletteSelected');
    const manualHex = $('manualHex'), manualPicker = $('manualColorPicker');
    const message = $('paletteMessage');
    let state = {palettes: [], activePaletteId: null, activeSwatchId: null, lastAugment: null};
    let helpVisible = true;
    let requestNumber = 0;
    try {
        const saved = JSON.parse(localStorage.getItem(key));
        if (saved && Array.isArray(saved.palettes)) state = {...state, ...saved};
        helpVisible = localStorage.getItem('terraria-palette-help') !== 'off';
    } catch (_) { /* Start with an empty draft. */ }
    const uid = () => globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`;
    const current = () => state.palettes.find(p => p.id === state.activePaletteId);
    const active = () => current()?.swatches.find(s => s.id === state.activeSwatchId);
    const normalize = value => /^#?[0-9a-fA-F]{6}$/.test(value.trim()) ? '#' + value.trim().replace(/^#/, '').toLowerCase() : null;
    function save() { try { localStorage.setItem(key, JSON.stringify(state)); } catch (_) { notice(t('Brouillon local indisponible.'), true); } }
    function pruneExpired() {
        const {palettes, changed} = expiry.migrateAndPrune(state.palettes);
        if (!changed) return false;
        state.palettes = palettes;
        if (!current()) {
            state.activePaletteId = palettes[0]?.id || null;
            state.activeSwatchId = palettes[0]?.swatches[0]?.id || null;
        }
        if (state.lastAugment && !palettes.some(p => p.id === state.lastAugment.sourceId)) state.lastAugment = null;
        save(); return true;
    }
    function notice(value, error = false) { message.textContent = value; message.hidden = !value; message.classList.toggle('error', error); }
    async function post(url, payload) {
        const response = await fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
        const data = await response.json();
        if (!response.ok) throw new Error(data.error ? t(data.error) : t('La requête a échoué.'));
        return data;
    }
    const makeSwatches = colors => colors.map(hex => ({id: uid(), hex, items: []}));
    function newPalette(colors, kind, sourceId = null, extra = {}) {
        const palette = {id: uid(), kind, sourceId, swatches: makeSwatches(colors), ...extra};
        expiry.touch(palette);
        state.palettes.push(palette);
        state.activePaletteId = palette.id;
        state.activeSwatchId = palette.swatches[0]?.id || null;
        $('renamePalettePanel').hidden = true;
        $('deletePalettePanel').hidden = true;
        save(); draw(); search();
    }
    function replacePaletteColors(palette, colors) {
        palette.swatches = makeSwatches(colors);
        expiry.touch(palette);
        state.activePaletteId = palette.id;
        state.activeSwatchId = palette.swatches[0]?.id || null;
        save(); draw(); search();
    }
    function syncHelp() {
        $('results').classList.toggle('help-off', !helpVisible);
        const button = $('togglePaletteHelp');
        button.textContent = t(helpVisible ? 'Masquer les aides' : 'Afficher les aides');
        button.setAttribute('aria-pressed', String(helpVisible));
    }
    function setActive(hex) {
        $('colorInput').value = hex;
        $('colorInput').dispatchEvent(new Event('input', {bubbles: true}));
        manualHex.value = hex; manualPicker.value = hex;
        $('activeColorLabel').innerHTML = '';
        const chip = document.createElement('i'); chip.className = 'swatch'; chip.style.setProperty('--swatch', hex);
        const code = document.createElement('strong'); code.className = 'mono'; code.textContent = hex;
        $('activeColorLabel').append(chip, code);
    }
    function draw() {
        const palette = current(), swatch = active();
        const history = $('paletteHistory'); history.replaceChildren();
        for (const [index, entry] of state.palettes.entries()) {
            const option = document.createElement('option'); option.value = entry.id;
            const fallback = t(entry.kind === 'manual' ? 'Palette manuelle' : entry.kind === 'augmented' ? 'Palette augmentée' : entry.kind === 'analogous' ? 'Analogous' : 'Complementary');
            option.textContent = `${index + 1} · ${entry.name || fallback} · ${entry.swatches.length}`;
            history.append(option);
        }
        if (palette) history.value = palette.id;
        history.disabled = !palette;
        swatches.replaceChildren();
        palette?.swatches.forEach((item, index) => {
            const button = document.createElement('button'); button.type = 'button'; button.className = 'palette-swatch';
            button.style.setProperty('--palette-color', item.hex);
            button.setAttribute('aria-pressed', String(item.id === state.activeSwatchId));
            button.setAttribute('aria-label', `${t('Couleur')} ${index + 1}: ${item.hex}`);
            button.innerHTML = `<span class="palette-swatch-color"></span><span class="mono"></span><small></small>`;
            button.querySelector('.mono').textContent = item.hex;
            button.querySelector('small').textContent = `${item.items.length} ${t(item.items.length === 1 ? 'matériau' : 'matériaux')}`;
            button.addEventListener('click', () => { state.activeSwatchId = item.id; save(); draw(); search(); });
            swatches.append(button);
        });
        const source = state.palettes.find(entry => entry.id === palette?.sourceId);
        $('paletteSource').hidden = !source;
        $('paletteSourceColors').replaceChildren();
        source?.swatches.forEach(item => { const chip = document.createElement('i'); chip.style.setProperty('--source-color', item.hex); chip.title = item.hex; $('paletteSourceColors').append(chip); });
        $('openAugment').disabled = !palette?.swatches.length;
        if (!palette?.swatches.length) { $('augmentPanel').hidden = true; $('openAugment').setAttribute('aria-expanded', 'false'); }
        $('rerollSteps').disabled = !(palette?.kind === 'augmented' && (palette.augmentPayload || state.lastAugment?.sourceId === palette.sourceId));
        $('renamePalette').disabled = !palette;
        $('exportPalette').disabled = !palette?.swatches.length;
        $('deletePalette').disabled = !palette;
        $('importPaletteWorkshop').disabled = !palette?.swatches.some(item => item.items.length);
        if (swatch) { setActive(swatch.hex); drawSelected(); }
        else { ++requestNumber; $('activeColorLabel').textContent = t('Choisissez une couleur dans la palette.'); selected.replaceChildren(); results.replaceChildren(); $('paletteResultCount').textContent = ''; $('paletteSearchStatus').textContent = t('Choisissez une couleur pour lancer la recherche.'); }
        updateSelectedButtons();
    }
    function updateSelectedButtons() {
        const keys = new Set((active()?.items || []).map(item => `${item.local_id}:${item.paint_id}`));
        results.querySelectorAll('[data-palette-toggle]').forEach(button => {
            const on = keys.has(`${button.dataset.localId}:${button.dataset.paintId}`);
            button.textContent = t(on ? 'Retirer de cette couleur' : 'Associer à cette couleur');
            button.setAttribute('aria-pressed', String(on));
            button.closest('.card').classList.toggle('palette-associated', on);
        });
    }
    function drawSelected() {
        selected.replaceChildren();
        $('importPaletteWorkshop').disabled = !current()?.swatches.some(swatch => swatch.items.length);
        const items = active()?.items || [];
        if (!items.length) { const text = document.createElement('p'); text.className = 'hint'; text.textContent = t('Aucun matériau associé à cette couleur.'); selected.append(text); return; }
        for (const item of items) {
            const row = document.createElement('div'); row.className = 'palette-selected-item';
            const image = document.createElement('img'); image.src = item.image_url; image.alt = ''; image.loading = 'lazy';
            const label = document.createElement('span'); label.textContent = item.name + (item.paint_name ? ` · ${t(item.paint_name)}` : '');
            const inspect = document.createElement('button'); inspect.type = 'button'; inspect.className = 'quiet-button'; inspect.textContent = t('Détails');
            inspect.addEventListener('click', async () => {
                try {
                    const response = await fetch(`/api/workshop/item/${item.local_id}/${item.paint_id}`);
                    if (!response.ok) throw new Error(t('Aperçu indisponible'));
                    const holder = document.createElement('div'); holder.className = 'cards palette-temp-card'; holder.innerHTML = await response.text();
                    document.body.append(holder);
                    const temporaryTrigger = holder.querySelector('[data-inspect]');
                    temporaryTrigger.inspectorReturn = inspect;
                    temporaryTrigger.click(); holder.remove();
                } catch (error) { notice(error.message, true); }
            });
            const addWorkshop = document.createElement('button'); addWorkshop.type = 'button'; addWorkshop.className = 'quiet-button';
            addWorkshop.dataset.addWorkshop = ''; addWorkshop.dataset.localId = item.local_id; addWorkshop.dataset.paintId = item.paint_id;
            addWorkshop.dataset.i18n = 'Ajouter au Workshop'; addWorkshop.textContent = t('Ajouter au Workshop');
            const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'quiet-button'; remove.textContent = t('Retirer');
            remove.addEventListener('click', () => { const palette = current(); active().items = active().items.filter(other => !(other.local_id === item.local_id && other.paint_id === item.paint_id)); expiry.touch(palette); save(); drawSelected(); updateSelectedButtons(); drawSwatchCounts(); });
            row.append(image, label, inspect, addWorkshop, remove); selected.append(row);
        }
    }
    function drawSwatchCounts() { swatches.querySelectorAll('small').forEach((el, index) => { const count = current().swatches[index].items.length; el.textContent = `${count} ${t(count === 1 ? 'matériau' : 'matériaux')}`; }); }
    async function search() {
        const swatch = active(); if (!swatch) return;
        const seq = ++requestNumber;
        results.replaceChildren(); $('paletteResultCount').textContent = '';
        $('paletteSearchStatus').textContent = t('Recherche en cours…');
        const params = new URLSearchParams(new FormData(colorForm)); params.set('color', swatch.hex);
        try {
            const response = await fetch('/api/palette-create/search?' + params);
            const data = await response.json();
            if (!response.ok) throw new Error(data.error ? t(data.error) : t('La recherche a échoué.'));
            if (seq !== requestNumber) return;
            for (const item of data.results) {
                const holder = document.createElement('div'); holder.innerHTML = item.html;
                const card = holder.firstElementChild;
                const button = document.createElement('button'); button.type = 'button'; button.className = 'card-palette-toggle'; button.dataset.paletteToggle = '';
                button.dataset.localId = item.local_id; button.dataset.paintId = item.paint_id;
                button.addEventListener('click', () => {
                    const target = active(); if (!target) return;
                    const found = target.items.findIndex(saved => saved.local_id === item.local_id && saved.paint_id === item.paint_id);
                    if (found >= 0) target.items.splice(found, 1); else target.items.push({local_id: item.local_id, paint_id: item.paint_id, name: item.name, paint_name: item.paint_name, image_url: item.image_url});
                    expiry.touch(current()); save(); drawSelected(); updateSelectedButtons(); drawSwatchCounts();
                });
                card.querySelector('.card-body').append(button);
                results.append(card);
            }
            render(results); updateSelectedButtons();
            $('paletteResultCount').textContent = `${data.results.length} ${t('résultats')}`;
            $('paletteSearchStatus').textContent = data.results.length ? '' : t('Aucun matériau trouvé');
        } catch (error) { if (seq === requestNumber) $('paletteSearchStatus').textContent = error.message; }
    }
    function generationPayload(reroll = false) {
        const values = Object.fromEntries(new FormData(generateForm));
        if (reroll) values.seed_color = '';
        return values;
    }
    async function generate(reroll = false) {
        try {
            const target = reroll && ['analogous', 'complementary'].includes(current()?.kind) ? current() : null;
            const payload = generationPayload(reroll);
            const data = await post('/api/palette-create/generate', payload);
            if (target && !state.palettes.includes(target)) return;
            generateForm.elements.seed_color.value = data.seed_color;
            if (target) { target.kind = data.mode; replacePaletteColors(target, data.colors); }
            else newPalette(data.colors, data.mode);
            notice('');
        } catch (error) { notice(error.message, true); }
    }
    async function augment(reroll = false) {
        const target = reroll ? current() : null;
        const source = reroll ? state.palettes.find(p => p.id === target?.sourceId) : current();
        if (!reroll && !source?.swatches.length) return;
        if (reroll && target?.kind !== 'augmented') return;
        const previous = target?.augmentPayload || (target && state.lastAugment?.sourceId === target.sourceId ? state.lastAugment.payload : null);
        if (reroll && !previous) return;
        const payload = reroll ? {...previous} : {...Object.fromEntries(new FormData(augmentForm)), colors: source.swatches.map(item => item.hex)};
        try {
            const data = await post('/api/palette-create/augment', payload);
            if (!state.palettes.includes(reroll ? target : source)) return;
            if (reroll) { target.augmentPayload = {...payload}; replacePaletteColors(target, data.colors); }
            else { state.lastAugment = {sourceId: source.id, payload: {...payload}}; newPalette(data.colors, 'augmented', source.id, {augmentPayload: {...payload}}); }
            notice(`${t('Pas utilisés')}: ${data.steps.map(v => v.toFixed(5)).join(' / ')}`);
        } catch (error) { notice(error.message, true); }
    }
    function manualColor() { const hex = normalize(manualHex.value); if (!hex) notice(t('Saisissez une couleur HEX à six chiffres.'), true); return hex; }
    manualPicker.addEventListener('input', () => { manualHex.value = manualPicker.value; notice(''); });
    manualHex.addEventListener('input', () => { const hex = normalize(manualHex.value); if (hex) { manualPicker.value = hex; notice(''); } });
    generateForm.addEventListener('submit', event => { event.preventDefault(); generate(); });
    $('rerollSeed').addEventListener('click', () => generate(true));
    generateForm.elements.mode.addEventListener('change', () => {
        const disabled = generateForm.elements.mode.value === 'complementary';
        $('generationSteps').classList.toggle('inactive', disabled);
        for (const name of ['lightness_step', 'green_red_step', 'blue_yellow_step']) generateForm.elements[name].disabled = disabled;
    });
    $('newManual').addEventListener('click', () => { newPalette([], 'manual'); notice(''); });
    $('openAugment').addEventListener('click', () => {
        if (!current()?.swatches.length) return;
        const panel = $('augmentPanel'); panel.hidden = !panel.hidden;
        $('openAugment').setAttribute('aria-expanded', String(!panel.hidden));
        if (!panel.hidden) $('augmentFactor').focus();
    });
    $('togglePaletteHelp').addEventListener('click', () => {
        helpVisible = !helpVisible;
        try { localStorage.setItem('terraria-palette-help', helpVisible ? 'on' : 'off'); } catch (_) {}
        syncHelp();
    });
    $('renamePalette').addEventListener('click', () => {
        if (!current()) return;
        $('deletePalettePanel').hidden = true;
        $('renamePalettePanel').hidden = false;
        $('paletteName').value = current().name || '';
        $('paletteName').focus();
    });
    $('cancelPaletteName').addEventListener('click', () => { $('renamePalettePanel').hidden = true; });
    $('savePaletteName').addEventListener('click', () => {
        const palette = current(); if (!palette) return;
        const name = $('paletteName').value.trim();
        if (!name) { notice(t('Donnez un nom à cette palette.'), true); $('paletteName').focus(); return; }
        if (palette.name !== name) { palette.name = name; expiry.touch(palette); save(); }
        $('renamePalettePanel').hidden = true; draw(); notice('');
    });
    $('paletteName').addEventListener('keydown', event => { if (event.key === 'Enter') { event.preventDefault(); $('savePaletteName').click(); } });
    function closeSharePanels() { $('exportPalettePanel').hidden = true; $('importPalettePanel').hidden = true; }
    $('exportPalette').addEventListener('click', () => {
        const palette = current(); if (!palette?.swatches.length) return;
        try {
            const fallback = t(palette.kind === 'manual' ? 'Palette manuelle' : palette.kind === 'augmented' ? 'Palette augmentée' : palette.kind === 'analogous' ? 'Analogous' : 'Complementary');
            $('paletteExportCode').value = share.exportCode(palette.name || fallback, palette.swatches);
            closeSharePanels(); $('paletteCopyStatus').textContent = ''; $('exportPalettePanel').hidden = false;
            $('paletteExportCode').focus(); $('paletteExportCode').select(); notice('');
        } catch (error) { notice(t(error.message), true); }
    });
    $('closePaletteExport').addEventListener('click', closeSharePanels);
    $('copyPaletteCode').addEventListener('click', async () => {
        const field = $('paletteExportCode');
        try { await navigator.clipboard.writeText(field.value); $('paletteCopyStatus').textContent = t('Code copié.'); }
        catch (_) { field.focus(); field.select(); $('paletteCopyStatus').textContent = t('Copie automatique indisponible. Copiez le code sélectionné.'); }
    });
    $('importPalette').addEventListener('click', () => {
        closeSharePanels(); $('paletteImportCode').value = ''; $('paletteImportError').textContent = '';
        $('importPalettePanel').hidden = false; $('paletteImportCode').focus();
    });
    $('cancelImportPalette').addEventListener('click', closeSharePanels);
    $('confirmImportPalette').addEventListener('click', async () => {
        try {
            const {name, swatches: importedSwatches} = share.importCode($('paletteImportCode').value);
            const references = importedSwatches.flatMap(swatch => swatch.materials);
            let resolved = [];
            if (references.length) resolved = (await post('/api/palette-create/materials', {items: references})).items;
            const materialMap = new Map(resolved.map(item => [`${item.local_id}:${item.paint_id}`, item]));
            const palette = {
                id: uid(), kind: 'manual', sourceId: null, name,
                swatches: importedSwatches.map(swatch => ({
                    id: uid(), hex: swatch.hex.toLowerCase(),
                    items: swatch.materials.map(([localId, paintId]) => ({...materialMap.get(`${localId}:${paintId}`)})),
                })),
            };
            if (palette.swatches.some(swatch => swatch.items.some(item => !item.local_id && item.local_id !== 0))) throw new Error('Impossible de restaurer les matériaux de la palette.');
            expiry.touch(palette);
            state.palettes.push(palette);
            state.activePaletteId = palette.id;
            state.activeSwatchId = palette.swatches[0]?.id || null;
            save(); draw(); search();
            closeSharePanels(); notice(t('Palette importée.'));
        } catch (error) { $('paletteImportError').textContent = t(error.message); }
    });
    $('importPaletteWorkshop').addEventListener('click', () => {
        const items = current()?.swatches.flatMap(swatch => swatch.items) || [];
        if (!items.length) return;
        try {
            const {added, limitReached} = window.TerrariaWorkshopStore.addMany(items);
            notice(added ? `${added} ${t(added === 1 ? 'matériau ajouté au Workshop.' : 'matériaux ajoutés au Workshop.')}${limitReached ? ` ${t('Limite de 64 matériaux atteinte.')}` : ''}` : t(limitReached ? 'Limite de 64 matériaux atteinte.' : 'Ces matériaux sont déjà dans le Workshop.'));
        } catch (_) { notice(t('Impossible d’ajouter au Workshop.'), true); }
    });
    $('deletePalette').addEventListener('click', () => {
        if (!current()) return;
        $('renamePalettePanel').hidden = true;
        $('deletePalettePanel').hidden = false;
        $('confirmDeletePalette').focus();
    });
    $('cancelDeletePalette').addEventListener('click', () => { $('deletePalettePanel').hidden = true; });
    $('confirmDeletePalette').addEventListener('click', () => {
        const index = state.palettes.findIndex(p => p.id === state.activePaletteId);
        if (index < 0) return;
        const removed = state.palettes.splice(index, 1)[0];
        if (state.lastAugment?.sourceId === removed.id) state.lastAugment = null;
        const next = state.palettes[Math.min(index, state.palettes.length - 1)];
        state.activePaletteId = next?.id || null;
        state.activeSwatchId = next?.swatches[0]?.id || null;
        $('deletePalettePanel').hidden = true;
        $('renamePalettePanel').hidden = true;
        save(); draw(); if (active()) search(); notice('');
    });
    $('paletteHistory').addEventListener('change', event => { state.activePaletteId = event.target.value; state.activeSwatchId = current()?.swatches[0]?.id || null; $('renamePalettePanel').hidden = true; $('deletePalettePanel').hidden = true; closeSharePanels(); save(); draw(); search(); });
    $('addColor').addEventListener('click', () => {
        const hex = manualColor(); if (!hex) return;
        if (!current()) newPalette([], 'manual');
        const item = {id: uid(), hex, items: []}; current().swatches.push(item); expiry.touch(current()); state.activeSwatchId = item.id; save(); draw(); search(); notice('');
    });
    $('editColor').addEventListener('click', () => { const hex = manualColor(); if (!hex || !active()) return; if (active().hex !== hex) { active().hex = hex; expiry.touch(current()); save(); } draw(); search(); notice(''); });
    $('removeColor').addEventListener('click', () => { const palette = current(); if (!palette || !active()) return; palette.swatches = palette.swatches.filter(item => item.id !== state.activeSwatchId); expiry.touch(palette); state.activeSwatchId = palette.swatches[0]?.id || null; save(); draw(); search(); });
    function move(delta) { const list = current()?.swatches; if (!list) return; const index = list.findIndex(item => item.id === state.activeSwatchId); const next = index + delta; if (index < 0 || next < 0 || next >= list.length) return; [list[index], list[next]] = [list[next], list[index]]; expiry.touch(current()); save(); draw(); }
    $('moveColorUp').addEventListener('click', () => move(-1)); $('moveColorDown').addEventListener('click', () => move(1));
    augmentForm.addEventListener('submit', event => { event.preventDefault(); augment(); });
    $('rerollSteps').addEventListener('click', () => augment(true));
    colorForm.addEventListener('submit', event => { event.preventDefault(); if (active()) search(); });
    colorForm.addEventListener('change', () => { if (active()) search(); });
    document.addEventListener('languagechange', () => { draw(); syncHelp(); if (active()) { render(results); updateSelectedButtons(); } });
    document.addEventListener('click', event => {
        if (!event.target.closest('.palette-page, #colorForm') || !pruneExpired()) return;
        event.preventDefault(); event.stopImmediatePropagation(); draw(); if (active()) search();
    }, true);
    document.addEventListener('submit', event => {
        if (!event.target.closest('.palette-page, #colorForm') || !pruneExpired()) return;
        event.preventDefault(); event.stopImmediatePropagation(); draw(); if (active()) search();
    }, true);
    document.addEventListener('change', event => {
        if (!event.target.closest('.palette-page, #colorForm') || !pruneExpired()) return;
        event.stopImmediatePropagation(); draw(); if (active()) search();
    }, true);
    document.addEventListener('visibilitychange', () => { if (!document.hidden && pruneExpired()) { draw(); if (active()) search(); } });
    pruneExpired(); syncHelp(); draw(); if (active()) search();
})();
