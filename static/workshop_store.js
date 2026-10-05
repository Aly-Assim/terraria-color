/* Shared entry point for adding search results to the local Workshop. */
(() => {
  const storageKey = 'terraria-color-workshop-v1';
  const limit = 64;
  const live = document.createElement('div');
  live.className = 'sr-only'; live.setAttribute('role', 'status'); live.setAttribute('aria-live', 'polite');
  document.body.append(live);

  function add(localId, paintId) {
    const stored = JSON.parse(localStorage.getItem(storageKey) || '{"version":1,"items":[]}');
    if (stored.version !== 1 || !Array.isArray(stored.items)) throw new Error('Invalid Workshop state');
    if (stored.items.length >= limit) return false;
    stored.items.push({local_id: localId, paint_id: paintId});
    localStorage.setItem(storageKey, JSON.stringify(stored));
    return true;
  }

  document.addEventListener('click', event => {
    const button = event.target.closest('[data-add-workshop]');
    if (!button) return;
    const {t} = window.TerrariaUI;
    try {
      const added = add(Number(button.dataset.localId), Number(button.dataset.paintId));
      const message = added ? 'Ajouté' : 'Limite de 64 matériaux atteinte.';
      button.dataset.i18n = message; button.textContent = t(message); live.textContent = t(message);
      if (added) setTimeout(() => { button.dataset.i18n = 'Ajouter au Workshop'; button.textContent = t('Ajouter au Workshop'); }, 1200);
    } catch (_) {
      live.textContent = t('Impossible d’ajouter au Workshop.');
    }
  });
})();
