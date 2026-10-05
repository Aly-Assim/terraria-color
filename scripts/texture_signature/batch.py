"""Resolve and process multiple catalog textures."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
from PIL import Image

from scripts.catalog import world_source_path
from scripts.paths import connect_readonly
from scripts.texture_signature.eligibility import (
    ineligible_texture_message,
    is_sketch_search_eligible,
)
from scripts.texture_signature.hog_pipeline import process_hog_texture


class TextureBatchError(ValueError):
    """A readable catalog or batch validation error."""


@dataclass(frozen=True)
class TextureSource:
    local_id: int
    name: str
    object_type: str
    image_path: Path


@dataclass(frozen=True)
class HogBatchResult:
    signatures: dict[int, np.ndarray]
    skipped: tuple[tuple[TextureSource, tuple[int, int]], ...]


def _catalog_sources(object_type: str) -> list[TextureSource]:
    if object_type not in {"block", "wall"}:
        raise TextureBatchError("Type must be 'block' or 'wall'.")
    with connect_readonly() as connection:
        rows = connection.execute(
            "SELECT local_id, name, object_type, world_image_path "
            "FROM objects WHERE object_type = ? ORDER BY local_id",
            (object_type,),
        ).fetchall()

    sources = []
    for row in rows:
        try:
            path = world_source_path(row)
        except (TypeError, ValueError) as error:
            raise TextureBatchError(f"Invalid world image for {row['name']}: {error}") from error
        sources.append(TextureSource(row["local_id"], row["name"], object_type, path))
    return sources


def resolve_textures(
    object_type: str,
    names: Iterable[str] | None = None,
) -> list[TextureSource]:
    """Resolve all textures or validate every requested name before processing."""
    catalog = _catalog_sources(object_type)
    requested = [name.strip() for name in names or [] if name.strip()]
    if names is None:
        selected = catalog
    else:
        if not requested:
            raise TextureBatchError("Select at least one material.")
        by_name = {item.name.casefold(): item for item in catalog}
        missing = [name for name in requested if name.casefold() not in by_name]
        if missing:
            raise TextureBatchError("Material not found: " + ", ".join(missing))
        selected = [by_name[name.casefold()] for name in requested]

    missing_images = [item.name for item in selected if not item.image_path.is_file()]
    if missing_images:
        raise TextureBatchError("World image missing: " + ", ".join(missing_images))
    return selected


def process_hog_textures(
    textures: Iterable[TextureSource],
    *,
    edge_method: str = "sobel",
    debug: bool = False,
    skip_ineligible: bool = False,
    on_complete: Callable[[int, int, TextureSource], None] | None = None,
    on_skip: Callable[[int, int, TextureSource, tuple[int, int]], None] | None = None,
) -> HogBatchResult:
    """Build an in-memory HOG signature for every resolved texture."""
    items = list(textures)
    sizes = []
    for item in items:
        try:
            with Image.open(item.image_path) as image:
                sizes.append(image.size)
        except Exception as error:
            raise TextureBatchError(f"Cannot read image for {item.name}: {error}") from error

    ineligible = [
        (item, size)
        for item, size in zip(items, sizes)
        if not is_sketch_search_eligible(item.object_type, size)
    ]
    if ineligible and not skip_ineligible:
        item, size = ineligible[0]
        raise TextureBatchError(ineligible_texture_message(item.name, item.object_type, size))

    signatures = {}
    skipped = []
    for index, (item, size) in enumerate(zip(items, sizes), start=1):
        if not is_sketch_search_eligible(item.object_type, size):
            skipped.append((item, size))
            if on_skip:
                on_skip(index, len(items), item, size)
            continue
        try:
            signatures[item.local_id] = process_hog_texture(
                item.image_path,
                edge_method=edge_method,
                debug=debug,
                debug_name=item.name,
                object_type=item.object_type,
            )
        except Exception as error:
            raise TextureBatchError(f"Failed to process HOG for {item.name}: {error}") from error
        if on_complete:
            on_complete(index, len(items), item)
    return HogBatchResult(signatures, tuple(skipped))
