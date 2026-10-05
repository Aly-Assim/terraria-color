"""Fixed production configuration for Sketch Search."""

BLOCK_SIZE = (48, 48)
HOG_CELL_SIZE = 12
HOG_BINS = 9
EDGE_METHODS = ("sobel", "canny")
CANNY_LOW_THRESHOLD = 50
CANNY_HIGH_THRESHOLD = 150


def validate_edge_method(edge_method: str) -> str:
    if edge_method not in EDGE_METHODS:
        raise ValueError("Edge method must be 'sobel' or 'canny'.")
    return edge_method
