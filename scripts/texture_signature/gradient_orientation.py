"""Calculate gradient strength and direction for HOG."""

import numpy as np


def gradient_magnitude_and_orientation(
    gx: np.ndarray,
    gy: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Return magnitude and unsigned orientation in the range [0, 180)."""
    if gx.shape != gy.shape:
        raise ValueError("Gx and Gy must have the same shape.")
    magnitude = np.hypot(gx, gy)
    # Unsigned HOG treats opposite gradient directions as the same orientation.
    orientation = np.mod(np.degrees(np.arctan2(gy, gx)), 180.0)
    return magnitude, orientation
