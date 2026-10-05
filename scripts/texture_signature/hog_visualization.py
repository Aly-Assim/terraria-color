"""Render HOG cell histograms as orientation lines."""

import math

import numpy as np
from PIL import Image, ImageDraw

from scripts.texture_signature.config import HOG_CELL_SIZE


def visualize_hog(histograms: np.ndarray, *, cell_size: int = HOG_CELL_SIZE) -> Image.Image:
    """Draw one short line per orientation bin in every HOG cell."""
    if histograms.ndim != 3:
        raise ValueError("HOG histograms must have three dimensions.")
    rows, columns, bins = histograms.shape
    output = Image.new("L", (columns * cell_size, rows * cell_size), 0)
    draw = ImageDraw.Draw(output)
    for row in range(rows):
        for column in range(columns):
            histogram = histograms[row, column]
            maximum = float(histogram.max())
            if maximum <= 0:
                continue
            center_x = column * cell_size + cell_size / 2
            center_y = row * cell_size + cell_size / 2
            for index, strength in enumerate(histogram):
                relative = float(strength) / maximum
                if relative <= 0:
                    continue
                angle = math.radians((index + 0.5) * 180.0 / bins)
                half_length = cell_size * 0.45 * relative
                dx = math.cos(angle) * half_length
                dy = math.sin(angle) * half_length
                draw.line(
                    (center_x - dx, center_y - dy, center_x + dx, center_y + dy),
                    fill=max(1, round(255 * relative)),
                    width=1,
                )
    return output
