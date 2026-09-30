"""Read-only catalogue/path/image validation; no automatic repairs."""
import sys
from pathlib import Path
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import argparse
from contextlib import closing
from collections import Counter, defaultdict
import csv
import re
from PIL import Image
from scripts.paths import PROJECT_ROOT, connect_readonly

ROLES = ("inventory", "world", "color")


def validate(rows: list[dict], root: Path = PROJECT_ROOT, object_type: str = "all") -> list[dict]:
    issues = []
    references = defaultdict(list)
    selected = [r for r in rows if object_type == "all" or r["object_type"] == object_type]

    def report(row, role, path, problem):
        issues.append(dict(object_type=row.get("object_type"), local_id=row.get("local_id"),
                           name=row.get("name"), role=role, path=path, problem=problem))

    for row in rows:
        for role in ROLES:
            value = row.get(role + "_image_path")
            if value:
                references[(root / value.replace("\\", "/")).resolve()].append((row, role))
    for row in selected:
        if row["object_type"] not in {"wall", "block"} or row["is_wall"] != int(row["object_type"] == "wall"):
            report(row, "", "", "object_type_is_wall_mismatch")
        for role in ROLES:
            value = row.get(role + "_image_path")
            if not value:
                report(row, role, "", "missing_path")
                continue
            path = (root / value.replace("\\", "/")).resolve()
            expected = root.resolve() / "images" / ("walls/" + role if row["object_type"] == "wall" else role)
            if path.parent != expected:
                report(row, role, value, "wrong_directory_or_object_type")
                continue  # Do not follow database paths outside the expected tree.
            if not path.stem.endswith("_" + role):
                report(row, role, value, "wrong_role_suffix")
            if not re.match(rf"^{row['local_id']}_", path.name):
                report(row, role, value, "filename_local_id_mismatch")
            if not path.is_file():
                report(row, role, value, "file_missing")
            else:
                try:
                    with Image.open(path) as image:
                        image.verify()
                except (OSError, ValueError) as error:
                    report(row, role, value, "invalid_image: " + str(error))
            if len(references[path]) > 1:
                report(row, role, value, "duplicated_path")
    for kind in ("block", "wall") if object_type == "all" else (object_type,):
        for role in ROLES:
            folder = root / "images" / ("walls/" + role if kind == "wall" else role)
            for path in folder.rglob("*"):
                if path.is_file() and path.name not in {".gitkeep", "README.md"} and path.resolve() not in references:
                    report({"object_type": kind}, role, path.relative_to(root).as_posix(), "orphan_file")
    return issues


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--type", choices=("block", "wall", "all"), default="all")
    parser.add_argument("--csv", type=Path, help="Optional report output (database/images remain read-only)")
    args = parser.parse_args(argv)
    with closing(connect_readonly()) as connection:
        rows = [dict(r) for r in connection.execute("SELECT * FROM objects ORDER BY local_id")]
    issues = validate(rows, object_type=args.type)
    print(f"Objects checked: {sum(args.type == 'all' or r['object_type'] == args.type for r in rows)}")
    print(f"Issues: {len(issues)}; {dict(Counter(i['problem'] for i in issues))}")
    for issue in issues:
        print(f"[{issue['local_id']}] {issue['name']} {issue['role']}: {issue['problem']} {issue['path']}")
    if args.csv:
        target = args.csv.resolve()
        # Reports must never overwrite catalogue/media/workbook files.
        target.relative_to((PROJECT_ROOT / "data/duplicates").resolve())
        if target.suffix.lower() != ".csv":
            raise ValueError("Report must be a CSV under data/duplicates/")
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=("object_type", "local_id", "name", "role", "path", "problem"))
            writer.writeheader()
            writer.writerows(issues)
        print("Report:", target)


if __name__ == "__main__":
    main()
