from pathlib import Path
import math
import sqlite3

from flask import Flask, abort, render_template, request, send_file, url_for


PROJECT_ROOT = Path(__file__).parent.resolve()
DB_PATH = PROJECT_ROOT / "data" / "terraria_blocks.db"
IMAGES_ROOT = PROJECT_ROOT / "images"

app = Flask(__name__)


def connect_db():
    if not DB_PATH.exists():
        raise FileNotFoundError(
            "BDD introuvable. Lance d'abord scripts/build_poc.py puis scripts/build_colors.py"
        )

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def table_exists(connection, table_name):
    cursor = connection.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None


def get_table_columns(connection, table_name):
    cursor = connection.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row["name"] for row in cursor.fetchall()}


def get_color_column_map(connection):
    if not table_exists(connection, "object_colors"):
        return None

    columns = get_table_columns(connection, "object_colors")

    possible_maps = [
        {
            "r": "correct_r",
            "g": "correct_g",
            "b": "correct_b",
            "hex": "correct_hex",
        },
        {
            "r": "avg_r",
            "g": "avg_g",
            "b": "avg_b",
            "hex": "avg_hex",
        },
        {
            "r": "r",
            "g": "g",
            "b": "b",
            "hex": "hex",
        },
    ]

    for candidate in possible_maps:
        if candidate["r"] in columns and candidate["g"] in columns and candidate["b"] in columns:
            return candidate

    return None


def normalize_path(path):
    if not path:
        return None

    return str(path).replace("\\", "/")


def image_url(path):
    path = normalize_path(path)

    if not path:
        return None

    return url_for("serve_image", image_path=path)


@app.route("/image/<path:image_path>")
def serve_image(image_path):
    image_path = image_path.replace("\\", "/")
    relative_path = Path(image_path)

    if not relative_path.parts or relative_path.parts[0] != "images":
        abort(404)

    full_path = (PROJECT_ROOT / relative_path).resolve()

    try:
        full_path.relative_to(IMAGES_ROOT.resolve())
    except ValueError:
        abort(404)

    if not full_path.exists():
        abort(404)

    return send_file(full_path)


def hex_to_rgb(hex_color):
    value = hex_color.strip().lower()

    if value.startswith("#"):
        value = value[1:]

    if len(value) == 3:
        value = "".join(char * 2 for char in value)

    if len(value) != 6:
        raise ValueError("La couleur HEX doit avoir 6 caractères.")

    try:
        r = int(value[0:2], 16)
        g = int(value[2:4], 16)
        b = int(value[4:6], 16)
    except ValueError as error:
        raise ValueError("Couleur HEX invalide.") from error

    return r, g, b


def rgb_to_hex(r, g, b):
    return f"#{int(r):02x}{int(g):02x}{int(b):02x}"


def safe_int(value, default, min_value, max_value):
    try:
        result = int(value)
    except Exception:
        return default

    return max(min_value, min(max_value, result))


def base_select_query(connection):
    color_map = get_color_column_map(connection)

    if color_map is None:
        color_select = """
            NULL AS avg_r,
            NULL AS avg_g,
            NULL AS avg_b,
            NULL AS avg_hex
        """
        color_join = ""
    else:
        color_select = f"""
            oc.{color_map["r"]} AS avg_r,
            oc.{color_map["g"]} AS avg_g,
            oc.{color_map["b"]} AS avg_b,
            oc.{color_map.get("hex", color_map["r"])} AS avg_hex
        """
        color_join = "LEFT JOIN object_colors oc ON o.local_id = oc.local_id"

    query = f"""
        SELECT
            o.local_id,
            o.name,
            o.canonical_name,
            o.category_name,
            o.page_url,
            o.status,
            o.problem,
            o.inventory_image_path,
            o.world_image_path,
            o.color_image_path,
            {color_select}
        FROM objects o
        {color_join}
    """

    return query


def row_to_card(row, distance=None):
    avg_r = row["avg_r"]
    avg_g = row["avg_g"]
    avg_b = row["avg_b"]

    avg_hex = row["avg_hex"]

    if not avg_hex and avg_r is not None and avg_g is not None and avg_b is not None:
        avg_hex = rgb_to_hex(avg_r, avg_g, avg_b)

    return {
        "local_id": row["local_id"],
        "name": row["name"],
        "canonical_name": row["canonical_name"],
        "category_name": row["category_name"],
        "page_url": row["page_url"],
        "status": row["status"],
        "problem": row["problem"],
        "inventory_image_url": image_url(row["inventory_image_path"]),
        "world_image_url": image_url(row["world_image_path"]),
        "color_image_url": image_url(row["color_image_path"]),
        "avg_r": avg_r,
        "avg_g": avg_g,
        "avg_b": avg_b,
        "avg_hex": avg_hex,
        "distance": distance,
    }


def search_catalog(query_text, limit=200):
    query_text = query_text.strip().lower()

    if not query_text:
        return []

    connection = connect_db()
    query = base_select_query(connection)

    cursor = connection.cursor()
    like_value = f"%{query_text}%"

    cursor.execute(
        query + """
        WHERE
            LOWER(o.name) LIKE ?
            OR LOWER(o.canonical_name) LIKE ?
            OR LOWER(COALESCE(o.category_name, '')) LIKE ?
        ORDER BY o.name
        LIMIT ?
        """,
        (like_value, like_value, like_value, limit)
    )

    rows = cursor.fetchall()
    connection.close()

    return [row_to_card(row) for row in rows]


def search_by_color(hex_color, k):
    target_r, target_g, target_b = hex_to_rgb(hex_color)

    connection = connect_db()

    if get_color_column_map(connection) is None:
        connection.close()
        return [], "La table object_colors est introuvable ou incompatible. Lance python scripts/build_colors.py."

    query = base_select_query(connection)
    cursor = connection.cursor()

    cursor.execute(
        query + """
        WHERE
            avg_r IS NOT NULL
            AND avg_g IS NOT NULL
            AND avg_b IS NOT NULL
        """
    )

    rows = cursor.fetchall()
    connection.close()

    results = []

    for row in rows:
        r = float(row["avg_r"])
        g = float(row["avg_g"])
        b = float(row["avg_b"])

        distance = math.sqrt(
            (r - target_r) ** 2
            + (g - target_g) ** 2
            + (b - target_b) ** 2
        )

        results.append(row_to_card(row, distance=distance))

    results.sort(key=lambda item: item["distance"])

    return results[:k], None


@app.route("/")
def index():
    mode = request.args.get("mode", "").strip()
    catalog_query = request.args.get("q", "").strip()
    color_value = request.args.get("color", "#8a6a4b").strip()
    k = safe_int(request.args.get("k", "20"), default=20, min_value=1, max_value=200)

    catalog_results = []
    color_results = []
    error = None
    target_rgb = None

    if mode == "catalog":
        catalog_results = search_catalog(catalog_query)

    if mode == "color":
        try:
            target_rgb = hex_to_rgb(color_value)
            color_value = rgb_to_hex(*target_rgb)
            color_results, error = search_by_color(color_value, k)
        except Exception as exception:
            error = str(exception)

    return render_template(
        "index.html",
        mode=mode,
        catalog_query=catalog_query,
        catalog_results=catalog_results,
        color_value=color_value,
        target_rgb=target_rgb,
        k=k,
        color_results=color_results,
        error=error,
    )


if __name__ == "__main__":
    app.run(debug=True)