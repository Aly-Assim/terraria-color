"""Apply OpenCV's Canny detector to an 8-bit grayscale image."""

import cv2
import numpy as np
from PIL import Image

from scripts.texture_signature.config import CANNY_HIGH_THRESHOLD, CANNY_LOW_THRESHOLD


def detect_canny_edges(
    grayscale: Image.Image,
    *,
    low_threshold: int = CANNY_LOW_THRESHOLD,
    high_threshold: int = CANNY_HIGH_THRESHOLD,
) -> np.ndarray:
    pixels = np.asarray(grayscale, dtype=np.uint8)
    return cv2.Canny(pixels, low_threshold, high_threshold)
