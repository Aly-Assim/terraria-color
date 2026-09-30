"""Manually selected wall deletion with stable IDs, backup and rollback.

The retained wall is not rewritten. No image tree is rebuilt. Without --apply
this command only prints the proposed deletion.
"""
import sys
from pathlib import Path
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import argparse
from contextlib import closing
import sqlite3
from scripts.paths import PROJECT_ROOT, DB_PATH, connect_readonly
from scripts.maintenance.manual_walls import require_wall
from scripts.maintenance.wall_storage import ROLES, backup_database, replace_bytes, snapshot, verify_originals, wall_path


def merge_walls(keep: int, remove: list[int], apply: bool = False, db: Path = DB_PATH, root: Path = PROJECT_ROOT):
    if not remove or keep in remove or len(set(remove)) != len(remove):
        raise ValueError("Choose one retained ID and distinct removed IDs")
    with closing(connect_readonly(db)) as reader:
        retained = require_wall(reader, keep)
        deleted = [require_wall(reader, local_id) for local_id in remove]
        before = snapshot(reader, root)
        remaining_paths = {(root / r[0].replace("\\", "/")).resolve()
                           for role in ROLES for r in reader.execute(
                               f"SELECT {role}_image_path FROM objects WHERE local_id NOT IN ({','.join('?' for _ in remove)})", remove) if r[0]}
    files = set()
    for row in deleted:
        for role in ROLES:
            if row[role + "_image_path"]:
                path = wall_path(row[role + "_image_path"], role, root, row["local_id"])
                if path not in remaining_paths and path.is_file():
                    files.add(path)
    print(f"KEEP {keep}: {retained['name']}")
    for row in deleted:
        print(f"REMOVE {row['local_id']}: {row['name']}")
    print(f"Selected source files: {len(files)}. Stable IDs retained; gaps are intentional.")
    if not apply:
        print("Preview only. Add --apply to execute this exact selection.")
        return
    backup = backup_database(db, root, "wall_merge")
    saved = {path: path.read_bytes() for path in files}
    for path, data in saved.items():
        target = backup / path.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        connection.execute("BEGIN IMMEDIATE")
        verify_originals(connection, before, root)
        for row in deleted:
            for table in ("object_colors", "object_paint_colors", "object_wall_ids"):
                if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
                    connection.execute(f"DELETE FROM {table} WHERE local_id=?", (row["local_id"],))
            connection.execute("DELETE FROM objects WHERE local_id=? AND object_type='wall'", (row["local_id"],))
        for path in files:
            path.unlink()
        verify_originals(connection, before, root, blocks_only=True)
        if connection.execute("PRAGMA foreign_key_check").fetchall():
            raise RuntimeError("Unremoved dependencies; merge rolled back")
        connection.commit()
    except BaseException:
        connection.rollback()
        for path, data in saved.items():
            replace_bytes(path, data)
        raise
    finally:
        connection.close()
    print("Merge complete. Backup:", backup)
    print("Existing painted exports are not altered; regenerate them only when you decide to rebuild.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", type=int, required=True)
    parser.add_argument("--remove", type=int, nargs="+", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    merge_walls(args.keep, args.remove, args.apply)


if __name__ == "__main__":
    main()
