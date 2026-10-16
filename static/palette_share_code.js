/* Share Code v2: palette name, ordered swatches and their material references. */
window.PaletteShareCode = (() => {
    const currentPrefix = 'TCP2:';
    const legacyPrefix = 'TCP1:';
    const maxLength = 524288;
    const hexPattern = /^#[0-9a-fA-F]{6}$/;

    function validateName(name) {
        if (typeof name !== 'string' || !name.trim() || name.trim().length > 80 || /[\u0000-\u001f\u007f]/.test(name)) throw new Error('Nom de palette invalide.');
        return name.trim();
    }

    function validateColors(colors) {
        if (!Array.isArray(colors) || colors.length < 1 || colors.length > 256 || !colors.every(color => typeof color === 'string' && hexPattern.test(color))) throw new Error('Couleurs de palette invalides (1 à 256 HEX #RRGGBB).');
        return colors.map(color => color.toUpperCase());
    }

    function validateMaterial(material) {
        if (!Array.isArray(material) || material.length !== 2 || !material.every(Number.isSafeInteger) || material[0] < 0 || material[1] < 0 || material[1] > 30) throw new Error('Code de palette invalide.');
        return [material[0], material[1]];
    }

    function normalizeSwatches(swatches) {
        if (!Array.isArray(swatches) || swatches.length < 1 || swatches.length > 256) throw new Error('Couleurs de palette invalides (1 à 256 HEX #RRGGBB).');
        return swatches.map(swatch => {
            if (!Array.isArray(swatch) || swatch.length !== 2 || typeof swatch[0] !== 'string' || !hexPattern.test(swatch[0]) || !Array.isArray(swatch[1])) throw new Error('Code de palette invalide.');
            const seen = new Set();
            const materials = swatch[1].map(validateMaterial).filter(material => {
                const key = material.join(':');
                if (seen.has(key)) return false;
                seen.add(key); return true;
            });
            return {hex: swatch[0].toUpperCase(), materials};
        });
    }

    function encode(data) {
        const bytes = new TextEncoder().encode(JSON.stringify(data));
        let binary = '';
        for (const byte of bytes) binary += String.fromCharCode(byte);
        return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
    }

    function decode(code, prefix) {
        const encoded = code.slice(prefix.length);
        if (!encoded || !/^[A-Za-z0-9_-]+$/.test(encoded) || encoded.length % 4 === 1) throw new Error('Code de palette invalide.');
        const binary = atob(encoded.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - encoded.length % 4) % 4));
        const bytes = Uint8Array.from(binary, char => char.charCodeAt(0));
        return JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(bytes));
    }

    function exportCode(name, swatches) {
        const cleanName = validateName(name);
        const compact = swatches.map(swatch => [swatch.hex, (swatch.items || []).map(item => [Number(item.local_id), Number(item.paint_id)])]);
        const cleanSwatches = normalizeSwatches(compact);
        if (cleanSwatches.reduce((total, swatch) => total + swatch.materials.length, 0) > 4096) throw new Error('Code de palette trop long.');
        const data = {v: 2, n: cleanName, s: cleanSwatches.map(swatch => [swatch.hex, swatch.materials])};
        const code = currentPrefix + encode(data);
        if (code.length > maxLength) throw new Error('Code de palette trop long.');
        return code;
    }

    function importCode(value) {
        const code = value.trim();
        if (!code) throw new Error('Collez un code de palette.');
        if (code.length > maxLength) throw new Error('Code de palette trop long.');
        const prefix = code.startsWith(currentPrefix) ? currentPrefix : code.startsWith(legacyPrefix) ? legacyPrefix : null;
        if (!prefix) throw new Error('Préfixe de code inconnu.');
        try {
            const data = decode(code, prefix);
            if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('Code de palette invalide.');
            if (data.v === 1 && prefix === legacyPrefix) {
                if (Object.keys(data).sort().join(',') !== 'c,n,v') throw new Error('Code de palette invalide.');
                const colors = validateColors(data.c);
                return {name: validateName(data.n), swatches: colors.map(hex => ({hex, materials: []}))};
            }
            if (data.v !== 2 || prefix !== currentPrefix) throw new Error('Version de code non prise en charge.');
            if (Object.keys(data).sort().join(',') !== 'n,s,v') throw new Error('Code de palette invalide.');
            const swatches = normalizeSwatches(data.s);
            if (swatches.reduce((total, swatch) => total + swatch.materials.length, 0) > 4096) throw new Error('Code de palette trop long.');
            return {name: validateName(data.n), swatches};
        } catch (error) {
            if (['Version de code non prise en charge.', 'Nom de palette invalide.', 'Code de palette invalide.'].includes(error.message) || error.message.startsWith('Couleurs de palette')) throw error;
            throw new Error('Code de palette corrompu.');
        }
    }

    return {exportCode, importCode};
})();
