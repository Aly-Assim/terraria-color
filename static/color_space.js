(() => {
    const {t} = window.TerrariaUI;
    const root = document.documentElement;
    const plot = document.getElementById('colorSpacePlot');
    const count = document.getElementById('colorSpaceCount');
    const excluded = document.getElementById('colorSpaceExcluded');
    const message = document.getElementById('colorSpaceMessage');
    const reset = document.getElementById('resetColorSpaceCamera');
    const paint = document.getElementById('colorSpacePaint');
    const paintInputs = [...paint.querySelectorAll('input[type="checkbox"]')];
    const pickerMode = document.body.dataset.colorSpacePicker === 'true';
    const pickerTarget = document.body.dataset.colorSpaceTarget === 'manual' ? 'manual' : 'seed';
    const selection = document.getElementById('colorSpaceSelection');
    const useSeed = document.getElementById('useColorSpaceSeed');
    const viewButtons = [...document.querySelectorAll('[data-color-space-view]')];
    const cameras = {
        initial: {eye: {x: 1.55, y: 1.55, z: 1.15}, up: {x: 0, y: 0, z: 1}, projection: {type: 'perspective'}},
        ab: {eye: {x: 0, y: 0, z: 2.5}, up: {x: 0, y: 1, z: 0}, projection: {type: 'orthographic'}},
        aL: {eye: {x: 0, y: -2.5, z: 0}, up: {x: 0, y: 0, z: 1}, projection: {type: 'orthographic'}},
        bL: {eye: {x: 2.5, y: 0, z: 0}, up: {x: 0, y: 0, z: 1}, projection: {type: 'orthographic'}},
    };
    const plotConfig = {
        responsive: true,
        scrollZoom: true,
        displaylogo: false,
        modeBarButtonsToRemove: ['toImage', 'sendDataToCloud'],
    };
    let points = [];
    let stats = null;
    let initialized = false;
    let requestNumber = 0;
    let activeView = 'initial';
    let selectedPoint = null;

    function syncStats() {
        if (!stats) {
            count.textContent = t('Chargement…');
            excluded.textContent = '';
            return;
        }
        const label = stats.selections.length === 1 && stats.selections[0] === 'original'
            ? 'blocs représentés'
            : 'points représentés';
        count.textContent = `${stats.count} ${t(label)}`;
        excluded.textContent = `${stats.excluded} ${t('points exclus sans couleur Average valide')}`;
    }

    function theme() {
        const styles = getComputedStyle(root);
        return {
            text: styles.getPropertyValue('--text').trim(),
            muted: styles.getPropertyValue('--text-muted').trim(),
            border: styles.getPropertyValue('--border').trim(),
            surface: styles.getPropertyValue('--surface').trim(),
        };
    }

    function hoverTemplate() {
        return `<b>%{customdata[1]}</b><br>%{customdata[2]}<br>${t('Couleur moyenne')}: %{customdata[3]}<br>L: %{z:.4f}<br>a: %{x:.4f}<br>b: %{y:.4f}<extra></extra>`;
    }

    function layout() {
        const colors = theme();
        const axis = (title, range, visible = true) => ({
            title: {text: title, font: {color: colors.muted, size: 11}},
            range,
            visible,
            color: colors.muted,
            gridcolor: colors.border,
            zerolinecolor: colors.text,
            zerolinewidth: 2,
            backgroundcolor: colors.surface,
            showbackground: true,
        });
        return {
            margin: {l: 0, r: 0, t: 0, b: 0},
            paper_bgcolor: colors.surface,
            plot_bgcolor: colors.surface,
            font: {color: colors.text, family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"},
            hoverlabel: {bgcolor: colors.surface, bordercolor: colors.border, font: {color: colors.text}},
            hovermode: 'closest',
            clickmode: 'event',
            scene: {
                xaxis: axis(t('a · Vert / Rouge'), [-0.35, 0.35], activeView !== 'bL'),
                yaxis: axis(t('b · Bleu / Jaune'), [-0.35, 0.35], activeView !== 'aL'),
                zaxis: axis(t('L · Luminosité'), [0, 1], activeView !== 'ab'),
                camera: cameras[activeView],
                dragmode: 'orbit',
                aspectmode: 'data',
                annotations: activeView === 'ab' ? [] : [{
                    x: 0, y: 0, z: 1,
                    text: t('Axe neutre'),
                    showarrow: false,
                    font: {color: colors.muted, size: 10},
                }],
            },
            uirevision: 'color-space-v1',
            showlegend: false,
        };
    }

    function pointTrace() {
        return {
            type: 'scatter3d',
            mode: 'markers',
            x: points.map(point => point.a),
            y: points.map(point => point.b),
            z: points.map(point => point.L),
            customdata: points.map(point => [
                point.local_id,
                point.name,
                point.paint_name ? t(point.paint_name) : t('Texture d’origine'),
                point.hex,
                point.paint_id,
            ]),
            marker: {
                color: points.map(point => point.hex),
                size: points.length > 2000 ? (pickerMode ? 3.5 : 2.5) : (pickerMode ? 6 : 4),
                opacity: points.length > 2000 ? 0.58 : 0.78,
                line: {width: points.length > 2000 ? 0 : 0.35, color: theme().border},
            },
            hovertemplate: hoverTemplate(),
        };
    }

    function neutralAxisTrace() {
        return {
            type: 'scatter3d',
            mode: 'lines',
            x: [0, 0],
            y: [0, 0],
            z: [0, 1],
            line: {color: theme().muted, width: 4, dash: 'dot'},
            hoverinfo: 'skip',
            showlegend: false,
        };
    }

    function traces() {
        return [pointTrace(), neutralAxisTrace()];
    }

    function updateSelectionPanel() {
        if (!selectedPoint || !selection) return;
        selection.hidden = false;
        document.getElementById('colorSpaceSelectionSwatch').style.setProperty('--selected-color', selectedPoint.hex);
        document.getElementById('colorSpaceSelectionName').textContent = selectedPoint.name;
        document.getElementById('colorSpaceSelectionVariant').textContent = selectedPoint.paint_name ? t(selectedPoint.paint_name) : t('Texture d’origine');
        document.getElementById('colorSpaceSelectionHex').textContent = selectedPoint.hex;
    }

    function showSelection(point) {
        selectedPoint = point;
        updateSelectionPanel();
    }

    function clearSelection() {
        selectedPoint = null;
        if (selection) selection.hidden = true;
    }

    function useSelectedPoint() {
        if (!selectedPoint) return;
        try { sessionStorage.setItem(`terraria-palette-${pickerTarget}-picked`, selectedPoint.hex); } catch (_) {}
        window.location.assign(`/palette-create?${pickerTarget}=${encodeURIComponent(selectedPoint.hex)}`);
    }

    function addPickerActionToInspector() {
        if (!pickerMode || !useSeed) return;
        const inspectorContent = document.getElementById('inspectorContent');
        if (!inspectorContent) return;
        inspectorContent.querySelector('.color-space-inspector-action')?.remove();
        const action = document.createElement('div');
        action.className = 'color-space-inspector-action';
        const button = useSeed.cloneNode(true);
        button.removeAttribute('id');
        button.addEventListener('click', useSelectedPoint);
        action.append(button);
        inspectorContent.prepend(action);
    }

    async function inspect(localId, paintId) {
        try {
            const url = paintId === null
                ? `/api/color-space/item/${localId}`
                : `/api/workshop/item/${localId}/${paintId}`;
            const response = await fetch(url);
            if (!response.ok) throw new Error(t('Fiche matériau indisponible.'));
            const holder = document.createElement('div');
            holder.className = 'cards';
            holder.hidden = true;
            holder.innerHTML = await response.text();
            document.body.append(holder);
            const trigger = holder.querySelector('[data-inspect]');
            trigger.inspectorReturn = plot;
            trigger.click();
            holder.remove();
            addPickerActionToInspector();
        } catch (error) {
            message.textContent = error.message;
            message.hidden = false;
        }
    }

    async function renderPlot() {
        if (!initialized) {
            await Plotly.newPlot(plot, traces(), layout(), plotConfig);
            plot.on('plotly_click', event => {
                const eventPoint = event.points?.[0];
                if (!eventPoint || eventPoint.curveNumber !== 0) return;
                const point = points[eventPoint.pointNumber];
                if (!point) return;
                if (pickerMode) {
                    showSelection(point);
                }
                inspect(point.local_id, point.paint_id);
            });
            initialized = true;
            return;
        }
        await Plotly.react(plot, traces(), layout(), plotConfig);
    }

    async function load() {
        if (!window.Plotly) {
            message.textContent = t('Impossible de charger la visualisation 3D.');
            message.hidden = false;
            return;
        }
        const sequence = ++requestNumber;
        stats = null;
        syncStats();
        message.hidden = true;
        paint.disabled = true;
        try {
            const checked = paintInputs.filter(input => input.checked).map(input => input.value);
            const selections = checked.includes('all') ? ['original', 'all'] : checked;
            const responses = await Promise.all(selections.map(async selection => {
                const response = await fetch(`/api/color-space/points?paint=${encodeURIComponent(selection)}`);
                const data = await response.json();
                if (!response.ok) throw new Error(data.error || t('Impossible de charger les couleurs.'));
                return data;
            }));
            if (sequence !== requestNumber) return;
            clearSelection();
            points = responses.flatMap(data => data.points);
            stats = {
                count: points.length,
                excluded: responses.reduce((total, data) => total + data.excluded, 0),
                selections,
            };
            syncStats();
            await renderPlot();
        } catch (error) {
            if (sequence !== requestNumber) return;
            message.textContent = error.message;
            message.hidden = false;
            count.textContent = t('Indisponible');
        } finally {
            if (sequence === requestNumber) paint.disabled = false;
        }
    }

    function selectPaint(event) {
        const input = event.target;
        if (!(input instanceof HTMLInputElement)) return;
        if (input.value === 'all' && input.checked) {
            paintInputs.forEach(other => {
                if (other !== input) other.checked = false;
            });
        } else if (input.checked) {
            paintInputs.find(other => other.value === 'all').checked = false;
        }
        if (!paintInputs.some(other => other.checked)) {
            paintInputs.find(other => other.value === 'original').checked = true;
        }
        load();
    }

    function setCamera(name) {
        activeView = name;
        viewButtons.forEach(button => {
            button.setAttribute('aria-pressed', String(button.dataset.colorSpaceView === name));
        });
        if (!window.Plotly || !initialized) return;
        Plotly.relayout(plot, {
            'scene.camera': cameras[name],
            'scene.xaxis.visible': name !== 'bL',
            'scene.yaxis.visible': name !== 'aL',
            'scene.zaxis.visible': name !== 'ab',
            'scene.annotations': name === 'ab' ? [] : layout().scene.annotations,
        });
    }

    reset.addEventListener('click', () => setCamera('initial'));
    paint.addEventListener('change', selectPaint);
    viewButtons.forEach(button => {
        button.addEventListener('click', () => setCamera(button.dataset.colorSpaceView));
    });
    new MutationObserver(() => {
        if (!window.Plotly || !initialized) return;
        Plotly.react(plot, traces(), layout(), plotConfig);
    }).observe(root, {attributes: true, attributeFilter: ['data-theme']});
    document.addEventListener('languagechange', () => {
        syncStats();
        updateSelectionPanel();
        if (!window.Plotly || !initialized) return;
        Plotly.react(plot, traces(), layout(), plotConfig);
    });
    useSeed?.addEventListener('click', useSelectedPoint);
    syncStats();
    load();
})();
