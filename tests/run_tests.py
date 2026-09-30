"""Run all non-destructive checks without a third-party test runner."""
from pathlib import Path
import sys
import argparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests import test_dataset, test_renderer, test_site, test_walls


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--maintenance", action="store_true", help="Also run isolated importer/tool tests (optional dependencies)")
    args = parser.parse_args()
    if test_renderer.main():
        raise SystemExit(1)
    test_site.main()
    test_walls.main()
    test_dataset.main()
    if args.maintenance:
        from tests import test_wall_import, test_wall_review
        test_wall_import.main()
        test_wall_review.main()
