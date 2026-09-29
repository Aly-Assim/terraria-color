"""Read-only checks for the shipped database, paths, and immutable images."""
from pathlib import Path
import csv
import hashlib
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.paths import PROJECT_ROOT, PAINTED_ROOT, connect_readonly
from scripts.paint.renderer import PAINTS


def main() -> None:
    with connect_readonly() as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()
        objects = connection.execute("SELECT * FROM objects").fetchall()
        assert len(objects) == 307, "Unexpected curated object count"
        for table in ("object_colors", "object_paint_colors"):
            assert connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE error IS NOT NULL"
            ).fetchone()[0] == 0, f"Errors in {table}"
        assert connection.execute("SELECT COUNT(*) FROM object_colors").fetchone()[0] == 307
        combinations = set(map(tuple, connection.execute(
            "SELECT local_id, paint_id FROM object_paint_colors"
        )))
        expected = {(obj["local_id"], paint) for obj in objects for paint in PAINTS}
        assert combinations == expected, "Missing or unexpected paint-color combinations"
        for obj in objects:
            for field in ("world_image_path", "inventory_image_path", "color_image_path"):
                path = PROJECT_ROOT / obj[field].replace("\\", "/")
                assert path.is_file(), f"Missing {field}: {path}"
    print("[PASS] SQLite integrity, 307 objects, 9517 combinations, and source paths")

    expected_hashes = {}
    for line in (PROJECT_ROOT / "data" / "immutable_images.sha256").read_text(encoding="utf-8").splitlines():
        digest, relative = line.split("  ", 1)
        expected_hashes[relative] = digest
    actual_hashes = {
        p.relative_to(PROJECT_ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for role in ("world", "inventory")
        for p in (PROJECT_ROOT / "images" / role).rglob("*") if p.is_file()
    }
    assert actual_hashes == expected_hashes, "Immutable image filenames or bytes changed"
    print(f"[PASS] All {len(actual_hashes)} immutable image filenames and SHA-256 hashes")

    with (PAINTED_ROOT / "manifest.csv").open(encoding="utf-8", newline="") as stream:
        manifest = list(csv.DictReader(stream))
    keys = set()
    paths = set()
    for row in manifest:
        key = (int(row["local_id"]), int(row["paint_id"]))
        assert key in expected and key not in keys, f"Invalid or duplicate manifest key: {key}"
        keys.add(key)
        assert row["paint_name"] == PAINTS[key[1]][1]
        path = (PAINTED_ROOT / row["relative_image_path"]).resolve()
        path.relative_to(PAINTED_ROOT)
        assert path.is_file(), f"Missing painted image: {path}"
        paths.add(path)
    actual_paths = {p.resolve() for p in PAINTED_ROOT.glob("*/*.png") if not p.name.startswith("_")}
    assert paths == actual_paths, "Painted images and manifest disagree"
    print(f"[PASS] Manifest: {len(keys)} variants; {len(expected - keys)} combinations not exported")


if __name__ == "__main__":
    main()
