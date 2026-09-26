import json
import os

from flask import Flask, Response, send_from_directory
from flask_cors import CORS

from backend.auth import admin_required
from backend.config import Config
from backend.extensions import db
from backend.routes.admin import admin_bp
from backend.routes.assistant import assistant_bp
from backend.routes.email import email_bp
from backend.routes.hotels import hotels_bp
from backend.routes.itinerary import itinerary_bp
from backend.routes.leads import leads_bp
from backend.routes.packages import packages_bp
from backend.routes.site_packages import public_packages_manifest, site_packages_bp
from backend.routes.site_photos import public_manifest, site_photos_bp

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUBLIC_DIR = ROOT_DIR
PWA_DIR = ROOT_DIR
ADMIN_DIST = os.path.join(ROOT_DIR, "admin", "dist")
OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "/tmp/output")


def create_app():
    app = Flask(__name__, static_folder=None)
    app.config.from_object(Config)
    CORS(app)
    db.init_app(app)

    app.register_blueprint(admin_bp, url_prefix="/api/admin")
    app.register_blueprint(leads_bp, url_prefix="/api/leads")
    app.register_blueprint(packages_bp, url_prefix="/api/packages")
    app.register_blueprint(itinerary_bp, url_prefix="/api/itinerary")
    app.register_blueprint(email_bp, url_prefix="/api/email")
    app.register_blueprint(site_photos_bp, url_prefix="/api")
    app.register_blueprint(hotels_bp, url_prefix="/api")
    app.register_blueprint(site_packages_bp, url_prefix="/api")
    app.register_blueprint(assistant_bp, url_prefix="/api")

    with app.app_context():
        try:
            db.create_all()
        except Exception as exc:  # never let a DB hiccup crash the whole app on cold start
            print(f"db.create_all() skipped/failed at startup: {exc}")

    @app.get("/")
    def serve_public_home():
        # The photo list is embedded straight into the page so photos appear
        # immediately (no extra round-trip). If anything goes wrong the page
        # still works: js/main.js falls back to fetching /api/site-photos.
        with open(os.path.join(PUBLIC_DIR, "index.html"), encoding="utf-8") as fh:
            html = fh.read()
        try:
            payload = json.dumps(public_manifest()).replace("</", "<\\/")
            html = html.replace(
                "<!--SITE_PHOTOS-->",
                f"<script>window.__SITE_PHOTOS__={payload};</script>",
                1,
            )
        except Exception as exc:  # never let a DB hiccup take the homepage down
            print(f"Site photo injection skipped: {exc}")
        try:
            pkg_payload = json.dumps(public_packages_manifest()).replace("</", "<\\/")
            html = html.replace(
                "<!--SITE_PACKAGES-->",
                f"<script>window.__SITE_PACKAGES__={pkg_payload};</script>",
                1,
            )
        except Exception as exc:  # never let a DB hiccup take the homepage down
            print(f"Site package injection skipped: {exc}")
        response = Response(html, mimetype="text/html")
        response.headers["Cache-Control"] = "no-cache"
        return response

    @app.get("/css/<path:filename>")
    def serve_public_css(filename):
        return send_from_directory(os.path.join(PUBLIC_DIR, "css"), filename)

    @app.get("/js/<path:filename>")
    def serve_public_js(filename):
        return send_from_directory(os.path.join(PUBLIC_DIR, "js"), filename)

    # --- PWA assets ---
    # sw.js and manifest.json must be served from the root ("/") so the
    # service worker's default scope covers the whole site, not just /public/.
    @app.get("/sw.js")
    def serve_service_worker():
        response = send_from_directory(PWA_DIR, "sw.js")
        # Prevent browsers/CDNs from caching the service worker script itself,
        # so updates to it are picked up promptly.
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Service-Worker-Allowed"] = "/"
        return response

    @app.get("/manifest.json")
    def serve_manifest():
        return send_from_directory(PWA_DIR, "manifest.json")

    @app.get("/icons/<path:filename>")
    def serve_pwa_icons(filename):
        return send_from_directory(os.path.join(PWA_DIR, "icons"), filename)

    # Android App Links verification. Must be served at exactly this path.
    # Fill in the real package name + SHA-256 fingerprint in
    # .well-known/assetlinks.json before this does anything useful.
    @app.get("/.well-known/assetlinks.json")
    def serve_asset_links():
        response = send_from_directory(os.path.join(PUBLIC_DIR, ".well-known"), "assetlinks.json")
        response.headers["Content-Type"] = "application/json"
        return response

    # Website Photos page (separate from the itinerary builder at /admin)
    @app.get("/admin/photos")
    def serve_admin_photos():
        return send_from_directory(ADMIN_DIST, "website.html")

    @app.get("/admin")
    def serve_admin_root():
        return send_from_directory(ADMIN_DIST, "index.html")

    @app.get("/admin/")
    def serve_admin_root_slash():
        return send_from_directory(ADMIN_DIST, "index.html")

    @app.get("/admin/<path:filename>")
    def serve_admin_assets(filename):
        return send_from_directory(ADMIN_DIST, filename)

    @app.get("/output/<path:filename>")
    @admin_required
    def serve_output(filename):
        return send_from_directory(OUTPUT_DIR, filename)

    return app


app = create_app()

if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    app.run(debug=True, port=5000)
