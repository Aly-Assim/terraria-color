"""Eligibility rules for native-resolution Sketch Search textures."""


from scripts.texture_signature.config import BLOCK_SIZE


EXPECTED_TEXTURE_SIZES = {
    "block": BLOCK_SIZE,
    "wall": (64, 64),
}


def expected_texture_size(object_type: str) -> tuple[int, int]:
    try:
        return EXPECTED_TEXTURE_SIZES[object_type]
    except KeyError as error:
        raise ValueError("Object type must be 'block' or 'wall'.") from error


def is_sketch_search_eligible(object_type: str, size: tuple[int, int]) -> bool:
    """Return whether a texture already has the required logical resolution."""
    return tuple(size) == expected_texture_size(object_type)


def ineligible_texture_message(
    name: str,
    object_type: str,
    size: tuple[int, int],
) -> str:
    expected = expected_texture_size(object_type)
    return (
        f'Cannot process "{name}": expected {object_type} texture '
        f"{expected[0]}x{expected[1]}, got {size[0]}x{size[1]}."
    )
