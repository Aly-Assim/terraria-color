/* UI state only. Search parameters, ranking and renderer remain server-owned. */
(() => {
    const root = document.documentElement;
    const {t, render} = window.TerrariaUI;
    const themeToggle = document.getElementById('themeToggle');
    const themeLabel = document.getElementById('themeLabel');
    const systemTheme = matchMedia('(prefers-color-scheme: light)');
    const picker = document.getElementById('colorPicker');
    const hex = document.getElementById('colorInput');
    const colorForm = document.getElementById('colorForm');
    const draft = document.getElementById('draftNotice');
    const initialParams = colorForm ? new URLSearchParams(new FormData(colorForm)).toString() : "";

    function normalizedHex(value) {
        value = value.trim().replace(/^#/, '');
        if (/^[\da-f]{3}$/i.test(value)) value = [...value].map(c => c + c).join('');
        return /^[\da-f]{6}$/i.test(value) ? '#' + value.toLowerCase() : null;
    }
    function rgb(value) { return value.match(/[\da-f]{2}/gi).map(v => parseInt(v, 16)); }
    function luminance(channels) {
        const linear = channels.map(v => { v /= 255; return v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4; });
        return linear[0] * .2126 + linear[1] * .7152 + linear[2] * .0722;
    }
    function accent() {
        if (!hex) return;
        const target = normalizedHex(hex.value);
        if (!target) return;
        const surface = rgb(getComputedStyle(root).getPropertyValue('--surface').trim());
        const ink = root.dataset.theme === 'light' ? [28, 29, 31] : [242, 242, 239];
        const original = rgb(target);
        let safe = original;
        // Target-colored borders get >=3:1 contrast against the surface.
        // Text and keyboard outlines always use neutral theme tokens.
        for (let step = 0; step <= 20; step++) {
            safe = original.map((v, i) => Math.round(v + (ink[i] - v) * step / 20));
            const a = luminance(safe), b = luminance(surface);
            if ((Math.max(a, b) + .05) / (Math.min(a, b) + .05) >= 3) break;
        }
        root.style.setProperty('--target', target);
        root.style.setProperty('--accent', `rgb(${safe.join(', ')})`);
        root.style.setProperty('--accent-soft', `rgba(${safe.join(', ')}, .08)`);
    }
    function syncTheme() {
        const light = root.dataset.theme === 'light';
        themeLabel.textContent = t(light ? 'Sombre' : 'Clair');
        themeToggle.setAttribute('aria-label', t(light ? 'Activer le thème sombre' : 'Activer le thème clair'));
        themeToggle.setAttribute('aria-pressed', String(light));
        accent();
    }
    themeToggle.hidden = false;
    themeToggle.addEventListener('click', () => {
        root.dataset.theme = root.dataset.theme === 'light' ? 'dark' : 'light';
        try { localStorage.setItem('terraria-color-theme', root.dataset.theme); } catch (_) { /* Session-only choice. */ }
        syncTheme();
    });
    systemTheme.addEventListener('change', () => {
        try { if (localStorage.getItem('terraria-color-theme')) return; } catch (_) { return; }
        root.dataset.theme = systemTheme.matches ? 'light' : 'dark';
        syncTheme();
    });
    window.addEventListener('storage', event => {
        if (event.key !== 'terraria-color-theme') return;
        root.dataset.theme = ['light', 'dark'].includes(event.newValue) ? event.newValue : (systemTheme.matches ? 'light' : 'dark');
        syncTheme();
    });
    const initial = hex ? normalizedHex(hex.value) : null;
    if (initial) picker.value = initial;
    picker?.addEventListener('input', () => { hex.value = picker.value; hex.setCustomValidity(''); accent(); });
    hex?.addEventListener('input', () => {
        const value = normalizedHex(hex.value);
        hex.setCustomValidity(value ? '' : t('Saisissez une couleur HEX à trois ou six chiffres.'));
        if (value) { picker.value = value; accent(); }
    });
    syncTheme();

    const slider = document.getElementById('dispersion');
    const output = document.getElementById('dispersionValue');
    const dispersion = document.getElementById('dispersionBlock');
    function syncMethod() {
        if (!colorForm) return;
        const dominant = colorForm.elements.color_mode.value === 'dominant';
        dispersion.classList.toggle('inactive', dominant);
        slider.title = t(dominant ? 'Sans effet en mode Dominante' : 'Pénalité de dispersion');
        // Preserve the submitted slider value when switching methods.
    }
    slider?.addEventListener('input', () => { output.textContent = slider.value + ' %'; });
    colorForm?.addEventListener('input', () => {
        draft.hidden = new URLSearchParams(new FormData(colorForm)).toString() === initialParams;
        syncMethod();
    });
    document.querySelectorAll('select[name="object_type"]').forEach(select => select.addEventListener('change', () => {
        if (!colorForm) return;
        document.querySelectorAll('select[name="object_type"]').forEach(other => { other.value = select.value; });
        draft.hidden = new URLSearchParams(new FormData(colorForm)).toString() === initialParams;
    }));
    syncMethod();
    document.addEventListener('languagechange', () => {
        syncTheme(); syncMethod();
        if (hex?.validity.customError) hex.setCustomValidity(t('Saisissez une couleur HEX à trois ou six chiffres.'));
    });

    const filterToggle = document.getElementById('filterToggle');
    const filterClose = document.getElementById('filterClose');
    filterToggle.hidden = false;
    filterClose.hidden = false;
    function filters(open) {
        root.classList.toggle('filters-open', open);
        filterToggle.setAttribute('aria-expanded', String(open));
        if (!open) filterToggle.focus();
    }
    filterToggle.addEventListener('click', () => filters(!root.classList.contains('filters-open')));
    filterClose.addEventListener('click', () => filters(false));

    const inspector = document.getElementById('inspector');
    const inspectorContent = document.getElementById('inspectorContent');
    const closeButton = document.getElementById('inspectorClose');
    const mobile = matchMedia('(max-width: 800px)');
    let trigger = null;
    let selected = null;
    let resizing = false;
    function showInspector() {
        if (mobile.matches) inspector.showModal(); else inspector.show();
        closeButton.focus({ preventScroll: true });
    }
    function inspect(card, button) {
        if (selected) selected.classList.remove('is-selected');
        selected = card;
        selected.classList.add('is-selected');
        trigger = button;
        const title = document.createElement('h2');
        title.id = 'inspectorTitle';
        title.textContent = card.querySelector('.card-name').textContent;
        const preview = card.querySelector('.image-zone').cloneNode(true);
        preview.querySelector('.inspect-affordance')?.remove();
        preview.querySelector('.inventory-frame')?.remove();
        const sources = document.createElement('div');
        sources.className = 'inspector-sources';
        for (const [role, caption] of [['world', 'Monde · original'], ['inventory', 'Inventaire']]) {
            if (!card.dataset[role]) continue;
            const figure = document.createElement('figure');
            const image = document.createElement('img');
            image.src = card.dataset[role]; image.alt = t(caption); image.setAttribute('data-i18n-alt', caption);
            const label = document.createElement('figcaption'); label.dataset.i18n = caption; label.textContent = t(caption);
            figure.append(image, label); sources.append(figure);
        }
        inspectorContent.replaceChildren(title, preview, card.querySelector('.paint-line').cloneNode(true), sources, card.querySelector('.detail-content').cloneNode(true));
        const wiki = card.querySelector('.wiki-link');
        if (wiki) inspectorContent.append(wiki.cloneNode(true));
        render(inspectorContent);
        inspector.scrollTop = 0;
        if (!inspector.open) showInspector();
    }
    document.addEventListener('click', event => {
        const button = event.target.closest('[data-inspect]');
        if (button?.closest('.cards')) inspect(button.closest('.card'), button);
    });
    closeButton.addEventListener('click', () => inspector.close());
    inspector.addEventListener('close', () => {
        if (resizing) return;
        selected?.classList.remove('is-selected');
        trigger?.focus({ preventScroll: true });
    });
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape' && inspector.open) { event.preventDefault(); inspector.close(); }
    });
    inspector.addEventListener('click', event => {
        if (!mobile.matches || event.target !== inspector) return;
        const box = inspector.getBoundingClientRect();
        if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) inspector.close();
    });
    mobile.addEventListener('change', () => {
        if (!inspector.open) return;
        resizing = true;
        inspector.close();
        // Close events are queued; reopen after that event has been handled.
        setTimeout(() => { showInspector(); resizing = false; }, 0);
    });
})();
