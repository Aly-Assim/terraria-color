"""Persistent review queues. Discovery is read-only; decisions are always explicit."""
from collections import defaultdict
from contextlib import closing
import csv
from hashlib import sha256
from itertools import combinations
import json
import re
from pathlib import Path

from scripts.paths import PROJECT_ROOT, DB_PATH, connect_readonly
from scripts.maintenance.find_duplicates import find_duplicate_groups
from scripts.maintenance.validate_catalog import validate
from scripts.maintenance.wall_storage import ROLES, replace_bytes, backup_database, wall_path
from scripts.maintenance.manual_walls import fix_wall
from scripts.maintenance.merge_walls import merge_walls


def fingerprint(value) -> str:
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def decision_identity(row: dict) -> dict:
    """Review decisions survive a pure ID/filename-prefix renumbering."""
    return {key: re.sub(r"(?<=/)\d+_", "ID_", str(value).replace("\\", "/"))
            if value and (key.endswith("_path") or key == "path") else value
            for key, value in row.items() if key != "local_id"}


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, fields: tuple, rows: list[dict]):
    from io import StringIO
    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    replace_bytes(path, stream.getvalue().encode("utf-8"))


class WallReview:
    def __init__(self, root: Path = PROJECT_ROOT, db: Path = DB_PATH):
        self.root, self.db = root.resolve(), db.resolve()
        self.folder = self.root / "data/duplicates/wall_review"
        self.folder.mkdir(parents=True, exist_ok=True)
        self.session_file = self.folder / "session.json"
        self.state = json.loads(self.session_file.read_text(encoding="utf-8")) if self.session_file.exists() else {
            "accepted": [], "distinct": [], "deferred": [], "merged": {}, "history": [], "finalized": False}
        self.rows, self.issues, self.pairs = {}, [], []
        self.revision = ""

    def save(self):
        replace_bytes(self.session_file, json.dumps(self.state, ensure_ascii=False, indent=2).encode())

    def refresh(self):
        with closing(connect_readonly(self.db)) as connection:
            all_rows = [dict(r) for r in connection.execute("SELECT * FROM objects ORDER BY local_id")]
        self.rows = {r["local_id"]: r for r in all_rows if r["object_type"] == "wall"}
        versions = {}
        for local_id, row in self.rows.items():
            hashes = {}
            for role in ROLES:
                relative = row.get(role + "_image_path")
                path = (self.root / relative.replace("\\", "/")).resolve() if relative else None
                if path and path.is_file() and path.is_relative_to(self.root / "images/walls"):
                    hashes[role] = sha256(path.read_bytes()).hexdigest()
            versions[local_id] = fingerprint([decision_identity(row), hashes])
        found = validate(all_rows, self.root, "wall")
        for row in self.rows.values():
            if row.get("problem") or row["status"] not in {"ok", "reviewed"}:
                found.append(dict(local_id=row["local_id"], name=row["name"], role="metadata", path="",
                                  problem=row.get("problem") or "status=" + row["status"]))
        # Existing reports provide provenance, never stale mutation instructions.
        imported = read_csv(self.root / "data/wall_import_report.csv")
        reported = read_csv(self.root / "data/duplicates/wall_validation.csv")
        self.issues = []
        for issue in found:
            local_id = issue.get("local_id")
            orphan_hash = None
            if local_id is None and issue.get("path"):
                candidate = (self.root / issue["path"]).resolve()
                if candidate.is_relative_to(self.root / "images/walls") and candidate.is_file():
                    orphan_hash = sha256(candidate.read_bytes()).hexdigest()
            issue["key"] = fingerprint([decision_identity(issue), versions.get(local_id), orphan_hash])
            issue["sources"] = "validation actuelle"
            if any(r.get("local_id") == str(local_id) and r.get("problem") == issue["problem"] for r in reported):
                issue["sources"] += ", wall_validation.csv"
            if any(r.get("local_id") == str(local_id) and r.get("problem") == issue["problem"] for r in imported):
                issue["sources"] += ", wall_import_report.csv"
            if issue["key"] not in self.state["accepted"]:
                self.issues.append(issue)
        groups, _ = find_duplicate_groups(list(self.rows.values()), self.root)
        # Preserve previously reported groups as review candidates only while the
        # current names/paths still agree. Live detection also finds new pairs.
        candidates = {}
        for group in groups:
            for a, b in combinations(group["items"], 2):
                candidates[tuple(sorted((a["local_id"], b["local_id"])))] = "pixels world identiques (première frame)"
        reported_groups = defaultdict(list)
        for row in read_csv(self.root / "data/duplicates/duplicate_groups.csv"):
            try:
                local_id = int(row["local_id"])
            except (ValueError, KeyError):
                continue
            current = self.rows.get(local_id)
            if current and row.get("name") == current["name"] and row.get("world_image_path", "").replace("\\", "/") == (current.get("world_image_path") or "").replace("\\", "/"):
                reported_groups[row["group_id"]].append(local_id)
        for ids in reported_groups.values():
            for pair in combinations(sorted(set(ids)), 2):
                candidates.setdefault(pair, "signalé dans duplicate_groups.csv ; à vérifier")
        self.pairs = []
        for (left, right), reason in sorted(candidates.items()):
            key = fingerprint([versions[left], versions[right]])
            if key not in self.state["distinct"]:
                self.pairs.append(dict(key=key, left_id=left, right_id=right, reason=reason))
        deferred = self.state["deferred"]
        def order(key):
            return deferred.index(key) + 1 if key in deferred else 0
        self.issues.sort(key=lambda i: (order(i["key"]), i.get("local_id") is None, i.get("local_id") or 0))
        self.pairs.sort(key=lambda p: (order(p["key"]), p["left_id"], p["right_id"]))
        self.revision = fingerprint([versions, self.issues, self.pairs])
        write_csv(self.folder / "issues.csv", ("key", "local_id", "name", "role", "path", "problem", "sources"), self.issues)
        write_csv(self.folder / "pairs.csv", ("key", "left_id", "right_id", "reason"), self.pairs)
        return self

    def current(self):
        if self.issues:
            return "issue", self.issues[0]
        if self.pairs:
            return "pair", self.pairs[0]
        return "done", None

    def act(self, action: str, revision: str, values: dict):
        self.refresh()
        if revision != self.revision:
            raise ValueError("Les données ont changé. Recharge la page avant de décider.")
        kind, item = self.current()
        if not item:
            raise ValueError("Aucune entrée à traiter")
        key = item["key"]
        ids = [item["local_id"]] if kind == "issue" else [item["left_id"], item["right_id"]]
        if action == "later":
            # Rotate deferred entries too; a deferred issue still blocks finalization.
            self.state["deferred"] = [k for k in self.state["deferred"] if k != key] + [key]
        elif action == "accept" and kind == "issue":
            if not values.get("note", "").strip():
                raise ValueError("Indique pourquoi tu acceptes ce signalement.")
            self.state["accepted"].append(key)
        elif action == "distinct" and kind == "pair":
            self.state["distinct"].append(key)
        elif action in {"keep_left", "keep_right"} and kind == "pair":
            keep, remove = ids if action == "keep_left" else ids[::-1]
            merge_walls(keep, [remove], True, self.db, self.root)
            self.state["merged"][str(remove)] = keep
        elif action in {"edit", "metadata"}:
            local_id = int(values["local_id"])
            if local_id not in ids or local_id not in self.rows:
                raise ValueError("Ce mur ne fait pas partie de l'entrée affichée")
            row = self.rows[local_id]
            changes = {field: values[field].strip() or None for field in ("page_url", "status", "problem")
                       if field in values and (values[field].strip() or None) != (row.get(field) or None)}
            if "status" in changes and not changes["status"]:
                raise ValueError("Le statut ne peut pas être vide")
            urls = {}
            for role in ROLES:
                url = values.get(role, "").strip()
                if not url:
                    continue
                try:
                    valid_path = bool(row.get(role + "_image_path")) and wall_path(
                        row[role + "_image_path"], role, self.root, local_id).is_file()
                except ValueError:
                    valid_path = False
                if url != row.get(role + "_image_url") or not valid_path or values.get("reload_" + role):
                    urls[role] = url
            fix_wall(local_id, changes, urls, action == "metadata", self.db, self.root)
        elif action == "delete_orphan" and kind == "issue" and item["problem"] == "orphan_file":
            path = (self.root / item["path"]).resolve()
            if path.parent not in {self.root / "images/walls" / r for r in ROLES}:
                raise ValueError("Le fichier ne se trouve pas dans un dossier de murs autorisé")
            # Current refresh confirms this file is still unreferenced.
            backup = backup_database(self.db, self.root, "wall_orphan")
            target = backup / item["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
            path.unlink()
        else:
            raise ValueError("Action non disponible pour cette entrée")
        self.state["history"].append(dict(action=action, ids=ids, key=key, note=values.get("note", "")))
        self.state["finalized"] = False
        self.save()
        self.refresh()
