"""Small Flask adapter around the original Color Palette Changer generator."""

from __future__ import annotations

import math

from flask import Blueprint, jsonify, request

from palette_creator.generation import augment_palette, generate_palette, generate_random_hex_color, normalize_hex_color


palette_api = Blueprint("palette_api", __name__)


def _json_payload():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object.")
    return payload


def _size(value, label):
    number = int(value)
    if number < 1 or number > 256:
        raise ValueError(f"{label} must be between 1 and 256.")
    return number


def _step(value, optional=False):
    if optional and (value is None or value == ""):
        return None
    number = float(value)
    if not math.isfinite(number) or abs(number) > 1:
        raise ValueError("Steps must be finite numbers between -1 and 1.")
    return number


@palette_api.post("/api/palette-create/generate")
def generate():
    try:
        payload = _json_payload()
        mode = payload.get("mode", "analogous")
        size = _size(payload.get("palette_size", 5), "Palette size")
        seed = normalize_hex_color(payload["seed_color"]) if payload.get("seed_color") else generate_random_hex_color()
        steps = (
            (_step(payload.get("lightness_step", 0)), _step(payload.get("green_red_step", 0)), _step(payload.get("blue_yellow_step", 0)))
            if mode == "analogous" else (0.0, 0.0, 0.0)
        )
        colors = generate_palette(
            seed_color=seed,
            palette_size=size,
            mode=mode,
            lightness_step=steps[0],
            green_red_step=steps[1],
            blue_yellow_step=steps[2],
        )
        return jsonify({"colors": colors, "seed_color": seed, "mode": mode})
    except (TypeError, ValueError) as error:
        return jsonify({"error": str(error)}), 400


@palette_api.post("/api/palette-create/augment")
def augment():
    try:
        payload = _json_payload()
        colors = payload.get("colors")
        if not isinstance(colors, list) or not colors:
            raise ValueError("Choose a non-empty source palette.")
        factor = _size(payload.get("factor", 5), "Colors per source")
        if len(colors) * factor > 256:
            raise ValueError("An augmented palette cannot exceed 256 colors.")
        result, steps = augment_palette(
            colors,
            factor,
            lightness_step=_step(payload.get("lightness_step"), True),
            green_red_step=_step(payload.get("green_red_step"), True),
            blue_yellow_step=_step(payload.get("blue_yellow_step"), True),
        )
        return jsonify({"colors": result, "steps": steps})
    except (TypeError, ValueError) as error:
        return jsonify({"error": str(error)}), 400
