"""Measure vertical image gradients with the Sobel Y kernel."""

import numpy as np
from PIL import Image


SOBEL_Y_KERNEL = np.array(
    [[-1, -2, -1], [0, 0, 0], [1, 2, 1]],
    dtype=np.float32,
)


def sobel_y(image: Image.Image | np.ndarray) -> np.ndarray:
    """Return Gy as a float array with the same width and height."""
    pixels = np.asarray(image, dtype=np.float32)
    if pixels.ndim != 2:
        raise ValueError("Sobel Y expects a two-dimensional grayscale image.")
    # Reflect padding avoids introducing a dark frame around the texture.
    padded = np.pad(pixels, 1, mode="reflect")
    windows = np.lib.stride_tricks.sliding_window_view(padded, (3, 3))
    return np.einsum("ijkl,kl->ij", windows, SOBEL_Y_KERNEL)
