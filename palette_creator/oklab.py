"""OKlab color conversion utilities."""

from __future__ import annotations

import numpy as np


def clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return min(max(value, lower), upper)


def srgb_to_linear(channel: float) -> float:
    if channel <= 0.04045:
        return channel / 12.92

    return ((channel + 0.055) / 1.055) ** 2.4


def linear_to_srgb(channel: float) -> float:
    if channel <= 0.0031308:
        return 12.92 * channel

    return 1.055 * channel ** (1 / 2.4) - 0.055


def rgb_to_oklab(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    """Convert one sRGB color in the [0, 1] range to OKlab."""
    red, green, blue = (srgb_to_linear(channel) for channel in rgb)

    long_cone = 0.4122214708 * red + 0.5363325363 * green + 0.0514459929 * blue
    medium_cone = 0.2119034982 * red + 0.6806995451 * green + 0.1073969566 * blue
    short_cone = 0.0883024619 * red + 0.2817188376 * green + 0.6299787005 * blue

    long_cone_root = long_cone ** (1 / 3)
    medium_cone_root = medium_cone ** (1 / 3)
    short_cone_root = short_cone ** (1 / 3)

    lightness = (
        0.2104542553 * long_cone_root
        + 0.7936177850 * medium_cone_root
        - 0.0040720468 * short_cone_root
    )
    green_red = (
        1.9779984951 * long_cone_root
        - 2.4285922050 * medium_cone_root
        + 0.4505937099 * short_cone_root
    )
    blue_yellow = (
        0.0259040371 * long_cone_root
        + 0.7827717662 * medium_cone_root
        - 0.8086757660 * short_cone_root
    )

    return lightness, green_red, blue_yellow


def oklab_to_rgb(oklab: tuple[float, float, float]) -> tuple[float, float, float]:
    """Convert one OKlab color to clamped sRGB values in the [0, 1] range."""
    lightness, green_red, blue_yellow = oklab

    long_cone_root = lightness + 0.3963377774 * green_red + 0.2158037573 * blue_yellow
    medium_cone_root = lightness - 0.1055613458 * green_red - 0.0638541728 * blue_yellow
    short_cone_root = lightness - 0.0894841775 * green_red - 1.2914855480 * blue_yellow

    long_cone = long_cone_root**3
    medium_cone = medium_cone_root**3
    short_cone = short_cone_root**3

    linear_red = 4.0767416621 * long_cone - 3.3077115913 * medium_cone + 0.2309699292 * short_cone
    linear_green = -1.2684380046 * long_cone + 2.6097574011 * medium_cone - 0.3413193965 * short_cone
    linear_blue = -0.0041960863 * long_cone - 0.7034186147 * medium_cone + 1.7076147010 * short_cone

    return (
        clamp(linear_to_srgb(clamp(linear_red))),
        clamp(linear_to_srgb(clamp(linear_green))),
        clamp(linear_to_srgb(clamp(linear_blue))),
    )


def rgb_array_to_oklab(rgb_values: np.ndarray) -> np.ndarray:
    """Convert an array of sRGB values in the [0, 1] range to OKlab points."""
    linear_rgb = np.where(
        rgb_values <= 0.04045,
        rgb_values / 12.92,
        ((rgb_values + 0.055) / 1.055) ** 2.4,
    )

    red = linear_rgb[:, :, 0]
    green = linear_rgb[:, :, 1]
    blue = linear_rgb[:, :, 2]

    long_cone = 0.4122214708 * red + 0.5363325363 * green + 0.0514459929 * blue
    medium_cone = 0.2119034982 * red + 0.6806995451 * green + 0.1073969566 * blue
    short_cone = 0.0883024619 * red + 0.2817188376 * green + 0.6299787005 * blue

    long_cone_root = np.cbrt(long_cone)
    medium_cone_root = np.cbrt(medium_cone)
    short_cone_root = np.cbrt(short_cone)

    lightness = (
        0.2104542553 * long_cone_root
        + 0.7936177850 * medium_cone_root
        - 0.0040720468 * short_cone_root
    )
    green_red = (
        1.9779984951 * long_cone_root
        - 2.4285922050 * medium_cone_root
        + 0.4505937099 * short_cone_root
    )
    blue_yellow = (
        0.0259040371 * long_cone_root
        + 0.7827717662 * medium_cone_root
        - 0.8086757660 * short_cone_root
    )

    return np.stack((lightness, green_red, blue_yellow), axis=2)
