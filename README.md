# Terraria Color

Find Terraria blocks and paint combinations that match a color you want to build with.
Terraria Color is a small local Flask app backed by a curated SQLite catalog. It
lets builders compare textures instead of guessing which block and paint will
work in a palette.

- Browse blocks and background walls by name or category, with inventory/world images and wiki links.
- Search 9,517 block × paint combinations using Average or Dominant color.
- Rank colors by perceptual OKLab distance and optionally penalize varied textures.
- Preview all 31 paint states through the same offline renderer used by the tools.
- Use the published painted PNG dataset independently of the website.

The included database is ready to use. **You do not need to rebuild or download
any data to start the website.** The interface is currently in French.

## Quick start (Windows PowerShell)

Use Python 3.12 or newer. Open PowerShell in the cloned repository:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Open [the local website](http://127.0.0.1:5000). Stop it with Ctrl+C.
The built-in server listens locally; debug mode is off by default.
For subsequent runs, activate the environment and run `python app.py`.

Runtime dependencies are Flask, NumPy, and Pillow. Their transitive dependencies
are installed by pip. Optional acquisition and maintenance tools have a separate
`requirements-maintenance.txt`; they are not part of normal setup.

## Search and color analysis

**Average (Moyenne)** compares the target with an alpha-weighted linear-light
mean. Pixels with alpha ≤ 10 are excluded; remaining sRGB pixels are converted to
linear RGB before averaging and converted back afterward. This avoids averaging
gamma-encoded values directly. The database also retains a naive sRGB mean for
comparison.

**Dominant (Dominante)** uses deterministic weighted k-means in OKLab, with up to
five clusters. Border pixels receive less clustering weight. The representative
is an actual pixel nearest the strongest cluster's center; the dominant ratio
uses alpha weights without the border adjustment.

**OKLab distance** is Euclidean distance between perceptual L, a, b coordinates.
Smaller values mean a closer color match. It is used for both search modes.

**Color dispersion** is the alpha-weighted root-mean-square distance of visible
pixels from their OKLab mean. It measures how varied a texture is. The derived
table normalizes it by the dataset's 95th percentile, capped at 1.

Average mode ranks with:

```text
score = OKLab distance + (slider / 100) × normalized dispersion × 0.15
```

At 0%, only color distance matters. Increasing the slider favors more uniform
textures. Dominant mode ignores the dispersion penalty. Paint filtering can
restrict results to one paint state or include all of them.

## Paint renderer

`scripts/paint/renderer.py` implements the project's existing ordinary tile paint
formulas using NumPy and Pillow. RGB channels are normalized to 0–1, the paint
transform is applied, results are clipped and rounded to bytes, and alpha is
preserved. The existing implementation attributes these formulas to a Terraria
TileShader reference; this is an offline texture transform, not a simulation of
in-game lighting, special tile effects, or every rendering context.

Normal hue paints combine the source channel maximum, minimum, and their
midpoint. Deep hues use `0.4 × minimum` as the low component. Black, White, Gray,
Brown, and Shadow have their own formulas; Negative inverts RGB. None preserves
the input. The exact formulas remain readable in the renderer and are covered by
known-pixel regression tests.

| IDs | States |
| --- | --- |
| 0 | None (unpainted) |
| 1–12 | Red, Orange, Yellow, Lime, Green, Teal, Cyan, Sky Blue, Blue, Purple, Violet, Pink |
| 13–24 | Deep versions of those same twelve hues, in the same order |
| 25–30 | Black, White, Gray, Brown, Shadow, Negative |

The 31 states therefore include unpainted plus 30 paints.

Flask serves `/painted-image/<local_id>/<paint_id>` by rendering into memory. It
uses the color-table source path, then color/world fallbacks. It does not require
the exported PNG dataset or write preview files.

## Included data

| Resource | Status |
| --- | --- |
| `data/terraria_blocks.db` | Curated release database: 307 objects, 307 base colors, 9,517 paint-color rows |
| `images/world/` | 307 immutable curated world textures |
| `images/inventory/` | 307 immutable curated inventory images |
| `images/color/` | 307 analysis inputs referenced by the database; retained in place |
| `images/painted/` | Public derived reference dataset, with contact sheets and an HTML index |
| `data/immutable_images.sha256` | Filename and SHA-256 baseline for world/inventory assets |
| Other data CSVs and gallery | Preserved exports and historical acquisition provenance; see maintenance documentation |

The database tables are `objects` (metadata and source paths), `object_colors`
(base analysis), and `object_paint_colors` (one row per local ID and paint ID).
The paint table contains average/linear/naive RGB, dominant RGB and ratio,
dispersion, alpha statistics, source/method fields, and errors. Local IDs are
project identifiers, not Terraria internal IDs.

**Never modify, move, rename, delete, or regenerate anything under
`images/world/` or `images/inventory/`.** The database snapshot is also preserved;
only deliberate maintenance should rebuild its derived tables.

### Painted reference dataset

The shipped export contains **8,959 PNG variants for 289 objects**. Each has all
31 states. The 18 GIF-backed world textures were not exported by the previous
PNG-only generator; 558 variants are therefore not yet present. They are already
included in the database's 9,517 combinations and work in dynamic previews.
No full image generation was performed during the repository reorganization.

```text
images/painted/
├── manifest.csv
├── index.html
├── 0_dirt_block_world/
│   ├── 00_none.png
│   ├── 01_red.png
│   ├── ...
│   ├── 30_negative.png
│   └── _contact_sheet.png
└── ...
```

The `_world` suffix records the source role and preserves existing export names.
`manifest.csv` contains `local_id`, `object_name`, `paint_id`, `paint_name`,
`relative_image_path`, and `source_image_path`. Variant paths are relative to
`images/painted/`; source paths are relative to the repository root. The manifest
indexes files that actually exist, so it can be used without Flask or SQLite.

The current generator can export all 307 objects, including frame zero of GIF
sources. PNG exports are static. These exports use world textures; color analysis
and Flask previews prefer the separately curated color textures.

## Project structure

```text
Terraria Color/
├── app.py
├── README.md
├── NOTICE.md
├── requirements.txt
├── requirements-maintenance.txt
├── run.ps1
├── docs/
│   └── maintenance.md
├── data/
│   ├── terraria_blocks.db
│   ├── immutable_images.sha256
│   ├── colors.csv
│   ├── color_gallery.html
│   └── historical CSV exports
├── images/
│   ├── inventory/             # immutable
│   ├── world/                 # immutable
│   ├── color/                 # analysis inputs
│   └── painted/               # published derived dataset
├── scripts/
│   ├── paths.py
│   ├── build/
│   │   ├── build_colors.py
│   │   └── build_paint_colors.py
│   ├── paint/
│   │   ├── renderer.py
│   │   └── generate_images.py
│   └── maintenance/
│       ├── find_duplicates.py
│       ├── view_colors.py
│       ├── import_catalog.py  # historical, guarded
│       ├── manual_fix.py      # historical, guarded
│       └── merge_duplicates.py # historical, guarded
├── tests/
│   ├── run_tests.py
│   ├── test_renderer.py
│   ├── test_site.py
│   └── test_dataset.py
├── templates/
└── static/
```

Python package marker files are omitted above. Local source workbooks, backups,
caches, reports, and merge checkpoints are ignored and are not release inputs.

## Tests and validation

```powershell
python tests/run_tests.py
```

No extra test framework is required. Tests check paint formulas and alpha,
Average/Dominant Flask searches, the painted endpoint, database integrity and
coverage, source paths, immutable image hashes, and manifest consistency. Tests
read the shipped data without rebuilding it. Do not pass Python's `-O` flag.
Individual checks can be run as `python tests/test_renderer.py`,
`python tests/test_site.py`, or `python tests/test_dataset.py`.

## Optional exports and rebuilds

These are maintainer commands, **not installation steps**. Run only the operation
you intend; full regeneration was deliberately not part of the cleanup.

Export painted PNGs, contact sheets, HTML index, and manifest:

```powershell
python scripts/paint/generate_images.py
```

Rebuild only derived color data (stop the app and back up the database first):

```powershell
New-Item -ItemType Directory -Force data/backups | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
Copy-Item -LiteralPath data/terraria_blocks.db -Destination "data/backups/before_colors_$stamp.db"
python scripts/build/build_colors.py
python scripts/build/build_paint_colors.py
python tests/run_tests.py
```

The paint builder also creates an automatic backup. It renders in memory, so a
painted-image export is not a prerequisite. **Its `--limit` option still replaces
the entire paint table; never use it as a smoke test on the release database.**

See [maintenance and provenance](docs/maintenance.md) for source-selection rules,
animation behavior, historical CSVs, gallery/duplicate tools, and guarded legacy
acquisition workflows. Those historical tools are retained for reference but
cannot be launched against the curated release through their normal entry points.

## Common errors

- **Python is not found:** install Python 3.12+ and reopen PowerShell. Check
  `python --version` before creating the environment.
- **The environment points to a missing Python installation:** preserve it with
  `Rename-Item -LiteralPath .venv -NewName .venv-old`, then create a fresh `.venv`
  and install requirements. Choose another backup name if `.venv-old` exists.
- **Activation is blocked:** you can use `.\.venv\Scripts\python.exe` in place of
  `python` for every command; activation is only a convenience.
- **ModuleNotFoundError:** install with `python -m pip install -r requirements.txt`
  using the same Python that runs the app.
- **Missing database or source image:** restore the included file from a complete
  checkout or your backup. Do not run the historical importer to repair a clone.
- **Missing/incompatible paint table:** first restore the shipped database. A
  deliberate derived-table rebuild is described above if that is what you need.
- **Paint preview failure:** run the renderer and site tests, then the dataset
  validator to locate missing source paths.
- **Port 5000 is in use:** stop the other local server, or use
  `python -m flask --app app run --port 5001`.

## Contributing and attribution

Background walls are imported from the external workbook into separate image
directories using a staged, append-only importer. Both search forms offer Tous /
Blocs / Murs. Raw walls await manual curation and derived color builds before
appearing in color search. See [adding walls](docs/adding-walls.md) and
[wall maintenance](docs/maintenance.md#wall-curation). Existing blocks are preserved.
For visual classification with images, issue queues and duplicate pairs, run
`python scripts/maintenance/curate_walls.py` (maintenance dependencies required).

Keep the project small, preserve existing color algorithms, and run the safe
tests before submitting changes. Do not include local caches, private reports,
backups, or secrets. Painted exports are intentionally versioned. Check
`git diff --check` and review staged files before committing.

See [NOTICE.md](NOTICE.md) for the separation between project code and Terraria /
Re-Logic assets. A source-code license has not yet been selected. Before public
release, the maintainer must choose one and verify image/derivative distribution
and attribution requirements. No source-code license is claimed to cover the
Terraria assets.
