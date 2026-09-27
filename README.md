# Terraria Color Catalog

Terraria Color Catalog is a local Flask web app for browsing Terraria blocks and finding block + paint combinations whose rendered color is closest to a target color.

The project now includes:

- a Terraria block catalog
- name/category search
- color search using perceptual **OKLab** distance
- **Average** and **Dominant** color matching modes
- support for all 31 Terraria paint states
- a dispersion penalty slider for average-color searches
- an offline Terraria paint renderer derived from `TileShader`
- dynamically rendered painted previews in the website
- SQLite-backed block, color, paint, and analysis data
- tools for manual fixes, duplicate detection, duplicate merging, visual paint checks, and smoke tests

The current paint-color build contains:

```text
307 objects × 31 paint states = 9517 combinations
9517 successful calculations
0 errors
```

---

## 1. Project principles

This project is kept intentionally simple and inspectable.

The main rules are:

- develop and run the project inside a Python virtual environment
- use PowerShell commands on Windows
- keep source/reference data separate from generated/debug data
- keep the normal workflow simple before adding automation
- make backups before destructive database changes
- avoid storing generated files when they can be reproduced
- keep debug outputs in dedicated folders
- prefer deterministic scripts and clear terminal output
- validate a small sample before running expensive full-database operations
- preserve existing working code when only a small change is required
- keep `.venv`, caches, backups, temporary files, and heavy generated output out of Git

---

## 2. Project structure

The important project files are currently organized like this:

```text
Terraria Color/
├── app.py
├── run.bat
├── requirements.txt
├── README.md
├── .gitignore
│
├── data/
│   ├── terraria_blocks.db
│   ├── backups/
│   ├── duplicates/
│   ├── paint_lab/
│   │   ├── generated/
│   │   └── tests/
│   └── tmp_merge/
│
├── images/
│   ├── inventory/
│   ├── world/
│   └── color/
│
├── static/
│   └── style.css
│
├── templates/
│   ├── index.html
│   └── partials_card.html
│
└── scripts/
    ├── build_poc.py
    ├── manual_fix.py
    ├── build_colors.py
    ├── view_colors.py
    ├── find_duplicates.py
    ├── merge_duplicates.py
    ├── build_paint_color_db.py
    ├── test_color_search_site.py
    │
    └── paint_shader/
        ├── terraria_paint_shader.py
        ├── test_paint_shader.py
        └── bulk_generate_blocks.py
```

Some temporary or historical folders may exist locally, but they are not required for normal website use.

---

# 3. Windows setup

## Requirements

You need:

- Python
- `pip`
- Git if you want to version/push the project

Check them with:

```powershell
python --version
pip --version
git --version
```

---

## Go to the project folder

PowerShell:

```powershell
Set-Location "$HOME\Documents\Projets\Python\Terraria Color"
```

Do **not** use CMD syntax such as:

```text
cd /d ...
```

inside PowerShell.

---

## Create the virtual environment

Only required the first time, or if `.venv` has been deleted:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.venv\Scripts\Activate.ps1
```

The prompt should then start with:

```text
(.venv)
```

Install the project dependencies:

```powershell
pip install -r requirements.txt
```

After intentionally changing dependencies, refresh the file with:

```powershell
pip freeze > requirements.txt
```

`.venv` must not be committed to Git.

---

# 4. Running the website

## Normal method

Activate the environment:

```powershell
.venv\Scripts\Activate.ps1
```

Run Flask:

```powershell
python app.py
```

Then open:

```text
http://127.0.0.1:5000
```

---

## Quick method

You can also use:

```text
run.bat
```

if it is configured for the current project environment.

---

# 5. Website features

## Catalogue search

The catalogue allows searches by:

- object name
- canonical name
- category

Examples:

```text
stone
bamboo
brick
moss
sand
```

The cards can show:

- world image
- inventory image
- block name
- local ID
- category
- base average color
- Terraria wiki link

---

## Color search

The color search works on **block + paint combinations**, not only on unpainted blocks.

A candidate can therefore be:

```text
Dirt Block + None
Dirt Block + Red
Dirt Block + Deep Red
Stone Block + Blue
Wood + Brown
...
```

The user can choose:

- target HEX color
- number of results
- **Average** or **Dominant** mode
- one specific paint or all paints
- dispersion importance from `0%` to `100%`

The results display:

- painted preview
- paint ID and paint name
- average color
- dominant color
- dominant ratio
- normalized dispersion
- OKLab distance
- final score when dispersion is active

---

# 6. Color matching model

## Why OKLab?

The original website compared colors using Euclidean RGB distance.

The current search converts colors to **OKLab** and computes perceptual distance there. This produces rankings that are more consistent with visible color differences.

---

## Average mode

For each rendered block + paint image:

1. transparent pixels below the alpha threshold are ignored
2. visible sRGB pixels are converted to linear RGB
3. an alpha-weighted mean is computed in linear RGB
4. the result is converted back to sRGB
5. the target and candidate colors are compared in OKLab

The database also stores the old/simple sRGB mean as `naive_*` values for debugging and comparison.

---

## Dominant mode

The dominant color is not simply the most frequent exact RGB value.

The current method:

1. converts visible pixels to OKLab
2. groups nearby colors with deterministic weighted k-means
3. slightly reduces the influence of the outer image border
4. finds the cluster with the highest weighted mass
5. selects a real source pixel close to that cluster center
6. stores the proportion of visible pixels belonging to the dominant cluster

This avoids a one-pixel border or tiny RGB variations becoming the "dominant color" by accident.

---

## Dispersion

Dispersion represents how spread out the visible colors are in OKLab.

A low value means the texture is relatively uniform.

A high value means the image contains visibly different colors.

The database stores:

```text
dispersion_oklab
dispersion_norm
```

`dispersion_norm` is normalized using the 95th percentile of the current dataset so extreme outliers do not make the slider useless.

The last full build used:

```text
dispersion p95 scale = 0.246059
```

---

## Average-mode score

In Average mode:

```text
score =
    OKLab distance
    + dispersion weight
    × normalized dispersion
    × maximum dispersion penalty
```

The current maximum additive penalty is:

```text
0.15 OKLab units
```

Therefore:

- `0%` ignores dispersion
- `100%` applies the maximum configured dispersion penalty

The purpose is to avoid cases where a highly multicolored texture has the correct average color but does not visually resemble the requested flat color.

Dominant mode currently ignores the dispersion penalty.

---

# 7. Terraria paint shader

The project no longer depends on manually taking TEdit screenshots for each paint.

`scripts/paint_shader/terraria_paint_shader.py` is an offline renderer based on the Terraria `TileShader` paint logic used for the project's block-texture workflow.

It can render all supported paint states directly from a source PNG.

This makes paint processing:

- repeatable
- deterministic
- fast
- scriptable
- independent from screenshot calibration

Painted previews used by the Flask website are generated dynamically and do not require storing thousands of PNG files permanently.

---

## Supported paint IDs

| ID | Paint |
|---:|---|
| 0 | None |
| 1 | Red |
| 2 | Orange |
| 3 | Yellow |
| 4 | Lime |
| 5 | Green |
| 6 | Teal |
| 7 | Cyan |
| 8 | Sky Blue |
| 9 | Blue |
| 10 | Purple |
| 11 | Violet |
| 12 | Pink |
| 13 | Deep Red |
| 14 | Deep Orange |
| 15 | Deep Yellow |
| 16 | Deep Lime |
| 17 | Deep Green |
| 18 | Deep Teal |
| 19 | Deep Cyan |
| 20 | Deep Sky Blue |
| 21 | Deep Blue |
| 22 | Deep Purple |
| 23 | Deep Violet |
| 24 | Deep Pink |
| 25 | Black |
| 26 | White |
| 27 | Gray |
| 28 | Brown |
| 29 | Shadow |
| 30 | Negative |

---

# 8. Testing one texture with all paints

List available paint names/IDs:

```powershell
python scripts\paint_shader\terraria_paint_shader.py --list
```

Generate every paint variant for one source image:

```powershell
python scripts\paint_shader\terraria_paint_shader.py --input "images\world\5_gray_brick_world.png" --all
```

The generated variants and contact sheet are placed under:

```text
data\paint_lab\generated/
```

This folder is for testing/inspection, not for normal website operation.

---

# 9. Visual validation for every block

Generate contact sheets for all block images:

```powershell
python scripts\paint_shader\bulk_generate_blocks.py
```

Then open the generated HTML index:

```powershell
Start-Process "data\paint_lab\generated\all_blocks\index.html"
```

This is useful for manually checking the 31 paint states block by block.

It is a development/validation workflow and is not required for normal website use.

---

# 10. Paint shader tests

Run the paint-engine tests with:

```powershell
python scripts\paint_shader\test_paint_shader.py
```

These tests verify the Python implementation against its expected shader formulas.

They are useful after modifying the renderer.

---

# 11. Main database

The project uses:

```text
data/terraria_blocks.db
```

The main tables are:

## `objects`

Stores block/object metadata such as:

- local ID
- object type
- name
- canonical name
- category
- wiki page
- inventory/world/color image paths
- Terraria internal IDs when known
- source/status/problem fields

---

## `object_colors`

Stores the unpainted/base color analysis.

Important fields include:

```text
avg_r / avg_g / avg_b / avg_hex
avg_linear_r / avg_linear_g / avg_linear_b
naive_r / naive_g / naive_b / naive_hex
useful_pixel_count
alpha_weight
image_used
image_role
method
alpha_threshold
error
```

---

## `object_paint_colors`

Stores one row per:

```text
object × paint
```

The current full build contains:

```text
9517 rows
```

Important fields include:

```text
local_id
paint_id
paint_name

avg_r / avg_g / avg_b / avg_hex
avg_linear_r / avg_linear_g / avg_linear_b
naive_r / naive_g / naive_b / naive_hex

dominant_r / dominant_g / dominant_b / dominant_hex
dominant_ratio

dispersion_oklab
dispersion_norm

useful_pixel_count
alpha_weight

image_used
image_role
method
alpha_threshold
error
```

The primary key is:

```text
(local_id, paint_id)
```

---

# 12. Building paint-color data

The script is:

```text
scripts/build_paint_color_db.py
```

It:

- reads the source image for each object
- renders all paint states in memory
- computes average color
- computes dominant color
- computes dominant ratio
- computes OKLab dispersion
- normalizes dispersion
- rebuilds `object_paint_colors`
- creates a database backup before modifying the table

Generated painted images are **not** saved during the database build.

---

## Smoke test first

Before rebuilding everything:

```powershell
python scripts\build_paint_color_db.py --limit 5
```

A successful five-object test currently creates:

```text
5 objects × 31 paints = 155 rows
```

Expected result:

```text
Rows created: 155
Successful calculations: 155
Errors: 0
```

---

## Full build

When the smoke test is good:

```powershell
python scripts\build_paint_color_db.py
```

The latest successful full run produced:

```text
Rows created: 9517
Successful calculations: 9517
Errors: 0
Dispersion p95 scale: 0.246059
```

The script recreates the `object_paint_colors` table, so do not interrupt or manually edit that table while it is running.

A database backup is automatically created first.

---

# 13. Website smoke tests

Run:

```powershell
python scripts\test_color_search_site.py
```

The current smoke test checks:

```text
home page
average + dispersion search
dominant + paint filter search
dynamic painted image endpoint
```

Expected result:

```text
[PASS] home
[PASS] average + dispersion search
[PASS] dominant + paint filter search
[PASS] dynamic painted image

4/4 test groups passed
ALL SITE TESTS PASSED
```

Run this after changes to:

- `app.py`
- color-search logic
- templates
- paint preview rendering
- paint database structure

---

# 14. Dynamic painted previews

The website does not need 9517 permanent painted PNGs.

When a result needs a preview, Flask uses:

```text
/painted-image/<local_id>/<paint_id>
```

The route:

1. finds the object's source image
2. renders the selected paint with the local shader implementation
3. writes the result into memory
4. sends the PNG to the browser

This keeps the repository smaller and avoids duplicated generated data.

---

# 15. Building the original block database

## `scripts/build_poc.py`

This is the main raw-data rebuild script.

It:

- reads the Terraria block list
- creates one entry per block
- finds wiki pages
- tries to retrieve inventory/world images
- stores records in `data/terraria_blocks.db`
- downloads images into `images/`

Run:

```powershell
python scripts\build_poc.py
```

> **Warning:** this is a full rebuild script and can overwrite manual corrections. Do not run it casually on a working curated database.

---

# 16. Manual fixes

## `scripts/manual_fix.py`

Used to repair missing or incorrect entries interactively.

Run:

```powershell
python scripts\manual_fix.py
```

Useful commands inside the tool:

```text
STOP
SKIP
SHOW
MODIF
PAGE <url>
INV <url>
WORLD <url>
COLOR <url>
```

When `WORLD` is updated, the color image is also updated with the same source image.

After changing block images, rebuild the color tables before trusting color-search results.

Recommended sequence:

```powershell
python scripts\build_colors.py
python scripts\build_paint_color_db.py --limit 5
python scripts\build_paint_color_db.py
python scripts\test_color_search_site.py
```

---

# 17. Base color analysis

## `scripts/build_colors.py`

Computes the base/unpainted average colors stored in `object_colors`.

Run it after:

- rebuilding the raw database
- fixing source images
- applying duplicate merges

```powershell
python scripts\build_colors.py
```

---

## `scripts/view_colors.py`

Creates a local gallery for checking the base computed colors visually.

Run:

```powershell
python scripts\view_colors.py
```

---

# 18. Duplicate detection

## `scripts/find_duplicates.py`

Finds objects with identical world images.

It compares image pixels after removing transparent borders.

It does not modify the database.

Run:

```powershell
python scripts\find_duplicates.py
```

It can create:

```text
data/duplicates/duplicate_groups.csv
```

---

# 19. Duplicate merging

## `scripts/merge_duplicates.py`

Reads duplicate groups and lets you decide what should be kept or removed.

Run:

```powershell
python scripts\merge_duplicates.py
```

Useful commands:

```text
KEEP <id>
KEEP <id> REMOVE <id> <id>
REMOVE <id> <id>
RIEN
SKIP
MODIF
MODIF <id> INV <url>
MODIF <id> WORLD <url>
MODIF <id> COLOR <url>
PAGE <id> <url>
UNDO
PREVIEW
APPLY
STOP
```

Meaning:

- `KEEP <id>` keeps that object and removes the others in the group
- `KEEP <id> REMOVE <ids>` removes only selected duplicates
- `REMOVE <ids>` removes only the listed IDs
- `RIEN` / `SKIP` keeps the group unchanged
- `MODIF` repairs incorrect images/data
- `PAGE <id> <url>` changes the wiki page and re-reads available data
- `UNDO` cancels the latest non-applied decision
- `PREVIEW` shows the current duplicate group
- `APPLY` applies removals and renumbers IDs
- `STOP` exits without applying pending decisions

After applying duplicate changes:

```powershell
python scripts\build_colors.py
python scripts\build_paint_color_db.py --limit 5
python scripts\build_paint_color_db.py
python scripts\find_duplicates.py
python scripts\test_color_search_site.py
```

---

# 20. Undoing or cleaning duplicate merge data

Restore the duplicate-merge checkpoint:

```powershell
python scripts\merge_duplicates.py --undo
```

Clean temporary merge files once everything is confirmed:

```powershell
python scripts\merge_duplicates.py --clean
```

---

# 21. Recommended workflows

## Normal website use

```powershell
.venv\Scripts\Activate.ps1
python app.py
```

---

## After fixing an image

```powershell
python scripts\manual_fix.py
python scripts\build_colors.py
python scripts\build_paint_color_db.py --limit 5
python scripts\build_paint_color_db.py
python scripts\test_color_search_site.py
python app.py
```

---

## After duplicate cleanup

```powershell
python scripts\find_duplicates.py
python scripts\merge_duplicates.py
python scripts\build_colors.py
python scripts\build_paint_color_db.py --limit 5
python scripts\build_paint_color_db.py
python scripts\find_duplicates.py
python scripts\test_color_search_site.py
python app.py
```

---

## Full rebuild from source data

Use only when intentionally rebuilding everything:

```powershell
python scripts\build_poc.py
python scripts\manual_fix.py
python scripts\find_duplicates.py
python scripts\merge_duplicates.py
python scripts\build_colors.py
python scripts\build_paint_color_db.py --limit 5
python scripts\build_paint_color_db.py
python scripts\test_color_search_site.py
python app.py
```

Manual-fix and duplicate steps only need to be used when required by the rebuilt data.

---

# 22. Useful database inspection commands

To inspect the current SQLite table definitions from PowerShell:

```powershell
@'
import sqlite3

db = sqlite3.connect(r"data\terraria_blocks.db")

for name, sql in db.execute("""
    SELECT name, sql
    FROM sqlite_master
    WHERE type = 'table'
      AND sql IS NOT NULL
    ORDER BY name
"""):
    print(f"\n--- {name} ---")
    print(sql)

db.close()
'@ | python -
```

Count paint-color rows:

```powershell
@'
import sqlite3

db = sqlite3.connect(r"data\terraria_blocks.db")

count = db.execute(
    "SELECT COUNT(*) FROM object_paint_colors"
).fetchone()[0]

errors = db.execute(
    """
    SELECT COUNT(*)
    FROM object_paint_colors
    WHERE error IS NOT NULL
    """
).fetchone()[0]

print("Rows:", count)
print("Errors:", errors)

db.close()
'@ | python -
```

---

# 23. PowerShell notes

This project is developed from PowerShell.

Do not mix PowerShell and old CMD syntax.

## Correct PowerShell examples

Change folder:

```powershell
Set-Location "C:\Users\assim\Documents\Projets\Python\Terraria Color"
```

Delete a folder:

```powershell
Remove-Item "data\paint_lab" -Recurse -Force
```

Delete only if it exists:

```powershell
Remove-Item "path\to\file" -Force -ErrorAction SilentlyContinue
```

Create a directory safely:

```powershell
New-Item -ItemType Directory -Force "data\paint_lab\generated"
```

Check whether a file exists:

```powershell
Test-Path "data\terraria_blocks.db"
```

Open a generated HTML file:

```powershell
Start-Process "data\paint_lab\generated\all_blocks\index.html"
```

---

## CMD syntax that should not be used in PowerShell

Avoid:

```text
cd /d ...
if exist ...
rmdir /s /q ...
del /q ...
2>nul
```

These caused parsing/errors during the old paint-lab cleanup because they are CMD commands, not native PowerShell syntax.

---

# 24. Git workflow

Before committing:

```powershell
git status --short
```

Inspect changes:

```powershell
git diff
```

Inspect the size/summary:

```powershell
git diff --stat
```

Stage only what you intend to commit.

Example:

```powershell
git add app.py
git add templates
git add static
git add scripts
git add README.md
git add requirements.txt
```

If `data/terraria_blocks.db` is intentionally versioned in this repository, add it explicitly:

```powershell
git add data/terraria_blocks.db
```

Then inspect the staged commit:

```powershell
git status --short
git diff --cached --stat
git diff --cached
```

Commit:

```powershell
git commit -m "feat: add Terraria paint shader and perceptual color search"
```

Push:

```powershell
git push
```

Never add secrets, tokens, passwords, or private credentials to Git.

---

# 25. Files that normally should not be committed

The exact rules belong in `.gitignore`, but local/generated files generally include:

```text
.venv/
__pycache__/
*.pyc

data/backups/
data/site_backups/
data/paint_lab/generated/
data/paint_lab/tests/
data/tmp_merge/

temporary screenshots
debug images
local caches
generated contact sheets
```

Whether `data/terraria_blocks.db` is tracked is a project decision.

For this project, the database has historically been included so the website can run without rebuilding the entire dataset. If that remains the chosen workflow, continue versioning the canonical database but exclude backup copies.

---

# 26. Troubleshooting

## `ModuleNotFoundError: No module named 'app'`

A script inside `scripts/` may not automatically see the project root.

The current `scripts/test_color_search_site.py` explicitly adds the project root to `sys.path`.

Run tests from the project root:

```powershell
python scripts\test_color_search_site.py
```

---

## `Missing '(' after 'if'`

You probably used CMD syntax like:

```text
if exist ...
```

inside PowerShell.

Use PowerShell commands such as:

```powershell
Test-Path
Remove-Item
New-Item
```

instead.

---

## `cd /d` fails

`cd /d` is CMD syntax.

Use:

```powershell
Set-Location "C:\path\to\project"
```

---

## Paint-color table missing

Run:

```powershell
python scripts\build_paint_color_db.py --limit 5
python scripts\build_paint_color_db.py
```

Then verify:

```powershell
python scripts\test_color_search_site.py
```

---

## Website runs but paint previews fail

First test the local shader:

```powershell
python scripts\paint_shader\test_paint_shader.py
```

Then test the Flask endpoint:

```powershell
python scripts\test_color_search_site.py
```

---

# 27. Current validated state

At the time of this README update:

```text
Paint combinations: 9517
Paint-color calculation errors: 0
Dispersion p95 scale: 0.246059
Website smoke tests: 4/4 passed
```

The working site supports:

```text
Catalogue
Average color search
Dominant color search
OKLab perceptual ranking
Paint filtering
Dispersion weighting
Dynamic painted previews
```

---

# 28. Development philosophy

When extending the project:

1. make the smallest version that works
2. test it manually
3. add a smoke test when the workflow becomes important
4. test on a small sample before processing the whole dataset
5. create a backup before destructive database work
6. keep generated/debug data reproducible and disposable
7. update this README when commands or project structure change
8. only push after the local workflow is working

The goal is to keep the project understandable months later without needing to remember how every script works.
