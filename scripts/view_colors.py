from pathlib import Path
import csv
import html
import os
import webbrowser
import math


CSV_PATH = Path("data/colors.csv")
OUTPUT_HTML_PATH = Path("data/color_gallery.html")


def safe_text(value):
    if value is None:
        return ""

    return html.escape(str(value))


def parse_int(value):
    try:
        return int(value)
    except Exception:
        return None


def color_distance(row):
    cr = parse_int(row.get("avg_r"))
    cg = parse_int(row.get("avg_g"))
    cb = parse_int(row.get("avg_b"))

    nr = parse_int(row.get("naive_r"))
    ng = parse_int(row.get("naive_g"))
    nb = parse_int(row.get("naive_b"))

    if None in [cr, cg, cb, nr, ng, nb]:
        return None

    return math.sqrt((cr - nr) ** 2 + (cg - ng) ** 2 + (cb - nb) ** 2)


def make_relative_image_src(image_used):
    if not image_used:
        return None

    image_path = Path(image_used)

    if not image_path.is_absolute():
        image_path = Path.cwd() / image_path

    if not image_path.exists():
        return None

    relative = os.path.relpath(image_path, OUTPUT_HTML_PATH.parent)
    return Path(relative).as_posix()


def load_rows():
    if not CSV_PATH.exists():
        raise FileNotFoundError(
            f"Fichier introuvable : {CSV_PATH}. Lance d'abord python scripts/build_colors.py"
        )

    with CSV_PATH.open("r", encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    rows.sort(key=lambda row: parse_int(row.get("local_id")) if parse_int(row.get("local_id")) is not None else 999999)

    return rows


def build_card(row):
    local_id = safe_text(row.get("local_id"))
    name = safe_text(row.get("name"))

    avg_hex = row.get("avg_hex") or "#000000"
    naive_hex = row.get("naive_hex") or "#000000"

    avg_rgb = f"{row.get('avg_r')}, {row.get('avg_g')}, {row.get('avg_b')}"
    naive_rgb = f"{row.get('naive_r')}, {row.get('naive_g')}, {row.get('naive_b')}"

    image_role = safe_text(row.get("image_role"))
    image_used = safe_text(row.get("image_used"))
    error = row.get("error") or ""

    distance = color_distance(row)
    distance_text = f"{distance:.2f}" if distance is not None else "—"

    image_src = make_relative_image_src(row.get("image_used"))

    if image_src:
        image_html = f'<img class="tile-img" src="{safe_text(image_src)}" alt="{name}">'
    else:
        image_html = '<div class="missing-img">image<br>missing</div>'

    if error:
        error_html = f'<div class="error">Erreur : {safe_text(error)}</div>'
    else:
        error_html = ""

    return f"""
    <article class="card">
        <div class="top">
            <div class="tile-box">
                {image_html}
            </div>

            <div class="title-box">
                <div class="local-id">#{local_id}</div>
                <h2>{name}</h2>
                <div class="small">image role : {image_role}</div>
            </div>
        </div>

        <div class="colors">
            <div class="color-row">
                <div class="swatch" style="background:{safe_text(avg_hex)}"></div>
                <div>
                    <div class="label">Correct linear RGB</div>
                    <div class="value">{safe_text(avg_hex)} — rgb({safe_text(avg_rgb)})</div>
                </div>
            </div>

            <div class="color-row">
                <div class="swatch" style="background:{safe_text(naive_hex)}"></div>
                <div>
                    <div class="label">Naïf RGB direct</div>
                    <div class="value">{safe_text(naive_hex)} — rgb({safe_text(naive_rgb)})</div>
                </div>
            </div>
        </div>

        <div class="meta">
            <div>différence correct / naïf : <strong>{distance_text}</strong></div>
            <details>
                <summary>image utilisée</summary>
                <code>{image_used}</code>
            </details>
        </div>

        {error_html}
    </article>
    """


def build_html(rows):
    ok_rows = [row for row in rows if not row.get("error")]
    error_rows = [row for row in rows if row.get("error")]

    cards_html = "\n".join(build_card(row) for row in rows)

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Terraria Color Gallery</title>
    <style>
        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
            padding: 24px;
            font-family: Arial, sans-serif;
            background: #15151a;
            color: #f2f2f2;
        }}

        header {{
            margin-bottom: 24px;
        }}

        h1 {{
            margin: 0 0 8px 0;
            font-size: 32px;
        }}

        .subtitle {{
            color: #b8b8c8;
            font-size: 15px;
        }}

        .stats {{
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
            margin-top: 16px;
        }}

        .stat {{
            background: #23232c;
            border: 1px solid #363646;
            border-radius: 12px;
            padding: 10px 14px;
        }}

        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(330px, 1fr));
            gap: 16px;
        }}

        .card {{
            background: #202029;
            border: 1px solid #343444;
            border-radius: 16px;
            padding: 14px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
        }}

        .top {{
            display: flex;
            gap: 14px;
            align-items: center;
            margin-bottom: 14px;
        }}

        .tile-box {{
            width: 72px;
            height: 72px;
            border-radius: 12px;
            background:
                linear-gradient(45deg, #2b2b35 25%, transparent 25%),
                linear-gradient(-45deg, #2b2b35 25%, transparent 25%),
                linear-gradient(45deg, transparent 75%, #2b2b35 75%),
                linear-gradient(-45deg, transparent 75%, #2b2b35 75%);
            background-size: 16px 16px;
            background-position: 0 0, 0 8px, 8px -8px, -8px 0px;
            display: flex;
            align-items: center;
            justify-content: center;
            image-rendering: pixelated;
            flex-shrink: 0;
            overflow: hidden;
            border: 1px solid #3c3c4d;
        }}

        .tile-img {{
            max-width: 64px;
            max-height: 64px;
            image-rendering: pixelated;
        }}

        .missing-img {{
            color: #9a9aac;
            font-size: 12px;
            text-align: center;
        }}

        .title-box h2 {{
            margin: 2px 0 6px 0;
            font-size: 19px;
            line-height: 1.15;
        }}

        .local-id {{
            color: #b6a7ff;
            font-weight: bold;
            font-size: 14px;
        }}

        .small {{
            color: #aaaabc;
            font-size: 13px;
        }}

        .colors {{
            display: flex;
            flex-direction: column;
            gap: 10px;
        }}

        .color-row {{
            display: flex;
            align-items: center;
            gap: 10px;
            background: #181820;
            border-radius: 12px;
            padding: 10px;
        }}

        .swatch {{
            width: 52px;
            height: 52px;
            border-radius: 10px;
            border: 1px solid rgba(255, 255, 255, 0.25);
            flex-shrink: 0;
        }}

        .label {{
            font-size: 13px;
            color: #b8b8c8;
            margin-bottom: 3px;
        }}

        .value {{
            font-size: 14px;
            font-family: Consolas, monospace;
        }}

        .meta {{
            margin-top: 12px;
            color: #c8c8d8;
            font-size: 13px;
        }}

        details {{
            margin-top: 6px;
        }}

        code {{
            display: block;
            margin-top: 6px;
            padding: 8px;
            background: #111116;
            border-radius: 8px;
            color: #d8d8e8;
            overflow-wrap: anywhere;
        }}

        .error {{
            margin-top: 12px;
            background: #3a1f25;
            border: 1px solid #8b3948;
            color: #ffb8c4;
            padding: 10px;
            border-radius: 10px;
            font-size: 13px;
        }}
    </style>
</head>
<body>
    <header>
        <h1>Terraria Color Gallery</h1>
        <div class="subtitle">
            Comparaison entre la moyenne correcte en linear RGB et la moyenne naïve RGB direct.
        </div>

        <div class="stats">
            <div class="stat">Total : <strong>{len(rows)}</strong></div>
            <div class="stat">OK : <strong>{len(ok_rows)}</strong></div>
            <div class="stat">Erreurs : <strong>{len(error_rows)}</strong></div>
            <div class="stat">Source : <strong>{CSV_PATH}</strong></div>
        </div>
    </header>

    <main class="grid">
        {cards_html}
    </main>
</body>
</html>
"""


def main():
    rows = load_rows()

    html_content = build_html(rows)

    OUTPUT_HTML_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_HTML_PATH.write_text(html_content, encoding="utf-8")

    print("Galerie créée.")
    print(f"HTML : {OUTPUT_HTML_PATH}")

    webbrowser.open(OUTPUT_HTML_PATH.resolve().as_uri())


if __name__ == "__main__":
    main()