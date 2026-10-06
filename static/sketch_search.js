(() => {
  const {t, render} = window.TerrariaUI;
  const canvas = document.getElementById('sketchCanvas');
  const context = canvas.getContext('2d', {willReadFrequently: true});
  const brushSize = document.getElementById('brushSize');
  const drawButton = document.getElementById('drawMode');
  const lineButton = document.getElementById('lineMode');
  const eraseButton = document.getElementById('eraseMode');
  const clearButton = document.getElementById('clearCanvas');
  const searchButton = document.getElementById('searchSketch');
  const resultCount = document.getElementById('resultCount');
  const status = document.getElementById('sketchStatus');
  const count = document.getElementById('sketchResultCount');
  const results = document.getElementById('sketchResults');
  const empty = document.getElementById('sketchEmpty');
  const storageKey = 'terraria-color-sketch-v1';
  let drawing = false;
  let mode = 'draw';
  let lineStart = null;
  let lineSnapshot = null;

  function saveCanvas() {
    try { sessionStorage.setItem(storageKey, canvas.toDataURL('image/png')); } catch (_) { /* Session persistence is optional. */ }
  }
  function clearCanvas(forget = true) {
    context.fillStyle = '#fff';
    context.fillRect(0, 0, 48, 48);
    if (forget) try { sessionStorage.removeItem(storageKey); } catch (_) { /* Canvas still works without storage. */ }
    results.replaceChildren();
    empty.hidden = false;
    status.textContent = '';
    count.textContent = t('Aucun résultat');
  }
  function setMode(next) {
    mode = next;
    drawButton.setAttribute('aria-pressed', String(mode === 'draw'));
    lineButton.setAttribute('aria-pressed', String(mode === 'line'));
    eraseButton.setAttribute('aria-pressed', String(mode === 'erase'));
  }
  function point(event) {
    const box = canvas.getBoundingClientRect();
    return {x: Math.floor((event.clientX - box.left) * 48 / box.width), y: Math.floor((event.clientY - box.top) * 48 / box.height)};
  }
  function stamp(x, y, erase = false) {
    const size = Number(brushSize.value), offset = Math.floor(size / 2);
    context.fillStyle = erase ? '#fff' : '#000';
    context.fillRect(x - offset, y - offset, size, size);
  }
  function paint(event) { const p = point(event); stamp(p.x, p.y, mode === 'erase'); }
  function previewLine(event) {
    if (!lineStart || !lineSnapshot) return;
    context.putImageData(lineSnapshot, 0, 0);
    const end = point(event);
    let x = lineStart.x, y = lineStart.y;
    const dx = Math.abs(end.x - x), dy = Math.abs(end.y - y);
    const sx = x < end.x ? 1 : -1, sy = y < end.y ? 1 : -1;
    let error = dx - dy;
    while (true) {
      stamp(x, y);
      if (x === end.x && y === end.y) break;
      const doubled = error * 2;
      if (doubled > -dy) { error -= dy; x += sx; }
      if (doubled < dx) { error += dx; y += sy; }
    }
  }
  canvas.addEventListener('pointerdown', event => {
    drawing = true; canvas.setPointerCapture(event.pointerId);
    if (mode === 'line') { lineStart = point(event); lineSnapshot = context.getImageData(0, 0, 48, 48); previewLine(event); }
    else paint(event);
  });
  canvas.addEventListener('pointermove', event => { if (drawing) mode === 'line' ? previewLine(event) : paint(event); });
  canvas.addEventListener('pointerup', event => { if (drawing && mode === 'line') previewLine(event); if (drawing) saveCanvas(); drawing = false; lineStart = lineSnapshot = null; });
  canvas.addEventListener('pointercancel', () => { if (lineSnapshot) context.putImageData(lineSnapshot, 0, 0); drawing = false; lineStart = lineSnapshot = null; });
  drawButton.addEventListener('click', () => setMode('draw'));
  lineButton.addEventListener('click', () => setMode('line'));
  eraseButton.addEventListener('click', () => setMode('erase'));
  clearButton.addEventListener('click', clearCanvas);

  searchButton.addEventListener('click', async () => {
    const rgba = context.getImageData(0, 0, 48, 48).data;
    const pixels = Array.from({length: 48 * 48}, (_, index) => rgba[index * 4]);
    if (pixels.every(value => value === 255)) { status.textContent = t('Dessinez quelque chose avant de rechercher.'); return; }
    searchButton.disabled = true; status.textContent = t('Recherche…');
    try {
      const edgeMethod = document.querySelector('input[name="edge_method"]:checked').value;
      const response = await fetch('/api/sketch-search/match', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({pixels, k: Number(resultCount.value), edge_method: edgeMethod})});
      const data = await response.json();
      if (!response.ok) throw new Error(data.code === 'empty_sketch' ? t('Dessinez quelque chose avant de rechercher.') : (data.error || t('La recherche a échoué.')));
      results.replaceChildren();
      for (const match of data.results) {
        const template = document.createElement('template'); template.innerHTML = match.html.trim();
        const card = template.content.firstElementChild;
        const line = card.querySelector('.match-line');
        line.replaceChildren();
        const label = document.createElement('span'); label.dataset.i18n = 'Similarité cosinus'; label.textContent = t('Similarité cosinus');
        const value = document.createElement('span'); value.className = 'mono distance'; value.textContent = match.similarity.toFixed(4);
        line.append(label, value); results.append(card); render(card);
      }
      empty.hidden = true;
      count.textContent = `${data.results.length} ${t(data.results.length === 1 ? 'résultat' : 'résultats')}`;
      status.textContent = t('Recherche terminée.');
    } catch (error) { status.textContent = error.message; }
    finally { searchButton.disabled = false; }
  });
  document.addEventListener('languagechange', () => { if (!results.children.length) count.textContent = t('Aucun résultat'); });
  clearCanvas(false); setMode('draw');
  try {
    const saved = sessionStorage.getItem(storageKey);
    if (saved) {
      const image = new Image();
      image.addEventListener('load', () => context.drawImage(image, 0, 0, 48, 48), {once: true});
      image.src = saved;
    }
  } catch (_) { /* Canvas remains available without session storage. */ }
})();
