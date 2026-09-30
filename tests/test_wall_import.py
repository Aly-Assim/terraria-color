"""Focused acquisition/maintenance safety checks on disposable fixtures only.

Optional dependencies: requirements-maintenance.txt. No network requests.
"""
import sys
from pathlib import Path
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contextlib import closing, redirect_stdout
from io import BytesIO, StringIO
import sqlite3
import tempfile
from unittest.mock import patch
from openpyxl import Workbook
from PIL import Image

from scripts.paths import connect_readonly
from scripts.maintenance import import_walls as importer, find_duplicates as duplicates
from scripts.maintenance.wall_source import read_walls
from scripts.maintenance.wall_storage import snapshot, verify_originals, wall_path
from scripts.maintenance.validate_catalog import validate
from scripts.maintenance.manual_walls import fix_wall
from scripts.maintenance.merge_walls import merge_walls


def main():
    with tempfile.TemporaryDirectory() as temporary, redirect_stdout(StringIO()):
        root = Path(temporary)
        db = root / "catalog.db"
        with closing(connect_readonly()) as source, closing(sqlite3.connect(db)) as target:
            source.backup(target)
        # Reduce the fixture, preserving the real schema, never the release DB.
        with closing(sqlite3.connect(db)) as connection, connection:
            for table in ("object_colors", "object_paint_colors", "object_wall_ids"):
                if connection.execute("SELECT 1 FROM sqlite_master WHERE name=?", (table,)).fetchone():
                    connection.execute(f"DELETE FROM {table}")
            connection.execute("DELETE FROM objects WHERE local_id != 0")
        for role in ("inventory", "world", "color"):
            path = root / "images" / role / f"0_dirt_block_{role}.png"
            path.parent.mkdir(parents=True)
            Image.new("RGBA", (2, 2), (8, 16, 32, 255)).save(path)
        with closing(connect_readonly(db)) as connection:
            before = snapshot(connection, root)

        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Walls"
        sheet.append(["Stone Walls", None, None])
        for name in importer.SAMPLE_NAMES:
            sheet.append([name, '=IMAGE("https://terraria.wiki.gg/images/Test_(placed).png")', False])
        workbook_path = root / "source.xlsx"
        workbook.save(workbook_path)
        entries, analysis = read_walls(workbook_path)
        assert len(entries) == 5 and analysis["duplicate_names"] == []

        output = BytesIO()
        Image.new("RGBA", (2, 2), (20, 40, 60, 255)).save(output, format="PNG")

        class Client:
            def get(self, url):
                return output.getvalue()

        class Resolver:
            client = Client()
            def resolve(self, entry):
                return dict(entry, name=entry["source_name"], internal_item_id=1, internal_wall_id=1,
                            wall_ids=[dict(wall_id=1, is_safe=1, internal_name="Fixture")],
                            page_url="https://terraria.wiki.gg/wiki/Test", status="ok", problem=None,
                            **{role + "_image_url": "https://terraria.wiki.gg/images/Test.png" for role in ("inventory", "world", "color")})

        resolver = Resolver()
        db_bytes = db.read_bytes()
        with patch.object(importer, "PROJECT_ROOT", root), patch.object(importer, "read_walls", return_value=(entries, analysis)), \
             patch.object(importer, "WallResolver", return_value=resolver):
            importer.main(["--dry-run"])
        assert db.read_bytes() == db_bytes and not (root / "images/walls").exists()
        importer.run_sample(entries, resolver, db, root / "cache")
        assert db.read_bytes() == db_bytes and not (root / "images/walls").exists()
        rows = importer.resolve_entries(entries[:2], resolver, root / "downloads")
        importer.append_rows(rows, db, root)
        with closing(connect_readonly(db)) as connection:
            verify_originals(connection, before, root)
            walls = [dict(r) for r in connection.execute("SELECT * FROM objects WHERE object_type='wall'")]
        assert [r["local_id"] for r in walls] == [1, 2]
        assert not validate(walls, root, "wall")
        with patch.object(duplicates, "DB_PATH", db), patch.object(duplicates, "PROJECT_ROOT", root):
            assert len(duplicates.load_objects("wall")) == 2
            assert len(duplicates.load_objects("block")) == 1
            groups, errors = duplicates.find_duplicate_groups(walls)
            assert len(groups) == 1 and not errors
        bad = {**walls[0], "world_image_path": "images/world/0_dirt_block_world.png", "inventory_image_path": None}
        issues = validate([bad], root, "wall")
        assert {"wrong_directory_or_object_type", "missing_path"} <= {i["problem"] for i in issues}
        try:
            wall_path("images/world/0_dirt_block_world.png", "world", root, 0)
        except ValueError:
            pass
        else:
            raise AssertionError("Block paths must be rejected")
        for operation in (lambda: fix_wall(0, {"status": "changed"}, {}, db=db, root=root),
                          lambda: merge_walls(1, [0], True, db, root)):
            try:
                operation()
            except ValueError:
                pass
            else:
                raise AssertionError("Block mutation must be refused")
        fix_wall(1, {"status": "review"}, {"world": "https://terraria.wiki.gg/images/Test.png"}, db=db, root=root, client=Client())
        merge_walls(1, [2], True, db, root)
        with closing(connect_readonly(db)) as connection:
            verify_originals(connection, before, root)
            assert [r[0] for r in connection.execute("SELECT local_id FROM objects ORDER BY local_id")] == [0, 1]
    print("[PASS] Workbook, dry-run/staging isolation, append, type filtering, validation, duplicates and wall-only edits/merge")


if __name__ == "__main__":
    main()
