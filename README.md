# Terraria Color Catalog

Terraria Color Catalog is a local Flask web app for browsing Terraria blocks and finding the blocks whose average color is closest to a selected color.

The app uses a SQLite database and local block images. It can be used as:

- a Terraria block catalog
- a block search tool
- a color matching tool for builds, pixel art, palettes, and decoration ideas

## Features

- Search blocks by name or category
- Search examples: `stone`, `bamboo`, `brick`, `moss`, `sand`
- Pick a color with a color picker
- Choose how many close blocks to display
- Display inventory images and placed/world images
- Display average block colors
- Show wiki links for each block
- Manually fix wrong images or missing data
- Detect duplicate world images with pixel comparison
- Merge duplicates safely with a temporary undo system

## Project structure

```text
terraria-color/
├── app.py
├── run.bat
├── requirements.txt
├── README.md
├── data/
│   └── terraria_blocks.db
├── images/
│   ├── inventory/
│   ├── world/
│   └── color/
├── static/
│   └── style.css
├── templates/
│   ├── index.html
│   └── partials_card.html
└── scripts/
    ├── build_poc.py
    ├── manual_fix.py
    ├── build_colors.py
    ├── view_colors.py
    ├── find_duplicates.py
    └── merge_duplicates.py
```

## How to run the website

### Quick Windows method

Double-click:

```bat
run.bat
```

Then open:

```text
http://127.0.0.1:5000
```

### Manual method

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Then open:

```text
http://127.0.0.1:5000
```

## Main app

### `app.py`

Runs the Flask website.

It provides:

- catalog search
- color picker
- closest block search
- image display
- wiki links

Run it with:

```bat
python app.py
```

Then open:

```text
http://127.0.0.1:5000
```

## Data scripts

### `scripts/build_poc.py`

Builds the main block database from the source Excel file and Terraria wiki pages.

It:

- reads the Terraria block list
- creates one entry per block
- tries to find inventory and world images from wiki infoboxes
- stores the result in `data/terraria_blocks.db`
- downloads images into `images/`

Important: this script is a rebuild script. Running it can overwrite manual corrections.

Run it only when rebuilding the database from scratch:

```bat
python scripts\build_poc.py
```

### `scripts/manual_fix.py`

Interactive script used to fix missing or wrong data manually.

It can:

- fix a wrong page URL
- add an inventory image
- add a world image
- add a color image
- update the database
- download the image into the correct folder

Run it with:

```bat
python scripts\manual_fix.py
```

Useful commands inside the script:

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

When `WORLD` is updated, the color image is updated with the same image.

### `scripts/build_colors.py`

Computes the average color of each block.

It reads the image used for color extraction and writes the result into the database.

Run this after:

- building the database
- fixing images manually
- merging duplicates

```bat
python scripts\build_colors.py
```

### `scripts/view_colors.py`

Creates a local gallery to visually inspect computed colors.

Run it with:

```bat
python scripts\view_colors.py
```

Then open the generated gallery if it does not open automatically.

## Duplicate tools

### `scripts/find_duplicates.py`

Finds blocks that have the same world image.

It compares pixels exactly after removing transparent borders.

It does not modify the database.

Run it with:

```bat
python scripts\find_duplicates.py
```

It creates:

```text
data/duplicates/duplicate_groups.csv
```

### `scripts/merge_duplicates.py`

Reads the duplicate groups and lets you decide what to keep or remove.

It shows a temporary preview PNG for each duplicate group with:

- block ID
- block name
- inventory image
- world image

Run it with:

```bat
python scripts\merge_duplicates.py
```

Useful commands inside the script:

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

- `KEEP <id>` keeps this block and removes the other blocks in the group
- `KEEP <id> REMOVE <ids>` removes only selected duplicates
- `REMOVE <ids>` removes only the given IDs
- `RIEN` or `SKIP` keeps the whole group unchanged
- `MODIF` fixes a wrong image manually
- `PAGE <id> <url>` changes the wiki page and tries to re-read the infobox
- `UNDO` cancels the last non-applied decision
- `APPLY` applies the removals and renumbers all IDs
- `STOP` exits without applying decisions

After applying duplicates, run:

```bat
python scripts\build_colors.py
python scripts\find_duplicates.py
```

## Undo after duplicate merge

If something goes wrong after an `APPLY`, restore the temporary checkpoint with:

```bat
python scripts\merge_duplicates.py --undo
```

When everything is confirmed, clean temporary merge files with:

```bat
python scripts\merge_duplicates.py --clean
```

## Recommended workflow

For normal use:

```bat
python app.py
```

For fixing images:

```bat
python scripts\manual_fix.py
python scripts\build_colors.py
python app.py
```

For duplicate cleaning:

```bat
python scripts\find_duplicates.py
python scripts\merge_duplicates.py
python scripts\build_colors.py
python app.py
```

## Notes

The database and images are included so the website can run directly without rebuilding the full dataset.

The source Excel file, cache files, debug files, and temporary merge files are not included in Git.