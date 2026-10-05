"""Write optional intermediate images for visual inspection."""

from pathlib import Path
import re
import unicodedata

import numpy as np
from PIL import Image

from scripts.paths import PROJECT_ROOT


DEBUG_ROOT = PROJECT_ROOT / "debug" / "texture_signature"


def safe_debug_name(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_name.casefold()).strip("_")
    return slug or "texture"


def _signed_gradient_image(values: np.ndarray) -> Image.Image:
    maximum = float(np.max(np.abs(values))) if values.size else 0.0
    visible = values / maximum * 127.0 + 128.0 if maximum > 0 else values
    return Image.fromarray(np.clip(visible, 0, 255).astype(np.uint8), mode="L")


def save_hog_outputs(
    *,
    object_type: str,
    name: str,
    original: Image.Image,
    grayscale: Image.Image,
    gx: np.ndarray,
    gy: np.ndarray,
    magnitude: Image.Image,
    canny_edges: Image.Image | None,
    visualization: Image.Image,
    edge_method: str,
) -> Path:
    """Save the final Sobel or Canny pipeline stages on explicit request."""
    output = DEBUG_ROOT / object_type / safe_debug_name(name) / edge_method
    output.mkdir(parents=True, exist_ok=True)
    for old_stage in output.glob("[0-9][0-9]_*.png"):
        old_stage.unlink()
    if edge_method == "canny":
        stages = [
            ("00_original.png", original),
            ("01_grayscale.png", grayscale),
            ("02_canny_edges.png", canny_edges),
            ("03_canny_sobel_x.png", _signed_gradient_image(gx)),
            ("04_canny_sobel_y.png", _signed_gradient_image(gy)),
            ("05_canny_gradient_magnitude.png", magnitude),
            ("06_hog_visualization.png", visualization),
        ]
    else:
        stages = [
            ("00_original.png", original),
            ("01_grayscale.png", grayscale),
            ("02_sobel_x.png", _signed_gradient_image(gx)),
            ("03_sobel_y.png", _signed_gradient_image(gy)),
            ("04_gradient_magnitude.png", magnitude),
            ("05_hog_visualization.png", visualization),
        ]
    for filename, image in stages:
        if image is None:
            raise ValueError(f"Missing debug image: {filename}")
        image.save(output / filename, format="PNG")
    return output
