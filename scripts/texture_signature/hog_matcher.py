"""Cosine nearest-neighbour matching for Sketch Search HOG signatures."""

from dataclasses import dataclass

import numpy as np

from scripts.texture_signature.hog_index import HogIndex


@dataclass(frozen=True)
class HogMatch:
    local_id: int
    name: str
    image_path: str
    similarity: float


def match_hog_signature(signature: np.ndarray, index: HogIndex, *, k: int = 10) -> list[HogMatch]:
    """Return the K index rows with the highest cosine similarity."""
    query = np.asarray(signature, dtype=np.float32).ravel()
    if k < 1:
        raise ValueError("K must be at least 1.")
    if index.features.shape[1] != query.size:
        raise ValueError("Sketch signature size does not match the HOG index.")
    query_norm = float(np.linalg.norm(query))
    if query_norm <= 1e-8:
        raise ValueError("Draw something before searching.")

    feature_norms = np.linalg.norm(index.features, axis=1)
    denominator = feature_norms * query_norm
    similarities = np.divide(
        index.features @ query,
        denominator,
        out=np.zeros_like(feature_norms, dtype=np.float32),
        where=denominator > 1e-8,
    )
    order = np.argsort(-similarities, kind="stable")[: min(k, len(similarities))]
    return [
        HogMatch(
            local_id=int(index.local_ids[position]),
            name=str(index.names[position]),
            image_path=str(index.image_paths[position]),
            similarity=float(np.clip(similarities[position], 0.0, 1.0)),
        )
        for position in order
    ]
