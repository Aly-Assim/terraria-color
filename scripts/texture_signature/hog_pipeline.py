"""Extract the fixed Sketch Search HOG feature for one texture."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from scripts.texture_signature.debug_output import save_hog_outputs
from scripts.texture_signature.canny_edges import detect_canny_edges
from scripts.texture_signature.config import (
    HOG_BINS,
    HOG_CELL_SIZE,
    validate_edge_method,
)
from scripts.texture_signature.eligibility import (
    ineligible_texture_message,
    is_sketch_search_eligible,
)
from scripts.texture_signature.gradient_magnitude import gradient_magnitude
from scripts.texture_signature.gradient_orientation import gradient_magnitude_and_orientation
from scripts.texture_signature.grayscale import to_grayscale
from scripts.texture_signature.hog_histogram import build_hog_histograms
from scripts.texture_signature.hog_visualization import visualize_hog
from scripts.texture_signature.sobel_x import sobel_x
from scripts.texture_signature.sobel_y import sobel_y


@dataclass(frozen=True)
class HogAnalysis:
    signature: np.ndarray
    visualization: Image.Image | None
    canny_edges: Image.Image | None = None


def analyze_hog_texture(
    source: str | Path | Image.Image,
    *,
    edge_method: str = "sobel",
    debug: bool = False,
    debug_name: str | None = None,
    object_type: str,
    include_visualization: bool = False,
) -> HogAnalysis:
    """Return both the numeric HOG signature and its visualization."""
    validate_edge_method(edge_method)
    if isinstance(source, Image.Image):
        original = source.copy()
        inferred_name = "texture"
    else:
        path = Path(source)
        with Image.open(path) as image:
            original = image.copy()
        inferred_name = path.stem

    name = debug_name or inferred_name
    if not is_sketch_search_eligible(object_type, original.size):
        raise ValueError(ineligible_texture_message(name, object_type, original.size))

    grayscale = to_grayscale(original)
    canny_array = None
    if edge_method == "canny":
        canny_array = detect_canny_edges(grayscale)
        edge_image = Image.fromarray(canny_array, mode="L")
        gx = sobel_x(edge_image)
        gy = sobel_y(edge_image)
    else:
        gx = sobel_x(grayscale)
        gy = sobel_y(grayscale)
    magnitude, orientation = gradient_magnitude_and_orientation(gx, gy)
    histograms = build_hog_histograms(
        magnitude,
        orientation,
        cell_size=HOG_CELL_SIZE,
        bins=HOG_BINS,
    )
    visualization = (
        visualize_hog(histograms, cell_size=HOG_CELL_SIZE)
        if debug or include_visualization else None
    )

    if debug:
        save_hog_outputs(
            object_type=object_type,
            name=name,
            original=original,
            grayscale=grayscale,
            gx=gx,
            gy=gy,
            magnitude=gradient_magnitude(gx, gy),
            canny_edges=(Image.fromarray(canny_array, mode="L") if canny_array is not None else None),
            visualization=visualization,
            edge_method=edge_method,
        )

    return HogAnalysis(
        histograms.ravel(),
        visualization,
        Image.fromarray(canny_array, mode="L") if canny_array is not None else None,
    )


def process_hog_texture(
    source: str | Path | Image.Image,
    *,
    edge_method: str = "sobel",
    debug: bool = False,
    debug_name: str | None = None,
    object_type: str,
) -> np.ndarray:
    """Return a flattened HOG signature while preserving the existing API."""
    return analyze_hog_texture(
        source,
        edge_method=edge_method,
        debug=debug,
        debug_name=debug_name,
        object_type=object_type,
    ).signature


def extract_hog_feature(
    source: str | Path | Image.Image,
    *,
    edge_method: str = "sobel",
    object_type: str = "block",
) -> np.ndarray:
    """Extract the fixed production HOG feature for one eligible texture."""
    return process_hog_texture(
        source,
        edge_method=edge_method,
        object_type=object_type,
    )
