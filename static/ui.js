/* Presentation only: no ranking or color-analysis calculations. */
(() => {
    const root = document.documentElement;
    const toggle = document.getElementById('themeToggle');
    const label = document.getElementById('themeLabel');
    function syncThemeButton() {
        const light = root.dataset.theme === 'light';
        label.textContent = light ? 'Thème sombre' : 'Thème clair';
        toggle.setAttribute('aria-label', light ? 'Activer le thème sombre' : 'Activer le thème clair');
        toggle.setAttribute('aria-pressed', String(light));
    }
    toggle.hidden = false;
    syncThemeButton();
    toggle.addEventListener('click', () => {
        root.dataset.theme = root.dataset.theme === 'light' ? 'dark' : 'light';
        try { localStorage.setItem('terraria-color-theme', root.dataset.theme); } catch (_) { /* Keep working without persistence. */ }
        syncThemeButton();
    });
    window.addEventListener('storage', (event) => {
        if (event.key === 'terraria-color-theme') {
            root.dataset.theme = event.newValue === 'light' ? 'light' : 'dark';
            syncThemeButton();
        }
    });

    const picker = document.getElementById('colorPicker');
    const hex = document.getElementById('colorInput');
    function normalizedHex(value) {
        value = value.trim().replace(/^#/, '');
        if (/^[\da-f]{3}$/i.test(value)) value = [...value].map(c => c + c).join('');
        return /^[\da-f]{6}$/i.test(value) ? '#' + value.toLowerCase() : null;
    }
    picker.addEventListener('input', () => { hex.value = picker.value; });
    hex.addEventListener('input', () => {
        const value = normalizedHex(hex.value);
        if (value) picker.value = value;
    });
    const initial = normalizedHex(hex.value);
    if (initial) picker.value = initial;

    const slider = document.getElementById('dispersion');
    const output = document.getElementById('dispersionValue');
    const block = document.getElementById('dispersionBlock');
    slider.addEventListener('input', () => { output.textContent = slider.value + ' %'; });
    function syncMethod() {
        const dominant = document.querySelector('input[name="color_mode"]:checked').value === 'dominant';
        block.classList.toggle('inactive', dominant);
        // Keep the control submitted so its value survives switching search modes.
        slider.title = dominant ? 'Sans effet en mode Dominante' : 'Favoriser les textures uniformes';
    }
    document.querySelectorAll('input[name="color_mode"]').forEach(input => input.addEventListener('change', syncMethod));
    syncMethod();
})();
