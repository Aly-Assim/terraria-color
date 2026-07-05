from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote, quote
import hashlib
import re
import shutil
import sqlite3
import time

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://terraria.wiki.gg"

DB_PATH = Path("data/terraria_blocks.db")

CACHE_PAGES_DIR = Path("cache/pages")
CACHE_IMAGES_DIR = Path("cache/images")

INVENTORY_IMAGES_DIR = Path("images/inventory")
WORLD_IMAGES_DIR = Path("images/world")
COLOR_IMAGES_DIR = Path("images/color")

REPORT_PATH = Path("data/manual_fix_report.txt")

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


def setup_dirs():
    CACHE_PAGES_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    INVENTORY_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    WORLD_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    COLOR_IMAGES_DIR.mkdir(parents=True, exist_ok=True)


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


def safe_filename(text):
    if not text:
        text = "unknown"

    text = str(text).lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = text.strip("_")

    return text or "unknown"


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


def get_extension_from_url(url):
    filename = get_filename_from_url(url)

    if not filename or "." not in filename:
        return ".png"

    extension = Path(filename).suffix.lower()

    if extension in {".png", ".gif", ".jpg", ".jpeg", ".webp"}:
        return extension

    return ".png"


def url_hash(url):
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


def download_image_to_cache(url):
    extension = get_extension_from_url(url)
    cache_path = CACHE_IMAGES_DIR / f"{url_hash(url)}{extension}"

    if cache_path.exists():
        return cache_path

    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()

    cache_path.write_bytes(response.content)

    time.sleep(REQUEST_DELAY)

    return cache_path


def output_path_for(row, role):
    base = safe_filename(f"{row['local_id']}_{row['name']}")

    if role == "inventory":
        folder = INVENTORY_IMAGES_DIR
        suffix = "inventory"
    elif role == "world":
        folder = WORLD_IMAGES_DIR
        suffix = "world"
    elif role == "color":
        folder = COLOR_IMAGES_DIR
        suffix = "color"
    else:
        raise ValueError(f"role inconnu : {role}")

    return folder, base + "_" + suffix


def copy_url_to_role(row, role, url):
    folder, base_name = output_path_for(row, role)
    extension = get_extension_from_url(url)

    output_path = folder / f"{base_name}{extension}"

    cached_path = download_image_to_cache(url)
    shutil.copyfile(cached_path, output_path)

    return str(output_path)


def get_img_src(img):
    if img is None:
        return None

    return img.get("src") or img.get("data-src")


def full_url(src):
    if not src:
        return None

    return urljoin(BASE_URL, src)


def page_url_from_name(name):
    page_title = clean_name(name)

    if not page_title:
        return None

    page_title = page_title.replace(" ", "_")
    return f"{BASE_URL}/wiki/{quote(page_title, safe='/')}"


def render_url_from_page_url(page_url):
    parsed = urlparse(page_url)
    path = parsed.path

    if "/wiki/" not in path:
        return page_url

    page_title = unquote(path.split("/wiki/", 1)[1])
    return f"{BASE_URL}/wiki/{quote(page_title, safe='/')}?action=render"


def cache_name_for_page(row, page_url):
    page_title = unquote(urlparse(page_url).path.split("/wiki/")[-1])
    return f"manual_page_{row['local_id']}_{safe_filename(page_title)}.html"


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


def image_matches_block_name(img, block_name, url=None):
    text = image_text_from_img(img, url)

    normalized_text = normalize_name(text)
    normalized_block = normalize_name(block_name)

    if not normalized_text or not normalized_block:
        return False

    compact_text = normalized_text.replace(" ", "")
    compact_block = normalized_block.replace(" ", "")

    return compact_block in compact_text


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


def extract_images_from_infobox(infobox, block_name):
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

            if image_matches_block_name(img, block_name, url):
                score += 50

            world_candidates.append((score, url))
            continue

        if image_matches_block_name(img, block_name, url):
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


def connect_db():
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"BDD introuvable : {DB_PATH}. Lance d'abord python scripts/build_poc.py"
        )

    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    return connection


def row_to_dict(row):
    if row is None:
        return None

    return dict(row)


def get_object(connection, local_id):
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM objects
        WHERE local_id = ?
    """, (local_id,))

    return row_to_dict(cursor.fetchone())


def get_pending_objects(connection):
    cursor = connection.cursor()

    cursor.execute("""
        SELECT *
        FROM objects
        WHERE
            status = 'problem'
            OR inventory_image_url IS NULL
            OR world_image_url IS NULL
            OR color_image_url IS NULL
            OR inventory_image_path IS NULL
            OR world_image_path IS NULL
            OR color_image_path IS NULL
        ORDER BY local_id
    """)

    return [row_to_dict(row) for row in cursor.fetchall()]


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


def set_role_image(connection, row, role, url):
    role = role.lower().strip()

    if role in {"inv", "item"}:
        role = "inventory"

    if role not in {"inventory", "world", "color"}:
        raise ValueError("image_role doit être inventory, world ou color")

    local_id = row["local_id"]

    if role == "inventory":
        path = copy_url_to_role(row, "inventory", url)

        update_object_field(connection, local_id, "inventory_image_url", url)
        update_object_field(connection, local_id, "inventory_image_path", path)

        return [f"inventory ajoutée : {path}"]

    if role == "world":
        world_path = copy_url_to_role(row, "world", url)
        color_path = copy_url_to_role(row, "color", url)

        update_object_field(connection, local_id, "world_image_url", url)
        update_object_field(connection, local_id, "world_image_path", world_path)

        update_object_field(connection, local_id, "color_image_url", url)
        update_object_field(connection, local_id, "color_image_path", color_path)

        return [
            f"world ajoutée : {world_path}",
            f"color ajoutée depuis world : {color_path}",
        ]

    if role == "color":
        path = copy_url_to_role(row, "color", url)

        update_object_field(connection, local_id, "color_image_url", url)
        update_object_field(connection, local_id, "color_image_path", path)

        return [f"color ajoutée : {path}"]


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
    missing = get_missing_roles(row)

    if not missing:
        if row.get("status") == "problem":
            update_object_field(connection, local_id, "status", "manual_fixed")
        elif row.get("status") not in {"ok", "manual_fixed"}:
            update_object_field(connection, local_id, "status", "manual_fixed")

        update_object_field(connection, local_id, "problem", None)
        return "complete"

    problem = "missing_" + "_and_".join(missing)
    update_object_field(connection, local_id, "status", "problem")
    update_object_field(connection, local_id, "problem", problem)

    return problem


def parse_page_and_apply(connection, row, page_url):
    local_id = row["local_id"]
    render_url = render_url_from_page_url(page_url)
    cache_name = cache_name_for_page(row, page_url)

    html, from_cache = download_html(render_url, cache_name)

    soup = BeautifulSoup(html, "html.parser")
    infobox = extract_infobox(soup)

    if infobox is None:
        update_object_field(connection, local_id, "page_url", page_url)
        update_object_field(connection, local_id, "status", "problem")
        update_object_field(connection, local_id, "problem", "infobox_not_found")
        return ["page mise à jour, mais infobox introuvable"]

    infobox = clean_infobox_for_strict_parse(infobox)

    inventory_url, world_url = extract_images_from_infobox(infobox, row["name"])
    internal_item_id, internal_tile_id = extract_internal_ids_from_infobox(infobox)

    update_object_field(connection, local_id, "page_url", page_url)

    messages = [f"page mise à jour : {page_url}"]

    if internal_item_id is not None:
        update_object_field(connection, local_id, "internal_item_id", internal_item_id)
        messages.append(f"internal_item_id trouvé : {internal_item_id}")

    if internal_tile_id is not None:
        update_object_field(connection, local_id, "internal_tile_id", internal_tile_id)
        messages.append(f"internal_tile_id trouvé : {internal_tile_id}")

    fresh_row = get_object(connection, local_id)

    if inventory_url:
        messages.extend(set_role_image(connection, fresh_row, "inventory", inventory_url))
        fresh_row = get_object(connection, local_id)
    else:
        messages.append("inventory non trouvée dans cette page")

    if world_url:
        messages.extend(set_role_image(connection, fresh_row, "world", world_url))
    else:
        messages.append("world non trouvée dans cette page")

    status = refresh_status(connection, local_id)
    messages.append(f"status : {status}")

    if from_cache:
        messages.append("source HTML : cache")
    else:
        messages.append("source HTML : téléchargement")

    return messages


def show_object(row):
    print()
    print("=" * 70)
    print(f"[{row['local_id']}] {row['name']}")
    print("=" * 70)
    print(f"status      : {row.get('status')}")
    print(f"problem     : {row.get('problem')}")
    print(f"category    : {row.get('category_name')}")
    print(f"page_url    : {row.get('page_url')}")
    print()
    print(f"inventory_url  : {row.get('inventory_image_url')}")
    print(f"inventory_path : {row.get('inventory_image_path')}")
    print()
    print(f"world_url      : {row.get('world_image_url')}")
    print(f"world_path     : {row.get('world_image_path')}")
    print()
    print(f"color_url      : {row.get('color_image_url')}")
    print(f"color_path     : {row.get('color_image_path')}")
    print()
    print(f"missing     : {', '.join(get_missing_roles(row)) or 'none'}")
    print()


def write_report(actions):
    lines = []

    lines.append("MANUAL FIX REPORT")
    lines.append("=================")
    lines.append("")

    if not actions:
        lines.append("Aucune action effectuée.")
    else:
        for action in actions:
            lines.append(action)

    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def is_url(text):
    return text.startswith("http://") or text.startswith("https://")


def ask(prompt):
    return input(prompt).strip()


def ask_manual_modification(connection, actions):
    print()
    print("MODE MODIF")
    print("----------")

    local_id_text = ask("local_id du bloc à modifier, ou STOP : ")

    if local_id_text.upper() == "STOP":
        return "STOP"

    if not local_id_text.isdigit():
        print("ID invalide.")
        return None

    local_id = int(local_id_text)
    row = get_object(connection, local_id)

    if row is None:
        print(f"Aucun bloc avec local_id={local_id}")
        return None

    show_object(row)

    role = ask("Rôle à modifier (inv/inventory/world/color), ou STOP : ").lower()

    if role.upper() == "STOP":
        return "STOP"

    if role == "inv":
        role = "inventory"

    if role not in {"inventory", "world", "color"}:
        print("Rôle invalide.")
        return None

    url = ask(f"URL image pour {role} : ")

    if url.upper() == "STOP":
        return "STOP"

    if not is_url(url):
        print("URL invalide.")
        return None

    messages = set_role_image(connection, row, role, url)
    status = refresh_status(connection, local_id)

    print()
    for message in messages:
        print("  " + message)

    print(f"  status : {status}")

    actions.append(f"[{local_id}] {row['name']} | MODIF {role} | {url} | status={status}")
    write_report(actions)

    return None


def handle_command(connection, row, command, current_role, actions):
    cmd = command.strip()

    if not cmd:
        return None

    upper = cmd.upper()

    if upper == "STOP":
        return "STOP"

    if upper == "SKIP":
        actions.append(f"[{row['local_id']}] {row['name']} | SKIP")
        write_report(actions)
        return "NEXT"

    if upper == "SHOW":
        fresh = get_object(connection, row["local_id"])
        show_object(fresh)
        return None

    if upper == "MODIF":
        return ask_manual_modification(connection, actions)

    if upper.startswith("ID "):
        parts = cmd.split(maxsplit=1)

        if len(parts) == 2 and parts[1].isdigit():
            other = get_object(connection, int(parts[1]))

            if other:
                show_object(other)
            else:
                print("ID introuvable.")

        return None

    if upper.startswith("PAGE "):
        page_url = cmd.split(maxsplit=1)[1].strip()

        if not is_url(page_url):
            print("URL page invalide.")
            return None

        messages = parse_page_and_apply(connection, row, page_url)

        print()
        for message in messages:
            print("  " + message)

        actions.append(f"[{row['local_id']}] {row['name']} | PAGE {page_url}")
        write_report(actions)

        return "REFRESH"

    if upper.startswith("INV "):
        url = cmd.split(maxsplit=1)[1].strip()

        if not is_url(url):
            print("URL image invalide.")
            return None

        messages = set_role_image(connection, row, "inventory", url)
        status = refresh_status(connection, row["local_id"])

        print()
        for message in messages:
            print("  " + message)

        print(f"  status : {status}")

        actions.append(f"[{row['local_id']}] {row['name']} | INV {url} | status={status}")
        write_report(actions)

        return "REFRESH"

    if upper.startswith("WORLD "):
        url = cmd.split(maxsplit=1)[1].strip()

        if not is_url(url):
            print("URL image invalide.")
            return None

        messages = set_role_image(connection, row, "world", url)
        status = refresh_status(connection, row["local_id"])

        print()
        for message in messages:
            print("  " + message)

        print(f"  status : {status}")

        actions.append(f"[{row['local_id']}] {row['name']} | WORLD {url} | status={status}")
        write_report(actions)

        return "REFRESH"

    if upper.startswith("COLOR "):
        url = cmd.split(maxsplit=1)[1].strip()

        if not is_url(url):
            print("URL image invalide.")
            return None

        messages = set_role_image(connection, row, "color", url)
        status = refresh_status(connection, row["local_id"])

        print()
        for message in messages:
            print("  " + message)

        print(f"  status : {status}")

        actions.append(f"[{row['local_id']}] {row['name']} | COLOR {url} | status={status}")
        write_report(actions)

        return "REFRESH"

    if is_url(cmd):
        if current_role == "page":
            messages = parse_page_and_apply(connection, row, cmd)

            print()
            for message in messages:
                print("  " + message)

            actions.append(f"[{row['local_id']}] {row['name']} | PAGE {cmd}")
            write_report(actions)

            return "REFRESH"

        messages = set_role_image(connection, row, current_role, cmd)
        status = refresh_status(connection, row["local_id"])

        print()
        for message in messages:
            print("  " + message)

        print(f"  status : {status}")

        actions.append(f"[{row['local_id']}] {row['name']} | {current_role.upper()} {cmd} | status={status}")
        write_report(actions)

        return "REFRESH"

    print("Commande inconnue.")
    return None


def choose_current_role(row):
    problem = row.get("problem") or ""
    missing = get_missing_roles(row)

    if "exception" in problem or "infobox_not_found" in problem:
        return "page"

    if "inventory" in missing:
        return "inventory"

    if "world" in missing:
        return "world"

    if "color" in missing:
        return "color"

    return "page"


def prompt_for_row(connection, row, actions):
    while True:
        fresh = get_object(connection, row["local_id"])
        show_object(fresh)

        missing = get_missing_roles(fresh)

        if not missing and fresh.get("status") != "problem":
            print("Ce bloc est complet.")
            return "NEXT"

        current_role = choose_current_role(fresh)

        print("Commandes : STOP | SKIP | SHOW | MODIF | PAGE <url> | INV <url> | WORLD <url> | COLOR <url>")
        print("Astuce : tu peux aussi coller directement l’URL demandée.")

        if current_role == "page":
            prompt = "Colle l'URL correcte de la page wiki : "
        elif current_role == "inventory":
            prompt = "Colle l'URL de l'image INVENTORY : "
        elif current_role == "world":
            prompt = "Colle l'URL de l'image WORLD/PLACED : "
        elif current_role == "color":
            prompt = "Colle l'URL de l'image COLOR : "
        else:
            prompt = "> "

        command = ask(prompt)
        result = handle_command(connection, fresh, command, current_role, actions)

        if result == "STOP":
            return "STOP"

        if result == "NEXT":
            return "NEXT"

        if result == "REFRESH":
            continue


def main():
    setup_dirs()

    connection = connect_db()
    actions = []

    print("MANUAL FIX TERRARIA")
    print("===================")
    print()
    print("Le programme tourne jusqu'à STOP.")
    print("Tu peux corriger les problèmes dans l'ordre, ou taper MODIF pour modifier n'importe quel bloc par local_id.")
    print()

    while True:
        pending = get_pending_objects(connection)

        if pending:
            row = pending[0]
            result = prompt_for_row(connection, row, actions)

            if result == "STOP":
                break

            continue

        print()
        print("Aucun bloc incomplet détecté.")
        print("Tu peux quand même taper MODIF pour remplacer une image, ID <id> pour voir un bloc, ou STOP.")
        command = ask("> ")

        if command.upper() == "STOP":
            break

        if command.upper() == "MODIF":
            result = ask_manual_modification(connection, actions)

            if result == "STOP":
                break

            continue

        if command.upper().startswith("ID "):
            fake_row = {"local_id": -1, "name": "menu"}
            handle_command(connection, fake_row, command, "page", actions)
            continue

        print("Commande inconnue. Utilise MODIF, ID <id> ou STOP.")

    write_report(actions)
    connection.close()

    print()
    print("Arrêt propre.")
    print(f"Rapport : {REPORT_PATH}")


if __name__ == "__main__":
    main()