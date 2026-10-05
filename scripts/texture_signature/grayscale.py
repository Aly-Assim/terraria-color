"""Convert a color image to grayscale."""

from PIL import Image


def to_grayscale(image: Image.Image) -> Image.Image:
    """Return a new 8-bit grayscale image without changing the source."""
    return image.convert("L")
