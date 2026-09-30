"""Shared block/wall conventions; local IDs remain unique across both types."""
from pathlib import Path

from scripts.paths import IMAGES_ROOT, PROJECT_ROOT

OBJECT_TYPES = {"all": "Tous", "block": "Blocs", "wall": "Murs"}


def normalize_object_type(value: str) -> str:
    return value if value in OBJECT_TYPES else "all"


def world_source_path(obj) -> Path:
    """Resolve a placed texture within the appropriate type's source directory."""
    kind = obj["object_type"]
    if kind not in {"block", "wall"}:
        raise ValueError(f"Unsupported object type: {kind!r}")
    source = obj["world_image_path"]
    if not source:
        raise ValueError("No world image path")
    path = (PROJECT_ROOT / source.replace("\\", "/")).resolve()
    directory = IMAGES_ROOT / "world" if kind == "block" else IMAGES_ROOT / "walls" / "world"
    path.relative_to(directory.resolve())
    return path


def painted_folder(obj) -> Path:
    """Keep existing block URLs; namespace wall exports to avoid collisions."""
    stem = world_source_path(obj).stem
    return Path("walls") / stem if obj["object_type"] == "wall" else Path(stem)
