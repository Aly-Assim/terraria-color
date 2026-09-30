# Terraria Color

Terraria Color is a local Flask application for finding Terraria blocks, background walls, and paint combinations that match a target color.

The project combines a curated SQLite catalog, perceptual color analysis, and an offline paint renderer so builders can compare materials programmatically instead of testing combinations manually in game.

## Features

- Browse blocks and background walls by name or category.
- Search by target color using Average or Dominant matching.
- Rank results with perceptual OKLab distance.
- Optionally penalize visually varied textures with the dispersion control.
- Filter results by Terraria paint.
- Preview painted textures directly in the application.
- Use the exported painted-image dataset independently of Flask.
- Maintain blocks and walls with dedicated validation and curation tools.

## Dataset

The repository currently includes:

| Resource | Count |
| --- | ---: |
| Blocks | 307 |
| Background walls | 278 |
| Total catalog objects | 585 |
| Base color records | 585 |
| Paint states per object | 31 |
| Object × paint color records | 18,135 |
| Exported painted variants | 18,135 |

The catalog uses stable project-local IDs. These are separate from Terraria's internal tile, wall, and item IDs.

Existing curated block assets under `images/world/` and `images/inventory/` are treated as immutable project data. Wall assets are stored separately under `images/walls/`.

## Quick start

### Windows PowerShell

Python 3.12 or newer is recommended.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Then open:

http://127.0.0.1:5000

For later runs:

```powershell
.\.venv\Scripts\Activate.ps1
python app.py
```

The application uses the database and images already included in the repository. No acquisition or rebuild step is required for normal use.

## Color matching

Terraria Color provides two search modes.

### Average

Average mode compares the target against an alpha-weighted linear-light mean of the source texture.

Transparent and near-transparent pixels are excluded before the visible pixels are converted from sRGB to linear RGB, averaged, and converted back.

An optional dispersion penalty can favor visually more uniform textures.

### Dominant

Dominant mode estimates the strongest representative color using deterministic weighted clustering in OKLab space.

This mode focuses on the visually dominant region of a texture and does not apply the dispersion penalty.

### OKLab

Search ranking uses Euclidean distance in OKLab space. Lower values represent closer perceptual matches.

## Paint renderer

The paint renderer is implemented in:

`scripts/paint/renderer.py`

It applies the project's reconstructed Terraria paint transformations to source textures while preserving alpha.

The renderer supports 31 states:

- unpainted
- 12 standard hue paints
- 12 deep hue paints
- Black
- White
- Gray
- Brown
- Shadow
- Negative

The renderer is an offline texture transformation. It is not intended to reproduce every in-game lighting condition, special rendering effect, or world-specific visual context.

## Painted reference dataset

Pre-generated painted variants are stored in:

`images/painted/`

The dataset contains one exported variant for every current object × paint combination represented in the database.

It also includes:

- `manifest.csv`
- `index.html`
- per-object contact sheets

Block and wall exports are kept in separate paths while sharing the same renderer and paint IDs.

The Flask endpoint:

`/painted-image/<local_id>/<paint_id>`

can render previews in memory and does not require writing new files.

## Project structure

```text
Terraria Color/
├── app.py
├── README.md
├── LICENSE
├── NOTICE.md
├── requirements.txt
├── requirements-maintenance.txt
├── data/
│   └── terraria_blocks.db
├── images/
│   ├── inventory/
│   ├── world/
│   ├── color/
│   ├── walls/
│   │   ├── inventory/
│   │   ├── world/
│   │   └── color/
│   └── painted/
├── scripts/
│   ├── build/
│   ├── maintenance/
│   └── paint/
├── source/
│   └── README.md
├── static/
├── templates/
├── tests/
└── docs/
```

Local source workbooks, caches, backups, reports, and virtual environments are intentionally excluded from Git.

## Tests

Run the project test suite with:

```powershell
python tests/run_tests.py
```

The tests cover the paint renderer, Flask search behavior, dataset consistency, wall support, and protected data assumptions.

Before committing larger data or maintenance changes, it is also useful to run:

```powershell
git diff --check
```

## Maintenance

Normal users do not need the maintenance dependencies.

For acquisition, validation, duplicate review, and catalog maintenance:

```powershell
python -m pip install -r requirements-maintenance.txt
```

Detailed maintenance workflows are documented in:

- `docs/maintenance.md`
- `docs/adding-walls.md`

The external workbook used during catalog acquisition is not distributed with the repository. Its provenance and expected local path are documented in `source/README.md`.

## License and third-party material

Original Terraria Color source code is licensed under the MIT License. See `LICENSE`.

Terraria game assets, names, trademarks, external datasets, and derivative material based on third-party assets are not covered by that MIT license.

Terraria Color is an independent community project and is not affiliated with or endorsed by Re-Logic.

See `NOTICE.md` for third-party attribution and scope details.
