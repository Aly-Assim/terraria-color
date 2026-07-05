# Terraria Color Catalog

Terraria Color Catalog is a small Flask web app that helps browse Terraria blocks and find the blocks whose average color is closest to a selected color.

The project uses a local SQLite database built from Terraria block data and local block images.

## Features

- Browse a Terraria block catalog
- Search blocks by name, such as `stone`, `bamboo`, `brick`, `moss`
- Pick a color with a color picker
- Choose how many close blocks to display
- Display block images, average colors, IDs and wiki links
- Run locally with a simple Windows launcher

## Preview

The app has two main tools:

- **Catalog search**: search blocks by name or category
- **Color search**: choose a color and display the closest matching blocks

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
    └── view_colors.py
```

## How to run on Windows

Download the project, unzip it, then double-click:

```bat
run.bat
```

Then open:

```text
http://127.0.0.1:5000
```

## Manual setup

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

## Requirements

- Python 3.10 or later
- Flask
- Pillow
- BeautifulSoup
- Requests
- OpenPyXL

Dependencies are listed in `requirements.txt`.

## Notes

The SQLite database and local images are included so the app can run without rebuilding the full dataset.

The scraping and correction scripts are kept in `scripts/` for reproducibility, but the main app only needs:

- `app.py`
- `templates/`
- `static/`
- `data/terraria_blocks.db`
- `images/`
- `requirements.txt`
- `run.bat`