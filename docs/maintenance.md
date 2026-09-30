# Maintenance and data provenance

Normal website use needs only the included database, image sources, and runtime
dependencies. No acquisition or rebuild step is required.

## Canonical inputs and historical exports

`data/terraria_blocks.db` retains 307 curated blocks with stable
local IDs, 307 base-color rows, and 9,517 block/paint rows, alongside newly imported
walls awaiting manual curation and derived data. `objects` contains
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
| `scripts/maintenance/import_walls.py` | Workbook-driven staged sample and safe wall append |
| `scripts/maintenance/validate_catalog.py` | Read-only missing/misplaced media, paths and orphan detection |
| `scripts/maintenance/manual_fix.py --type wall` | Explicit wall-only edits; original block workflow remains guarded |
| `scripts/maintenance/merge_walls.py` | Explicit retained/removed wall IDs, preview by default; backup and transaction on apply |
| `scripts/maintenance/merge_duplicates.py` | Historical merge, ID renumbering, image-tree replacement, and undo; disabled for this curated release |

The historical implementations remain for provenance. Block import, block fixes
and the old renumbering merge entry points fail before any writes. They are not supported
library APIs; importing and calling their internal mutation functions bypasses
the entry-point guard. Any revival requires a separately designed staging-data
workflow that preserves the immutable images and stable IDs. No override flag is
provided. Do not remove the guard merely to run an old recipe.

Optional acquisition dependencies are in `requirements-maintenance.txt`; ordinary
users do not need them. Existing local backups, merge checkpoints, source workbook,
and debug previews are retained and ignored by Git. Nothing in those local
directories should be staged with `git add -f`.

## Wall curation

Acquisition is documented in [adding-walls.md](adding-walls.md). Review
`data/wall_import_report.csv` first. Wall IDs are stable; gaps after merges are normal.
None of the following curation actions is run by the importer.

### Visual workflow (recommended)

```powershell
python scripts/maintenance/curate_walls.py
```

This opens a separate local interface at `http://127.0.0.1:5001/`. It reads the
current catalogue, validation results, import problems and existing duplicate
CSV, then presents **problems first**, followed by **duplicate pairs**. Each wall
shows its inventory/world images, URLs, paths, category and game IDs. The ordinary
website is unchanged. Use `--port 5002` if needed, or `--no-browser` to open manually.

- Correct URLs/status/problems directly, refresh wiki metadata, or explicitly
  accept a warning with a note. World and color are separate editable URLs.
- For a duplicate pair, choose which wall to keep or explicitly keep both.
  A merge backs up and deletes the chosen duplicate immediately; surviving IDs
  do not change during classification.
- **Later** retains the pending row. Close the tab and use Ctrl+C in the terminal
  to stop; running the same command resumes saved decisions.
- Progress and pending `issues.csv` / `pairs.csv` live in ignored
  `data/duplicates/wall_review/`. Decided rows disappear from these working CSVs;
  headers remain. An externally changed wall/image is reviewed again.
- **Finalize and renumber walls** becomes available only when both working CSVs
  have no remaining rows. The server rechecks this condition before any changes.
  The final step compacts wall IDs after the largest non-wall ID and updates wall
  filenames, database paths, dependent rows and current CSV exports. It creates
  backups plus `id_map.csv`. Block rows, IDs and files remain unchanged.

Historical block acquisition CSVs are not work queues and are never renumbered.
The import report retains source names and original IDs. Existing wall paint
exports block final renumbering: classify and finalize before generating paints.
Missing or invalid source paths and filename collisions must be repaired before
finalization, even if a warning was acknowledged. No color build or paint export
is started by this interface.

The commands below remain available for individual operations.

From the repository root, with the environment activated:

```powershell
python -m pip install -r requirements-maintenance.txt
python scripts/maintenance/validate_catalog.py --type wall
python scripts/maintenance/validate_catalog.py --type wall --csv data/duplicates/wall_validation.csv
python scripts/maintenance/find_duplicates.py --type wall
python scripts/maintenance/manual_fix.py --type wall
```

Validation finds absent role paths/files, misplaced directories, role suffix and
local-ID mismatches, invalid images, shared paths and orphan files. CSV output
is restricted to `data/duplicates/` to prevent overwriting assets. Use `--type
block` or `--type all` on validation and duplicate detection to change the scope.
Duplicate detection compares exact first-frame RGBA pixels after trimming
transparent borders; it is not an animation-equivalence test. Its CSV includes
object type, local ID, name and world path, and never chooses a survivor.

The wall editor asks for an ID, then `page`, `inventory`, `world`, `color`,
`metadata`, `status`, or `problem`. Type `STOP` at the ID prompt to finish.
Noninteractive equivalents are available:

```powershell
$wallId = [int](Read-Host 'Wall ID to edit')
python scripts/maintenance/manual_fix.py --type wall --id $wallId --refresh-metadata
python scripts/maintenance/manual_fix.py --type wall --id $wallId --status reviewed --problem ''
# Supply the exact official wiki URL when changing media:
$imageUrl = Read-Host 'Official world image URL'
python scripts/maintenance/manual_fix.py --type wall --id $wallId --world $imageUrl --color $imageUrl
```

Each edit backs up the database and replaced files. Only wall rows and
`images/walls/{inventory,world,color}/` can change. Shared files, block IDs and
out-of-scope paths are refused. Metadata refresh changes IDs/page metadata only;
it does not silently replace images. World and color are independent edits.
An image edit invalidates that wall's derived color rows to avoid stale results;
no rebuild is triggered. Existing painted exports remain until an intentional
future export. Block mode keeps its original safety guard.

Use the separate wall merger instead of reviving the historical tool, whose
renumbering/image-tree replacement is incompatible with stable curated IDs:

```powershell
$keepId = [int](Read-Host 'Wall ID to KEEP')
$removeId = [int](Read-Host 'Duplicate wall ID to REMOVE')
python scripts/maintenance/merge_walls.py --keep $keepId --remove $removeId
# After reviewing the displayed selection:
python scripts/maintenance/merge_walls.py --keep $keepId --remove $removeId --apply
```

`--remove` accepts multiple explicitly chosen IDs. The kept record is unchanged.
Apply backs up SQLite and selected media, removes dependent color/wall-ID rows,
and deletes only selected wall files not referenced by remaining objects.
Exceptions restore files and roll back SQL. No IDs are renumbered. Keep the
backup until satisfied; a hard interruption may require restoring that backup.
Run validation again after your edits. Only once curation is complete should you
decide whether to run the derived builders and paint exporter documented above.

## Development checks

```powershell
python tests/run_tests.py
git diff --check
git diff --exit-code -- images/world images/inventory images/color
```

Tests use read-only SQLite connections, in-memory synthetic renderer samples,
Flask's test client, source-path checks, immutable image hashes, and the public
manifest. Optional `--maintenance` tests write only disposable fixture databases
and images; they never mutate the canonical dataset. Run them
without Python's `-O` option, which disables assertions.

Keep changes small, preserve paint formulas and color metric semantics, document
CLI changes, and update the manifest after an intentional painted export. The
French website interface is retained; public documentation is in English.
