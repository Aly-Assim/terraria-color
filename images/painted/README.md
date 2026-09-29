# Painted world-texture reference dataset

This directory is an intentionally published, derived resource. It can be used
without running the website. See `../../NOTICE.md` for third-party asset
attribution and unresolved redistribution/licensing questions.

Open `index.html` to browse the contact sheets. Read `manifest.csv` to enumerate
individual PNGs. It is UTF-8 with these columns:

| Column | Meaning |
| --- | --- |
| `local_id` | Stable ID in the curated project database |
| `object_name` | Object display name |
| `paint_id` | Integer from 0 (None) through 30 (Negative) |
| `paint_name` | Human-readable paint name |
| `relative_image_path` | PNG path relative to this directory |
| `source_image_path` | Original world texture path relative to the repository root |

The initial public export contains 289 objects × 31 states = 8,959 PNGs, plus
289 contact sheets. The remaining 18 objects have GIF world textures and were
not included in the earlier export. The database includes all 307 objects.

Folders retain their world-source stems, for example `0_dirt_block_world/`.
Paint files use `00_none.png` through `30_negative.png`. Contact sheets begin
with `_` and are not manifest variants. No existing PNG was re-rendered during
the public-release reorganization.

From the repository root, `python scripts/paint/generate_images.py` optionally
exports every object, including a static frame-zero PNG for GIF sources. It
replaces the derived PNGs, contact sheets, HTML index, and manifest. To index
existing files only, use `python scripts/paint/generate_images.py --manifest-only`.
Neither command changes the database or world/inventory sources.

These images are world-texture transforms. The Flask previews and color builders
prefer `images/color/` where available, so the world export is not guaranteed to
match those analysis inputs after future curation. No lighting simulation or
animated painted output is included.
