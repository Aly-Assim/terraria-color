"""Small safety boundary shared by wall acquisition and manual maintenance."""
from datetime import datetime, timezone
from contextlib import closing
from hashlib import sha256
from pathlib import Path
import json
import os
import sqlite3
import tempfile

from scripts.paths import PROJECT_ROOT, DB_PATH, connect_readonly

ROLES = ("inventory", "world", "color")


def replace_bytes(path: Path, data: bytes):
    """Replace a validated wall path without writing through an existing hardlink."""
    descriptor, temporary = tempfile.mkstemp(prefix=".wall_", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def wall_path(relative: str, role: str, root: Path = PROJECT_ROOT, local_id: int | None = None) -> Path:
    if role not in ROLES:
        raise ValueError(f"Unknown image role: {role}")
    base = root.resolve() / "images/walls" / role
    # Resolve both sides, but do not allow a symlinked role directory to escape.
    base.resolve().relative_to(root.resolve() / "images/walls")
    path = (root / relative.replace("\\", "/")).resolve()
    path.relative_to(base.resolve())
    if path.parent != base.resolve():
        raise ValueError(f"Nested wall image path is not supported: {relative}")
    if not path.stem.endswith("_" + role):
        raise ValueError(f"Wrong role suffix: {relative}")
    if local_id is not None and not path.name.startswith(f"{local_id}_"):
        raise ValueError(f"Filename/local ID mismatch: {relative}")
    return path


def image_hashes(root: Path = PROJECT_ROOT) -> dict:
    return {p.relative_to(root).as_posix(): sha256(p.read_bytes()).hexdigest()
            for role in ROLES for p in (root / "images" / role).rglob("*") if p.is_file()}


def snapshot(connection, root: Path = PROJECT_ROOT) -> dict:
    rows = [dict(row) for row in connection.execute("SELECT * FROM objects ORDER BY local_id")]
    return dict(objects=rows, count=len(rows), max_id=max((r["local_id"] for r in rows), default=-1),
                block_images=image_hashes(root))


def verify_originals(connection, before: dict, root: Path = PROJECT_ROOT, blocks_only: bool = False):
    for original in before["objects"]:
        if blocks_only and original["object_type"] != "block":
            continue
        current = connection.execute("SELECT * FROM objects WHERE local_id=?", (original["local_id"],)).fetchone()
        if current is None or any(current[k] != v for k, v in original.items()):
            raise RuntimeError(f"Original object changed: {original['local_id']}")
    if image_hashes(root) != before["block_images"]:
        raise RuntimeError("Protected block image names/bytes changed")


def backup_database(db: Path = DB_PATH, root: Path = PROJECT_ROOT, label: str = "wall_import") -> Path:
    folder = root / "data/backups" / (label + "_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    folder.mkdir(parents=True, exist_ok=False)
    with closing(connect_readonly(db)) as source, closing(sqlite3.connect(folder / db.name)) as target:
        source.backup(target)
    return folder


def ensure_wall_schema(connection):
    columns = {r[1] for r in connection.execute("PRAGMA table_info(objects)")}
    if "internal_wall_id" not in columns:
        connection.execute("ALTER TABLE objects ADD COLUMN internal_wall_id INTEGER")
    connection.execute("""CREATE TABLE IF NOT EXISTS object_wall_ids (
        local_id INTEGER NOT NULL REFERENCES objects(local_id) ON DELETE CASCADE,
        wall_id INTEGER NOT NULL, is_safe INTEGER CHECK(is_safe IN (0,1)),
        internal_name TEXT, PRIMARY KEY(local_id, wall_id))""")


def store_wall_ids(connection, local_id: int, ids: list[dict]):
    connection.execute("DELETE FROM object_wall_ids WHERE local_id=?", (local_id,))
    connection.executemany("INSERT INTO object_wall_ids VALUES (?,?,?,?)", [
        (local_id, w["wall_id"], w["is_safe"], w["internal_name"]) for w in ids])


def save_snapshot(path: Path, before: dict):
    path.write_text(json.dumps(before, indent=2, ensure_ascii=False), encoding="utf-8")
