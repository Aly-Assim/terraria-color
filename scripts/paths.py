"""Repository paths shared by the website and command-line tools."""
from pathlib import Path
import sqlite3

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "terraria_blocks.db"
IMAGES_ROOT = PROJECT_ROOT / "images"
PAINTED_ROOT = IMAGES_ROOT / "painted"


def connect_readonly(path: Path = DB_PATH) -> sqlite3.Connection:
    """Open an existing database without creating or modifying it."""
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def protect_curated_release() -> None:
    """Historical acquisition tools must not overwrite this curated release."""
    raise RuntimeError(
        "This historical tool replaces curated images or object IDs and is disabled "
        "for the public dataset. See docs/maintenance.md."
    )
