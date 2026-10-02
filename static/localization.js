/* Attribute-based localization: only explicitly marked UI copy is translated. */
(() => {
    const {labels, help} = window.TerrariaTranslations;
    let language = 'fr';
    try { if (localStorage.getItem('terraria-color-language') === 'en') language = 'en'; } catch (_) {}
    function t(source) {
        if (labels[source]) return labels[source][language];
        const count = source.match(/^(\d+) résultat\(s\)$/);
        if (count) return `${count[1]} ${language === 'fr' ? 'résultat' : 'result'}${Number(count[1]) === 1 ? '' : 's'}`;
        const paint = source.match(/^(\d{2}) · (.+)$/);
        if (paint) return `${paint[1]} · ${t(paint[2])}`;
        return source; // Technical data is never guessed or translated.
    }
    function render(scope = document) {
        scope.querySelectorAll('[data-i18n]').forEach(el => {
            if (!el.dataset.i18n) el.dataset.i18n = el.textContent.trim();
            el.textContent = t(el.dataset.i18n);
        });
        for (const attr of ['aria-label','title','placeholder','alt']) {
            scope.querySelectorAll(`[data-i18n-${attr}]`).forEach(el => el.setAttribute(attr, t(el.getAttribute(`data-i18n-${attr}`))));
        }
        scope.querySelectorAll('[data-inspect-label]').forEach(el => el.setAttribute('aria-label', t('Inspecter ') + el.dataset.objectName));
        scope.querySelectorAll('[data-wiki-label]').forEach(el => el.setAttribute('aria-label', el.dataset.objectName + t(' sur le Wiki (nouvel onglet)')));
        scope.querySelectorAll('[data-image-name]').forEach(el => el.alt = el.dataset.imageName + (el.dataset.imagePaint ? ' · ' + t(el.dataset.imagePaint) : ''));
        scope.querySelectorAll('[data-help]').forEach(el => {
            el.hidden = false;
            el.setAttribute('aria-label', t('Explication : ') + (el.previousElementSibling?.textContent || help[el.dataset.help][language].label));
        });
    }
    function apply() {
        document.documentElement.lang = language;
        document.title = 'Terraria Color · ' + t('Matériaux');
        render();
        document.querySelectorAll('[data-language]').forEach(el => el.setAttribute('aria-pressed', String(el.dataset.language === language)));
        document.dispatchEvent(new Event('languagechange'));
        if (active) open(active);
    }
    window.TerrariaUI = {t, render};
    document.querySelector('.language-switch').hidden = false;
    document.querySelectorAll('[data-language]').forEach(el => el.addEventListener('click', () => {
        language = el.dataset.language;
        try { localStorage.setItem('terraria-color-language', language); } catch (_) {}
        apply();
    }));

    // One tooltip, shared by sidebar and inspector. Keep it inside modal dialogs.
    const tooltip = document.createElement('div');
    tooltip.id = 'metric-tooltip'; tooltip.className = 'metric-tooltip';
    tooltip.setAttribute('role', 'tooltip'); tooltip.hidden = true;
    let active = null, timer = null, touch = false;
    function close() {
        clearTimeout(timer);
        active?.removeAttribute('aria-describedby');
        active = null; tooltip.hidden = true;
    }
    function position() {
        if (!active) return;
        const r = active.getBoundingClientRect(), box = tooltip.getBoundingClientRect();
        const width = document.documentElement.clientWidth;
        const height = window.innerHeight;
        const panel = active.closest('dialog')?.getBoundingClientRect();
        const left = panel ? Math.max(8, panel.left + 8) : 8;
        const right = panel ? Math.min(width - 8, panel.right - 8) : width - 8;
        tooltip.style.left = Math.max(left, Math.min(r.left, right - box.width)) + 'px';
        const above = r.top - box.height - 8;
        tooltip.style.top = Math.max(8, Math.min(above >= 8 ? above : r.bottom + 8, height - box.height - 8)) + 'px';
    }
    function open(button) {
        clearTimeout(timer);
        if (active !== button) close();
        active = button;
        (button.closest('dialog') || document.body).append(tooltip);
        tooltip.textContent = help[button.dataset.help][language].text;
        tooltip.hidden = false;
        button.setAttribute('aria-describedby', tooltip.id);
        position();
    }
    function scheduleClose() {
        clearTimeout(timer);
        timer = setTimeout(() => {
            if (active && document.activeElement !== active && !tooltip.matches(':hover')) close();
        }, 140);
    }
    document.addEventListener('pointerdown', event => {
        touch = event.pointerType === 'touch';
        if (!event.target.closest('[data-help], .metric-tooltip')) close();
    });
    document.addEventListener('pointerover', event => {
        const button = event.target.closest('[data-help]');
        if (button && event.pointerType !== 'touch') open(button);
    });
    document.addEventListener('pointerout', event => { if (event.target.closest('[data-help]')) scheduleClose(); });
    document.addEventListener('focusin', event => {
        if (event.target.matches('[data-help]') && !touch) open(event.target);
        else if (!event.target.closest('.metric-tooltip')) close();
    });
    document.addEventListener('focusout', event => { if (event.target.matches('[data-help]')) scheduleClose(); });
    document.addEventListener('click', event => {
        const button = event.target.closest('[data-help]');
        if (button) {
            if (touch && active === button) close(); else open(button);
        } else if (!event.target.closest('.metric-tooltip')) close();
    });
    tooltip.addEventListener('pointerenter', () => clearTimeout(timer));
    tooltip.addEventListener('pointerleave', scheduleClose);
    document.addEventListener('keydown', event => {
        touch = false;
        if (event.key === 'Escape' && active) {
            close(); event.preventDefault(); event.stopImmediatePropagation();
        }
    }, true);
    window.addEventListener('resize', close);
    document.addEventListener('scroll', event => { if (event.target !== tooltip) close(); }, true);
    document.getElementById('inspector').addEventListener('close', close);
    apply();
})();
