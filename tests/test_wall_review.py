"""One offline end-to-end review scenario, exclusively on a temporary catalogue."""
import sys
from pathlib import Path
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contextlib import closing, redirect_stdout
from io import StringIO
import json
import re
import sqlite3
import tempfile
from PIL import Image

from scripts.paths import connect_readonly
from scripts.maintenance.curate_walls import create_app
from scripts.maintenance.wall_review import read_csv, write_csv
from scripts.maintenance.wall_storage import snapshot, verify_originals


def main():
    with tempfile.TemporaryDirectory() as temporary, redirect_stdout(StringIO()):
        root = Path(temporary)
        db = root / "catalog.db"
        with closing(connect_readonly()) as source, closing(sqlite3.connect(db)) as connection:
            source.backup(connection)
        with closing(sqlite3.connect(db)) as connection, connection:
            connection.row_factory = sqlite3.Row
            for table in ("object_wall_ids", "object_colors", "object_paint_colors"):
                connection.execute(f"DELETE FROM {table} WHERE local_id != 0")
            connection.execute("DELETE FROM objects WHERE local_id != 0")
            block = dict(connection.execute("SELECT * FROM objects WHERE local_id=0").fetchone())
            walls = []
            for local_id in (1, 3, 5):
                row = dict(block, local_id=local_id, object_type="wall", is_wall=1, internal_tile_id=None,
                           internal_wall_id=1, name=f"Fixture Wall {local_id}", source=f"fixture:{local_id}",
                           status="review" if local_id == 3 else "ok", problem="source_alias" if local_id == 3 else None)
                for role in ("world", "inventory", "color"):
                    relative = f"images/walls/{role}/{local_id}_fixture_{role}.png"
                    path = root / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    Image.new("RGBA", (8, 8), (80, 120, 160, 255)).save(path)
                    row[role + "_image_path"] = relative
                connection.execute(f"INSERT INTO objects ({','.join(row)}) VALUES ({','.join('?' for _ in row)})", tuple(row.values()))
                connection.execute("INSERT INTO object_wall_ids VALUES (?,?,?,?)", (local_id, 1, 1, "Fixture"))
                values = dict(connection.execute("SELECT * FROM object_colors WHERE local_id=0").fetchone())
                values.update(local_id=local_id, image_used=row["color_image_path"])
                connection.execute(f"INSERT INTO object_colors ({','.join(values)}) VALUES ({','.join('?' for _ in values)})", tuple(values.values()))
                walls.append(row)
            for role in ("world", "inventory", "color"):
                path = root / block[role + "_image_path"].replace("\\", "/")
                path.parent.mkdir(parents=True, exist_ok=True)
                Image.new("RGBA", (2, 2), (10, 20, 30, 255)).save(path)
        write_csv(root / "data/wall_import_report.csv", tuple(walls[0]), walls)
        with closing(connect_readonly(db)) as connection:
            before = snapshot(connection, root)
        app = create_app(root, db)
        client = app.test_client()

        def submit(action, **values):
            page = client.get("/")
            html = page.data.decode()
            token = re.search(r'name="csrf" value="([^"]+)"', html)[1]
            revision = re.search(r'name="revision" value="([^"]+)"', html)[1]
            return client.post("/action", data=dict(csrf=token, revision=revision, action=action, **values))

        page = client.get("/")
        assert page.status_code == 200 and b"source_alias" in page.data
        assert b"/image/3/world" in page.data and b"/image/3/inventory" in page.data
        assert client.get("/image/3/world").status_code == 200
        assert client.get("/image/0/world").status_code == 404
        assert client.post("/action", data={"action": "finalize"}).status_code == 403
        assert submit("finalize").status_code == 400  # issues still pending
        assert submit("accept", note="Nom source vérifié").status_code == 303
        assert app.config["WALL_REVIEW"].current()[0] == "pair"
        assert submit("finalize").status_code == 400  # pairs still pending
        assert submit("keep_left").status_code == 303  # keep 1, delete 3
        with closing(connect_readonly(db)) as connection:
            assert [r[0] for r in connection.execute("SELECT local_id FROM objects ORDER BY local_id")] == [0, 1, 5]
        assert submit("distinct").status_code == 303  # keep 1 and 5 as distinct
        # Reopening must not resurrect decided pairs.
        app = create_app(root, db)
        client = app.test_client()
        app.config["WALL_REVIEW"].refresh()
        assert app.config["WALL_REVIEW"].current()[0] == "done"
        assert submit("finalize").status_code == 303
        review = app.config["WALL_REVIEW"]
        assert review.state["finalized"] and not review.issues and not review.pairs
        assert not read_csv(review.folder / "issues.csv") and not read_csv(review.folder / "pairs.csv")
        assert read_csv(review.folder / "id_map.csv") == [{"old_id": "1", "new_id": "1"}, {"old_id": "5", "new_id": "2"}]
        with closing(connect_readonly(db)) as connection:
            verify_originals(connection, before, root, blocks_only=True)
            assert [r[0] for r in connection.execute("SELECT local_id FROM objects ORDER BY local_id")] == [0, 1, 2]
            assert not connection.execute("PRAGMA foreign_key_check").fetchall()
            assert connection.execute("SELECT image_used FROM object_colors WHERE local_id=2").fetchone()[0] == "images/walls/color/2_fixture_color.png"
        assert (root / "images/walls/world/2_fixture_world.png").exists()
        assert not (root / "images/walls/world/5_fixture_world.png").exists()
        assert client.get("/").status_code == 200
    print("[PASS] Visual review, problem priority, pair decisions, resume and CSV-gated wall-only renumbering")


if __name__ == "__main__":
    main()
