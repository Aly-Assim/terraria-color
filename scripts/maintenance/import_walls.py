"""Append workbook walls without rebuilding the catalogue or touching block media."""
import sys
from pathlib import Path
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import argparse
from contextlib import closing
import csv
import json
import sqlite3
import tempfile

from scripts.paths import PROJECT_ROOT, DB_PATH, connect_readonly
from scripts.maintenance.wall_source import (
    WORKBOOK, WikiClient, WallResolver, image_bytes, normalize_name, read_walls, safe_filename,
)
from scripts.maintenance.wall_storage import (
    ROLES, backup_database, ensure_wall_schema, save_snapshot, snapshot,
    store_wall_ids, verify_originals, wall_path,
)

SAMPLE_NAMES = ("Stone Wall", "Topaz Stone Wall", "Crimstone Wall", "Natural Dirt Wall", "Cog Wall")
REPORT_FIELDS = ("local_id", "source_name", "name", "category_name", "page_url", "internal_item_id",
                 "internal_wall_id", "wall_ids", "inventory_image_url", "world_image_url", "color_image_url",
                 "inventory_image_path", "world_image_path", "color_image_path", "status", "problem",
                 "grouped_page", "excel_image_url", "source_row", "source_column", "import_action")


def source_key(name: str) -> str:
    return "workbook:Walls:" + normalize_name(name)


def write_report(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=REPORT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, "wall_ids": json.dumps(row.get("wall_ids", []), ensure_ascii=False)})


def resolve_entries(entries: list[dict], resolver: WallResolver, staging: Path | None = None) -> list[dict]:
    results = []
    for index, entry in enumerate(entries):
        try:
            row = resolver.resolve(entry)
            row["_files"] = {}
            if staging is not None:
                for role in ("inventory", "world"):
                    url = row.get(role + "_image_url")
                    if not url:
                        continue
                    try:
                        data = resolver.client.get(url)
                        extension = image_bytes(data)
                        target = staging / f"{index}_{safe_filename(row['name'])}_{role}{extension}"
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(data)
                        row["_files"][role] = target
                    except Exception as error:
                        # A failed download is reported, never replaced by a sibling image.
                        row["status"] = "review"
                        row["problem"] = (row.get("problem") or "") + f"; {role}_download_failed: {error}"
                if "world" in row["_files"]:
                    row["_files"]["color"] = row["_files"]["world"]
            row["import_action"] = "pending"
        except Exception as error:
            row = dict(entry, name=entry["source_name"], status="failed", problem=str(error), import_action="failed")
        results.append(row)
        print(f"[{index + 1}/{len(entries)}] {row['source_name']}: {row['status']} {row.get('problem') or ''}", flush=True)
    return results


def verify_wall(connection, row: dict, root: Path):
    stored = connection.execute("SELECT * FROM objects WHERE local_id=?", (row["local_id"],)).fetchone()
    if stored["object_type"] != "wall" or stored["is_wall"] != 1 or stored["internal_tile_id"] is not None:
        raise RuntimeError("Invalid wall semantics")
    for role in ROLES:
        relative = stored[role + "_image_path"]
        if relative:
            path = wall_path(relative, role, root, row["local_id"])
            image_bytes(path.read_bytes())
    if stored["world_image_path"] and stored["color_image_path"]:
        if (root / stored["world_image_path"]).read_bytes() != (root / stored["color_image_path"]).read_bytes():
            raise RuntimeError("Imported color media must be a byte-for-byte copy of world media")


def append_rows(rows: list[dict], db: Path = DB_PATH, root: Path = PROJECT_ROOT) -> dict:
    if not db.is_file():
        raise FileNotFoundError(db)
    with closing(connect_readonly(db)) as reader:
        before = snapshot(reader, root)
    backup = backup_database(db, root)
    save_snapshot(backup / "before.json", before)
    created = []
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        connection.execute("BEGIN IMMEDIATE")
        verify_originals(connection, before, root)
        if connection.execute("SELECT COUNT(*) FROM objects").fetchone()[0] != before["count"]:
            raise RuntimeError("Catalogue changed during preparation; rerun")
        ensure_wall_schema(connection)
        next_id = before["max_id"] + 1
        for row in rows:
            if row["status"] == "failed":
                continue
            source = source_key(row["source_name"])
            existing = connection.execute("SELECT * FROM objects WHERE object_type='wall' AND source=?", (source,)).fetchone()
            if existing:
                row.update(dict(existing), import_action="skipped_existing")
                continue
            row["local_id"] = next_id
            for role in ROLES:
                row[role + "_image_path"] = None
                if role not in row["_files"]:
                    continue
                staged = row["_files"][role]
                extension = image_bytes(staged.read_bytes())
                relative = f"images/walls/{role}/{next_id}_{safe_filename(row['name'])}_{role}{extension}"
                path = wall_path(relative, role, root, next_id)
                path.parent.mkdir(parents=True, exist_ok=True)
                # Exclusive create: never overwrite even an unreferenced existing wall file.
                with path.open("xb") as output:
                    created.append(path)
                    output.write(staged.read_bytes())
                row[role + "_image_path"] = relative
            values = {k: row.get(k) for k in (
                "local_id", "name", "category_name", "page_url", "internal_item_id", "internal_wall_id", "status", "problem",
                *(role + "_image_" + suffix for role in ROLES for suffix in ("url", "path")))}
            values.update(object_type="wall", is_wall=1, internal_tile_id=None,
                          normalized_name=normalize_name(row["name"]), canonical_name=normalize_name(row["name"]), source=source)
            connection.execute(f"INSERT INTO objects ({','.join(values)}) VALUES ({','.join('?' for _ in values)})", tuple(values.values()))
            store_wall_ids(connection, next_id, row["wall_ids"])
            verify_wall(connection, row, root)
            row["import_action"] = "inserted"
            next_id += 1
        verify_originals(connection, before, root)
        if connection.execute("PRAGMA foreign_key_check").fetchall():
            raise RuntimeError("Foreign-key validation failed")
        if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("SQLite integrity validation failed")
        inserted = sum(row.get("import_action") == "inserted" for row in rows)
        if connection.execute("SELECT COUNT(*) FROM objects").fetchone()[0] != before["count"] + inserted:
            raise RuntimeError("Imported row count does not reconcile")
        connection.commit()
    except BaseException:
        connection.rollback()
        for path in created:
            path.unlink()  # only files this operation created, validated above
        raise
    finally:
        connection.close()
    result = dict(original_objects=before["count"], original_max_id=before["max_id"],
                  protected_images=len(before["block_images"]), inserted=inserted,
                  skipped=sum(row.get("import_action") == "skipped_existing" for row in rows),
                  failed=sum(row["status"] == "failed" for row in rows), backup=str(backup),
                  inventory=sum(bool(row.get("inventory_image_path")) for row in rows if row.get("import_action") == "inserted"),
                  world=sum(bool(row.get("world_image_path")) for row in rows if row.get("import_action") == "inserted"))
    save_snapshot(backup / "verification.json", result)
    return result


def run_sample(entries: list[dict], resolver: WallResolver, db: Path = DB_PATH,
               cache: Path = PROJECT_ROOT / "cache/walls") -> Path:
    cache.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="sample_", dir=cache))
    sample = [next((e for e in entries if e["source_name"] == name), None) for name in SAMPLE_NAMES]
    if any(e is None for e in sample):
        raise ValueError("Representative sample names missing from workbook; update sample selection explicitly")
    rows = resolve_entries(sample, resolver, stage / "downloads")
    write_report(stage / "sample_report.csv", rows)
    for row in rows:
        print(json.dumps({k: v for k, v in row.items() if k != "_files"}, ensure_ascii=False))
        print("Staged files:", {k: str(v) for k, v in row.get("_files", {}).items()})
    if any(row["status"] == "failed" or not row.get("internal_wall_id") or
           "world" not in row.get("_files", {}) or
           (row.get("internal_item_id") and "inventory" not in row.get("_files", {})) or
           "ambiguous" in (row.get("problem") or "") for row in rows):
        raise RuntimeError(f"Sample failed. Canonical data untouched. Report: {stage / 'sample_report.csv'}")
    stage_db = stage / "catalog.db"
    with closing(connect_readonly(db)) as source, closing(sqlite3.connect(stage_db)) as target:
        source.backup(target)
        # Always exercise a fresh append, even when sampling an already imported
        # catalogue. Only the disposable copy's source keys are namespaced.
        target.execute("UPDATE objects SET source='sample-existing:' || source WHERE object_type='wall'")
        target.commit()
    print("Sample append:", append_rows(rows, stage_db, stage))
    write_report(stage / "sample_report.csv", rows)
    return stage


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--dry-run", action="store_true", help="Resolve workbook entries; cache/report only")
    modes.add_argument("--sample", action="store_true", help="Download and append five walls in ignored staging only")
    parser.add_argument("--force-refresh-cache", action="store_true")
    args = parser.parse_args(argv)
    entries, analysis = read_walls()
    print(json.dumps(analysis, ensure_ascii=False, indent=2), flush=True)
    resolver = WallResolver(WikiClient(refresh=args.force_refresh_cache))
    if args.dry_run:
        rows = resolve_entries(entries, resolver)
        path = PROJECT_ROOT / "cache/walls/dry_run.csv"
        write_report(path, rows)
        print("Dry-run report:", path)
        return
    sample_path = run_sample(entries, resolver)
    print("Sample passed:", sample_path, flush=True)
    if args.sample:
        return
    with closing(connect_readonly()) as connection:
        known = {row[0] for row in connection.execute("SELECT source FROM objects WHERE object_type='wall'")}
    pending = [e for e in entries if source_key(e["source_name"]) not in known]
    if not pending:
        print("All source walls are already imported; no canonical changes.")
        return
    stage = Path(tempfile.mkdtemp(prefix="full_", dir=PROJECT_ROOT / "cache/walls"))
    rows = resolve_entries(pending, resolver, stage / "downloads")
    write_report(stage / "resolved.csv", rows)
    summary = append_rows(rows)
    write_report(PROJECT_ROOT / "data/wall_import_report.csv", rows)
    print(json.dumps(summary, indent=2))
    print("Old object rows and protected block media verified unchanged. No curation or color builds performed.")


if __name__ == "__main__":
    main()
