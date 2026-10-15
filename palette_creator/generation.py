"""Color palette generation utilities."""

from __future__ import annotations

import random
import re

from palette_creator.oklab import oklab_to_rgb, rgb_to_oklab


HEX_COLOR_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")
# Working a/b square, not a promise that its samples are in the sRGB gamut.
COMPLEMENTARY_AXIS_LIMIT = 0.4
AUGMENTATION_MAX_SPAN = 0.15


def generate_random_hex_color() -> str:
    """Return a random color encoded as #RRGGBB."""
    return f"#{random.randint(0, 0xFFFFFF):06x}"


def normalize_hex_color(color: str) -> str:
    """Normalize a hexadecimal color to #rrggbb."""
    match = HEX_COLOR_RE.match(color)
    if match is None:
        raise ValueError("Color must be encoded as hexadecimal #RRGGBB, for example #336699.")

    return f"#{match.group(1).lower()}"


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    """Convert a #RRGGBB color to integer RGB components."""
    value = normalize_hex_color(color)[1:]
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    """Convert integer RGB components to #RRGGBB."""
    red, green, blue = rgb
    return f"#{red:02x}{green:02x}{blue:02x}"


def _float_rgb_to_hex(rgb: tuple[float, float, float]) -> str:
    return rgb_to_hex(tuple(round(channel * 255) for channel in rgb))


def generate_palette(
    seed_color: str | None = None,
    lightness_step: float = 0.0,
    green_red_step: float = 0.0,
    blue_yellow_step: float = 0.0,
    palette_size: int = 5,
    mode: str = "analogous",
) -> list[str]:
    """Generate an analogous ramp or a random complementary line in OKlab.

    Complementary mode uses only the seed's lightness and ignores steps.
    Its N samples are the interior boundaries of N + 1 equal segments.
    """
    if palette_size < 1:
        raise ValueError("Palette size must be at least 1.")
    if mode not in ("analogous", "complementary"):
        raise ValueError(f"Unknown palette mode: {mode}")
    if seed_color is None:
        seed_color = generate_random_hex_color()

    red, green, blue = hex_to_rgb(seed_color)
    lightness, green_red, blue_yellow = rgb_to_oklab((red / 255, green / 255, blue / 255))

    if mode == "complementary":
        x_axis = random.choice(("a", "b"))
        slope = random.uniform(-1.0, 1.0)
        # In normalized coordinates, y = slope*x + origin for x in [-1, 1].
        # Restrict the origin so the whole line stays inside the working square.
        origin_limit = 1.0 - abs(slope)
        origin = random.uniform(-origin_limit, origin_limit)
        colors = []
        for index in range(1, palette_size + 1):
            x = -1 + 2 * index / (palette_size + 1)
            y = slope * x + origin
            a, b = (x, y) if x_axis == "a" else (y, x)
            colors.append(_float_rgb_to_hex(oklab_to_rgb((
                lightness, a * COMPLEMENTARY_AXIS_LIMIT, b * COMPLEMENTARY_AXIS_LIMIT,
            ))))
        return colors

    span_offset = (palette_size - 1) / 2
    oklab_values = [
        (
            lightness + (index - span_offset) * lightness_step,
            green_red + (index - span_offset) * green_red_step,
            blue_yellow + (index - span_offset) * blue_yellow_step,
        )
        for index in range(palette_size)
    ]

    return [_float_rgb_to_hex(oklab_to_rgb(value)) for value in oklab_values]


def augment_palette(
    colors: list[str] | tuple[str, ...],
    factor: int,
    lightness_step: float | None = None,
    green_red_step: float | None = None,
    blue_yellow_step: float | None = None,
) -> tuple[list[str], tuple[float, float, float]]:
    """Expand every source color into one coherent analogous sub-palette.

    Missing steps are sampled once for the whole operation. Their range is
    scaled by the factor so the span of each sub-palette remains bounded.
    """
    if factor < 1:
        raise ValueError("Augmentation factor must be at least 1.")
    if not colors:
        raise ValueError("Palette must contain at least one color.")
    normalized_colors = [normalize_hex_color(color) for color in colors]
    maximum_step = AUGMENTATION_MAX_SPAN / max(factor - 1, 1)
    steps = tuple(
        value if value is not None else random.uniform(-maximum_step, maximum_step)
        for value in (lightness_step, green_red_step, blue_yellow_step)
    )
    augmented = []
    for color in normalized_colors:
        augmented.extend(
            generate_palette(
                seed_color=color,
                lightness_step=steps[0],
                green_red_step=steps[1],
                blue_yellow_step=steps[2],
                palette_size=factor,
                mode="analogous",
            )
        )
    return augmented, steps
