from pathlib import Path
import csv
import sqlite3
from PIL import Image, ImageSequence, ImageFile


ImageFile.LOAD_TRUNCATED_IMAGES = True


DB_PATH = Path("data/terraria_blocks.db")

COLOR_REPORT_PATH = Path("data/color_report.txt")
COLOR_CSV_PATH = Path("data/colors.csv")

ALPHA_THRESHOLD = 10

PROCESS_ANIMATED_IMAGES = True
MAX_FRAMES_PER_IMAGE = 60

METHOD_NAME = "alpha_weighted_linear_rgb_mean_v1"


def clamp01(value):
    return max(0.0, min(1.0, value))


def clamp255(value):
    return max(0, min(255, int(round(value))))


def srgb_to_linear(channel):
    """
    channel : valeur sRGB normalisée entre 0 et 1.
    Retourne la valeur linear RGB.
    """
    channel = clamp01(channel)

    if channel <= 0.04045:
        return channel / 12.92

    return ((channel + 0.055) / 1.055) ** 2.4


def linear_to_srgb(channel):
    """
    channel : valeur linear RGB entre 0 et 1.
    Retourne la valeur sRGB normalisée entre 0 et 1.
    """
    channel = clamp01(channel)

    if channel <= 0.0031308:
        return 12.92 * channel

    return 1.055 * (channel ** (1 / 2.4)) - 0.055


def rgb_to_hex(r, g, b):
    return f"#{r:02X}{g:02X}{b:02X}"


def choose_image_path(row):
    """
    Pour la couleur, on préfère :
    1. color_image_path
    2. world_image_path
    3. inventory_image_path en dernier secours
    """
    if row["color_image_path"]:
        return row["color_image_path"], "color_image_path"

    if row["world_image_path"]:
        return row["world_image_path"], "world_image_path"

    if row["inventory_image_path"]:
        return row["inventory_image_path"], "inventory_image_path"

    return None, None


def resolve_image_path(path_text):
    if not path_text:
        return None

    path = Path(path_text)

    if path.exists():
        return path

    # Au cas où la BDD contient un chemin relatif avec séparateurs Windows/autres.
    project_relative = Path.cwd() / path_text

    if project_relative.exists():
        return project_relative

    return path


def iter_frames(image):
    """
    Renvoie les frames à analyser.
    Pour une image normale : une seule frame.
    Pour un GIF/WebP animé : plusieurs frames, limitées par sécurité.
    """
    if not PROCESS_ANIMATED_IMAGES:
        yield image, 1.0
        return

    frame_count = getattr(image, "n_frames", 1)

    if frame_count <= 1:
        yield image, 1.0
        return

    count = 0

    for frame in ImageSequence.Iterator(image):
        if count >= MAX_FRAMES_PER_IMAGE:
            break

        duration_ms = frame.info.get("duration", 100)

        if not duration_ms or duration_ms <= 0:
            duration_ms = 100

        duration_weight = duration_ms / 100.0

        yield frame, duration_weight

        count += 1


def calculate_correct_average_rgb(image_path):
    """
    Moyenne correcte :
    - ouverture en RGBA
    - pixels transparents ignorés
    - alpha partiel utilisé comme poids
    - conversion sRGB -> linear RGB
    - moyenne en linear RGB
    - conversion linear RGB -> sRGB final

    On calcule aussi une moyenne naïve pour comparaison/debug.
    """
    sum_linear_r = 0.0
    sum_linear_g = 0.0
    sum_linear_b = 0.0

    sum_naive_r = 0.0
    sum_naive_g = 0.0
    sum_naive_b = 0.0

    total_weight = 0.0
    useful_pixel_count = 0
    frames_used = 0

    with Image.open(image_path) as image:
        for frame, frame_weight in iter_frames(image):
            rgba = frame.convert("RGBA")
            pixels = rgba.getdata()

            frames_used += 1

            for r, g, b, a in pixels:
                if a <= ALPHA_THRESHOLD:
                    continue

                alpha_weight = (a / 255.0) * frame_weight

                sr = r / 255.0
                sg = g / 255.0
                sb = b / 255.0

                linear_r = srgb_to_linear(sr)
                linear_g = srgb_to_linear(sg)
                linear_b = srgb_to_linear(sb)

                sum_linear_r += linear_r * alpha_weight
                sum_linear_g += linear_g * alpha_weight
                sum_linear_b += linear_b * alpha_weight

                sum_naive_r += r * alpha_weight
                sum_naive_g += g * alpha_weight
                sum_naive_b += b * alpha_weight

                total_weight += alpha_weight
                useful_pixel_count += 1

    if total_weight <= 0:
        raise ValueError("aucun pixel utile trouvé après filtrage alpha")

    avg_linear_r = sum_linear_r / total_weight
    avg_linear_g = sum_linear_g / total_weight
    avg_linear_b = sum_linear_b / total_weight

    avg_srgb_r = linear_to_srgb(avg_linear_r)
    avg_srgb_g = linear_to_srgb(avg_linear_g)
    avg_srgb_b = linear_to_srgb(avg_linear_b)

    avg_r = clamp255(avg_srgb_r * 255)
    avg_g = clamp255(avg_srgb_g * 255)
    avg_b = clamp255(avg_srgb_b * 255)

    naive_r = clamp255(sum_naive_r / total_weight)
    naive_g = clamp255(sum_naive_g / total_weight)
    naive_b = clamp255(sum_naive_b / total_weight)

    return {
        "avg_r": avg_r,
        "avg_g": avg_g,
        "avg_b": avg_b,
        "avg_hex": rgb_to_hex(avg_r, avg_g, avg_b),

        "avg_linear_r": avg_linear_r,
        "avg_linear_g": avg_linear_g,
        "avg_linear_b": avg_linear_b,

        "naive_r": naive_r,
        "naive_g": naive_g,
        "naive_b": naive_b,
        "naive_hex": rgb_to_hex(naive_r, naive_g, naive_b),

        "useful_pixel_count": useful_pixel_count,
        "alpha_weight": total_weight,
        "frames_used": frames_used,
    }


def connect_db():
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"BDD introuvable : {DB_PATH}. Lance d'abord scripts/build_poc.py."
        )

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def create_color_table(connection):
    cursor = connection.cursor()

    cursor.execute("""
        DROP TABLE IF EXISTS object_colors
    """)

    cursor.execute("""
        CREATE TABLE object_colors (
            local_id INTEGER PRIMARY KEY,

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

            useful_pixel_count INTEGER,
            alpha_weight REAL,
            frames_used INTEGER,

            image_used TEXT,
            image_role TEXT,

            method TEXT NOT NULL,
            alpha_threshold INTEGER NOT NULL,

            error TEXT,

            FOREIGN KEY(local_id) REFERENCES objects(local_id)
        )
    """)

    connection.commit()


def insert_color_result(connection, local_id, result):
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO object_colors (
            local_id,

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

            useful_pixel_count,
            alpha_weight,
            frames_used,

            image_used,
            image_role,

            method,
            alpha_threshold,

            error
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        local_id,

        result.get("avg_r"),
        result.get("avg_g"),
        result.get("avg_b"),
        result.get("avg_hex"),

        result.get("avg_linear_r"),
        result.get("avg_linear_g"),
        result.get("avg_linear_b"),

        result.get("naive_r"),
        result.get("naive_g"),
        result.get("naive_b"),
        result.get("naive_hex"),

        result.get("useful_pixel_count"),
        result.get("alpha_weight"),
        result.get("frames_used"),

        result.get("image_used"),
        result.get("image_role"),

        METHOD_NAME,
        ALPHA_THRESHOLD,

        result.get("error"),
    ))

    connection.commit()


def read_objects(connection):
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            local_id,
            name,
            color_image_path,
            world_image_path,
            inventory_image_path
        FROM objects
        ORDER BY local_id
    """)

    return cursor.fetchall()


def write_csv(results):
    with COLOR_CSV_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        writer.writerow([
            "local_id",
            "name",

            "avg_r",
            "avg_g",
            "avg_b",
            "avg_hex",

            "naive_r",
            "naive_g",
            "naive_b",
            "naive_hex",

            "useful_pixel_count",
            "alpha_weight",
            "frames_used",

            "image_role",
            "image_used",

            "error",
        ])

        for item in results:
            writer.writerow([
                item.get("local_id"),
                item.get("name"),

                item.get("avg_r"),
                item.get("avg_g"),
                item.get("avg_b"),
                item.get("avg_hex"),

                item.get("naive_r"),
                item.get("naive_g"),
                item.get("naive_b"),
                item.get("naive_hex"),

                item.get("useful_pixel_count"),
                item.get("alpha_weight"),
                item.get("frames_used"),

                item.get("image_role"),
                item.get("image_used"),

                item.get("error"),
            ])


def write_report(results):
    total = len(results)
    success = [item for item in results if not item.get("error")]
    errors = [item for item in results if item.get("error")]

    missing_images = [
        item for item in results
        if item.get("error") == "aucune image disponible"
    ]

    lines = []

    lines.append("TERRARIA COLOR REPORT")
    lines.append("=====================")
    lines.append("")
    lines.append("MÉTHODE")
    lines.append("-------")
    lines.append("Moyenne correcte en linear RGB avec pondération alpha.")
    lines.append("Étapes :")
    lines.append("1. ouvrir l'image en RGBA")
    lines.append("2. ignorer les pixels avec alpha trop faible")
    lines.append("3. convertir chaque canal sRGB vers linear RGB")
    lines.append("4. faire la moyenne en linear RGB")
    lines.append("5. reconvertir la moyenne finale vers sRGB 0-255")
    lines.append("")
    lines.append(f"method : {METHOD_NAME}")
    lines.append(f"alpha_threshold : {ALPHA_THRESHOLD}")
    lines.append(f"process_animated_images : {PROCESS_ANIMATED_IMAGES}")
    lines.append(f"max_frames_per_image : {MAX_FRAMES_PER_IMAGE}")
    lines.append("")
    lines.append("COUNTS")
    lines.append("------")
    lines.append(f"Objets lus : {total}")
    lines.append(f"Couleurs calculées : {len(success)}")
    lines.append(f"Erreurs : {len(errors)}")
    lines.append(f"Images manquantes : {len(missing_images)}")
    lines.append("")
    lines.append("EXEMPLES")
    lines.append("--------")

    for item in success[:80]:
        lines.append(
            f"{item['local_id']:03d} | {item['name']} | "
            f"correct={item['avg_hex']} ({item['avg_r']}, {item['avg_g']}, {item['avg_b']}) | "
            f"naive={item['naive_hex']} ({item['naive_r']}, {item['naive_g']}, {item['naive_b']}) | "
            f"pixels={item['useful_pixel_count']} | "
            f"image_role={item['image_role']}"
        )

    lines.append("")
    lines.append("ERREURS")
    lines.append("-------")

    for item in errors[:200]:
        lines.append(
            f"{item['local_id']:03d} | {item['name']} | "
            f"error={item['error']} | image={item.get('image_used')}"
        )

    lines.append("")
    lines.append("FICHIERS")
    lines.append("--------")
    lines.append(f"BDD : {DB_PATH}")
    lines.append(f"Table créée : object_colors")
    lines.append(f"CSV : {COLOR_CSV_PATH}")
    lines.append(f"Rapport : {COLOR_REPORT_PATH}")

    COLOR_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main():
    connection = connect_db()
    create_color_table(connection)

    objects = read_objects(connection)

    results = []

    print("Calcul des couleurs moyennes...")
    print()

    for row in objects:
        local_id = row["local_id"]
        name = row["name"]

        image_path_text, image_role = choose_image_path(row)

        base_result = {
            "local_id": local_id,
            "name": name,
            "image_used": image_path_text,
            "image_role": image_role,
        }

        print(f"[{local_id}] {name}")

        if not image_path_text:
            result = {
                **base_result,
                "error": "aucune image disponible",
            }

            insert_color_result(connection, local_id, result)
            results.append(result)

            print("  erreur : aucune image disponible")
            continue

        image_path = resolve_image_path(image_path_text)

        if image_path is None or not image_path.exists():
            result = {
                **base_result,
                "error": f"image introuvable : {image_path_text}",
            }

            insert_color_result(connection, local_id, result)
            results.append(result)

            print(f"  erreur : image introuvable : {image_path_text}")
            continue

        try:
            color_result = calculate_correct_average_rgb(image_path)

            result = {
                **base_result,
                **color_result,
                "image_used": str(image_path),
                "error": None,
            }

            insert_color_result(connection, local_id, result)
            results.append(result)

            print(
                f"  correct : {result['avg_hex']} "
                f"({result['avg_r']}, {result['avg_g']}, {result['avg_b']})"
            )
            print(
                f"  naive   : {result['naive_hex']} "
                f"({result['naive_r']}, {result['naive_g']}, {result['naive_b']})"
            )

        except Exception as error:
            result = {
                **base_result,
                "image_used": str(image_path),
                "error": str(error),
            }

            insert_color_result(connection, local_id, result)
            results.append(result)

            print(f"  erreur : {error}")

    connection.close()

    write_csv(results)
    write_report(results)

    print()
    print("Terminé.")
    print(f"Rapport : {COLOR_REPORT_PATH}")
    print(f"CSV : {COLOR_CSV_PATH}")
    print("Table BDD créée : object_colors")


if __name__ == "__main__":
    main()