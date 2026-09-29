from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from scripts.paint.renderer import PAINTS, apply_paint


EXPECTED_FOR_100_150_200 = {
    "none": (100, 150, 200),
    "red": (200, 100, 100),
    "orange": (200, 150, 100),
    "yellow": (200, 200, 100),
    "lime": (150, 200, 100),
    "green": (100, 200, 100),
    "teal": (100, 200, 150),
    "cyan": (100, 200, 200),
    "sky_blue": (100, 150, 200),
    "blue": (100, 100, 200),
    "purple": (150, 100, 200),
    "violet": (200, 100, 200),
    "pink": (200, 100, 150),
    "deep_red": (200, 40, 40),
    "deep_orange": (200, 120, 40),
    "deep_yellow": (200, 200, 40),
    "deep_lime": (120, 200, 40),
    "deep_green": (40, 200, 40),
    "deep_teal": (40, 200, 120),
    "deep_cyan": (40, 200, 200),
    "deep_sky_blue": (40, 120, 200),
    "deep_blue": (40, 40, 200),
    "deep_purple": (120, 40, 200),
    "deep_violet": (200, 40, 200),
    "deep_pink": (200, 40, 120),
    "black": (45, 45, 45),
    "white": (240, 240, 240),
    "gray": (150, 150, 150),
    "brown": (200, 140, 98),
    "shadow": (8, 8, 8),
    "negative": (155, 105, 55),
}


def assert_equal(actual, expected, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message}: expected {expected}, got {actual}")


def test_catalog() -> None:
    assert_equal(list(PAINTS.keys()), list(range(31)), "Paint IDs must be exactly 0..30")


def test_all_known_pixel_outputs() -> None:
    source = Image.new("RGBA", (1, 1), (100, 150, 200, 173))

    for paint_id, (slug, _) in PAINTS.items():
        output = apply_paint(source, paint_id)
        pixel = output.getpixel((0, 0))

        expected_rgb = EXPECTED_FOR_100_150_200[slug]
        expected = (*expected_rgb, 173)
        assert_equal(pixel, expected, f"{paint_id:02d} {slug}")


def test_alpha_is_preserved() -> None:
    source = Image.new("RGBA", (3, 1))
    source.putdata([
        (100, 150, 200, 0),
        (100, 150, 200, 77),
        (100, 150, 200, 255),
    ])

    for paint_id in PAINTS:
        output = apply_paint(source, paint_id)
        alphas = [output.getpixel((x, 0))[3] for x in range(3)]
        assert_equal(alphas, [0, 77, 255], f"Alpha preservation for paint {paint_id}")


def test_none_is_identity() -> None:
    source = Image.new("RGBA", (2, 2))
    source.putdata([
        (1, 2, 3, 4),
        (100, 150, 200, 255),
        (255, 0, 127, 99),
        (33, 44, 55, 66),
    ])

    output = apply_paint(source, 0)
    assert_equal(output.tobytes(), source.tobytes(), "None paint must be identity")


def test_negative_is_rgb_inverse() -> None:
    source = Image.new("RGBA", (1, 1), (12, 34, 56, 78))
    output = apply_paint(source, 30)
    assert_equal(output.getpixel((0, 0)), (243, 221, 199, 78), "Negative paint")


def test_deep_is_more_saturated_than_normal_on_sample() -> None:
    source = Image.new("RGBA", (1, 1), (100, 150, 200, 255))

    normal = apply_paint(source, 1).getpixel((0, 0))
    deep = apply_paint(source, 13).getpixel((0, 0))

    if not (deep[1] < normal[1] and deep[2] < normal[2] and deep[0] == normal[0]):
        raise AssertionError(f"Deep Red relation failed: normal={normal}, deep={deep}")


def main() -> int:

    tests = [
        ("catalog", test_catalog),
        ("31 shader outputs", test_all_known_pixel_outputs),
        ("alpha preservation", test_alpha_is_preserved),
        ("none identity", test_none_is_identity),
        ("negative inversion", test_negative_is_rgb_inverse),
        ("deep saturation", test_deep_is_more_saturated_than_normal_on_sample),
    ]

    passed = 0
    print("=== TERRARIA PAINT SHADER TESTS ===")

    for name, function in tests:
        try:
            function()
        except Exception as exc:
            print(f"[FAIL] {name}: {exc}")
        else:
            passed += 1
            print(f"[PASS] {name}")

    print()
    print(f"{passed}/{len(tests)} test groups passed")

    if passed != len(tests):
        return 1

    print("ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

