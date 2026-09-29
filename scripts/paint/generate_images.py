from __future__ import annotations

import sys
from pathlib import Path
from html import escape

import argparse
import csv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if __package__ in {None, ""}:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.paths import PAINTED_ROOT, connect_readonly
from scripts.paint.renderer import PAINTS, generate_all_paints, build_contact_sheet


def write_manifest(output_root: Path = PAINTED_ROOT) -> Path:
    """Index existing variants only; never render or modify an image."""
    with connect_readonly() as connection:
        objects = connection.execute(
            "SELECT local_id, name, world_image_path FROM objects ORDER BY local_id"
        ).fetchall()
    rows = []
    for obj in objects:
        source = obj["world_image_path"]
        if not source:
            continue
        folder = Path(source.replace("\\", "/")).stem
        for paint_id, (slug, name) in PAINTS.items():
            relative = Path(folder) / f"{paint_id:02d}_{slug}.png"
            if (output_root / relative).is_file():
                rows.append((obj["local_id"], obj["name"], paint_id, name,
                             relative.as_posix(), source.replace("\\", "/")))
    manifest = output_root / "manifest.csv"
    with manifest.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(("local_id", "object_name", "paint_id", "paint_name",
                         "relative_image_path", "source_image_path"))
        writer.writerows(rows)
    return manifest


def build_html_index(output_root: Path, block_names: list[str]) -> Path:
    cards = []

    for block_name in block_names:
        folder = output_root / block_name
        contact_sheet = folder / "_contact_sheet.png"

        if not contact_sheet.exists():
            continue

        relative_contact_sheet = f"{block_name}/_contact_sheet.png"

        cards.append(
            f"""
            <div class="card">
                <h2>{escape(block_name)}</h2>
                <p>
                    <a href="{escape(relative_contact_sheet)}" target="_blank">
                        Ouvrir la contact sheet
                    </a>
                </p>
                <a href="{escape(relative_contact_sheet)}" target="_blank">
                    <img src="{escape(relative_contact_sheet)}" alt="{escape(block_name)}">
                </a>
            </div>
            """
        )

    html = f"""
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Terraria Paint Shader — All Blocks</title>
    <style>
        body {{
            margin: 0;
            font-family: Arial, sans-serif;
            background: #111318;
            color: #f0f0f0;
        }}

        header {{
            padding: 24px;
            background: #1b1f27;
            border-bottom: 1px solid #2d3440;
            position: sticky;
            top: 0;
            z-index: 10;
        }}

        h1 {{
            margin: 0 0 8px 0;
            font-size: 28px;
        }}

        p {{
            margin: 0;
            color: #c7ccd6;
        }}

        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(420px, 1fr));
            gap: 20px;
            padding: 24px;
        }}

        .card {{
            background: #1b1f27;
            border: 1px solid #2d3440;
            border-radius: 12px;
            padding: 16px;
        }}

        .card h2 {{
            margin-top: 0;
            margin-bottom: 10px;
            font-size: 20px;
            word-break: break-word;
        }}

        .card p {{
            margin-bottom: 14px;
        }}

        .card a {{
            color: #7ec8ff;
            text-decoration: none;
        }}

        .card a:hover {{
            text-decoration: underline;
        }}

        .card img {{
            width: 100%;
            height: auto;
            border-radius: 8px;
            border: 1px solid #2d3440;
            background: #0f1116;
        }}
    </style>
</head>
<body>
    <header>
        <h1>Terraria Paint Shader — Tous les blocs</h1>
        <p>{len(block_names)} blocs générés. Clique sur une image pour l’ouvrir en grand.</p>
    </header>

    <main class="grid">
        {''.join(cards)}
    </main>
</body>
</html>
"""

    index_path = output_root / "index.html"
    index_path.write_text(html, encoding="utf-8")
    return index_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Export the public world-texture paint dataset.")
    parser.add_argument("--manifest-only", action="store_true",
                        help="Index existing PNGs without generating images.")
    args = parser.parse_args()
    if args.manifest_only:
        if not PAINTED_ROOT.is_dir():
            parser.error("The painted dataset directory is missing.")
        print(write_manifest())
        return 0

    with connect_readonly() as connection:
        objects = connection.execute(
            "SELECT local_id, name, world_image_path FROM objects ORDER BY local_id"
        ).fetchall()
    PAINTED_ROOT.mkdir(parents=True, exist_ok=True)
    generated_blocks = []
    errors = 0
    for obj in objects:
        try:
            if not obj["world_image_path"]:
                raise ValueError("No world image path")
            source = (PROJECT_ROOT / obj["world_image_path"].replace("\\", "/")).resolve()
            source.relative_to(PROJECT_ROOT / "images" / "world")
            output = PAINTED_ROOT / source.stem
            # Pillow reads frame zero for GIFs, as in the Flask paint endpoint.
            paths = generate_all_paints(source, output)
            build_contact_sheet(paths, output / "_contact_sheet.png", columns=4)
            generated_blocks.append(source.stem)
            print(f"[OK] {obj['local_id']}: {obj['name']}")
        except Exception as exc:
            errors += 1
            print(f"[ERROR] {obj['local_id']}: {exc}")
    print(build_html_index(PAINTED_ROOT, generated_blocks))
    print(write_manifest())
    print(f"Exported {len(generated_blocks)} objects; {errors} errors.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
