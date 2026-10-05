"""Build and load the production block HOG indexes."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

from scripts.paths import PROJECT_ROOT
from scripts.texture_signature.batch import (
    HogBatchResult,
    TextureSource,
    process_hog_textures,
    resolve_textures,
)
from scripts.texture_signature.config import (
    BLOCK_SIZE,
    HOG_BINS,
    HOG_CELL_SIZE,
    validate_edge_method,
)


INDEX_ROOT = PROJECT_ROOT / "data" / "sketch_search"


def block_hog_index_path(edge_method: str) -> Path:
    validate_edge_method(edge_method)
    return INDEX_ROOT / f"block_hog_{edge_method}.npz"


@dataclass(frozen=True)
class HogIndex:
    features: np.ndarray
    local_ids: np.ndarray
    names: np.ndarray
    image_paths: np.ndarray
    edge_method: str
    cell_size: int
    bins: int


def build_block_hog_index(
    *,
    path: Path | None = None,
    edge_method: str = "sobel",
    on_complete: Callable[[int, int, TextureSource], None] | None = None,
    on_skip: Callable[[int, int, TextureSource, tuple[int, int]], None] | None = None,
) -> tuple[HogIndex, HogBatchResult]:
    """Build and save signatures for every eligible 48x48 block texture."""
    validate_edge_method(edge_method)
    path = path or block_hog_index_path(edge_method)
    textures = resolve_textures("block")
    result = process_hog_textures(
        textures,
        edge_method=edge_method,
        skip_ineligible=True,
        on_complete=on_complete,
        on_skip=on_skip,
    )
    eligible = [item for item in textures if item.local_id in result.signatures]
    features = np.stack([result.signatures[item.local_id] for item in eligible]).astype(np.float32)
    index = HogIndex(
        features=features,
        local_ids=np.asarray([item.local_id for item in eligible], dtype=np.int64),
        names=np.asarray([item.name for item in eligible], dtype=np.str_),
        image_paths=np.asarray(
            [item.image_path.relative_to(PROJECT_ROOT).as_posix() for item in eligible],
            dtype=np.str_,
        ),
        edge_method=edge_method,
        cell_size=HOG_CELL_SIZE,
        bins=HOG_BINS,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        features=index.features,
        local_ids=index.local_ids,
        names=index.names,
        image_paths=index.image_paths,
        edge_method=np.asarray(index.edge_method, dtype=np.str_),
        cell_size=np.asarray(index.cell_size, dtype=np.int64),
        bins=np.asarray(index.bins, dtype=np.int64),
        feature_dimension=np.asarray(index.features.shape[1], dtype=np.int64),
    )
    return index, result


def load_block_hog_index(
    edge_method: str = "sobel",
    path: Path | None = None,
) -> HogIndex:
    """Load a production index without allowing pickled objects."""
    validate_edge_method(edge_method)
    path = path or block_hog_index_path(edge_method)
    if not path.is_file():
        raise FileNotFoundError(path)
    with np.load(path, allow_pickle=False) as data:
        index = HogIndex(
            features=np.asarray(data["features"], dtype=np.float32),
            local_ids=np.asarray(data["local_ids"], dtype=np.int64),
            names=np.asarray(data["names"], dtype=np.str_),
            image_paths=np.asarray(data["image_paths"], dtype=np.str_),
            edge_method=str(data["edge_method"]),
            cell_size=int(data["cell_size"]),
            bins=int(data["bins"]),
        )
    count = len(index.features)
    if index.features.ndim != 2 or not (
        len(index.local_ids) == len(index.names) == len(index.image_paths) == count
    ):
        raise ValueError("Invalid HOG block index.")
    expected_features = (BLOCK_SIZE[0] // HOG_CELL_SIZE) ** 2 * HOG_BINS
    if (
        index.edge_method != edge_method
        or index.cell_size != HOG_CELL_SIZE
        or index.bins != HOG_BINS
        or index.features.shape[1] != expected_features
    ):
        raise ValueError(
            "HOG index configuration is incompatible. Rebuild the index."
        )
    return index
