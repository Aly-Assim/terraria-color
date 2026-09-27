from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DB_PATH = PROJECT_ROOT / "data" / "terraria_blocks.db"

PAINT_SHADER_DIR = PROJECT_ROOT / "scripts" / "paint_shader"

if str(PAINT_SHADER_DIR) not in sys.path:
    sys.path.insert(0, str(PAINT_SHADER_DIR))

from terraria_paint_shader import PAINTS, apply_paint


ALPHA_THRESHOLD = 10
DOMINANT_CLUSTER_COUNT = 5


# ============================================================
# RGB / LINEAR RGB
# ============================================================

def srgb_to_linear(rgb: np.ndarray) -> np.ndarray:
    rgb = np.asarray(rgb, dtype=np.float64)

    return np.where(
        rgb <= 0.04045,
        rgb / 12.92,
        ((rgb + 0.055) / 1.055) ** 2.4,
    )


def linear_to_srgb(rgb: np.ndarray) -> np.ndarray:
    rgb = np.asarray(rgb, dtype=np.float64)

    return np.where(
        rgb <= 0.0031308,
        12.92 * rgb,
        1.055 * np.power(rgb, 1.0 / 2.4) - 0.055,
    )


# ============================================================
# OKLAB
# ============================================================

def linear_rgb_to_oklab(rgb: np.ndarray) -> np.ndarray:
    r = rgb[..., 0]
    g = rgb[..., 1]
    b = rgb[..., 2]

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

    l_ = np.cbrt(l)
    m_ = np.cbrt(m)
    s_ = np.cbrt(s)

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

    return np.stack((L, a, b), axis=-1)


def srgb_to_oklab(rgb: np.ndarray) -> np.ndarray:
    return linear_rgb_to_oklab(srgb_to_linear(rgb))


# ============================================================
# HELPERS
# ============================================================

def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def make_edge_weights(
    width: int,
    height: int,
) -> np.ndarray:
    """
    The edge is not deleted.

    It is only slightly down-weighted for the dominant-color search so
    that a uniform 1-pixel border cannot trivially become the dominant
    cluster while the actual texture is varied.
    """

    weights = np.ones((height, width), dtype=np.float64)

    if width < 8 or height < 8:
        return weights

    # Outermost pixel ring.
    weights[0, :] *= 0.35
    weights[-1, :] *= 0.35
    weights[:, 0] *= 0.35
    weights[:, -1] *= 0.35

    # Second ring.
    if width >= 10 and height >= 10:
        weights[1, 1:-1] *= 0.70
        weights[-2, 1:-1] *= 0.70
        weights[1:-1, 1] *= 0.70
        weights[1:-1, -2] *= 0.70

    return weights


# ============================================================
# DOMINANT COLOR
# ============================================================

def weighted_kmeans(
    points: np.ndarray,
    weights: np.ndarray,
    cluster_count: int,
    max_iterations: int = 40,
) -> tuple[np.ndarray, np.ndarray]:
    count = len(points)

    if count == 0:
        raise ValueError("No points for clustering.")

    cluster_count = min(cluster_count, count)

    # First centroid = global weighted center.
    first = np.average(points, axis=0, weights=weights)

    centroids = [first]

    # Deterministic farthest-point initialization.
    while len(centroids) < cluster_count:
        centroid_array = np.asarray(centroids)

        distances = np.sum(
            (points[:, None, :] - centroid_array[None, :, :]) ** 2,
            axis=2,
        )

        nearest_distance = np.min(distances, axis=1)

        score = nearest_distance * np.sqrt(weights)

        next_index = int(np.argmax(score))

        centroids.append(points[next_index])

    centroids = np.asarray(centroids, dtype=np.float64)

    assignments = np.zeros(count, dtype=np.int32)

    for _ in range(max_iterations):
        distances = np.sum(
            (points[:, None, :] - centroids[None, :, :]) ** 2,
            axis=2,
        )

        new_assignments = np.argmin(distances, axis=1)

        new_centroids = centroids.copy()

        for cluster_index in range(cluster_count):
            mask = new_assignments == cluster_index

            if not np.any(mask):
                continue

            new_centroids[cluster_index] = np.average(
                points[mask],
                axis=0,
                weights=weights[mask],
            )

        movement = np.max(
            np.linalg.norm(
                new_centroids - centroids,
                axis=1,
            )
        )

        centroids = new_centroids
        assignments = new_assignments

        if movement < 1e-6:
            break

    return centroids, assignments


def calculate_dominant_color(
    rgb_pixels: np.ndarray,
    lab_pixels: np.ndarray,
    alpha_weights: np.ndarray,
    spatial_weights: np.ndarray,
) -> tuple[tuple[int, int, int], float]:
    clustering_weights = alpha_weights * spatial_weights

    unique_count = len(
        np.unique(
            np.round(lab_pixels, decimals=4),
            axis=0,
        )
    )

    cluster_count = min(
        DOMINANT_CLUSTER_COUNT,
        max(1, unique_count),
    )

    centroids, assignments = weighted_kmeans(
        lab_pixels,
        clustering_weights,
        cluster_count,
    )

    cluster_masses = np.zeros(cluster_count, dtype=np.float64)

    for cluster_index in range(cluster_count):
        mask = assignments == cluster_index

        cluster_masses[cluster_index] = np.sum(
            clustering_weights[mask]
        )

    dominant_cluster = int(np.argmax(cluster_masses))

    dominant_mask = assignments == dominant_cluster

    dominant_lab = lab_pixels[dominant_mask]
    dominant_rgb = rgb_pixels[dominant_mask]

    dominant_centroid = centroids[dominant_cluster]

    # Pick a REAL source pixel closest to the cluster center.
    # This avoids inventing a color that never existed in the texture.
    distances = np.sum(
        (dominant_lab - dominant_centroid) ** 2,
        axis=1,
    )

    representative_index = int(np.argmin(distances))

    representative_rgb = dominant_rgb[representative_index]

    rgb_tuple = tuple(
        int(round(channel * 255.0))
        for channel in representative_rgb
    )

    # Ratio is calculated with real alpha weights,
    # not the edge-deemphasized clustering weights.
    dominant_alpha_mass = np.sum(
        alpha_weights[dominant_mask]
    )

    total_alpha_mass = np.sum(alpha_weights)

    dominant_ratio = (
        dominant_alpha_mass / total_alpha_mass
        if total_alpha_mass > 0
        else 0.0
    )

    return rgb_tuple, float(dominant_ratio)


# ============================================================
# COLOR STATISTICS
# ============================================================

def calculate_color_metrics(
    image: Image.Image,
) -> dict:
    rgba = np.asarray(
        image.convert("RGBA"),
        dtype=np.uint8,
    )

    height, width = rgba.shape[:2]

    alpha = rgba[..., 3].astype(np.float64)

    useful_mask = alpha > ALPHA_THRESHOLD

    useful_pixel_count = int(np.count_nonzero(useful_mask))

    if useful_pixel_count == 0:
        raise ValueError("Image contains no useful visible pixels.")

    rgb = (
        rgba[..., :3]
        .astype(np.float64)
        / 255.0
    )

    rgb_pixels = rgb[useful_mask]

    alpha_weights = (
        alpha[useful_mask]
        / 255.0
    )

    alpha_weight = float(
        np.sum(alpha_weights)
    )

    # --------------------------------------------------------
    # Naive weighted sRGB mean
    # --------------------------------------------------------

    naive = np.average(
        rgb_pixels,
        axis=0,
        weights=alpha_weights,
    )

    naive_rgb = tuple(
        int(round(channel * 255.0))
        for channel in naive
    )

    # --------------------------------------------------------
    # Linear-light weighted RGB mean
    # Same philosophy as the existing object_colors table.
    # --------------------------------------------------------

    linear_pixels = srgb_to_linear(
        rgb_pixels
    )

    avg_linear = np.average(
        linear_pixels,
        axis=0,
        weights=alpha_weights,
    )

    avg_srgb = np.clip(
        linear_to_srgb(avg_linear),
        0.0,
        1.0,
    )

    avg_rgb = tuple(
        int(round(channel * 255.0))
        for channel in avg_srgb
    )

    # --------------------------------------------------------
    # OKLab dispersion
    # --------------------------------------------------------

    lab_pixels = linear_rgb_to_oklab(
        linear_pixels
    )

    lab_mean = np.average(
        lab_pixels,
        axis=0,
        weights=alpha_weights,
    )

    squared_distances = np.sum(
        (lab_pixels - lab_mean) ** 2,
        axis=1,
    )

    dispersion_oklab = float(
        np.sqrt(
            np.average(
                squared_distances,
                weights=alpha_weights,
            )
        )
    )

    # --------------------------------------------------------
    # Intelligent dominant color
    # --------------------------------------------------------

    edge_map = make_edge_weights(
        width,
        height,
    )

    spatial_weights = edge_map[
        useful_mask
    ]

    dominant_rgb, dominant_ratio = (
        calculate_dominant_color(
            rgb_pixels,
            lab_pixels,
            alpha_weights,
            spatial_weights,
        )
    )

    return {
        "avg_r": avg_rgb[0],
        "avg_g": avg_rgb[1],
        "avg_b": avg_rgb[2],
        "avg_hex": rgb_to_hex(avg_rgb),

        "avg_linear_r": float(avg_linear[0]),
        "avg_linear_g": float(avg_linear[1]),
        "avg_linear_b": float(avg_linear[2]),

        "naive_r": naive_rgb[0],
        "naive_g": naive_rgb[1],
        "naive_b": naive_rgb[2],
        "naive_hex": rgb_to_hex(naive_rgb),

        "dominant_r": dominant_rgb[0],
        "dominant_g": dominant_rgb[1],
        "dominant_b": dominant_rgb[2],
        "dominant_hex": rgb_to_hex(dominant_rgb),

        "dominant_ratio": dominant_ratio,

        "dispersion_oklab": dispersion_oklab,

        "useful_pixel_count": useful_pixel_count,
        "alpha_weight": alpha_weight,
    }


# ============================================================
# DATABASE
# ============================================================

def create_backup() -> Path:
    backup_dir = PROJECT_ROOT / "data" / "backups"

    backup_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    backup_path = (
        backup_dir
        / f"terraria_blocks_before_paint_colors_{timestamp}.db"
    )

    shutil.copy2(
        DB_PATH,
        backup_path,
    )

    return backup_path


def create_table(
    connection: sqlite3.Connection,
) -> None:
    connection.execute(
        """
        DROP TABLE IF EXISTS object_paint_colors
        """
    )

    connection.execute(
        """
        CREATE TABLE object_paint_colors (
            local_id INTEGER NOT NULL,

            paint_id INTEGER NOT NULL,
            paint_name TEXT NOT NULL,

            avg_r INTEGER,
            avg_g INTEGER,
            avg_b INTEGER,
            avg_hex TEXT,

            avg_linear_r REAL,
            avg_linear_g REAL,
            avg_linear_b REAL,

            naive_r INTEGER,
            naive_g INTEGER,
            naive_b INTEGER,
            naive_hex TEXT,

            dominant_r INTEGER,
            dominant_g INTEGER,
            dominant_b INTEGER,
            dominant_hex TEXT,

            dominant_ratio REAL,

            dispersion_oklab REAL,
            dispersion_norm REAL,

            useful_pixel_count INTEGER,
            alpha_weight REAL,

            image_used TEXT,
            image_role TEXT,

            method TEXT NOT NULL,
            alpha_threshold INTEGER NOT NULL,

            error TEXT,

            PRIMARY KEY(local_id, paint_id),

            FOREIGN KEY(local_id)
                REFERENCES objects(local_id)
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS
        idx_object_paint_colors_paint_id
        ON object_paint_colors(paint_id)
        """
    )


def insert_result(
    connection: sqlite3.Connection,
    local_id: int,
    paint_id: int,
    paint_name: str,
    image_used: str,
    image_role: str,
    metrics: dict | None,
    error: str | None,
) -> None:
    if metrics is None:
        metrics = {}

    connection.execute(
        """
        INSERT INTO object_paint_colors (
            local_id,

            paint_id,
            paint_name,

            avg_r,
            avg_g,
            avg_b,
            avg_hex,

            avg_linear_r,
            avg_linear_g,
            avg_linear_b,

            naive_r,
            naive_g,
            naive_b,
            naive_hex,

            dominant_r,
            dominant_g,
            dominant_b,
            dominant_hex,

            dominant_ratio,

            dispersion_oklab,
            dispersion_norm,

            useful_pixel_count,
            alpha_weight,

            image_used,
            image_role,

            method,
            alpha_threshold,

            error
        )
        VALUES (
            ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?,
            ?, NULL,
            ?, ?,
            ?, ?,
            ?,
            ?,
            ?
        )
        """,
        (
            local_id,

            paint_id,
            paint_name,

            metrics.get("avg_r"),
            metrics.get("avg_g"),
            metrics.get("avg_b"),
            metrics.get("avg_hex"),

            metrics.get("avg_linear_r"),
            metrics.get("avg_linear_g"),
            metrics.get("avg_linear_b"),

            metrics.get("naive_r"),
            metrics.get("naive_g"),
            metrics.get("naive_b"),
            metrics.get("naive_hex"),

            metrics.get("dominant_r"),
            metrics.get("dominant_g"),
            metrics.get("dominant_b"),
            metrics.get("dominant_hex"),

            metrics.get("dominant_ratio"),

            metrics.get("dispersion_oklab"),

            metrics.get("useful_pixel_count"),
            metrics.get("alpha_weight"),

            image_used,
            image_role,

            "tile_shader_v1+linear_mean+oklab_kmeans5_edge_safe",
            ALPHA_THRESHOLD,

            error,
        ),
    )


def normalize_dispersion(
    connection: sqlite3.Connection,
) -> float:
    values = [
        row[0]
        for row in connection.execute(
            """
            SELECT dispersion_oklab
            FROM object_paint_colors
            WHERE error IS NULL
              AND dispersion_oklab IS NOT NULL
            """
        )
    ]

    if not values:
        return 1.0

    values_array = np.asarray(
        values,
        dtype=np.float64,
    )

    # Robust scale:
    # extreme outliers do not ruin the 0..1 slider.
    p95 = float(
        np.percentile(
            values_array,
            95,
        )
    )

    if p95 <= 0:
        p95 = 1.0

    rows = connection.execute(
        """
        SELECT
            local_id,
            paint_id,
            dispersion_oklab
        FROM object_paint_colors
        WHERE error IS NULL
          AND dispersion_oklab IS NOT NULL
        """
    ).fetchall()

    for local_id, paint_id, dispersion in rows:
        normalized = min(
            1.0,
            float(dispersion) / p95,
        )

        connection.execute(
            """
            UPDATE object_paint_colors
            SET dispersion_norm = ?
            WHERE local_id = ?
              AND paint_id = ?
            """,
            (
                normalized,
                local_id,
                paint_id,
            ),
        )

    return p95


# ============================================================
# BUILD
# ============================================================

def resolve_source_image(
    row: sqlite3.Row,
) -> tuple[Path | None, str | None, str | None]:
    candidates = [
        (
            "color_image_path",
            row["color_image_path"],
        ),
        (
            "world_image_path",
            row["world_image_path"],
        ),
    ]

    for role, relative_path in candidates:
        if not relative_path:
            continue

        path = PROJECT_ROOT / relative_path

        if path.exists():
            return path, relative_path, role

    return None, None, None


def build_database(
    limit: int | None = None,
) -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found: {DB_PATH}"
        )

    backup_path = create_backup()

    print(
        f"[BACKUP] {backup_path.relative_to(PROJECT_ROOT)}"
    )

    connection = sqlite3.connect(
        DB_PATH
    )

    connection.row_factory = sqlite3.Row

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    try:
        rows = connection.execute(
            """
            SELECT
                local_id,
                name,
                color_image_path,
                world_image_path
            FROM objects
            ORDER BY local_id
            """
        ).fetchall()

        if limit is not None:
            rows = rows[:limit]

        create_table(connection)

        total_objects = len(rows)
        total_success = 0
        total_errors = 0

        print()
        print(
            f"Objects: {total_objects}"
        )

        print(
            f"Paints per object: {len(PAINTS)}"
        )

        print(
            f"Expected rows: "
            f"{total_objects * len(PAINTS)}"
        )

        print()

        for object_index, row in enumerate(
            rows,
            start=1,
        ):
            local_id = row["local_id"]
            name = row["name"]

            (
                source_path,
                image_used,
                image_role,
            ) = resolve_source_image(row)

            print(
                f"[{object_index}/{total_objects}] "
                f"{local_id} - {name}"
            )

            if source_path is None:
                message = (
                    "No usable color_image_path "
                    "or world_image_path."
                )

                print(
                    f"    [ERROR] {message}"
                )

                for paint_id, (_, paint_name) in PAINTS.items():
                    insert_result(
                        connection,
                        local_id,
                        paint_id,
                        paint_name,
                        "",
                        "",
                        None,
                        message,
                    )

                    total_errors += 1

                continue

            try:
                with Image.open(source_path) as source_image:
                    source_image = source_image.convert(
                        "RGBA"
                    )

                    for paint_id, (_, paint_name) in PAINTS.items():
                        try:
                            painted_image = apply_paint(
                                source_image,
                                paint_id,
                            )

                            metrics = calculate_color_metrics(
                                painted_image
                            )

                            insert_result(
                                connection,
                                local_id,
                                paint_id,
                                paint_name,
                                image_used,
                                image_role,
                                metrics,
                                None,
                            )

                            total_success += 1

                        except Exception as exc:
                            message = (
                                f"{type(exc).__name__}: {exc}"
                            )

                            insert_result(
                                connection,
                                local_id,
                                paint_id,
                                paint_name,
                                image_used,
                                image_role,
                                None,
                                message,
                            )

                            total_errors += 1

                            print(
                                f"    [PAINT {paint_id:02d} ERROR] "
                                f"{message}"
                            )

            except Exception as exc:
                message = (
                    f"{type(exc).__name__}: {exc}"
                )

                print(
                    f"    [IMAGE ERROR] {message}"
                )

                for paint_id, (_, paint_name) in PAINTS.items():
                    insert_result(
                        connection,
                        local_id,
                        paint_id,
                        paint_name,
                        image_used or "",
                        image_role or "",
                        None,
                        message,
                    )

                    total_errors += 1

        print()
        print(
            "Normalizing OKLab dispersion..."
        )

        p95 = normalize_dispersion(
            connection
        )

        connection.commit()

        actual_rows = connection.execute(
            """
            SELECT COUNT(*)
            FROM object_paint_colors
            """
        ).fetchone()[0]

        print()
        print(
            "===== COMPLETE ====="
        )

        print(
            f"Rows created: {actual_rows}"
        )

        print(
            f"Successful calculations: {total_success}"
        )

        print(
            f"Errors: {total_errors}"
        )

        print(
            f"Dispersion p95 scale: {p95:.6f}"
        )

        print()
        print(
            "Database:"
        )

        print(
            DB_PATH
        )

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


# ============================================================
# CLI
# ============================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build object_paint_colors using the "
            "Terraria paint shader."
        )
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Only process the first N objects. "
            "Useful for a quick smoke test."
        ),
    )

    args = parser.parse_args()

    try:
        build_database(
            limit=args.limit
        )

    except Exception as exc:
        print()
        print(
            "[FATAL ERROR]"
        )

        print(
            f"{type(exc).__name__}: {exc}"
        )

        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())