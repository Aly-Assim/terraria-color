/* Share Code v1: palette name and ordered HEX colors only. No server storage. */
window.PaletteShareCode = (() => {
    const prefix = 'TCP1:';
    const maxLength = 4096;
    const hexPattern = /^#[0-9a-fA-F]{6}$/;
    function validate(name, colors) {
        if (typeof name !== 'string' || !name.trim() || name.trim().length > 80 || /[\u0000-\u001f\u007f]/.test(name)) throw new Error('Nom de palette invalide.');
        if (!Array.isArray(colors) || colors.length < 1 || colors.length > 256 || !colors.every(color => typeof color === 'string' && hexPattern.test(color))) throw new Error('Couleurs de palette invalides (1 à 256 HEX #RRGGBB).');
        return {name: name.trim(), colors: colors.map(color => color.toUpperCase())};
    }
    function exportCode(name, colors) {
        const palette = validate(name, colors);
        const json = JSON.stringify({v: 1, n: palette.name, c: palette.colors});
        const bytes = new TextEncoder().encode(json);
        let binary = '';
        for (const byte of bytes) binary += String.fromCharCode(byte);
        return prefix + btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
    }
    function importCode(value) {
        const code = value.trim();
        if (!code) throw new Error('Collez un code de palette.');
        if (code.length > maxLength) throw new Error('Code de palette trop long.');
        if (!code.startsWith(prefix)) throw new Error('Préfixe de code inconnu.');
        const encoded = code.slice(prefix.length);
        if (!encoded || !/^[A-Za-z0-9_-]+$/.test(encoded) || encoded.length % 4 === 1) throw new Error('Code de palette invalide.');
        try {
            const binary = atob(encoded.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - encoded.length % 4) % 4));
            const bytes = Uint8Array.from(binary, char => char.charCodeAt(0));
            const data = JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(bytes));
            if (!data || typeof data !== 'object' || Array.isArray(data) || data.v !== 1) throw new Error('Version de code non prise en charge.');
            if (Object.keys(data).sort().join(',') !== 'c,n,v') throw new Error('Code de palette invalide.');
            return validate(data.n, data.c);
        } catch (error) {
            if (error.message === 'Version de code non prise en charge.' || error.message === 'Nom de palette invalide.' || error.message.startsWith('Couleurs de palette') || error.message === 'Code de palette invalide.') throw error;
            throw new Error('Code de palette corrompu.');
        }
    }
    return {exportCode, importCode};
})();
