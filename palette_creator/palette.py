"""Palette data model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Pallette:
    """Validated palette colors and size metadata."""

    palette_size: int
    colors: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.palette_size, int):
            raise ValueError("Palette must contain an integer palette_size.")
        if self.palette_size < 1:
            raise ValueError("Palette size must be at least 1.")
        if not isinstance(self.colors, (list, tuple)):
            raise ValueError("Palette must contain a colors sequence.")
        object.__setattr__(self, "colors", tuple(self.colors))
        if not all(isinstance(color, str) for color in self.colors):
            raise ValueError("Palette must contain encoded color strings.")
        if len(self.colors) != self.palette_size:
            raise ValueError(f"Palette contains {len(self.colors)} colors, but palette size is {self.palette_size}.")

    @classmethod
    def from_json_data(cls, data: object) -> "Pallette":
        if not isinstance(data, dict):
            raise ValueError("Palette JSON must contain an object.")

        colors = data.get("colors")
        if not isinstance(colors, list) or not all(isinstance(color, str) for color in colors):
            raise ValueError("Palette JSON must contain a colors array of encoded color strings.")

        palette_size = data.get("palette_size")
        if not isinstance(palette_size, int):
            raise ValueError("Palette JSON must contain an integer palette_size.")

        return cls(palette_size=palette_size, colors=tuple(colors))
