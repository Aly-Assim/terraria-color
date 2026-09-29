"""Run all non-destructive checks without a third-party test runner."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests import test_dataset, test_renderer, test_site


if __name__ == "__main__":
    if test_renderer.main():
        raise SystemExit(1)
    test_site.main()
    test_dataset.main()
