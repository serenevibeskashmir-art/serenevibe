"""
Cloudinary image storage
========================
Images are stored on Cloudinary instead of inside the database. The database
only keeps a small pointer row (table `cloud_media`) per image.

Cloudinary is OPTIONAL: if the three CLOUDINARY_* environment variables are not
set, `configured()` is False and every route keeps using the database exactly as
before. That also means existing images keep working until they are migrated
(see scripts/migrate_images_to_cloudinary.py).

kind / ref pairs used in `cloud_media`
    site_photo  / <slot>        e.g. "hero", "gallery-1"
    package     / <package id>  e.g. "3"

Hotel photos need no pointer row: backend/routes/admin.py simply stores the
Cloudinary https:// URL inside HotelImages.images_json (the PDF, website and AI
assistant already understand https:// URLs).

Uses the Cloudinary REST API through `requests`, so no extra dependency.
"""
import hashlib
import logging
import time

import requests

from backend.config import Config
from backend.extensions import db
from backend.models import CloudMedia

log = logging.getLogger(__name__)

ROOT_FOLDER = "serenevibe"
UPLOAD_TIMEOUT = 25


def configured() -> bool:
    return bool(Config.CLOUDINARY_CLOUD_NAME and Config.CLOUDINARY_API_KEY and Config.CLOUDINARY_API_SECRET)


def _sign(params: dict) -> str:
    to_sign = "&".join(f"{k}={params[k]}" for k in sorted(params) if params[k] not in (None, ""))
    return hashlib.sha1((to_sign + Config.CLOUDINARY_API_SECRET).encode()).hexdigest()


def upload_bytes(data: bytes, public_id: str, filename: str = "image"):
    """Upload raw image bytes. Returns (secure_url, public_id). Raises RuntimeError on failure."""
    if not configured():
        raise RuntimeError("Cloudinary is not configured.")
    params = {
        "public_id": public_id,
        "overwrite": "true",
        "invalidate": "true",
        "timestamp": str(int(time.time())),
    }
    payload = dict(params, api_key=Config.CLOUDINARY_API_KEY, signature=_sign(params))
    url = f"https://api.cloudinary.com/v1_1/{Config.CLOUDINARY_CLOUD_NAME}/image/upload"
    try:
        resp = requests.post(url, data=payload, files={"file": (filename, data)}, timeout=UPLOAD_TIMEOUT)
    except requests.RequestException as exc:
        raise RuntimeError(f"Could not reach Cloudinary: {exc}") from exc
    if resp.status_code != 200:
        try:
            msg = resp.json().get("error", {}).get("message", resp.text[:200])
        except ValueError:
            msg = resp.text[:200]
        raise RuntimeError(f"Cloudinary upload failed: {msg}")
    body = resp.json()
    return body["secure_url"], body["public_id"]


def destroy(public_id: str) -> None:
    """Delete an image from Cloudinary. Never raises (a leftover file is harmless)."""
    if not (configured() and public_id):
        return
    params = {"public_id": public_id, "invalidate": "true", "timestamp": str(int(time.time()))}
    payload = dict(params, api_key=Config.CLOUDINARY_API_KEY, signature=_sign(params))
    try:
        requests.post(f"https://api.cloudinary.com/v1_1/{Config.CLOUDINARY_CLOUD_NAME}/image/destroy",
                      data=payload, timeout=UPLOAD_TIMEOUT)
    except requests.RequestException as exc:
        log.warning("Cloudinary delete failed for %s: %s", public_id, exc)


def optimized(url: str) -> str:
    """Add automatic format + quality (WebP/AVIF, smaller files) to a Cloudinary delivery URL."""
    marker = "/image/upload/"
    if url and marker in url and "/f_auto" not in url:
        return url.replace(marker, marker + "f_auto,q_auto/", 1)
    return url


# ---------------------------------------------------------------------------
# Pointer rows (cloud_media table)
# ---------------------------------------------------------------------------
def get(kind: str, ref):
    return CloudMedia.query.filter_by(kind=kind, ref=str(ref)).first()


def url_map(kind: str) -> dict:
    """{ref: row} for every pointer of one kind (one query)."""
    return {r.ref: r for r in CloudMedia.query.filter_by(kind=kind).all()}


def save(kind: str, ref, data: bytes) -> CloudMedia:
    """Upload `data`, then create/replace the pointer row. Does NOT commit."""
    public_id = f"{ROOT_FOLDER}/{kind}/{ref}"
    url, pid = upload_bytes(data, public_id)
    row = get(kind, ref)
    if row is None:
        row = CloudMedia(kind=kind, ref=str(ref), url=url, public_id=pid)
        db.session.add(row)
    else:
        row.url, row.public_id = url, pid
    return row


def remove(kind: str, ref) -> None:
    """Delete the Cloudinary file and its pointer row. Does NOT commit."""
    row = get(kind, ref)
    if row is not None:
        destroy(row.public_id)
        db.session.delete(row)


def fetch_bytes(kind: str, ref):
    """Image bytes for a pointer (used by the PDF builder), or None."""
    url = None
    try:
        row = get(kind, ref)
        url = row.url if row is not None else None
    except Exception as exc:          # database exhausted / unreachable
        db.session.rollback()
        log.warning("cloud_media pointer lookup failed for %s/%s: %s", kind, ref, exc)
    if not url:                       # no pointer row: ask Cloudinary itself
        url = catalog().get(kind, {}).get(str(ref))
    if not url:
        return None
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.content
    except requests.RequestException as exc:
        log.warning("Could not download %s/%s from Cloudinary: %s", kind, ref, exc)
        return None


# ---------------------------------------------------------------------------
# Database-independent catalogue (the safety net)
# ---------------------------------------------------------------------------
# Every image is uploaded under a predictable name (serenevibe/<kind>/<ref>[/<hash>]), so
# Cloudinary itself can tell us which photo belongs where. When the database is exhausted,
# unreachable, or the app has failed over to an EMPTY second database, the site and the
# itinerary use this instead and photos keep showing.
CATALOG_TTL = 600        # seconds a successful listing is reused (keeps Admin API calls low)
CATALOG_RETRY = 60       # seconds before retrying after a failed listing
_catalog = {"at": 0.0, "data": None}


def _empty_catalog() -> dict:
    return {"site_photo": {}, "package": {}, "hotels": {}}


def _fetch_catalog() -> dict:
    url = f"https://api.cloudinary.com/v1_1/{Config.CLOUDINARY_CLOUD_NAME}/resources/image/upload"
    params = {"prefix": ROOT_FOLDER + "/", "max_results": 500}
    auth = (Config.CLOUDINARY_API_KEY, Config.CLOUDINARY_API_SECRET)
    resources = []
    while True:
        resp = requests.get(url, params=params, auth=auth, timeout=8)
        resp.raise_for_status()
        body = resp.json()
        resources += body.get("resources", [])
        if not body.get("next_cursor"):
            break
        params["next_cursor"] = body["next_cursor"]

    out = _empty_catalog()
    for res in sorted(resources, key=lambda r: r.get("created_at", "")):
        parts = res["public_id"].split("/")          # serenevibe / kind / ref [/ hash]
        if len(parts) == 3 and parts[1] in ("site_photo", "package"):
            out[parts[1]][parts[2]] = res["secure_url"]
        elif len(parts) == 4 and parts[1] == "hotels":
            out["hotels"].setdefault(parts[2], []).append(res["secure_url"])
    return out


def catalog() -> dict:
    """{"site_photo": {slot: url}, "package": {id: url}, "hotels": {hotel_id: [urls]}} straight from
    Cloudinary. Cached in memory; if Cloudinary can't be reached the last good copy is returned.
    Never raises."""
    if not configured():
        return _empty_catalog()
    now = time.time()
    if _catalog["data"] is not None and now - _catalog["at"] < CATALOG_TTL:
        return _catalog["data"]
    try:
        _catalog["data"], _catalog["at"] = _fetch_catalog(), now
    except Exception as exc:
        log.warning("Could not list Cloudinary images: %s", exc)
        _catalog["at"] = now - CATALOG_TTL + CATALOG_RETRY   # try again soon, serve stale meanwhile
        if _catalog["data"] is None:
            return _empty_catalog()
    return _catalog["data"]


def hotel_photos_fallback() -> dict:
    """{hotel_id: [https urls]} for the itinerary / website hotel photos, without the database."""
    return dict(catalog()["hotels"])


def hotel_data_url_to_cloud(src: str, hotel_id: str) -> str:
    """Turn a base64 data URL into a Cloudinary https URL. Anything else is returned unchanged.
    The file name is a hash of the picture, so saving the same photo twice never duplicates it."""
    import base64
    if not (isinstance(src, str) and src.startswith(("data:image/", "data:application/octet-stream")) and ";base64," in src):
        return src
    raw = base64.b64decode(src.split(",", 1)[1])
    digest = hashlib.sha1(raw).hexdigest()[:16]
    url, _ = upload_bytes(raw, f"{ROOT_FOLDER}/hotels/{hotel_id}/{digest}")
    return url
