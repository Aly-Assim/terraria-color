# Importing background walls

The importer reads the private workbook described in [source/README.md](../source/README.md).
Obtain it separately at `source/all_items_terraria_145.xlsx`; never commit it.
The wiki enriches the workbook list and never adds extra catalogue objects.

## Inspected source

The workbook has 15 sheets. `Walls` occupies 46 rows and 40 columns, containing
292 entries without duplicate normalized names. Category headings are in row 1;
each entry is a name, adjacent `=IMAGE("https://...")` formula, and checkbox.
Checkboxes do not filter the import. This matches the historical block reader's
layout, but duplicate source names cause an explicit error instead of collapsing.

| Category | Entries |
| --- | ---: |
| Soil Walls | 35 |
| Dungeon Walls | 10 |
| Wood Walls | 30 |
| Stone Walls | 38 |
| Brick Walls | 30 |
| Gem Walls | 28 |
| Decorative Walls | 44 |
| Metal Walls | 40 |
| Wallpaper | 22 |
| Unsafe Walls | 15 |

## Acquisition commands (PowerShell)

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-maintenance.txt
python scripts/maintenance/import_walls.py --dry-run
python scripts/maintenance/import_walls.py --sample
python scripts/maintenance/import_walls.py
```

These are acquisition commands, not website setup prerequisites.

- Dry-run resolves all names and writes `cache/walls/dry_run.csv`; canonical data stays untouched.
- Sample downloads Stone Wall, Topaz Stone Wall, Crimstone Wall, Natural Dirt Wall
  and animated Cog Wall. It appends to a temporary database copy under ignored
  `cache/walls/sample_*/`, validates images, and prints a detailed report.
- The default command repeats this sample gate using cached responses, stages pending
  downloads, then appends in one transaction. Existing source keys are skipped,
  preserving manual edits. Deleted objects can be imported again: do not rerun
  acquisition after merging unless you intend to restore those source entries.
- `--force-refresh-cache` refreshes wiki responses. Requests use a descriptive
  User-Agent, a minimum half-second interval, and persistent page/media caching.

Full imports write `data/wall_import_report.csv`, intentionally published with the
images. Source names, cell coordinates, media URLs, IDs, status and problems are
preserved there. Failed resolutions are reported and not inserted. Missing media
remain NULL paths with review problems; no sprite is invented. Already imported
incomplete rows also stay untouched on rerun; use the manual editor for repairs.

## Resolution and files

`wall_source.py` reads the workbook and resolves exact-name wiki infoboxes, image
filenames, Item ID rows and Wall ID rows. Group-page ID ranges are never assigned
positionally. Cursed Dungeon variants use the exact Shimmer output/input row,
matching workbook texture and corresponding unsafe ID. A source-name alias is
accepted only when confirmed by the wall index, and is flagged for review.

Original PNG/GIF bytes and transparency are retained. Naming follows the blocks:

```text
images/walls/inventory/<local_id>_<slug>_inventory.<ext>
images/walls/world/<local_id>_<slug>_world.<ext>
images/walls/color/<local_id>_<slug>_color.<ext>
```

Color is a separate byte-for-byte copy of world media. Existing files are never
overwritten by the importer. Ambiguity and missing media are reported explicitly.

## Database and safety

Walls use `object_type='wall'`, `is_wall=1`, and IDs allocated from MAX(local_id)+1.
The nullable `internal_wall_id` holds the main placed ID: the unique safe ID for
normal walls, or the unsafe ID for an explicitly unsafe variant.
`object_wall_ids(local_id, wall_id, is_safe, internal_name)` preserves additional
verified IDs; `is_safe` may be NULL. `internal_tile_id` stays NULL for walls.
The stable source key is `workbook:Walls:<normalized source name>`.

Before appending, SQLite is backed up under `data/backups/`, all original object
rows/count/MAX ID are recorded, and every existing block inventory/world/color
file is hashed. Before commit, original rows and hashes, new paths/roles/IDs,
image decoding, row counts, foreign keys and SQLite integrity are checked.
Exceptions roll back SQL and remove only files created by that operation.
Hard process/power interruption may leave orphan wall files; validation reports
these and subsequent imports refuse to overwrite them.

## After acquisition

The initial acquisition on 2026-09-30 inserted all 292 source walls at local IDs
307–598: 292 inventory files, 292 world files and 292 color copies. There were no
failed entries, missing media or ambiguous resolutions. 141 entries resolve on
grouped pages, including Gemstone Walls, Cave Walls, Sandstone Walls, Wallpapers
and Dungeon Brick Walls. Three source aliases remain explicitly flagged:

| Local ID | Source name | Wiki-resolved name |
| ---: | --- | --- |
| 344 | Tin Plating Fence | Tin Plating Wall |
| 408 | Spooky Wood | Spooky Wood Wall |
| 439 | Flinx Fur Block | Flinx Fur Wall |

The five staged sample entries all passed image and database checks. The 307
original object rows and 921 existing block image filenames/SHA-256 hashes were
unchanged. Original base-color and paint-color table contents were also compared
and remained identical. The workbook was unchanged and remains Git-ignored.
The pre-import database and row/hash snapshot are stored locally under
`data/backups/wall_import_20260930T154145336080Z/`.

Implementation files are `scripts/maintenance/import_walls.py`, `wall_source.py`
and `wall_storage.py`; curation adds `validate_catalog.py`, `manual_walls.py` and
`merge_walls.py`, and extends `find_duplicates.py` and the `manual_fix.py` dispatcher.
The original destructive merger remains guarded. Tests add `test_wall_import.py`
and extend `test_walls.py`, `test_dataset.py` and `run_tests.py`. README, maintenance
documentation, wall-image README and optional-dependency comments were updated.
Data changes are the appended database, import CSV and 876 new wall image files.

Follow [wall curation](maintenance.md#wall-curation). No fixing, merging, color
building or paint generation is performed automatically. Raw walls are browsable
in the catalogue but require derived colors before color search/painted previews.
The shared paint and color algorithms are unchanged. Future paint exports use
`images/painted/walls/<source_stem>/`. A future full color rebuild normalizes
dispersion across blocks and walls together, which can affect Average rankings.

For the guided visual classification, run `python scripts/maintenance/curate_walls.py`.
It shows issues before duplicate pairs and saves decisions for resuming. Wall IDs
remain stable throughout review; an explicit finalization can renumber only walls
once both pending work CSVs are empty, updating files and references together.

Offline fixture tests (maintenance dependencies required):

```powershell
python tests/test_wall_import.py
# Alternatively include them in the existing suite:
python tests/run_tests.py --maintenance
```
