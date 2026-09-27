from __future__ import annotations

import sys
from pathlib import Path
from html import escape

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from terraria_paint_shader import generate_all_paints, build_contact_sheet


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
    project_root = Path(__file__).resolve().parents[2]
    source_dir = project_root / "images" / "world"
    output_root = project_root / "data" / "paint_lab" / "generated" / "all_blocks"

    if not source_dir.exists():
        print(f"[ERREUR] Dossier source introuvable : {source_dir}")
        return 1

    output_root.mkdir(parents=True, exist_ok=True)

    image_paths = sorted(source_dir.glob("*.png"))

    if not image_paths:
        print(f"[ERREUR] Aucune image trouvée dans : {source_dir}")
        return 1

    print("=== GENERATION DES PAINTS POUR TOUS LES BLOCS ===")
    print(f"Source : {source_dir}")
    print(f"Destination : {output_root}")
    print(f"Nombre d'images : {len(image_paths)}")
    print()

    generated_blocks = []

    for index, image_path in enumerate(image_paths, start=1):
        block_name = image_path.stem
        block_output_dir = output_root / block_name

        print(f"[{index}/{len(image_paths)}] {block_name}")

        try:
            generated_paths = generate_all_paints(image_path, block_output_dir)

            build_contact_sheet(
                generated_paths,
                block_output_dir / "_contact_sheet.png",
                columns=4,
            )

            generated_blocks.append(block_name)
            print("    OK")
        except Exception as exc:
            print(f"    ERREUR : {exc}")

    print()
    print("=== CONSTRUCTION DE L'INDEX HTML ===")
    index_path = build_html_index(output_root, generated_blocks)

    print(f"Index HTML : {index_path}")
    print()
    print("=== TERMINE ===")
    print(f"{len(generated_blocks)} blocs générés avec succès.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())