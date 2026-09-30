"""Local visual wall review: issues first, duplicate pairs next, IDs last."""
import sys
from pathlib import Path
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import argparse
import secrets
import threading
import webbrowser
from urllib.parse import urlparse

from flask import Flask, abort, redirect, render_template, request, send_file, url_for
from werkzeug.serving import make_server
from scripts.paths import PROJECT_ROOT, DB_PATH
from scripts.maintenance.wall_review import WallReview
from scripts.maintenance.wall_storage import ROLES, wall_path
from scripts.maintenance.renumber_walls import finalize


def create_app(root=PROJECT_ROOT, db=DB_PATH):
    app = Flask(__name__, template_folder=str(Path(__file__).parent / "review_ui"),
                static_folder=str(Path(__file__).parent / "review_ui/static"))
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024
    review = WallReview(root, db)
    csrf = secrets.token_urlsafe(32)
    app.config["WALL_REVIEW"] = review

    @app.template_filter("safe_link")
    def safe_link(value):
        return value if value and urlparse(value).scheme in {"http", "https"} else "#"

    @app.after_request
    def headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self'; style-src 'self'; form-action 'self'; frame-ancestors 'none'"
        return response

    def page(error=None, status=200):
        review.refresh()
        kind, current = review.current()
        ids = ([current["local_id"]] if kind == "issue" else
               [current["left_id"], current["right_id"]] if kind == "pair" else [])
        rows = [review.rows[local_id] for local_id in ids if local_id in review.rows]
        return render_template("review.html", review=review, kind=kind, current=current,
                               rows=rows, roles=ROLES, csrf=csrf, error=error), status

    @app.get("/")
    def index():
        return page()

    @app.get("/image/<int:local_id>/<role>")
    def image(local_id, role):
        if role not in ROLES:
            abort(404)
        # Load on demand too: an external editor may have changed these paths.
        from contextlib import closing
        from scripts.paths import connect_readonly
        with closing(connect_readonly(review.db)) as connection:
            row = connection.execute("SELECT * FROM objects WHERE local_id=? AND object_type='wall'", (local_id,)).fetchone()
        if row is None or not row[role + "_image_path"]:
            abort(404)
        try:
            path = wall_path(row[role + "_image_path"], role, review.root, local_id)
        except ValueError:
            abort(404)
        if not path.is_file():
            abort(404)
        return send_file(path)

    @app.get("/orphan/<key>")
    def orphan(key):
        review.refresh()
        issue = next((i for i in review.issues if i["key"] == key and i["problem"] == "orphan_file"), None)
        if not issue:
            abort(404)
        path = (review.root / issue["path"]).resolve()
        if path.parent not in {review.root / "images/walls" / r for r in ROLES} or not path.is_file():
            abort(404)
        return send_file(path)

    @app.post("/action")
    def action():
        if not secrets.compare_digest(request.form.get("csrf", ""), csrf):
            abort(403)
        try:
            if request.form.get("action") == "finalize":
                finalize(review, request.form.get("revision", ""))
            else:
                review.act(request.form.get("action", ""), request.form.get("revision", ""), request.form.to_dict())
        except Exception as error:
            # Helpers roll back failed mutations; show the error beside the entry.
            return page(str(error), 400)
        return redirect(url_for("index"), code=303)

    return app


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=5001)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    app = create_app()
    # Bind before opening a tab; never navigate to an unrelated process on an occupied port.
    server = make_server("127.0.0.1", args.port, app, threaded=False)
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"Classification des murs : {url}\nCtrl+C pour arrêter. La progression est conservée.", flush=True)
    if not args.no_browser:
        threading.Timer(0.3, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
