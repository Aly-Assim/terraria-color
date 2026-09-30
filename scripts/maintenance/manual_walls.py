"""Explicit wall-only edits; called by manual_fix.py --type wall."""
import argparse
from contextlib import closing
from pathlib import Path
import sqlite3

from scripts.paths import PROJECT_ROOT, DB_PATH, connect_readonly
from scripts.maintenance.wall_source import WikiClient, WallResolver, image_bytes, official_url, safe_filename
from scripts.maintenance.wall_storage import (
    ROLES, backup_database, ensure_wall_schema, replace_bytes, snapshot, store_wall_ids, verify_originals, wall_path,
)


def require_wall(connection, local_id: int) -> dict:
    row = connection.execute("SELECT * FROM objects WHERE local_id=?", (local_id,)).fetchone()
    if row is None or row["object_type"] != "wall" or row["is_wall"] != 1:
        raise ValueError(f"{local_id} is not a wall; no changes allowed")
    return dict(row)


def fix_wall(local_id: int, changes: dict, image_urls: dict, refresh: bool = False,
             db: Path = DB_PATH, root: Path = PROJECT_ROOT, client=None):
    with closing(connect_readonly(db)) as reader:
        row = require_wall(reader, local_id)
        before = snapshot(reader, root)
    if set(changes) - {"page_url", "status", "problem"}:
        raise ValueError("Only page_url, status and problem may be edited directly")
    if "page_url" in changes:
        changes["page_url"] = official_url(changes["page_url"])
    client = client or WikiClient()
    metadata = None
    if refresh:
        entry = dict(source_name=row["name"], category_name=row["category_name"],
                     excel_image_url=row.get("world_image_url") or "",
                     page_url=changes.get("page_url") or row.get("page_url"))
        metadata = WallResolver(client).resolve(entry)
        changes = {**{k: metadata[k] for k in ("internal_item_id", "internal_wall_id", "page_url")}, **changes}
    downloads = {}
    for role, url in image_urls.items():
        if role not in ROLES:
            raise ValueError(f"Invalid image role: {role}")
        url = official_url(url)
        data = client.get(url)
        extension = image_bytes(data)
        relative = f"images/walls/{role}/{local_id}_{safe_filename(row['name'])}_{role}{extension}"
        downloads[role] = (relative, data)
        changes[role + "_image_url"] = url
        changes[role + "_image_path"] = relative
    if not changes and metadata is None:
        print("No changes requested")
        return
    backup = backup_database(db, root, "wall_fix")
    saved = {}
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        connection.execute("BEGIN IMMEDIATE")
        if require_wall(connection, local_id) != row:
            raise RuntimeError("Wall changed concurrently; retry")
        ensure_wall_schema(connection)
        for role, (relative, data) in downloads.items():
            target = wall_path(relative, role, root, local_id)
            old = row.get(role + "_image_path")
            try:
                old_path = wall_path(old, role, root, local_id) if old else None
            except ValueError:
                # Repair a bad database reference without touching the misplaced
                # file (in particular, never follow it into a block directory).
                old_path = None
            for path in {p for p in (target, old_path) if p is not None}:
                normalized = path.relative_to(root).as_posix()
                # Refuse to overwrite/delete media referenced by another object.
                shared = connection.execute("SELECT local_id FROM objects WHERE local_id != ? AND ("
                    "replace(inventory_image_path, char(92), '/')=? OR replace(world_image_path, char(92), '/')=? OR "
                    "replace(color_image_path, char(92), '/')=?)", (local_id, normalized, normalized, normalized)).fetchone()
                if shared:
                    raise ValueError(f"Image is shared with object {shared[0]}: {path}")
                if path == target and target.exists() and target != old_path:
                    raise FileExistsError(f"Unreferenced target already exists: {target}")
                saved[path] = path.read_bytes() if path.exists() else None
                if saved[path] is not None:
                    copy = backup / "images" / role / path.name
                    copy.parent.mkdir(parents=True, exist_ok=True)
                    copy.write_bytes(saved[path])
            target.parent.mkdir(parents=True, exist_ok=True)
            replace_bytes(target, data)
            if old_path and old_path != target and old_path.exists():
                old_path.unlink()
        connection.execute("UPDATE objects SET " + ",".join(f"{k}=?" for k in changes) +
                           " WHERE local_id=? AND object_type='wall'", (*changes.values(), local_id))
        if metadata is not None:
            store_wall_ids(connection, local_id, metadata["wall_ids"])
        # Existing derived values become stale when the analysis image changes.
        if downloads:
            for table in ("object_colors", "object_paint_colors"):
                connection.execute(f"DELETE FROM {table} WHERE local_id=?", (local_id,))
        verify_originals(connection, before, root, blocks_only=True)
        connection.commit()
    except BaseException:
        connection.rollback()
        for path, data in saved.items():
            if data is None:
                path.unlink(missing_ok=True)
            else:
                replace_bytes(path, data)
        raise
    finally:
        connection.close()
    print(f"Wall {local_id} updated. Backup: {backup}")
    if downloads:
        print("Wall derived color rows invalidated. World and color are separate: replace both when appropriate.")
    if metadata and metadata["problem"]:
        print("Wiki review:", metadata["problem"])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--type", choices=("wall",), default="wall")
    parser.add_argument("--id", type=int)
    parser.add_argument("--page")
    for role in ROLES:
        parser.add_argument("--" + role, help="Explicit official wiki image URL")
    parser.add_argument("--refresh-metadata", action="store_true")
    parser.add_argument("--status")
    parser.add_argument("--problem", help="Use an empty string to clear")
    args = parser.parse_args(argv)
    if args.id is not None:
        changes = {field: value for field, value in {"page_url": args.page, "status": args.status, "problem": args.problem}.items() if value is not None}
        urls = {role: getattr(args, role) for role in ROLES if getattr(args, role)}
        fix_wall(args.id, changes, urls, args.refresh_metadata)
        return
    print("Wall editor. Enter a wall ID, or STOP. Each explicit edit is saved with a backup.")
    while True:
        value = input("Wall ID > ").strip()
        if value.upper() == "STOP":
            return
        try:
            local_id = int(value)
            with closing(connect_readonly()) as connection:
                print(require_wall(connection, local_id))
            action = input("page / inventory / world / color / metadata / status / problem / back > ").strip()
            if action == "metadata":
                fix_wall(local_id, {}, {}, True)
            elif action in ROLES:
                fix_wall(local_id, {}, {action: input("Official image URL > ").strip()})
            elif action in {"page", "status", "problem"}:
                fix_wall(local_id, {"page_url" if action == "page" else action: input("New value > ").strip()}, {})
        except (ValueError, OSError, sqlite3.Error) as error:
            print("No edit completed:", error)
