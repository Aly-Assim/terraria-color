"""Wall preparation regression checks using an isolated in-memory database."""
from pathlib import Path
import sqlite3
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app as site
from scripts.catalog import painted_folder, world_source_path
from scripts.paths import connect_readonly


def fixture_connection():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    with connect_readonly() as source:
        source.backup(connection)
    # Isolate the synthetic fixture from the acquired wall catalogue.
    for table in ("object_colors", "object_paint_colors", "object_wall_ids"):
        if connection.execute("SELECT 1 FROM sqlite_master WHERE name=?", (table,)).fetchone():
            connection.execute(f"DELETE FROM {table} WHERE local_id IN (SELECT local_id FROM objects WHERE object_type='wall')")
    connection.execute("DELETE FROM objects WHERE object_type='wall'")
    row = dict(connection.execute("SELECT * FROM objects WHERE local_id = 0").fetchone())
    wall_id = connection.execute("SELECT MAX(local_id) + 1 FROM objects").fetchone()[0]
    row.update(local_id=wall_id, object_type="wall", is_wall=1,
               name="Fixture Wall", canonical_name="fixture wall")
    # Reuse a real texture only within this fixture to test the painted endpoint.
    columns = ", ".join(row)
    connection.execute(f"INSERT INTO objects ({columns}) VALUES ({','.join('?' for _ in row)})", tuple(row.values()))
    for table in ("object_colors", "object_paint_colors"):
        for original in connection.execute(f"SELECT * FROM {table} WHERE local_id = 0").fetchall():
            values = dict(original)
            values["local_id"] = wall_id
            connection.execute(
                f"INSERT INTO {table} ({', '.join(values)}) VALUES ({','.join('?' for _ in values)})",
                tuple(values.values()),
            )
    connection.commit()
    return connection


def main():
    with patch.object(site, "connect_db", side_effect=fixture_connection):
        with site.app.test_request_context():
            assert len(site.search_catalog("fixture", object_type="wall")) == 1
            assert not site.search_catalog("fixture", object_type="block")
            # Category/name OR terms must not bypass the type filter.
            assert not site.search_catalog("dirt", object_type="wall")
            for mode in ("average", "dominant"):
                results, error = site.search_by_color("#8a6a4b", 5, mode, 35, "13", object_type="wall")
                assert error is None and len(results) == 1
                assert results[0]["object_type"] == "wall" and results[0]["paint_id"] == 13
                wall_id = results[0]["local_id"]
                blocks, error = site.search_by_color("#8a6a4b", 5, mode, 35, "all", object_type="block")
                assert blocks and all(row["object_type"] == "block" for row in blocks)
        client = site.app.test_client()
        response = client.get("/", query_string={"mode": "catalog", "q": "fixture", "object_type": "wall"})
        assert response.status_code == 200 and b"Fixture Wall" in response.data
        assert b'value="wall" selected' in response.data
        response = client.get(f"/painted-image/{wall_id}/13")
        assert response.status_code == 200 and response.mimetype == "image/png"
    assert painted_folder({"object_type": "block", "world_image_path": "images/world/0_dirt_block_world.png"}).as_posix() == "0_dirt_block_world"
    wall = {"object_type": "wall", "world_image_path": "images/walls/world/307_example_wall.png"}
    assert painted_folder(wall).as_posix() == "walls/307_example_wall"
    try:
        world_source_path({**wall, "world_image_path": "images/world/0_dirt_block_world.png"})
    except ValueError:
        pass
    else:
        raise AssertionError("Wall exports must use the separate wall source directory")
    print("[PASS] Block/wall filtering, shared painted endpoint, and separate export paths (in memory)")


if __name__ == "__main__":
    main()
