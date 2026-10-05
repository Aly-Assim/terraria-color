"""Combine horizontal and vertical gradients into an edge map."""

import numpy as np
from PIL import Image


def gradient_magnitude(gx: np.ndarray, gy: np.ndarray) -> Image.Image:
    """Return sqrt(Gx² + Gy²), normalized to a visualizable 8-bit image."""
    if gx.shape != gy.shape:
        raise ValueError("Gx and Gy must have the same shape.")
    magnitude = np.hypot(gx, gy)
    maximum = float(magnitude.max()) if magnitude.size else 0.0
    normalized = magnitude / maximum * 255.0 if maximum > 0 else magnitude
    return Image.fromarray(np.clip(normalized, 0, 255).astype(np.uint8), mode="L")
