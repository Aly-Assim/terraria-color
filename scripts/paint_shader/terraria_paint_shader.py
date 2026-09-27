from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import numpy as np
from PIL import Image, ImageDraw, ImageFont


PAINTS = {
    0: ("none", "None"),
    1: ("red", "Red"),
    2: ("orange", "Orange"),
    3: ("yellow", "Yellow"),
    4: ("lime", "Lime"),
    5: ("green", "Green"),
    6: ("teal", "Teal"),
    7: ("cyan", "Cyan"),
    8: ("sky_blue", "Sky Blue"),
    9: ("blue", "Blue"),
    10: ("purple", "Purple"),
    11: ("violet", "Violet"),
    12: ("pink", "Pink"),
    13: ("deep_red", "Deep Red"),
    14: ("deep_orange", "Deep Orange"),
    15: ("deep_yellow", "Deep Yellow"),
    16: ("deep_lime", "Deep Lime"),
    17: ("deep_green", "Deep Green"),
    18: ("deep_teal", "Deep Teal"),
    19: ("deep_cyan", "Deep Cyan"),
    20: ("deep_sky_blue", "Deep Sky Blue"),
    21: ("deep_blue", "Deep Blue"),
    22: ("deep_purple", "Deep Purple"),
    23: ("deep_violet", "Deep Violet"),
    24: ("deep_pink", "Deep Pink"),
    25: ("black", "Black"),
    26: ("white", "White"),
    27: ("gray", "Gray"),
    28: ("brown", "Brown"),
    29: ("shadow", "Shadow"),
    30: ("negative", "Negative"),
}

PAINT_NAME_TO_ID = {}
for paint_id, (slug, display_name) in PAINTS.items():
    aliases = {
        slug,
        display_name.lower(),
        display_name.lower().replace(" ", "_"),
        display_name.lower().replace(" ", "-"),
        str(paint_id),
    }
    for alias in aliases:
        PAINT_NAME_TO_ID[alias] = paint_id


def resolve_paint_id(value: int | str) -> int:
    if isinstance(value, int):
        paint_id = value
    else:
        key = value.strip().lower()
        if key not in PAINT_NAME_TO_ID:
            raise ValueError(f"Unknown paint: {value!r}")
        paint_id = PAINT_NAME_TO_ID[key]

    if paint_id not in PAINTS:
        raise ValueError(f"Paint ID must be between 0 and 30, got {paint_id}")
    return paint_id


def _normal_hue(maximum: np.ndarray, minimum: np.ndarray, paint_id: int) -> np.ndarray:
    midpoint = (maximum + minimum) * 0.5

    if paint_id == 1:
        return np.concatenate((maximum, minimum, minimum), axis=2)
    if paint_id == 2:
        return np.concatenate((maximum, midpoint, minimum), axis=2)
    if paint_id == 3:
        return np.concatenate((maximum, maximum, minimum), axis=2)
    if paint_id == 4:
        return np.concatenate((midpoint, maximum, minimum), axis=2)
    if paint_id == 5:
        return np.concatenate((minimum, maximum, minimum), axis=2)
    if paint_id == 6:
        return np.concatenate((minimum, maximum, midpoint), axis=2)
    if paint_id == 7:
        return np.concatenate((minimum, maximum, maximum), axis=2)
    if paint_id == 8:
        return np.concatenate((minimum, midpoint, maximum), axis=2)
    if paint_id == 9:
        return np.concatenate((minimum, minimum, maximum), axis=2)
    if paint_id == 10:
        return np.concatenate((midpoint, minimum, maximum), axis=2)
    if paint_id == 11:
        return np.concatenate((maximum, minimum, maximum), axis=2)
    if paint_id == 12:
        return np.concatenate((maximum, minimum, midpoint), axis=2)

    raise ValueError(f"Not a normal hue paint ID: {paint_id}")


def _deep_hue(maximum: np.ndarray, minimum: np.ndarray, paint_id: int) -> np.ndarray:
    deep_low = minimum * 0.4
    deep_mid = (maximum + deep_low) * 0.5
    index = paint_id - 12

    if index == 1:
        return np.concatenate((maximum, deep_low, deep_low), axis=2)
    if index == 2:
        return np.concatenate((maximum, deep_mid, deep_low), axis=2)
    if index == 3:
        return np.concatenate((maximum, maximum, deep_low), axis=2)
    if index == 4:
        return np.concatenate((deep_mid, maximum, deep_low), axis=2)
    if index == 5:
        return np.concatenate((deep_low, maximum, deep_low), axis=2)
    if index == 6:
        return np.concatenate((deep_low, maximum, deep_mid), axis=2)
    if index == 7:
        return np.concatenate((deep_low, maximum, maximum), axis=2)
    if index == 8:
        return np.concatenate((deep_low, deep_mid, maximum), axis=2)
    if index == 9:
        return np.concatenate((deep_low, deep_low, maximum), axis=2)
    if index == 10:
        return np.concatenate((deep_mid, deep_low, maximum), axis=2)
    if index == 11:
        return np.concatenate((maximum, deep_low, maximum), axis=2)
    if index == 12:
        return np.concatenate((maximum, deep_low, deep_mid), axis=2)

    raise ValueError(f"Not a deep hue paint ID: {paint_id}")


def apply_paint(image: Image.Image, paint: int | str) -> Image.Image:
    """
    Apply Terraria's ordinary tile paint transform to an image.

    The RGB math mirrors the TileShader formulas extracted from the user's
    Terraria TileShader.xnb. Alpha is preserved unchanged.
    """
    paint_id = resolve_paint_id(paint)

    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    rgb = rgba[..., :3].astype(np.float32) / 255.0
    alpha = rgba[..., 3:4]

    if paint_id == 0:
        out_rgb = rgb.copy()
    elif 1 <= paint_id <= 12:
        maximum = np.max(rgb, axis=2, keepdims=True)
        minimum = np.min(rgb, axis=2, keepdims=True)
        out_rgb = _normal_hue(maximum, minimum, paint_id)
    elif 13 <= paint_id <= 24:
        maximum = np.max(rgb, axis=2, keepdims=True)
        minimum = np.min(rgb, axis=2, keepdims=True)
        out_rgb = _deep_hue(maximum, minimum, paint_id)
    else:
        maximum = np.max(rgb, axis=2, keepdims=True)
        minimum = np.min(rgb, axis=2, keepdims=True)

        if paint_id == 25:  # Black
            value = 0.15 * (maximum + minimum)
            out_rgb = np.repeat(value, 3, axis=2)

        elif paint_id == 26:  # White
            value = (
                (0.7 * maximum + 0.3 * minimum)
                * (2.0 - 0.5 * (maximum + minimum))
            )
            out_rgb = np.repeat(value, 3, axis=2)

        elif paint_id == 27:  # Gray
            value = 0.5 * (maximum + minimum)
            out_rgb = np.repeat(value, 3, axis=2)

        elif paint_id == 28:  # Brown
            out_rgb = np.concatenate(
                (
                    maximum,
                    0.70 * maximum,
                    0.49 * maximum,
                ),
                axis=2,
            )

        elif paint_id == 29:  # Shadow
            value = 0.025 * (maximum + minimum)
            out_rgb = np.repeat(value, 3, axis=2)

        elif paint_id == 30:  # Negative
            out_rgb = 1.0 - rgb

        else:
            raise AssertionError(f"Unhandled paint ID: {paint_id}")

    out_rgb = np.clip(out_rgb, 0.0, 1.0)
    out_rgb_u8 = np.rint(out_rgb * 255.0).astype(np.uint8)
    out_rgba = np.concatenate((out_rgb_u8, alpha), axis=2)

    return Image.fromarray(out_rgba, mode="RGBA")


def paint_file(
    input_path: str | Path,
    output_path: str | Path,
    paint: int | str,
) -> Path:
    input_path = Path(input_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(input_path) as image:
        painted = apply_paint(image, paint)
        painted.save(output_path)

    return output_path


def generate_all_paints(
    input_path: str | Path,
    output_dir: str | Path,
) -> list[Path]:
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    generated = []
    with Image.open(input_path) as source:
        for paint_id, (slug, _) in PAINTS.items():
            output_path = output_dir / f"{paint_id:02d}_{slug}.png"
            apply_paint(source, paint_id).save(output_path)
            generated.append(output_path)

    return generated


def _fit_inside(image: Image.Image, max_width: int, max_height: int) -> Image.Image:
    copy = image.copy()
    copy.thumbnail((max_width, max_height), Image.Resampling.NEAREST)
    return copy


def build_contact_sheet(
    image_paths: Iterable[Path],
    output_path: str | Path,
    columns: int = 4,
    cell_size: int = 180,
) -> Path:
    image_paths = list(image_paths)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = (len(image_paths) + columns - 1) // columns
    label_height = 30
    sheet = Image.new(
        "RGBA",
        (columns * cell_size, rows * (cell_size + label_height)),
        (28, 28, 32, 255),
    )
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()

    for index, image_path in enumerate(image_paths):
        row = index // columns
        column = index % columns
        x = column * cell_size
        y = row * (cell_size + label_height)

        with Image.open(image_path) as image:
            preview = _fit_inside(image.convert("RGBA"), cell_size - 16, cell_size - 16)

        px = x + (cell_size - preview.width) // 2
        py = y + (cell_size - preview.height) // 2
        sheet.alpha_composite(preview, (px, py))

        stem = image_path.stem
        draw.text((x + 8, y + cell_size + 8), stem, fill=(240, 240, 240, 255), font=font)

    sheet.save(output_path)
    return output_path


def create_demo_texture(output_path: str | Path, size: int = 96) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    pixels = image.load()

    for y in range(size):
        for x in range(size):
            r = int(255 * x / max(1, size - 1))
            g = int(255 * y / max(1, size - 1))
            b = int(255 * (x + y) / max(1, 2 * size - 2))

            # Transparent corners make alpha preservation visible.
            alpha = 0 if (x < 10 and y < 10) or (x >= size - 10 and y >= size - 10) else 255

            # Add a few strongly colored regions so all paint transforms are obvious.
            if 18 <= x < 42 and 18 <= y < 42:
                r, g, b = 220, 35, 80
            elif 54 <= x < 78 and 18 <= y < 42:
                r, g, b = 40, 190, 240
            elif 30 <= x < 66 and 56 <= y < 82:
                r, g, b = 205, 180, 70

            pixels[x, y] = (r, g, b, alpha)

    image.save(output_path)
    return output_path


def run_demo(root: Path) -> None:
    test_dir = root / "data" / "paint_lab" / "tests"
    generated_dir = root / "data" / "paint_lab" / "generated" / "demo"

    source = create_demo_texture(test_dir / "demo_input.png")
    generated = generate_all_paints(source, generated_dir)
    contact_sheet = build_contact_sheet(
        generated,
        test_dir / "paint_shader_contact_sheet.png",
        columns=4,
    )

    print(f"Demo input: {source}")
    print(f"Generated paints: {generated_dir}")
    print(f"Contact sheet: {contact_sheet}")


def _default_project_root() -> Path:
    # scripts/paint_shader/terraria_paint_shader.py -> project root is two parents up
    return Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Offline Terraria tile paint renderer based on TileShader.xnb."
    )
    parser.add_argument("--list", action="store_true", help="List paint IDs and names.")
    parser.add_argument("--demo", action="store_true", help="Generate a complete visual demo.")
    parser.add_argument("--input", type=Path, help="Input PNG/image.")
    parser.add_argument("--paint", help="Paint name or ID for one output.")
    parser.add_argument("--all", action="store_true", help="Generate all paint IDs 0..30.")
    parser.add_argument("--output", type=Path, help="Output file or directory.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.list:
        for paint_id, (_, display_name) in PAINTS.items():
            print(f"{paint_id:02d}  {display_name}")
        return

    if args.demo:
        run_demo(_default_project_root())
        return

    if args.input is None:
        parser.error("Use --input, --demo, or --list.")

    if args.all:
        output_dir = args.output
        if output_dir is None:
            output_dir = (
                _default_project_root()
                / "data"
                / "paint_lab"
                / "generated"
                / args.input.stem
            )

        paths = generate_all_paints(args.input, output_dir)
        sheet = build_contact_sheet(
            paths,
            Path(output_dir) / "_contact_sheet.png",
            columns=4,
        )

        print(f"Generated {len(paths)} variants in: {output_dir}")
        print(f"Contact sheet: {sheet}")
        return

    if args.paint is None:
        parser.error("Use --paint <name-or-id> or --all.")

    paint_id = resolve_paint_id(args.paint)
    slug = PAINTS[paint_id][0]

    output_path = args.output
    if output_path is None:
        output_path = (
            _default_project_root()
            / "data"
            / "paint_lab"
            / "generated"
            / f"{args.input.stem}_{paint_id:02d}_{slug}.png"
        )

    path = paint_file(args.input, output_path, paint_id)
    print(f"Saved: {path}")


if __name__ == "__main__":
    main()

