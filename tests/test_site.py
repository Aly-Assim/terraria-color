from __future__ import annotations

import sys
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import app, DB_PATH
from scripts.paths import connect_readonly


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    print("=== SITE COLOR SEARCH SMOKE TEST ===")

    with connect_readonly(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row

        row = connection.execute(
            """
            SELECT local_id, paint_id
            FROM object_paint_colors
            WHERE error IS NULL
            ORDER BY local_id, paint_id
            LIMIT 1
            """
        ).fetchone()

    assert_true(
        row is not None,
        "object_paint_colors is empty",
    )

    client = app.test_client()

    response = client.get("/")
    assert_true(
        response.status_code == 200,
        f"GET / returned {response.status_code}",
    )
    print("[PASS] home")

    response = client.get(
        "/",
        query_string={
            "mode": "color",
            "color": "#8a6a4b",
            "k": "5",
            "color_mode": "average",
            "dispersion": "35",
            "paint": "all",
        },
    )

    assert_true(
        response.status_code == 200,
        f"average search returned {response.status_code}",
    )

    assert_true(
        b"Distance OKLab" in response.data,
        "average search rendered no results",
    )

    print("[PASS] average + dispersion search")

    response = client.get(
        "/",
        query_string={
            "mode": "color",
            "color": "#8a6a4b",
            "k": "5",
            "color_mode": "dominant",
            "dispersion": "35",
            "paint": "13",
        },
    )

    assert_true(
        response.status_code == 200,
        f"dominant search returned {response.status_code}",
    )

    assert_true(
        b"Distance OKLab" in response.data,
        "dominant search rendered no results",
    )

    print("[PASS] dominant + paint filter search")

    response = client.get(
        f"/painted-image/{row['local_id']}/{row['paint_id']}"
    )

    assert_true(
        response.status_code == 200,
        f"painted preview returned {response.status_code}",
    )

    assert_true(
        response.mimetype == "image/png",
        f"painted preview mimetype is {response.mimetype}",
    )

    print("[PASS] dynamic painted image")

    response = client.get("/workshop")
    assert_true(
        response.status_code == 200 and b'data-workshop' in response.data,
        f"Workshop returned {response.status_code}",
    )

    response = client.get(
        "/api/workshop/search",
        query_string={"q": "stone", "object_type": "wall"},
    )
    workshop_results = response.get_json()
    assert_true(
        response.status_code == 200
        and workshop_results
        and all(item["object_type"] == "wall" for item in workshop_results),
        "Workshop wall search returned invalid results",
    )

    response = client.get(
        f"/api/workshop/item/{row['local_id']}/{row['paint_id']}"
    )
    assert_true(
        response.status_code == 200
        and f"/painted-image/{row['local_id']}/{row['paint_id']}".encode()
        in response.data,
        "Workshop item did not use the painted-image endpoint",
    )

    print("[PASS] Workshop page, filtered search, and painted item")

    print()
    print("5/5 test groups passed")
    print("ALL SITE TESTS PASSED")


if __name__ == "__main__":
    main()
