from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote, quote
import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import time

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw


PROJECT_ROOT = Path(__file__).resolve().parent.parent

DB_PATH = PROJECT_ROOT / "data" / "terraria_blocks.db"

DUPLICATES_DIR = PROJECT_ROOT / "data" / "duplicates"
DUPLICATE_GROUPS_CSV = DUPLICATES_DIR / "duplicate_groups.csv"

TMP_DIR = PROJECT_ROOT / "data" / "tmp_merge"
SESSION_PATH = TMP_DIR / "session.json"
PREVIEW_PATH = TMP_DIR / "current_group_preview.png"

BEFORE_DB_PATH = TMP_DIR / "terraria_blocks_before_apply.db"
BEFORE_IMAGES_DIR = TMP_DIR / "images_before_apply"

MERGE_REPORT_PATH = DUPLICATES_DIR / "merge_report.txt"

CACHE_PAGES_DIR = PROJECT_ROOT / "cache" / "pages"
CACHE_IMAGES_DIR = PROJECT_ROOT / "cache" / "images"

BASE_URL = "https://terraria.wiki.gg"
REQUEST_DELAY = 0.20

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    )
}

BAD_IMAGE_PARTS = [
    "desktop",
    "console",
    "mobile",
    "old-gen",
    "old_gen",
    "3ds",
    "journey",
    "classic",
    "expert",
    "master",
    "rarity",
    "research",
    "check",
    "cross",
    "yes",
    "no",
    "icon",
    "logo",
]

IMAGE_ROLES = [
    ("inventory", "inventory_image_path"),
    ("world", "world_image_path"),
    ("color", "color_image_path"),
]


def normalize_path(path):
    if not path:
        return None

    return str(path).replace("\\", "/")


def resolve_project_path(path):
    if not path:
        return None

    return (PROJECT_ROOT / normalize_path(path)).resolve()


def safe_filename(text):
    if not text:
        text = "unknown"

    text = str(text).lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = text.strip("_")

    return text or "unknown"


def clean_name(text):
    if text is None:
        return None

    text = str(text).strip()

    if not text:
        return None

    text = text.replace(".png", "")
    text = text.replace(".gif", "")
    text = text.replace(".jpg", "")
    text = text.replace(".jpeg", "")
    text = text.replace(".webp", "")

    text = text.replace("(placed)", "")
    text = text.replace("(Placed)", "")
    text = text.replace("_", " ")

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def split_camel_case(text):
    if not text:
        return text

    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)
    text = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", text)

    return text


def normalize_name(text):
    text = clean_name(text)

    if not text:
        return None

    text = split_camel_case(text)
    text = text.lower()
    text = text.replace("’", "'")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def get_extension(path_or_url):
    if not path_or_url:
        return ".png"

    extension = Path(str(path_or_url)).suffix.lower()

    if extension in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        return extension

    return ".png"


def get_filename_from_url(url):
    if not url:
        return None

    parsed = urlparse(url)
    path = unquote(parsed.path)
    parts = [part for part in path.split("/") if part]

    if not parts:
        return None

    filename = parts[-1]

    if "thumb" in parts and len(parts) >= 2:
        previous = parts[-2]

        if "." in previous:
            filename = previous

    return filename


def page_title_from_url(page_url):
    parsed = urlparse(page_url)
    path = parsed.path

    if "/wiki/" not in path:
        return None

    title = unquote(path.split("/wiki/", 1)[1])
    title = title.replace("_", " ")

    return clean_name(title)


def setup_dirs():
    DUPLICATES_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_PAGES_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    (PROJECT_ROOT / "images" / "inventory").mkdir(parents=True, exist_ok=True)
    (PROJECT_ROOT / "images" / "world").mkdir(parents=True, exist_ok=True)
    (PROJECT_ROOT / "images" / "color").mkdir(parents=True, exist_ok=True)


def connect_db():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"BDD introuvable : {DB_PATH}")

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


def get_columns(connection, table_name):
    cursor = connection.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [row["name"] for row in cursor.fetchall()]


def get_object(connection, local_id):
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM objects
        WHERE local_id = ?
    """, (local_id,))

    row = cursor.fetchone()

    if row is None:
        return None

    return dict(row)


def update_object_field(connection, local_id, field, value):
    allowed = {
        "page_url",
        "inventory_image_url",
        "world_image_url",
        "color_image_url",
        "inventory_image_path",
        "world_image_path",
        "color_image_path",
        "internal_item_id",
        "internal_tile_id",
        "status",
        "problem",
        "source",
    }

    if field not in allowed:
        raise ValueError(f"Champ interdit : {field}")

    cursor = connection.cursor()
    cursor.execute(
        f"UPDATE objects SET {field} = ? WHERE local_id = ?",
        (value, local_id)
    )
    connection.commit()


def delete_color_row(connection, local_id):
    if not table_exists(connection, "object_colors"):
        return

    cursor = connection.cursor()
    cursor.execute("DELETE FROM object_colors WHERE local_id = ?", (local_id,))
    connection.commit()


def load_duplicate_groups():
    if not DUPLICATE_GROUPS_CSV.exists():
        raise FileNotFoundError(
            f"CSV introuvable : {DUPLICATE_GROUPS_CSV}\n"
            "Lance d'abord : python scripts\\find_duplicates.py"
        )

    groups = {}

    with DUPLICATE_GROUPS_CSV.open("r", newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)

        for row in reader:
            group_id = int(row["group_id"])
            local_id = int(row["local_id"])

            item = {
                "group_id": group_id,
                "local_id": local_id,
                "name": row["name"],
                "category_name": row.get("category_name"),
                "inventory_image_path": normalize_path(row.get("inventory_image_path")),
                "world_image_path": normalize_path(row.get("world_image_path")),
                "color_image_path": normalize_path(row.get("color_image_path")),
                "page_url": row.get("page_url"),
                "method": row.get("method"),
                "pixel_width": row.get("pixel_width"),
                "pixel_height": row.get("pixel_height"),
                "pixel_hash": row.get("pixel_hash"),
            }

            groups.setdefault(group_id, []).append(item)

    return [
        {
            "group_id": group_id,
            "items": items,
        }
        for group_id, items in sorted(groups.items())
    ]


def refresh_group_from_db(group):
    connection = connect_db()
    refreshed_items = []

    for item in group["items"]:
        row = get_object(connection, item["local_id"])

        if row is None:
            continue

        refreshed_items.append({
            "group_id": group["group_id"],
            "local_id": row["local_id"],
            "name": row["name"],
            "category_name": row.get("category_name"),
            "inventory_image_path": normalize_path(row.get("inventory_image_path")),
            "world_image_path": normalize_path(row.get("world_image_path")),
            "color_image_path": normalize_path(row.get("color_image_path")),
            "page_url": row.get("page_url"),
            "method": item.get("method"),
            "pixel_width": item.get("pixel_width"),
            "pixel_height": item.get("pixel_height"),
            "pixel_hash": item.get("pixel_hash"),
        })

    connection.close()

    return {
        "group_id": group["group_id"],
        "items": refreshed_items,
    }


def default_session():
    return {
        "decisions": [],
    }


def load_session():
    setup_dirs()

    if SESSION_PATH.exists():
        try:
            return json.loads(SESSION_PATH.read_text(encoding="utf-8"))
        except Exception:
            return default_session()

    return default_session()


def save_session(session):
    setup_dirs()
    SESSION_PATH.write_text(json.dumps(session, indent=2, ensure_ascii=False), encoding="utf-8")


def get_decided_group_ids(session):
    return {
        decision["group_id"]
        for decision in session["decisions"]
    }


def get_remove_ids_from_session(session):
    remove_ids = set()

    for decision in session["decisions"]:
        if decision["action"] == "remove":
            for local_id in decision["remove_ids"]:
                remove_ids.add(int(local_id))

    return remove_ids


def ensure_undo_checkpoint():
    """
    Crée un checkpoint temporaire avant la première vraie modification.
    Si le checkpoint existe déjà, on ne l'écrase pas.
    """
    setup_dirs()

    if BEFORE_DB_PATH.exists() and BEFORE_IMAGES_DIR.exists():
        return

    print("Création checkpoint temporaire undo...")

    shutil.copyfile(DB_PATH, BEFORE_DB_PATH)

    images_dir = PROJECT_ROOT / "images"

    if BEFORE_IMAGES_DIR.exists():
        shutil.rmtree(BEFORE_IMAGES_DIR)

    if images_dir.exists():
        shutil.copytree(images_dir, BEFORE_IMAGES_DIR)
    else:
        BEFORE_IMAGES_DIR.mkdir(parents=True, exist_ok=True)


def restore_undo_checkpoint():
    if not BEFORE_DB_PATH.exists() or not BEFORE_IMAGES_DIR.exists():
        print("Aucun checkpoint undo disponible.")
        return

    shutil.copyfile(BEFORE_DB_PATH, DB_PATH)

    images_dir = PROJECT_ROOT / "images"

    if images_dir.exists():
        shutil.rmtree(images_dir)

    shutil.copytree(BEFORE_IMAGES_DIR, images_dir)

    print("Undo effectué : BDD + images restaurées.")


def clean_tmp():
    if TMP_DIR.exists():
        shutil.rmtree(TMP_DIR)

    print("Dossier temporaire supprimé.")


def open_image_file(path):
    return Image.open(path).convert("RGBA")


def trim_transparent(image):
    image = image.convert("RGBA")
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()

    if bbox is None:
        return image

    return image.crop(bbox)


def resize_to_box(image, max_width, max_height):
    image = image.convert("RGBA")
    image = trim_transparent(image)

    width, height = image.size

    if width == 0 or height == 0:
        return image

    scale = min(max_width / width, max_height / height)

    if scale > 1:
        scale = min(scale, 8)

    new_width = max(1, int(width * scale))
    new_height = max(1, int(height * scale))

    return image.resize((new_width, new_height), Image.Resampling.NEAREST)


def paste_center(canvas, image, box):
    x, y, w, h = box
    px = x + (w - image.width) // 2
    py = y + (h - image.height) // 2
    canvas.alpha_composite(image, (px, py))


def draw_image_box(draw, box, label):
    x, y, w, h = box
    draw.rectangle((x, y, x + w, y + h), outline=(180, 180, 180, 255), width=2)
    draw.text((x + 6, y + 6), label, fill=(230, 230, 230, 255))


def create_group_preview(group):
    group = refresh_group_from_db(group)
    items = group["items"]

    width = 1000
    row_height = 190
    header_height = 70
    height = max(header_height + row_height * len(items), 260)

    canvas = Image.new("RGBA", (width, height), (22, 22, 30, 255))
    draw = ImageDraw.Draw(canvas)

    draw.text(
        (24, 22),
        f"GROUP {group['group_id']} - duplicates pixels exacts",
        fill=(255, 255, 255, 255)
    )

    if not items:
        draw.text((24, 90), "Tous les items de ce groupe semblent absents de la BDD.", fill=(255, 140, 140, 255))

    for index, item in enumerate(items):
        top = header_height + index * row_height

        draw.rectangle((18, top + 8, width - 18, top + row_height - 8), outline=(80, 80, 100, 255), width=2)

        label = f"[{item['local_id']}] {item['name']}"
        draw.text((36, top + 22), label, fill=(255, 255, 255, 255))

        if item.get("category_name"):
            draw.text((36, top + 46), f"Category: {item['category_name']}", fill=(190, 190, 210, 255))

        inv_box = (380, top + 24, 180, 130)
        world_box = (600, top + 24, 340, 130)

        draw_image_box(draw, inv_box, "inventory")
        draw_image_box(draw, world_box, "world")

        inv_path = resolve_project_path(item.get("inventory_image_path"))
        world_path = resolve_project_path(item.get("world_image_path"))

        if inv_path and inv_path.exists():
            try:
                inv_img = resize_to_box(open_image_file(inv_path), 120, 90)
                paste_center(canvas, inv_img, inv_box)
            except Exception as error:
                draw.text((inv_box[0] + 8, inv_box[1] + 44), f"error: {error}", fill=(255, 120, 120, 255))
        else:
            draw.text((inv_box[0] + 8, inv_box[1] + 54), "missing", fill=(255, 120, 120, 255))

        if world_path and world_path.exists():
            try:
                world_img = resize_to_box(open_image_file(world_path), 280, 95)
                paste_center(canvas, world_img, world_box)
            except Exception as error:
                draw.text((world_box[0] + 8, world_box[1] + 44), f"error: {error}", fill=(255, 120, 120, 255))
        else:
            draw.text((world_box[0] + 8, world_box[1] + 54), "missing", fill=(255, 120, 120, 255))

    setup_dirs()
    canvas.convert("RGB").save(PREVIEW_PATH)

    return PREVIEW_PATH


def open_preview(path):
    try:
        os.startfile(path)
    except Exception:
        print(f"Preview créée ici : {path}")


def print_group(group):
    group = refresh_group_from_db(group)

    print()
    print("=" * 80)
    print(f"GROUP {group['group_id']}")
    print("=" * 80)

    for item in group["items"]:
        print(f"[{item['local_id']}] {item['name']}")
        print(f"  category : {item.get('category_name')}")
        print(f"  world    : {item.get('world_image_path')}")
        print(f"  inv      : {item.get('inventory_image_path')}")
        print(f"  wiki     : {item.get('page_url')}")
        print()

    print("Commandes :")
    print("  KEEP <id>                 → garde cet ID et supprime tous les autres du groupe")
    print("  KEEP <id> REMOVE <ids>    → garde cet ID et supprime seulement certains IDs")
    print("  REMOVE <ids>              → supprime seulement ces IDs")
    print("  RIEN ou SKIP              → aucun doublon / ne rien faire")
    print("  MODIF                     → modifier une image avec questions")
    print("  MODIF <id> INV <url>      → remplace inventory")
    print("  MODIF <id> WORLD <url>    → remplace world + color")
    print("  MODIF <id> COLOR <url>    → remplace color seulement")
    print("  PAGE <id> <url>           → met la page puis relit l'infobox")
    print("  UNDO                      → annule la dernière décision non appliquée")
    print("  PREVIEW                   → réouvre l'image temporaire")
    print("  APPLY                     → applique vraiment les décisions")
    print("  STOP                      → quitte sans appliquer")
    print()


def parse_ids(tokens):
    ids = []

    for token in tokens:
        if token.isdigit():
            ids.append(int(token))

    return ids


def parse_decision(command, group):
    command = command.strip()
    upper = command.upper()

    group = refresh_group_from_db(group)
    group_ids = [item["local_id"] for item in group["items"]]

    if upper in {"RIEN", "SKIP"}:
        return {
            "action": "skip",
            "group_id": group["group_id"],
            "remove_ids": [],
            "keep_id": None,
        }

    tokens = command.split()
    tokens_upper = [token.upper() for token in tokens]

    if not tokens:
        return None

    if tokens_upper[0] == "KEEP":
        if len(tokens) < 2 or not tokens[1].isdigit():
            raise ValueError("Format attendu : KEEP <id> ou KEEP <id> REMOVE <ids>")

        keep_id = int(tokens[1])

        if keep_id not in group_ids:
            raise ValueError("L'ID à garder n'est pas dans ce groupe.")

        if "REMOVE" in tokens_upper:
            remove_index = tokens_upper.index("REMOVE")
            remove_ids = parse_ids(tokens[remove_index + 1:])
        else:
            remove_ids = [local_id for local_id in group_ids if local_id != keep_id]

        for local_id in remove_ids:
            if local_id not in group_ids:
                raise ValueError(f"L'ID {local_id} n'est pas dans ce groupe.")

        if keep_id in remove_ids:
            raise ValueError("Tu ne peux pas garder et supprimer le même ID.")

        if not remove_ids:
            raise ValueError("Aucun ID à supprimer.")

        return {
            "action": "remove",
            "group_id": group["group_id"],
            "remove_ids": remove_ids,
            "keep_id": keep_id,
        }

    if tokens_upper[0] == "REMOVE":
        remove_ids = parse_ids(tokens[1:])

        if not remove_ids:
            raise ValueError("Format attendu : REMOVE <id> <id> ...")

        for local_id in remove_ids:
            if local_id not in group_ids:
                raise ValueError(f"L'ID {local_id} n'est pas dans ce groupe.")

        if len(remove_ids) >= len(group_ids):
            raise ValueError("Tu ne peux pas supprimer tout le groupe.")

        return {
            "action": "remove",
            "group_id": group["group_id"],
            "remove_ids": remove_ids,
            "keep_id": None,
        }

    return None


def undo_last_decision(session):
    if not session["decisions"]:
        print("Aucune décision à annuler.")
        return

    decision = session["decisions"].pop()
    save_session(session)

    print("Dernière décision annulée :")
    print(decision)


def is_url(text):
    return text.startswith("http://") or text.startswith("https://")


def url_hash(url):
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


def download_image_to_cache(url):
    extension = get_extension(url)
    cache_path = CACHE_IMAGES_DIR / f"{url_hash(url)}{extension}"

    if cache_path.exists():
        return cache_path

    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()

    cache_path.write_bytes(response.content)

    time.sleep(REQUEST_DELAY)

    return cache_path


def output_path_for_role(row, role, url):
    local_id = row["local_id"]
    name = row["name"]
    base = safe_filename(f"{local_id}_{name}")
    extension = get_extension(url)

    if role == "inventory":
        return PROJECT_ROOT / "images" / "inventory" / f"{base}_inventory{extension}", f"images/inventory/{base}_inventory{extension}"

    if role == "world":
        return PROJECT_ROOT / "images" / "world" / f"{base}_world{extension}", f"images/world/{base}_world{extension}"

    if role == "color":
        return PROJECT_ROOT / "images" / "color" / f"{base}_color{extension}", f"images/color/{base}_color{extension}"

    raise ValueError(f"role inconnu : {role}")


def copy_url_to_role(row, role, url):
    full_output_path, relative_path = output_path_for_role(row, role, url)

    full_output_path.parent.mkdir(parents=True, exist_ok=True)

    cached_path = download_image_to_cache(url)
    shutil.copyfile(cached_path, full_output_path)

    return normalize_path(relative_path)


def get_missing_roles(row):
    missing = []

    if not row.get("inventory_image_url") or not row.get("inventory_image_path"):
        missing.append("inventory")

    if not row.get("world_image_url") or not row.get("world_image_path"):
        missing.append("world")

    if not row.get("color_image_url") or not row.get("color_image_path"):
        missing.append("color")

    return missing


def refresh_status(connection, local_id):
    row = get_object(connection, local_id)

    if row is None:
        return "missing_object"

    missing = get_missing_roles(row)

    if not missing:
        current_status = row.get("status")

        if current_status not in {"ok", "manual_fixed"}:
            update_object_field(connection, local_id, "status", "manual_fixed")

        update_object_field(connection, local_id, "problem", None)
        return "complete"

    problem = "missing_" + "_and_".join(missing)
    update_object_field(connection, local_id, "status", "problem")
    update_object_field(connection, local_id, "problem", problem)

    return problem


def set_role_image(connection, local_id, role, url):
    role = role.lower().strip()

    if role in {"inv", "item"}:
        role = "inventory"

    if role not in {"inventory", "world", "color"}:
        raise ValueError("role doit être inventory, inv, world ou color")

    row = get_object(connection, local_id)

    if row is None:
        raise ValueError(f"Aucun bloc avec local_id={local_id}")

    ensure_undo_checkpoint()

    messages = []

    if role == "inventory":
        relative_path = copy_url_to_role(row, "inventory", url)

        update_object_field(connection, local_id, "inventory_image_url", url)
        update_object_field(connection, local_id, "inventory_image_path", relative_path)

        messages.append(f"inventory remplacée : {relative_path}")

    elif role == "world":
        world_path = copy_url_to_role(row, "world", url)
        color_path = copy_url_to_role(row, "color", url)

        update_object_field(connection, local_id, "world_image_url", url)
        update_object_field(connection, local_id, "world_image_path", world_path)

        update_object_field(connection, local_id, "color_image_url", url)
        update_object_field(connection, local_id, "color_image_path", color_path)

        delete_color_row(connection, local_id)

        messages.append(f"world remplacée : {world_path}")
        messages.append(f"color remplacée depuis world : {color_path}")
        messages.append("ancienne couleur calculée supprimée : relance build_colors.py après")

    elif role == "color":
        color_path = copy_url_to_role(row, "color", url)

        update_object_field(connection, local_id, "color_image_url", url)
        update_object_field(connection, local_id, "color_image_path", color_path)

        delete_color_row(connection, local_id)

        messages.append(f"color remplacée : {color_path}")
        messages.append("ancienne couleur calculée supprimée : relance build_colors.py après")

    status = refresh_status(connection, local_id)
    messages.append(f"status : {status}")

    return messages


def get_img_src(img):
    if img is None:
        return None

    return img.get("src") or img.get("data-src")


def full_url(src):
    if not src:
        return None

    return urljoin(BASE_URL, src)


def image_text_from_img(img, url=None):
    alt = ""
    src = ""

    if img is not None:
        alt = img.get("alt", "") or ""
        src = get_img_src(img) or ""

    filename = get_filename_from_url(url or src) or ""

    return f"{alt} {src} {filename}".lower()


def image_is_bad(img, url=None):
    text = image_text_from_img(img, url)

    for bad in BAD_IMAGE_PARTS:
        if bad in text:
            return True

    return False


def image_is_placed(img, url=None):
    text = image_text_from_img(img, url)
    return "placed" in text


def image_matches_block_name(img, possible_names, url=None):
    text = image_text_from_img(img, url)
    normalized_text = normalize_name(text)

    if not normalized_text:
        return False

    compact_text = normalized_text.replace(" ", "")

    for name in possible_names:
        normalized_block = normalize_name(name)

        if not normalized_block:
            continue

        compact_block = normalized_block.replace(" ", "")

        if compact_block and compact_block in compact_text:
            return True

    return False


def extract_infobox(soup):
    selectors = [
        "aside.portable-infobox",
        ".portable-infobox",
        "table.infobox",
        ".infobox",
    ]

    for selector in selectors:
        infobox = soup.select_one(selector)

        if infobox is not None:
            return infobox

    return None


def clean_infobox_for_strict_parse(infobox):
    for tag_name in ["script", "style", "noscript"]:
        for tag in infobox.find_all(tag_name):
            tag.decompose()

    selectors = [
        ".mw-editsection",
        ".pi-header",
        ".pi-navigation",
        ".infobox-notice",
        ".game-icon",
        ".eicons",
        ".eil",
        ".i.s",
        ".plainlinks",
    ]

    for selector in selectors:
        for tag in infobox.select(selector):
            tag.decompose()

    return infobox


def extract_internal_ids_from_infobox(infobox):
    text = infobox.get_text(" ", strip=True)

    internal_item_id = None
    internal_tile_id = None

    item_match = re.search(r"Internal\s+Item\s+ID\s*:\s*(\d+)", text, flags=re.IGNORECASE)

    if item_match:
        internal_item_id = int(item_match.group(1))

    tile_match = re.search(r"Internal\s+Tile\s+ID\s*:\s*(\d+)", text, flags=re.IGNORECASE)

    if tile_match:
        internal_tile_id = int(tile_match.group(1))

    return internal_item_id, internal_tile_id


def extract_images_from_infobox(infobox, possible_names):
    inventory_candidates = []
    world_candidates = []

    imgs = infobox.find_all("img")

    for img in imgs:
        src = get_img_src(img)

        if not src:
            continue

        url = full_url(src)

        if image_is_bad(img, url):
            continue

        if image_is_placed(img, url):
            score = 100

            if image_matches_block_name(img, possible_names, url):
                score += 50

            world_candidates.append((score, url))
            continue

        if image_matches_block_name(img, possible_names, url):
            score = 100

            try:
                width = int(img.get("width", "0"))
                height = int(img.get("height", "0"))
            except Exception:
                width = 0
                height = 0

            if width and height and width <= 96 and height <= 96:
                score += 20

            inventory_candidates.append((score, url))

    inventory_url = None
    world_url = None

    if inventory_candidates:
        inventory_candidates.sort(key=lambda item: item[0], reverse=True)
        inventory_url = inventory_candidates[0][1]

    if world_candidates:
        world_candidates.sort(key=lambda item: item[0], reverse=True)
        world_url = world_candidates[0][1]

    return inventory_url, world_url


def render_url_from_page_url(page_url):
    parsed = urlparse(page_url)
    path = parsed.path

    if "/wiki/" not in path:
        return page_url

    page_title = unquote(path.split("/wiki/", 1)[1])
    return f"{BASE_URL}/wiki/{quote(page_title, safe='/')}?action=render"


def cache_name_for_page(local_id, page_url):
    page_title = unquote(urlparse(page_url).path.split("/wiki/")[-1])
    return f"merge_page_{local_id}_{safe_filename(page_title)}.html"


def download_html(url, cache_name):
    cache_path = CACHE_PAGES_DIR / cache_name

    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8"), True

    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()

    html = response.text
    cache_path.write_text(html, encoding="utf-8")

    time.sleep(REQUEST_DELAY)

    return html, False


def parse_page_and_apply(connection, local_id, page_url):
    row = get_object(connection, local_id)

    if row is None:
        raise ValueError(f"Aucun bloc avec local_id={local_id}")

    ensure_undo_checkpoint()

    render_url = render_url_from_page_url(page_url)
    cache_name = cache_name_for_page(local_id, page_url)

    html, from_cache = download_html(render_url, cache_name)

    soup = BeautifulSoup(html, "html.parser")
    infobox = extract_infobox(soup)

    update_object_field(connection, local_id, "page_url", page_url)

    messages = [f"page mise à jour : {page_url}"]

    if infobox is None:
        update_object_field(connection, local_id, "status", "problem")
        update_object_field(connection, local_id, "problem", "infobox_not_found")
        messages.append("infobox introuvable")
        return messages

    infobox = clean_infobox_for_strict_parse(infobox)

    page_title = page_title_from_url(page_url)
    possible_names = [row["name"]]

    if page_title:
        possible_names.append(page_title)

    inventory_url, world_url = extract_images_from_infobox(infobox, possible_names)
    internal_item_id, internal_tile_id = extract_internal_ids_from_infobox(infobox)

    if internal_item_id is not None:
        update_object_field(connection, local_id, "internal_item_id", internal_item_id)
        messages.append(f"internal_item_id trouvé : {internal_item_id}")

    if internal_tile_id is not None:
        update_object_field(connection, local_id, "internal_tile_id", internal_tile_id)
        messages.append(f"internal_tile_id trouvé : {internal_tile_id}")

    if inventory_url:
        messages.extend(set_role_image(connection, local_id, "inventory", inventory_url))
    else:
        messages.append("inventory non trouvée dans cette page")

    if world_url:
        messages.extend(set_role_image(connection, local_id, "world", world_url))
    else:
        messages.append("world non trouvée dans cette page")

    status = refresh_status(connection, local_id)
    messages.append(f"status final : {status}")

    if from_cache:
        messages.append("source HTML : cache")
    else:
        messages.append("source HTML : téléchargement")

    return messages


def ask_manual_modif():
    local_id_text = input("local_id à modifier : ").strip()

    if not local_id_text.isdigit():
        print("ID invalide.")
        return

    local_id = int(local_id_text)

    role = input("role à modifier (inv/inventory/world/color/page) : ").strip().lower()

    if role == "inv":
        role = "inventory"

    if role == "page":
        url = input("URL de la page wiki : ").strip()

        if not is_url(url):
            print("URL invalide.")
            return

        connection = connect_db()

        try:
            messages = parse_page_and_apply(connection, local_id, url)
        finally:
            connection.close()

        for message in messages:
            print("  " + message)

        return

    if role not in {"inventory", "world", "color"}:
        print("Role invalide.")
        return

    url = input(f"URL image pour {role} : ").strip()

    if not is_url(url):
        print("URL invalide.")
        return

    connection = connect_db()

    try:
        messages = set_role_image(connection, local_id, role, url)
    finally:
        connection.close()

    for message in messages:
        print("  " + message)


def handle_modif_command(command):
    tokens = command.strip().split()

    if len(tokens) == 1:
        ask_manual_modif()
        return True

    if len(tokens) < 4:
        print("Format attendu : MODIF <id> INV/WORLD/COLOR <url>")
        return True

    if not tokens[1].isdigit():
        print("ID invalide.")
        return True

    local_id = int(tokens[1])
    role = tokens[2].lower()

    if role == "inv":
        role = "inventory"

    url = tokens[3]

    if role not in {"inventory", "world", "color"}:
        print("Role invalide. Utilise INV, WORLD ou COLOR.")
        return True

    if not is_url(url):
        print("URL invalide.")
        return True

    connection = connect_db()

    try:
        messages = set_role_image(connection, local_id, role, url)
    finally:
        connection.close()

    for message in messages:
        print("  " + message)

    return True


def handle_page_command(command):
    tokens = command.strip().split(maxsplit=2)

    if len(tokens) < 3:
        print("Format attendu : PAGE <id> <url>")
        return True

    if not tokens[1].isdigit():
        print("ID invalide.")
        return True

    local_id = int(tokens[1])
    page_url = tokens[2].strip()

    if not is_url(page_url):
        print("URL page invalide.")
        return True

    connection = connect_db()

    try:
        messages = parse_page_and_apply(connection, local_id, page_url)
    finally:
        connection.close()

    for message in messages:
        print("  " + message)

    return True


def fetch_table_rows(connection, table_name):
    cursor = connection.cursor()
    cursor.execute(f"SELECT * FROM {table_name} ORDER BY local_id")
    return [dict(row) for row in cursor.fetchall()]


def clear_table(connection, table_name):
    cursor = connection.cursor()
    cursor.execute(f"DELETE FROM {table_name}")
    connection.commit()


def insert_row(connection, table_name, columns, row):
    cursor = connection.cursor()

    placeholders = ", ".join(["?"] * len(columns))
    columns_sql = ", ".join(columns)

    values = [row.get(column) for column in columns]

    cursor.execute(
        f"INSERT INTO {table_name} ({columns_sql}) VALUES ({placeholders})",
        values
    )


def copy_image_to_new_folder(old_path, new_relative_path, new_images_root):
    if not old_path:
        return None

    old_full_path = resolve_project_path(old_path)

    if old_full_path is None or not old_full_path.exists():
        return None

    new_full_path = new_images_root / normalize_path(new_relative_path)
    new_full_path.parent.mkdir(parents=True, exist_ok=True)

    shutil.copyfile(old_full_path, new_full_path)

    return normalize_path(new_relative_path)


def build_new_image_paths(row, new_id, new_images_root):
    name = row["name"]
    base = safe_filename(f"{new_id}_{name}")

    new_paths = {}

    for role, column in IMAGE_ROLES:
        old_path = row.get(column)

        if not old_path:
            new_paths[column] = None
            continue

        extension = get_extension(old_path)
        new_relative_path = f"images/{role}/{base}_{role}{extension}"

        new_paths[column] = copy_image_to_new_folder(
            old_path=old_path,
            new_relative_path=new_relative_path,
            new_images_root=new_images_root,
        )

    return new_paths


def apply_decisions(session):
    remove_ids = get_remove_ids_from_session(session)

    if not remove_ids:
        print("Aucune suppression à appliquer.")
        return

    print()
    print("APPLY")
    print("=====")
    print(f"IDs supprimés : {sorted(remove_ids)}")
    print()

    ensure_undo_checkpoint()

    connection = connect_db()

    object_columns = get_columns(connection, "objects")
    object_rows = fetch_table_rows(connection, "objects")

    kept_rows = [
        row for row in object_rows
        if int(row["local_id"]) not in remove_ids
    ]

    old_to_new = {
        int(row["local_id"]): new_id
        for new_id, row in enumerate(kept_rows)
    }

    temp_new_images_root = TMP_DIR / "new_images"

    if temp_new_images_root.exists():
        shutil.rmtree(temp_new_images_root)

    clear_table(connection, "objects")

    for new_id, row in enumerate(kept_rows):
        row["local_id"] = new_id

        image_paths = build_new_image_paths(row, new_id, temp_new_images_root)

        for column, value in image_paths.items():
            row[column] = value

        insert_row(connection, "objects", object_columns, row)

    if table_exists(connection, "object_colors"):
        color_columns = get_columns(connection, "object_colors")
        color_rows = fetch_table_rows(connection, "object_colors")

        kept_color_rows = [
            row for row in color_rows
            if int(row["local_id"]) in old_to_new
        ]

        clear_table(connection, "object_colors")

        for row in kept_color_rows:
            old_id = int(row["local_id"])
            row["local_id"] = old_to_new[old_id]
            insert_row(connection, "object_colors", color_columns, row)

    connection.commit()
    connection.close()

    images_dir = PROJECT_ROOT / "images"

    if images_dir.exists():
        shutil.rmtree(images_dir)

    shutil.copytree(temp_new_images_root / "images", images_dir)

    write_merge_report(session, old_to_new, remove_ids)

    print("Merge appliqué.")
    print(f"Rapport : {MERGE_REPORT_PATH}")
    print()
    print("Prochaine étape conseillée :")
    print("python scripts\\build_colors.py")
    print("python scripts\\find_duplicates.py")


def write_merge_report(session, old_to_new, remove_ids):
    lines = []

    lines.append("MERGE DUPLICATES REPORT")
    lines.append("=======================")
    lines.append("")
    lines.append(f"IDs supprimés : {sorted(remove_ids)}")
    lines.append("")
    lines.append("Décisions :")
    lines.append("----------")

    for decision in session["decisions"]:
        lines.append(json.dumps(decision, ensure_ascii=False))

    lines.append("")
    lines.append("Mapping old_id -> new_id :")
    lines.append("------------------------")

    for old_id, new_id in sorted(old_to_new.items()):
        lines.append(f"{old_id} -> {new_id}")

    MERGE_REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def interactive_loop():
    setup_dirs()

    groups = load_duplicate_groups()
    session = load_session()

    print("MERGE DUPLICATES")
    print("================")
    print()
    print(f"Groupes détectés : {len(groups)}")
    print(f"Décisions déjà en session : {len(session['decisions'])}")
    print()
    print("Tu peux maintenant aussi corriger une mauvaise image avec MODIF ou PAGE.")
    print()

    while True:
        decided_group_ids = get_decided_group_ids(session)

        next_group = None

        for group in groups:
            if group["group_id"] not in decided_group_ids:
                next_group = group
                break

        if next_group is None:
            print("Tous les groupes ont une décision.")
            print("Tape APPLY pour appliquer, MODIF pour corriger une image, UNDO pour revenir, ou STOP.")

            command = input("> ").strip()
            upper = command.upper()

            if upper == "APPLY":
                apply_decisions(session)
                save_session(session)
                return

            if upper == "UNDO":
                undo_last_decision(session)
                continue

            if upper == "STOP":
                save_session(session)
                print("Arrêt sans appliquer. Session sauvegardée.")
                return

            if upper.startswith("MODIF"):
                handle_modif_command(command)
                continue

            if upper.startswith("PAGE "):
                handle_page_command(command)
                continue

            print("Commande inconnue.")
            continue

        preview_path = create_group_preview(next_group)
        open_preview(preview_path)

        while True:
            print_group(next_group)
            command = input("> ").strip()
            upper = command.upper()

            if upper == "STOP":
                save_session(session)
                print("Arrêt sans appliquer. Session sauvegardée.")
                return

            if upper == "APPLY":
                apply_decisions(session)
                save_session(session)
                return

            if upper == "UNDO":
                undo_last_decision(session)
                break

            if upper == "PREVIEW":
                preview_path = create_group_preview(next_group)
                open_preview(preview_path)
                continue

            if upper.startswith("MODIF"):
                handle_modif_command(command)
                preview_path = create_group_preview(next_group)
                open_preview(preview_path)
                continue

            if upper.startswith("PAGE "):
                handle_page_command(command)
                preview_path = create_group_preview(next_group)
                open_preview(preview_path)
                continue

            try:
                decision = parse_decision(command, next_group)
            except Exception as error:
                print(f"Erreur : {error}")
                continue

            if decision is None:
                print("Commande inconnue.")
                continue

            session["decisions"].append(decision)
            save_session(session)

            if decision["action"] == "skip":
                print("Groupe ignoré.")
            else:
                print(f"Décision enregistrée : remove {decision['remove_ids']}")

            break


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--undo", action="store_true", help="Restaure l'état avant les modifications/apply.")
    parser.add_argument("--clean", action="store_true", help="Supprime les fichiers temporaires de merge.")
    args = parser.parse_args()

    if args.undo:
        restore_undo_checkpoint()
        return

    if args.clean:
        clean_tmp()
        return

    interactive_loop()


if __name__ == "__main__":
    main()