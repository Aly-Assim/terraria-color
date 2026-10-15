/* Palette Create draft expiration; timestamps belong to palettes, not the session. */
window.PaletteExpiry = (() => {
    const lifetime = 24 * 60 * 60 * 1000;
    function migrateAndPrune(palettes, now = Date.now()) {
        let changed = false;
        const remaining = palettes.filter(palette => {
            if (!Number.isFinite(palette.lastModified)) { palette.lastModified = now; changed = true; }
            if (now - palette.lastModified >= lifetime) { changed = true; return false; }
            return true;
        });
        return {palettes: remaining, changed};
    }
    function touch(palette, now = Date.now()) { palette.lastModified = now; }
    return {migrateAndPrune, touch};
})();
