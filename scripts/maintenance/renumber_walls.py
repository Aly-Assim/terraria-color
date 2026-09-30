"""Final wall-only compaction, available only after all review queues are empty."""
from contextlib import closing
import csv
from io import StringIO
import json
from pathlib import Path
import sqlite3

from scripts.paths import connect_readonly
from scripts.maintenance.wall_review import read_csv, write_csv
from scripts.maintenance.wall_storage import (
    ROLES, backup_database, replace_bytes, snapshot, verify_originals, wall_path, save_snapshot,
)


def finalize(review, revision: str) -> dict[int, int]:
    review.refresh()
    if revision != review.revision:
        raise ValueError("Les données ont changé. Recharge la page.")
    if review.issues or review.pairs or any(read_csv(review.folder / name) for name in ("issues.csv", "pairs.csv")):
        raise ValueError("Tous les problèmes et toutes les paires doivent être traités avant la renumérotation.")
    root, db = review.root, review.db
    if any(p.is_file() for p in (root / "images/painted/walls").rglob("*")):
        raise ValueError("Des peintures de murs existent déjà. Finalise la classification avant leur génération ; ces exports ne seront pas déplacés automatiquement.")
    with closing(connect_readonly(db)) as reader:
        before = snapshot(reader, root)
        objects = before["objects"]
        walls = [r for r in objects if r["object_type"] == "wall"]
        start = max((r["local_id"] for r in objects if r["object_type"] != "wall"), default=-1) + 1
        mapping = {r["local_id"]: start + index for index, r in enumerate(walls)}
        tables = {r[0] for r in reader.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        dependencies = [t for t in ("object_colors", "object_paint_colors", "object_wall_ids") if t in tables]
        for table in tables - {"objects", *dependencies}:
            if any(r[2] == "objects" for r in reader.execute('PRAGMA foreign_key_list("' + table.replace('"', '""') + '")')):
                raise ValueError(f"Dépendance non prise en charge : {table}. Aucun ID modifié.")
    path_map, files, new_rows = {}, {}, {}
    for row in walls:
        new = dict(row, local_id=mapping[row["local_id"]])
        for role in ROLES:
            relative = row.get(role + "_image_path")
            if not relative:
                continue
            source = wall_path(relative, role, root, row["local_id"])
            if not source.is_file():
                raise ValueError(f"Répare le fichier manquant avant de finaliser : {relative}")
            target_relative = (Path(relative.replace("\\", "/")).parent /
                               (str(new["local_id"]) + "_" + source.name.split("_", 1)[1])).as_posix()
            target = wall_path(target_relative, role, root, new["local_id"])
            path_map[relative.replace("\\", "/")] = target_relative
            new[role + "_image_path"] = target_relative
            if target != source:
                files[source] = (target, source.read_bytes())
        new_rows[row["local_id"]] = new
    for source, (target, _) in files.items():
        if target.exists() and target not in files:
            raise FileExistsError(f"Collision de nom : {target}. Aucun ID modifié.")
    backup = backup_database(db, root, "wall_finalize")
    save_snapshot(backup / "before.json", before)
    save_snapshot(backup / "id_map.json", mapping)
    for source, (_, data) in files.items():
        target = backup / source.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    # Only current exports are updated. Historical block acquisition CSVs are
    # unrelated snapshots whose old IDs must never be interpreted as wall IDs.
    report_paths = [root / "data/wall_import_report.csv", root / "data/colors.csv",
                    root / "data/duplicates/duplicate_groups.csv", root / "data/duplicates/wall_validation.csv"]
    reports_before = {p: p.read_bytes() for p in report_paths if p.exists()}
    for path, data in reports_before.items():
        target = backup / path.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    created = []
    removed = []
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("PRAGMA defer_foreign_keys=ON")
        verify_originals(connection, before, root)
        if connection.execute("SELECT COUNT(*) FROM objects").fetchone()[0] != before["count"]:
            raise ValueError("Le catalogue a changé pendant la préparation")
        temporary = {old: -max(abs(r["local_id"]) for r in objects) - index - 1
                     for index, old in enumerate(mapping)}
        for old, temp in temporary.items():
            connection.execute("UPDATE objects SET local_id=? WHERE local_id=? AND object_type='wall'", (temp, old))
            for table in dependencies:
                connection.execute(f"UPDATE {table} SET local_id=? WHERE local_id=?", (temp, old))
        for old, new in mapping.items():
            temp = temporary[old]
            connection.execute("UPDATE objects SET local_id=? WHERE local_id=? AND object_type='wall'", (new, temp))
            for table in dependencies:
                connection.execute(f"UPDATE {table} SET local_id=? WHERE local_id=?", (new, temp))
            row = new_rows[old]
            connection.execute("UPDATE objects SET inventory_image_path=?,world_image_path=?,color_image_path=? WHERE local_id=?",
                               (*(row.get(role + "_image_path") for role in ROLES), new))
            for table in ("object_colors", "object_paint_colors"):
                if table not in dependencies:
                    continue
                old_row = next(r for r in walls if r["local_id"] == old)
                for role in ROLES:
                    original = (old_row.get(role + "_image_path") or "").replace("\\", "/")
                    replacement = row.get(role + "_image_path")
                    if not original or original == replacement:
                        continue
                    connection.execute(f"UPDATE {table} SET image_used=? WHERE local_id=? AND replace(image_used,char(92),'/')=?",
                                       (replacement, new, original))
        for source in files:
            source.unlink()
            removed.append(source)
        for target, data in files.values():
            with target.open("xb") as stream:
                created.append(target)
                stream.write(data)
        for path, content in reports_before.items():
            reader = csv.DictReader(StringIO(content.decode("utf-8-sig")))
            fields = list(reader.fieldnames or [])
            rows = list(reader)
            if path.name == "colors.csv":
                rows = [r for r in rows if r.get("local_id") not in review.state["merged"]]
            if path.name in {"duplicate_groups.csv", "wall_validation.csv"}:
                # The wall work has been decided. Preserve unrelated block rows.
                rows = [r for r in rows if r.get("object_type") == "block"]
            else:
                for row in rows:
                    try:
                        old = int(row["local_id"])
                    except (KeyError, ValueError):
                        continue
                    destination = old
                    seen = set()
                    while str(destination) in review.state["merged"]:
                        if destination in seen:
                            raise ValueError("Cycle dans les décisions de fusion")
                        seen.add(destination)
                        destination = review.state["merged"][str(destination)]
                    if destination not in mapping:
                        continue
                    row["local_id"] = str(mapping[destination])
                    if path.name == "wall_import_report.csv":
                        if "original_local_id" not in fields:
                            fields.append("original_local_id")
                        row.setdefault("original_local_id", str(old))
                        if destination != old:
                            row["import_action"] = "merged"
                        current = new_rows[destination]
                        for field in ("name", "category_name", "page_url", "internal_item_id", "internal_wall_id", "status", "problem",
                                      *(role + "_image_" + suffix for role in ROLES for suffix in ("url", "path"))):
                            if field in fields:
                                row[field] = current.get(field) if current.get(field) is not None else ""
                    else:
                        for field, value in row.items():
                            row[field] = path_map.get(value.replace("\\", "/"), value) if value else value
            write_csv(path, tuple(fields), rows)
        verify_originals(connection, before, root, blocks_only=True)
        for old, expected in new_rows.items():
            actual = dict(connection.execute("SELECT * FROM objects WHERE local_id=?", (mapping[old],)).fetchone())
            if actual != expected:
                raise RuntimeError(f"Vérification du mur {old} échouée")
        for target, data in files.values():
            if target.read_bytes() != data:
                raise RuntimeError("Le contenu d'une image a changé")
        if connection.execute("PRAGMA foreign_key_check").fetchall():
            raise RuntimeError("Références invalides ; annulation")
        connection.commit()
    except BaseException:
        connection.rollback()
        for path in created:
            path.unlink(missing_ok=True)
        for source in removed:
            replace_bytes(source, files[source][1])
        for path, data in reports_before.items():
            replace_bytes(path, data)
        raise
    finally:
        connection.close()
    review.state["history"].append(dict(action="renumber", mapping=mapping, backup=str(backup)))
    review.state["merged"] = {}
    review.state["finalized"] = True
    review.save()
    write_csv(review.folder / "id_map.csv", ("old_id", "new_id"), [dict(old_id=a, new_id=b) for a, b in mapping.items()])
    review.refresh()
    return mapping
