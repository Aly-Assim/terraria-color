from __future__ import annotations

from io import BytesIO
from pathlib import Path
import math
import sqlite3

from flask import Flask, abort, render_template, request, send_file, url_for
from PIL import Image


from scripts.paths import PROJECT_ROOT, DB_PATH, IMAGES_ROOT, connect_readonly
from scripts.paint.renderer import PAINTS, apply_paint


app = Flask(__name__)

# Maximum additive penalty, expressed in OKLab-distance units.
# At 100% slider + dispersion_norm=1, a candidate receives +0.15.
MAX_DISPERSION_PENALTY = 0.15


# ============================================================
# DATABASE
# ============================================================

def connect_db():
    if not DB_PATH.exists():
        raise FileNotFoundError(
            "BDD introuvable : data/terraria_blocks.db"
        )

    connection = connect_readonly(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def table_exists(connection, table_name):
    cursor = connection.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def get_table_columns(connection, table_name):
    cursor = connection.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row["name"] for row in cursor.fetchall()}


def get_color_column_map(connection):
    """
    Keeps the old catalogue compatible with the pre-paint object_colors table.
    """
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
        if (
            candidate["r"] in columns
            and candidate["g"] in columns
            and candidate["b"] in columns
        ):
            return candidate

    return None


def paint_color_table_ready(connection):
    if not table_exists(connection, "object_paint_colors"):
        return False

    required = {
        "local_id",
        "paint_id",
        "paint_name",
        "avg_r",
        "avg_g",
        "avg_b",
        "dominant_r",
        "dominant_g",
        "dominant_b",
        "dominant_ratio",
        "dispersion_oklab",
        "dispersion_norm",
        "image_used",
        "error",
    }

    return required.issubset(
        get_table_columns(connection, "object_paint_colors")
    )


# ============================================================
# PATHS / IMAGES
# ============================================================

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


def resolve_painted_source(connection, local_id, paint_id):
    row = connection.execute(
        """
        SELECT
            opc.image_used,
            o.color_image_path,
            o.world_image_path
        FROM object_paint_colors opc
        JOIN objects o
            ON o.local_id = opc.local_id
        WHERE opc.local_id = ?
          AND opc.paint_id = ?
        LIMIT 1
        """,
        (local_id, paint_id),
    ).fetchone()

    if row is None:
        return None

    candidates = [
        row["image_used"],
        row["color_image_path"],
        row["world_image_path"],
    ]

    for candidate in candidates:
        if not candidate:
            continue

        candidate = normalize_path(candidate)
        full_path = (PROJECT_ROOT / candidate).resolve()

        try:
            full_path.relative_to(IMAGES_ROOT.resolve())
        except ValueError:
            continue

        if full_path.exists():
            return full_path

    return None


@app.route("/painted-image/<int:local_id>/<int:paint_id>")
def serve_painted_image(local_id, paint_id):
    if paint_id not in PAINTS:
        abort(404)

    connection = connect_db()

    try:
        if not paint_color_table_ready(connection):
            abort(404)

        source_path = resolve_painted_source(
            connection,
            local_id,
            paint_id,
        )
    finally:
        connection.close()

    if source_path is None:
        abort(404)

    with Image.open(source_path) as source:
        painted = apply_paint(
            source.convert("RGBA"),
            paint_id,
        )

        memory_file = BytesIO()
        painted.save(memory_file, format="PNG")
        memory_file.seek(0)

    return send_file(
        memory_file,
        mimetype="image/png",
        download_name=f"{local_id}_{paint_id}.png",
        max_age=3600,
    )


# ============================================================
# COLOR MATH
# ============================================================

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


def srgb_channel_to_linear(channel):
    channel = channel / 255.0

    if channel <= 0.04045:
        return channel / 12.92

    return ((channel + 0.055) / 1.055) ** 2.4


def rgb_to_oklab(r, g, b):
    """
    Convert an sRGB 0..255 triplet to OKLab.
    """
    r = srgb_channel_to_linear(float(r))
    g = srgb_channel_to_linear(float(g))
    b = srgb_channel_to_linear(float(b))

    l = (
        0.4122214708 * r
        + 0.5363325363 * g
        + 0.0514459929 * b
    )

    m = (
        0.2119034982 * r
        + 0.6806995451 * g
        + 0.1073969566 * b
    )

    s = (
        0.0883024619 * r
        + 0.2817188376 * g
        + 0.6299787005 * b
    )

    l_ = math.copysign(abs(l) ** (1.0 / 3.0), l)
    m_ = math.copysign(abs(m) ** (1.0 / 3.0), m)
    s_ = math.copysign(abs(s) ** (1.0 / 3.0), s)

    L = (
        0.2104542553 * l_
        + 0.7936177850 * m_
        - 0.0040720468 * s_
    )

    a = (
        1.9779984951 * l_
        - 2.4285922050 * m_
        + 0.4505937099 * s_
    )

    b = (
        0.0259040371 * l_
        + 0.7827717662 * m_
        - 0.8086757660 * s_
    )

    return L, a, b


def oklab_distance(rgb_a, rgb_b):
    lab_a = rgb_to_oklab(*rgb_a)
    lab_b = rgb_to_oklab(*rgb_b)

    return math.sqrt(
        sum(
            (value_a - value_b) ** 2
            for value_a, value_b in zip(lab_a, lab_b)
        )
    )


# ============================================================
# CATALOGUE
# ============================================================

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
        color_join = (
            "LEFT JOIN object_colors oc "
            "ON o.local_id = oc.local_id"
        )

    return f"""
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


def row_value(row, key, default=None):
    if key not in row.keys():
        return default

    value = row[key]

    if value is None:
        return default

    return value


def row_to_card(
    row,
    *,
    distance=None,
    score=None,
    search_color_mode=None,
):
    avg_r = row_value(row, "avg_r")
    avg_g = row_value(row, "avg_g")
    avg_b = row_value(row, "avg_b")
    avg_hex = row_value(row, "avg_hex")

    if (
        not avg_hex
        and avg_r is not None
        and avg_g is not None
        and avg_b is not None
    ):
        avg_hex = rgb_to_hex(avg_r, avg_g, avg_b)

    dominant_r = row_value(row, "dominant_r")
    dominant_g = row_value(row, "dominant_g")
    dominant_b = row_value(row, "dominant_b")
    dominant_hex = row_value(row, "dominant_hex")

    if (
        not dominant_hex
        and dominant_r is not None
        and dominant_g is not None
        and dominant_b is not None
    ):
        dominant_hex = rgb_to_hex(
            dominant_r,
            dominant_g,
            dominant_b,
        )

    paint_id = row_value(row, "paint_id")
    paint_name = row_value(row, "paint_name")

    painted_image_url = None

    if paint_id is not None:
        painted_image_url = url_for(
            "serve_painted_image",
            local_id=row["local_id"],
            paint_id=paint_id,
        )

    if search_color_mode == "dominant":
        matched_hex = dominant_hex
    else:
        matched_hex = avg_hex

    return {
        "local_id": row["local_id"],
        "name": row["name"],
        "canonical_name": row["canonical_name"],
        "category_name": row["category_name"],
        "page_url": row["page_url"],
        "status": row["status"],
        "problem": row["problem"],

        "inventory_image_url": image_url(
            row["inventory_image_path"]
        ),
        "world_image_url": image_url(
            row["world_image_path"]
        ),
        "color_image_url": image_url(
            row["color_image_path"]
        ),
        "painted_image_url": painted_image_url,

        "paint_id": paint_id,
        "paint_name": paint_name,

        "avg_r": avg_r,
        "avg_g": avg_g,
        "avg_b": avg_b,
        "avg_hex": avg_hex,

        "dominant_r": dominant_r,
        "dominant_g": dominant_g,
        "dominant_b": dominant_b,
        "dominant_hex": dominant_hex,
        "dominant_ratio": row_value(
            row,
            "dominant_ratio",
        ),

        "dispersion_oklab": row_value(
            row,
            "dispersion_oklab",
        ),
        "dispersion_norm": row_value(
            row,
            "dispersion_norm",
        ),

        "matched_hex": matched_hex,
        "search_color_mode": search_color_mode,
        "distance": distance,
        "score": score,
    }


def search_catalog(query_text, limit=200):
    query_text = query_text.strip().lower()

    if not query_text:
        return []

    connection = connect_db()

    try:
        query = base_select_query(connection)
        cursor = connection.cursor()
        like_value = f"%{query_text}%"

        cursor.execute(
            query
            + """
            WHERE
                LOWER(o.name) LIKE ?
                OR LOWER(o.canonical_name) LIKE ?
                OR LOWER(COALESCE(o.category_name, '')) LIKE ?
            ORDER BY o.name
            LIMIT ?
            """,
            (
                like_value,
                like_value,
                like_value,
                limit,
            ),
        )

        rows = cursor.fetchall()
    finally:
        connection.close()

    return [row_to_card(row) for row in rows]


# ============================================================
# COLOR SEARCH
# ============================================================

def search_by_color(
    hex_color,
    k,
    color_mode,
    dispersion_weight,
    paint_filter,
):
    target_rgb = hex_to_rgb(hex_color)

    connection = connect_db()

    try:
        if not paint_color_table_ready(connection):
            return (
                [],
                (
                    "La table object_paint_colors est introuvable ou "
                    "incompatible. Lance "
                    "python scripts/build/build_paint_colors.py"
                ),
            )

        if color_mode not in {"average", "dominant"}:
            color_mode = "average"

        if color_mode == "average":
            r_column = "avg_r"
            g_column = "avg_g"
            b_column = "avg_b"
        else:
            r_column = "dominant_r"
            g_column = "dominant_g"
            b_column = "dominant_b"

        sql = f"""
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

                opc.paint_id,
                opc.paint_name,

                opc.avg_r,
                opc.avg_g,
                opc.avg_b,
                opc.avg_hex,

                opc.dominant_r,
                opc.dominant_g,
                opc.dominant_b,
                opc.dominant_hex,
                opc.dominant_ratio,

                opc.dispersion_oklab,
                opc.dispersion_norm,

                opc.image_used

            FROM object_paint_colors opc
            JOIN objects o
                ON o.local_id = opc.local_id

            WHERE opc.error IS NULL
              AND opc.{r_column} IS NOT NULL
              AND opc.{g_column} IS NOT NULL
              AND opc.{b_column} IS NOT NULL
        """

        parameters = []

        if paint_filter != "all":
            sql += " AND opc.paint_id = ?"
            parameters.append(int(paint_filter))

        rows = connection.execute(
            sql,
            parameters,
        ).fetchall()
    finally:
        connection.close()

    results = []
    weight = dispersion_weight / 100.0

    for row in rows:
        if color_mode == "average":
            candidate_rgb = (
                row["avg_r"],
                row["avg_g"],
                row["avg_b"],
            )
        else:
            candidate_rgb = (
                row["dominant_r"],
                row["dominant_g"],
                row["dominant_b"],
            )

        distance = oklab_distance(
            target_rgb,
            candidate_rgb,
        )

        if color_mode == "average":
            dispersion_norm = (
                row["dispersion_norm"]
                if row["dispersion_norm"] is not None
                else 0.0
            )

            penalty = (
                weight
                * float(dispersion_norm)
                * MAX_DISPERSION_PENALTY
            )
        else:
            penalty = 0.0

        score = distance + penalty

        results.append(
            row_to_card(
                row,
                distance=distance,
                score=score,
                search_color_mode=color_mode,
            )
        )

    results.sort(
        key=lambda item: (
            item["score"],
            item["distance"],
            item["name"].lower(),
            item["paint_id"],
        )
    )

    return results[:k], None


# ============================================================
# PAGE
# ============================================================

def paint_options():
    return [
        {
            "id": paint_id,
            "slug": slug,
            "name": display_name,
        }
        for paint_id, (slug, display_name) in PAINTS.items()
    ]


@app.route("/")
def index():
    mode = request.args.get(
        "mode",
        "",
    ).strip()

    catalog_query = request.args.get(
        "q",
        "",
    ).strip()

    color_value = request.args.get(
        "color",
        "#8a6a4b",
    ).strip()

    k = safe_int(
        request.args.get("k", "20"),
        default=20,
        min_value=1,
        max_value=200,
    )

    color_mode = request.args.get(
        "color_mode",
        "average",
    ).strip().lower()

    if color_mode not in {
        "average",
        "dominant",
    }:
        color_mode = "average"

    dispersion_weight = safe_int(
        request.args.get(
            "dispersion",
            "35",
        ),
        default=35,
        min_value=0,
        max_value=100,
    )

    paint_filter = request.args.get(
        "paint",
        "all",
    ).strip().lower()

    valid_paint_ids = {
        str(paint_id)
        for paint_id in PAINTS
    }

    if (
        paint_filter != "all"
        and paint_filter not in valid_paint_ids
    ):
        paint_filter = "all"

    catalog_results = []
    color_results = []
    error = None
    target_rgb = None

    if mode == "catalog":
        catalog_results = search_catalog(
            catalog_query
        )

    if mode == "color":
        try:
            target_rgb = hex_to_rgb(
                color_value
            )

            color_value = rgb_to_hex(
                *target_rgb
            )

            color_results, error = (
                search_by_color(
                    color_value,
                    k,
                    color_mode,
                    dispersion_weight,
                    paint_filter,
                )
            )

        except Exception as exception:
            error = str(exception)

    selected_paint_name = "Toutes les peintures"

    if paint_filter != "all":
        paint_id = int(paint_filter)
        selected_paint_name = PAINTS[
            paint_id
        ][1]

    return render_template(
        "index.html",

        mode=mode,

        catalog_query=catalog_query,
        catalog_results=catalog_results,

        color_value=color_value,
        target_rgb=target_rgb,
        k=k,
        color_results=color_results,

        color_mode=color_mode,
        dispersion_weight=dispersion_weight,

        paint_filter=paint_filter,
        selected_paint_name=selected_paint_name,
        paint_options=paint_options(),

        error=error,
    )


if __name__ == "__main__":
    app.run()

