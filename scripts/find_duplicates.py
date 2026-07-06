from pathlib import Path
import csv
import hashlib
import sqlite3

from PIL import Image


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "terraria_blocks.db"

DUPLICATES_DIR = PROJECT_ROOT / "data" / "duplicates"
DUPLICATE_GROUPS_CSV = DUPLICATES_DIR / "duplicate_groups.csv"


def normalize_path(path):
    if not path:
        return None

    return str(path).replace("\\", "/")


def resolve_project_path(path):
    if not path:
        return None

    path = normalize_path(path)
    return (PROJECT_ROOT / path).resolve()


def connect_db():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"BDD introuvable : {DB_PATH}")

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def trim_transparent(image):
    """
    Supprime les bords totalement transparents.
    Si l'image n'a aucun pixel visible, on retourne l'image telle quelle.
    """
    image = image.convert("RGBA")
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()

    if bbox is None:
        return image

    return image.crop(bbox)


def pixel_signature(image_path):
    """
    Signature pixel exacte :
    - ouvre l'image
    - convertit en RGBA
    - enlève les bords transparents
    - hash la taille + les pixels exacts
    """
    image = Image.open(image_path).convert("RGBA")
    image = trim_transparent(image)

    width, height = image.size
    raw_pixels = image.tobytes()

    digest = hashlib.sha256()
    digest.update(str(width).encode("utf-8"))
    digest.update(b"x")
    digest.update(str(height).encode("utf-8"))
    digest.update(b":")
    digest.update(raw_pixels)

    return {
        "hash": digest.hexdigest(),
        "width": width,
        "height": height,
    }


def load_objects():
    connection = connect_db()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            local_id,
            name,
            category_name,
            page_url,
            inventory_image_path,
            world_image_path,
            color_image_path
        FROM objects
        WHERE world_image_path IS NOT NULL
        ORDER BY local_id
    """)

    rows = [dict(row) for row in cursor.fetchall()]
    connection.close()

    return rows


def find_duplicate_groups(objects):
    buckets = {}
    errors = []

    for row in objects:
        world_path = resolve_project_path(row.get("world_image_path"))

        if world_path is None or not world_path.exists():
            errors.append(f"[{row['local_id']}] {row['name']} | image world introuvable : {row.get('world_image_path')}")
            continue

        try:
            signature = pixel_signature(world_path)
        except Exception as error:
            errors.append(f"[{row['local_id']}] {row['name']} | erreur image : {error}")
            continue

        key = signature["hash"]

        if key not in buckets:
            buckets[key] = {
                "hash": key,
                "width": signature["width"],
                "height": signature["height"],
                "items": [],
            }

        buckets[key]["items"].append(row)

    duplicate_groups = []

    for bucket in buckets.values():
        if len(bucket["items"]) >= 2:
            duplicate_groups.append(bucket)

    duplicate_groups.sort(key=lambda group: group["items"][0]["local_id"])

    return duplicate_groups, errors


def save_duplicate_groups_csv(groups):
    DUPLICATES_DIR.mkdir(parents=True, exist_ok=True)

    with DUPLICATE_GROUPS_CSV.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)

        writer.writerow([
            "group_id",
            "local_id",
            "name",
            "category_name",
            "inventory_image_path",
            "world_image_path",
            "color_image_path",
            "page_url",
            "method",
            "pixel_width",
            "pixel_height",
            "pixel_hash",
        ])

        for group_index, group in enumerate(groups, start=1):
            for item in group["items"]:
                writer.writerow([
                    group_index,
                    item["local_id"],
                    item["name"],
                    item.get("category_name"),
                    normalize_path(item.get("inventory_image_path")),
                    normalize_path(item.get("world_image_path")),
                    normalize_path(item.get("color_image_path")),
                    item.get("page_url"),
                    "trimmed_pixel_equal",
                    group["width"],
                    group["height"],
                    group["hash"],
                ])


def main():
    print("FIND DUPLICATES")
    print("===============")
    print()

    objects = load_objects()

    print(f"Images world à analyser : {len(objects)}")
    print("Comparaison pixels exacts après crop transparent...")
    print()

    groups, errors = find_duplicate_groups(objects)
    save_duplicate_groups_csv(groups)

    total_items_in_groups = sum(len(group["items"]) for group in groups)

    print("Terminé.")
    print(f"Groupes de duplicates : {len(groups)}")
    print(f"Items concernés : {total_items_in_groups}")
    print(f"CSV : {DUPLICATE_GROUPS_CSV}")

    if errors:
        print()
        print("Erreurs / images ignorées :")
        for error in errors:
            print("- " + error)

    if groups:
        print()
        print("Prochaine étape :")
        print("python scripts\\merge_duplicates.py")
    else:
        print()
        print("Aucun duplicate pixel exact trouvé.")


if __name__ == "__main__":
    main()