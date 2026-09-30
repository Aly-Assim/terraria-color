# Wall image inputs

Raw wall resources imported from the private workbook and official wiki:

- `images/walls/world/`: placed wall textures
- `images/walls/inventory/`: inventory icons
- `images/walls/color/`: separate byte-for-byte copies of placed textures for analysis

Do not put new files in the immutable block directories `images/world/` or
`images/inventory/`, or overwrite existing `images/color/` files.
See [the import workflow](../../docs/adding-walls.md) and
[import report](../../data/wall_import_report.csv). These raw assets await manual
curation. Terraria/Re-Logic assets are distinct from the project's code; see
[NOTICE](../../NOTICE.md).
