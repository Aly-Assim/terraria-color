# Maintenance and data provenance

Normal website use needs only the included database, image sources, and runtime
dependencies. No acquisition or rebuild step is required.

## Canonical inputs and historical exports

`data/terraria_blocks.db` is the curated release snapshot: 307 objects with stable
local IDs, 307 base-color rows, and 9,517 object/paint rows. `objects` contains
names, categories, source URLs, image paths, internal game IDs where known, and
curation status. `object_colors` and `object_paint_colors` are derived tables,
but their shipped values are preserved in the release database.

`images/world/` and `images/inventory/` are immutable curated resources. Their
614 filenames and SHA-256 hashes are recorded in `data/immutable_images.sha256`.
Never overwrite, rename, move, optimize, or deduplicate these files. Preserve
the local IDs and existing spelling in filenames, even when a name looks unusual.

`images/color/` remains in place because the database and color-analysis tools
reference it. Treat it as a curated analysis input, not a disposable preview.

The other tracked data files are retained for provenance:

| File | Purpose |
| --- | --- |
| `colors.csv` | Export of the 307 base-color results; rewritten by the base-color builder |
| `color_gallery.html` | Static comparison of linear-light and naive RGB means |
| `all_entries.csv` | Historical 315-entry acquisition export, before duplicate curation |
| `excel_blocks_read.csv` | Historical 315-entry spreadsheet extraction |
| `problem_entries.csv` | Historical 79-entry acquisition problem report |
| `manual_fixes.csv` | Historical 108-row repair worksheet, not an automatic migration input |

Historical CSV IDs must not be joined blindly to the current database: the
original merge workflow renumbered records. These files are not runtime inputs.
The private source workbook under `source/` is not published or required to run
the app. Its redistribution status has not been established.

## Derived color rebuilds (optional, write to the database)

Stop the app before a rebuild and keep a backup. Run from the repository root:

```powershell
New-Item -ItemType Directory -Force data/backups | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
Copy-Item -LiteralPath data/terraria_blocks.db -Destination "data/backups/before_colors_$stamp.db"
python scripts/build/build_colors.py
python scripts/build/build_paint_colors.py
python tests/run_tests.py
```

The first builder replaces `object_colors`, updates `data/colors.csv`, and writes
a local report. It prefers color, then world, then inventory images. Animated
base-color analysis uses up to 60 frames, weighted by duration and alpha.

The second builder makes its own timestamped database backup, replaces
`object_paint_colors`, renders each paint in memory, computes color metrics, and
normalizes dispersion. It prefers color images, then world images, and analyzes
the first frame. It does not save painted PNGs. Neither builder modifies source
images or object IDs.

**`--limit N` on the paint-color builder is destructive:** it replaces the whole
derived table with only N objects. It is not a smoke test. Do not use it on the
release database. Use `tests/run_tests.py` for non-destructive validation.

## Painted image export (optional)

```powershell
python scripts/paint/generate_images.py
Start-Process images/painted/index.html
python tests/test_dataset.py
```

This rewrites variants and contact sheets under `images/painted/`, plus its HTML
index and manifest. It reads the database without modifying it. World textures
are the reference inputs for this dataset; the app's previews and color tables
prefer color images, which may differ from world images after future curation.
GIF inputs are exported as static PNGs of frame zero. Animation is not preserved.

To update only the index of existing PNGs, without rendering any image:

```powershell
python scripts/paint/generate_images.py --manifest-only
```

For one-image inspection, use an explicit scratch destination:

```powershell
python scripts/paint/renderer.py --list
python scripts/paint/renderer.py --input images/world/1_wood_world.png --all --output cache/paint_previews/wood
```

## Maintenance tools

| Tool | Effect |
| --- | --- |
| `scripts/maintenance/find_duplicates.py` | Reads world-image pixels, trims transparency in memory, and writes a local CSV report; does not merge anything |
| `scripts/maintenance/view_colors.py` | Rewrites `data/color_gallery.html` from `colors.csv` and opens it in a browser |
| `scripts/maintenance/import_catalog.py` | Historical spreadsheet/wiki acquisition and full database/image rebuild; disabled for this curated release |
| `scripts/maintenance/manual_fix.py` | Historical interactive image replacement; disabled for this curated release |
| `scripts/maintenance/merge_duplicates.py` | Historical merge, ID renumbering, image-tree replacement, and undo; disabled for this curated release |

The three historical tools retain their implementation for provenance and future
development. Their CLI entry points fail before any writes. They are not supported
library APIs; importing and calling their internal mutation functions bypasses
the entry-point guard. Any revival requires a separately designed staging-data
workflow that preserves the immutable images and stable IDs. No override flag is
provided. Do not remove the guard merely to run an old recipe.

Optional acquisition dependencies are in `requirements-maintenance.txt`; ordinary
users do not need them. Existing local backups, merge checkpoints, source workbook,
and debug previews are retained and ignored by Git. Nothing in those local
directories should be staged with `git add -f`.

## Development checks

```powershell
python tests/run_tests.py
git diff --check
git diff --exit-code -- images/world images/inventory data/terraria_blocks.db
```

Tests use read-only SQLite connections, in-memory synthetic renderer samples,
Flask's test client, source-path checks, immutable image hashes, and the public
manifest. They do not regenerate datasets or write database rows. Run them
without Python's `-O` option, which disables assertions.

Keep changes small, preserve paint formulas and color metric semantics, document
CLI changes, and update the manifest after an intentional painted export. The
French website interface is retained; public documentation is in English.
