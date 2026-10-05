"""Summarize local gradient orientations in regular HOG cells."""

import numpy as np

from scripts.texture_signature.config import HOG_BINS, HOG_CELL_SIZE


def build_hog_histograms(
    magnitude: np.ndarray,
    orientation: np.ndarray,
    *,
    cell_size: int = HOG_CELL_SIZE,
    bins: int = HOG_BINS,
) -> np.ndarray:
    """Return L2-normalized histograms shaped (cell rows, cell columns, bins)."""
    if magnitude.shape != orientation.shape or magnitude.ndim != 2:
        raise ValueError("Magnitude and orientation must be matching 2D arrays.")
    if cell_size < 1 or bins < 1:
        raise ValueError("Cell size and bin count must be positive.")
    height, width = magnitude.shape
    if height % cell_size or width % cell_size:
        raise ValueError(
            f"Image size {width}x{height} is not divisible by cell size {cell_size}."
        )

    histograms = np.zeros((height // cell_size, width // cell_size, bins), dtype=np.float32)
    bin_width = 180.0 / bins
    for row in range(histograms.shape[0]):
        for column in range(histograms.shape[1]):
            y = slice(row * cell_size, (row + 1) * cell_size)
            x = slice(column * cell_size, (column + 1) * cell_size)
            positions = orientation[y, x] / bin_width
            lower = np.floor(positions).astype(np.int32) % bins
            fraction = positions - np.floor(positions)
            weights = magnitude[y, x]
            histogram = histograms[row, column]
            np.add.at(histogram, lower.ravel(), (weights * (1.0 - fraction)).ravel())
            np.add.at(histogram, ((lower + 1) % bins).ravel(), (weights * fraction).ravel())
            norm = float(np.linalg.norm(histogram))
            if norm > 0:
                histogram /= norm
    return histograms
