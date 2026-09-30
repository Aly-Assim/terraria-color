# Wall catalog preparation

This is infrastructure only. No wall records, images, or derived colors have
been added, and no import workflow is enabled yet.

## Existing schema, shared renderer

Use the existing `objects` table with `object_type = 'wall'` and `is_wall = 1`.
Blocks retain `object_type = 'block'` and `is_wall = 0`. No schema migration is
needed. The maintainer confirmed that blocks and walls share the paint formulas;
both therefore use `scripts/paint/renderer.py` without separate algorithms.

`local_id` must be globally unique across blocks and walls because derived tables
and preview URLs use it as their object key. Preserve existing block IDs 0–306.
Allocate new wall IDs above the current maximum at import time, without assuming
that Terraria's internal item/tile IDs are local IDs.

## Image paths

Store repository-relative paths with forward slashes:

| Database field | Future wall directory |
| --- | --- |
| `world_image_path` | `images/walls/world/` |
| `inventory_image_path` | `images/walls/inventory/` |
| `color_image_path` | `images/walls/color/` |

Use a globally unique local-ID prefix in each filename. The existing
`world_image_path` field means a placed texture for either type; it does not
require that a wall live in the block image directory. Supply the three image
roles before considering a wall ready for release.

Painted wall variants will use `images/painted/walls/<source_stem>/`.
Block export paths remain unchanged. The common manifest retains its existing
columns and globally unique local IDs; wall variant paths carry the `walls/`
prefix. The shared HTML index can display both types.

## Search and derived data

Both catalog and color search accept `object_type=all`, `block`, or `wall`.
The UI exposes the same filter in both forms. The default remains all, which
currently returns only blocks. An empty wall search is expected until import.

The existing color builders already iterate all objects and use their stored
paths, so they need no wall-specific formula or table. The painted export now
resolves wall sources within their own directory. Once wall records and images
are approved, their derived color rows will need to be built before color search
and painted previews work. Do not run builds as part of this preparation.

The full derived-color rebuild replaces the corresponding derived table, and
dispersion normalization is shared across all included objects. Adding walls can
therefore change normalized dispersion and Average rankings for blocks in a
future rebuild. The preserved database is unchanged by this preparation.

## Next stage (awaiting maintainer instructions)

Decide the wall list, source/curation process, and image naming details, then
implement a dedicated reviewed importer with stable IDs and backups. Do not
reactivate the historical acquisition or duplicate-merge tools: they can replace
block images and renumber records.

Safe checks: `python tests/run_tests.py`. Wall-search tests use an in-memory
SQLite fixture and never insert records into the shipped database. Release
validation retains the original block-ID and immutable-image checks while
allowing additional complete wall records.
