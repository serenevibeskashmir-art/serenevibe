"""
Website photos
==============
Photos shown on the PUBLIC website are uploaded in the admin panel
(/admin/photos) and stored in the database (table `site_photos`).

This module is independent from the itinerary tool: it does not touch
HotelImages, the PDF service, or any itinerary route.

Public endpoints
    GET  /api/site-photos          -> {"photos": {slot: {"url", "alt"}},
                                       "links":  {slot: "https://..."}}
    GET  /api/media/<slot>         -> the image bytes (cached; URL is versioned)

Admin endpoints (Bearer token required)
    GET    /api/admin/site-photos          -> every slot + whether it has a photo
    PUT    /api/admin/site-photos/<slot>   -> raw image body (jpeg/png/webp)
    PATCH  /api/admin/site-photos/<slot>   -> {"alt": "..."} and/or {"link": "https://..."}
                                              (link only for slots marked "has_link")
    DELETE /api/admin/site-photos/<slot>   -> remove the photo
"""
import re
from urllib.parse import urlparse

from flask import Blueprint, Response, abort, jsonify, request

from backend.auth import admin_required
from backend.extensions import db
from backend.models import SiteLink, SitePhoto

site_photos_bp = Blueprint("site_photos", __name__)

# Vercel serverless functions reject request bodies above ~4.5 MB. The admin
# page shrinks every photo in the browser first, so real uploads are far below
# this; the cap is a safety net.
MAX_UPLOAD_BYTES = 4 * 1024 * 1024
MAX_LINK_LENGTH = 500

# ---------------------------------------------------------------------------
# Slot catalogue: the single source of truth for what the website can show.
# To add a photo spot: add an entry here and a matching data-photo="<slot>"
# container in index.html. The admin page picks it up automatically.
# ---------------------------------------------------------------------------
SLOTS = [
    # --- Home page banner --------------------------------------------------
    {"slot": "hero", "group": "Home page banner", "label": "Main banner",
     "hint": "Full-width photo behind the headline at the very top of the site.",
     "ratio": "16 / 9", "size": "2400 × 1350 px", "max_dim": 2400},

    # --- Destinations ------------------------------------------------------
    {"slot": "dest-srinagar", "group": "Destinations", "label": "Srinagar",
     "hint": "Large feature card. Dal Lake, gardens, houseboats.",
     "ratio": "1 / 1", "size": "1400 × 1400 px", "max_dim": 1600},
    {"slot": "dest-pahalgam", "group": "Destinations", "label": "Pahalgam",
     "hint": "Destination card.", "ratio": "4 / 3", "size": "1200 × 900 px", "max_dim": 1400},
    {"slot": "dest-gulmarg", "group": "Destinations", "label": "Gulmarg",
     "hint": "Destination card.", "ratio": "4 / 3", "size": "1200 × 900 px", "max_dim": 1400},
    {"slot": "dest-sonamarg", "group": "Destinations", "label": "Sonamarg",
     "hint": "Destination card.", "ratio": "4 / 3", "size": "1200 × 900 px", "max_dim": 1400},
    {"slot": "dest-doodhpathri", "group": "Destinations", "label": "Doodhpathri",
     "hint": "Destination card.", "ratio": "4 / 3", "size": "1200 × 900 px", "max_dim": 1400},

    # --- Destination explorer (the distance chart) ------------------------
    {"slot": "reach-srinagar", "group": "Destination explorer (chart)", "label": "Srinagar",
     "hint": "Large photo beside the description when Srinagar is selected in the distance chart. If left empty, the Srinagar card photo above is used.",
     "ratio": "16 / 10", "size": "1400 × 875 px", "max_dim": 1600},
    {"slot": "reach-doodhpathri", "group": "Destination explorer (chart)", "label": "Doodhpathri",
     "hint": "Large photo beside the description when Doodhpathri is selected in the distance chart. If left empty, the Doodhpathri card photo above is used.",
     "ratio": "16 / 10", "size": "1400 × 875 px", "max_dim": 1600},
    {"slot": "reach-gulmarg", "group": "Destination explorer (chart)", "label": "Gulmarg",
     "hint": "Large photo beside the description when Gulmarg is selected in the distance chart. If left empty, the Gulmarg card photo above is used.",
     "ratio": "16 / 10", "size": "1400 × 875 px", "max_dim": 1600},
    {"slot": "reach-sonamarg", "group": "Destination explorer (chart)", "label": "Sonamarg",
     "hint": "Large photo beside the description when Sonamarg is selected in the distance chart. If left empty, the Sonamarg card photo above is used.",
     "ratio": "16 / 10", "size": "1400 × 875 px", "max_dim": 1600},
    {"slot": "reach-pahalgam", "group": "Destination explorer (chart)", "label": "Pahalgam",
     "hint": "Large photo beside the description when Pahalgam is selected in the distance chart. If left empty, the Pahalgam card photo above is used.",
     "ratio": "16 / 10", "size": "1400 × 875 px", "max_dim": 1600},

    # Tour package photos moved to the dedicated "Packages" admin tab, where
    # they're edited together with each package's text (see site_packages.py).

    # --- About us ----------------------------------------------------------
    {"slot": "about-main", "group": "About us", "label": "Main photo",
     "hint": "Tall photo beside the About text.", "ratio": "4 / 5", "size": "1200 × 1500 px", "max_dim": 1600},
    {"slot": "about-accent", "group": "About us", "label": "Small overlapping photo",
     "hint": "Small photo layered over the corner of the main photo.", "ratio": "1 / 1", "size": "800 × 800 px", "max_dim": 1000},

    # --- Gallery -----------------------------------------------------------
    {"slot": "gallery-1", "group": "Gallery", "label": "Gallery photo 1",
     "hint": "Shown extra large at the top-left of the gallery.", "ratio": "16 / 10", "size": "1800 × 1125 px", "max_dim": 1800},
    {"slot": "gallery-2", "group": "Gallery", "label": "Gallery photo 2",
     "hint": "Opens full-screen when visitors click it. Upload all 6 (or 3) for the tidiest layout.", "ratio": "16 / 10", "size": "1200 × 750 px", "max_dim": 1400},
    {"slot": "gallery-3", "group": "Gallery", "label": "Gallery photo 3",
     "hint": "Opens full-screen when visitors click it. Upload all 6 (or 3) for the tidiest layout.", "ratio": "16 / 10", "size": "1200 × 750 px", "max_dim": 1400},
    {"slot": "gallery-4", "group": "Gallery", "label": "Gallery photo 4",
     "hint": "Opens full-screen when visitors click it. Upload all 6 (or 3) for the tidiest layout.", "ratio": "16 / 10", "size": "1200 × 750 px", "max_dim": 1400},
    {"slot": "gallery-5", "group": "Gallery", "label": "Gallery photo 5",
     "hint": "Opens full-screen when visitors click it. Upload all 6 (or 3) for the tidiest layout.", "ratio": "16 / 10", "size": "1200 × 750 px", "max_dim": 1400},
    {"slot": "gallery-6", "group": "Gallery", "label": "Gallery photo 6",
     "hint": "Opens full-screen when visitors click it. Upload all 6 (or 3) for the tidiest layout.", "ratio": "16 / 10", "size": "1200 × 750 px", "max_dim": 1400},
    # --- Seasons -------------------------------------------------------
    {"slot": "season-spring", "group": "Seasons", "label": "Spring Bloom (Mar–May)",
     "hint": "Background photo for the Spring Bloom season card.", "ratio": "4 / 5", "size": "900 × 1125 px", "max_dim": 1200},
    {"slot": "season-summer", "group": "Seasons", "label": "Summer Greens (Jun–Aug)",
     "hint": "Background photo for the Summer Greens season card.", "ratio": "4 / 5", "size": "900 × 1125 px", "max_dim": 1200},
    {"slot": "season-autumn", "group": "Seasons", "label": "Autumn Gold (Sep–Nov)",
     "hint": "Background photo for the Autumn Gold season card.", "ratio": "4 / 5", "size": "900 × 1125 px", "max_dim": 1200},
    {"slot": "season-winter", "group": "Seasons", "label": "Winter Snow (Dec–Feb)",
     "hint": "Background photo for the Winter Snow season card.", "ratio": "4 / 5", "size": "900 × 1125 px", "max_dim": 1200},

    # --- Why travellers trust us (trust/proof section) ----------------------
    {"slot": "proof-certificate", "group": "Why travellers trust us", "label": "Registration certificate",
     "hint": "A scan or photo of your J&K Tourism registration certificate.", "ratio": "4 / 5", "size": "1000 × 1250 px", "max_dim": 1400},
    {"slot": "proof-office", "group": "Why travellers trust us", "label": "Office photo 1",
     "hint": "Shown as a slideshow on the site — upload just this one, or add photos 2 and 3 for it to rotate through them. Inside or outside your Srinagar office.",
     "ratio": "16 / 10", "size": "1200 × 750 px", "max_dim": 1400},
    {"slot": "proof-office-2", "group": "Why travellers trust us", "label": "Office photo 2",
     "hint": "Optional — adds a second photo to the office slideshow.", "ratio": "16 / 10", "size": "1200 × 750 px", "max_dim": 1400},
    {"slot": "proof-office-3", "group": "Why travellers trust us", "label": "Office photo 3",
     "hint": "Optional — adds a third photo to the office slideshow.", "ratio": "16 / 10", "size": "1200 × 750 px", "max_dim": 1400},
    {"slot": "proof-hotel", "group": "Why travellers trust us", "label": "Hotel partnership photo",
     "hint": "A partner hotel or houseboat.", "ratio": "16 / 10", "size": "1200 × 750 px", "max_dim": 1400},
    {"slot": "proof-video-thumb", "group": "Why travellers trust us", "label": "Highlight video (thumbnail + link)",
     "hint": "Thumbnail shown behind the play button. Paste the video link below: Instagram reel, YouTube, Vimeo, Google Drive or a direct .mp4 link. Visitors watch it in a pop-up on the site.",
     "ratio": "16 / 10", "size": "1200 × 750 px", "max_dim": 1400,
     "has_link": True, "link_label": "Video link",
     "link_placeholder": "e.g. https://www.instagram.com/reel/…  or  https://youtu.be/…"},
    {"slot": "proof-team-1", "group": "Why travellers trust us", "label": "Team photo 1",
     "hint": "Headshot or portrait — shown with the name/role below it in the code.", "ratio": "3 / 4", "size": "600 × 800 px", "max_dim": 900},
    {"slot": "proof-team-2", "group": "Why travellers trust us", "label": "Team photo 2",
     "hint": "Headshot or portrait.", "ratio": "3 / 4", "size": "600 × 800 px", "max_dim": 900},
    {"slot": "proof-team-3", "group": "Why travellers trust us", "label": "Team photo 3",
     "hint": "Headshot or portrait.", "ratio": "3 / 4", "size": "600 × 800 px", "max_dim": 900},
    {"slot": "proof-guest-1", "group": "Why travellers trust us", "label": "Guest photo 1",
     "hint": "Shown as a slideshow on the site — just this one is enough, or add up to 6 for it to rotate through them.",
     "ratio": "1 / 1", "size": "800 × 800 px", "max_dim": 1000},
    {"slot": "proof-guest-2", "group": "Why travellers trust us", "label": "Guest photo 2",
     "hint": "Optional — adds a photo to the guest slideshow.", "ratio": "1 / 1", "size": "800 × 800 px", "max_dim": 1000},
    {"slot": "proof-guest-3", "group": "Why travellers trust us", "label": "Guest photo 3",
     "hint": "Optional — adds a photo to the guest slideshow.", "ratio": "1 / 1", "size": "800 × 800 px", "max_dim": 1000},
    {"slot": "proof-guest-4", "group": "Why travellers trust us", "label": "Guest photo 4",
     "hint": "Optional — adds a photo to the guest slideshow.", "ratio": "1 / 1", "size": "800 × 800 px", "max_dim": 1000},
    {"slot": "proof-guest-5", "group": "Why travellers trust us", "label": "Guest photo 5",
     "hint": "Optional — adds a photo to the guest slideshow.", "ratio": "1 / 1", "size": "800 × 800 px", "max_dim": 1000},
    {"slot": "proof-guest-6", "group": "Why travellers trust us", "label": "Guest photo 6",
     "hint": "Optional — adds a photo to the guest slideshow.", "ratio": "1 / 1", "size": "800 × 800 px", "max_dim": 1000},
]
SLOT_INDEX = {s["slot"]: s for s in SLOTS}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _sniff_mime(data: bytes):
    """Identify the image from its first bytes. Never trust the client's label.
    SVG is deliberately not accepted (it can carry scripts)."""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _version(updated_at) -> int:
    """Cache-busting number that changes every time a photo is replaced."""
    return int(updated_at.timestamp() * 1000) if updated_at else 0


def _url(slot: str, updated_at) -> str:
    return f"/api/media/{slot}?v={_version(updated_at)}"


def _metadata_rows():
    # Explicit columns: the (large) image bytes are never loaded here.
    return db.session.query(
        SitePhoto.slot, SitePhoto.alt, SitePhoto.size, SitePhoto.updated_at
    ).all()


def _clean_link(raw):
    """Validate an admin-entered link. Returns (url, error); an empty value clears the link.
    Only http(s) is accepted, so a pasted 'javascript:' or 'data:' URL can never reach the site."""
    url = str(raw or "").strip()
    if not url:
        return "", None
    if len(url) > MAX_LINK_LENGTH:
        return None, f"That link is too long (limit {MAX_LINK_LENGTH} characters)."
    if re.search(r"\s", url):
        return None, "The link must not contain spaces."
    if not re.match(r"^[a-z][a-z0-9+.\-]*:", url, re.I):
        url = "https://" + url  # tolerate "youtu.be/abc" pasted without the scheme
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
        return None, "Please paste a full video link starting with https://"
    return url, None


def _link_rows() -> dict:
    """{slot: url} for every slot that has a non-empty link saved."""
    return {r.slot: r.url for r in SiteLink.query.all() if r.url and r.slot in SLOT_INDEX}


def _save_link(slot: str, url: str):
    row = SiteLink.query.filter_by(slot=slot).first()
    if not url:
        if row is not None:
            db.session.delete(row)
        return
    if row is None:
        db.session.add(SiteLink(slot=slot, url=url))
    else:
        row.url = url


def public_manifest() -> dict:
    """{"photos": {slot: {"url", "alt"}}, "links": {slot: url}} (uploaded photos / saved links only)."""
    photos = {}
    for row in _metadata_rows():
        if row.slot in SLOT_INDEX:
            photos[row.slot] = {"url": _url(row.slot, row.updated_at), "alt": row.alt or ""}
    return {"photos": photos, "links": _link_rows()}


def _slot_payload(slot_def: dict, row, link: str = "") -> dict:
    payload = dict(slot_def)
    payload.update(
        has_photo=row is not None,
        url=_url(slot_def["slot"], row.updated_at) if row else None,
        alt=(row.alt if row else "") or "",
        size_bytes=row.size if row else 0,
        updated_at=row.updated_at.isoformat() + "Z" if row else None,
        has_link=bool(slot_def.get("has_link")),
        link=link or "",
    )
    return payload


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------
@site_photos_bp.get("/site-photos")
def get_public_photos():
    resp = jsonify(public_manifest())
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@site_photos_bp.get("/media/<slot>")
def get_photo_bytes(slot):
    if slot not in SLOT_INDEX:
        abort(404)
    row = SitePhoto.query.filter_by(slot=slot).first()
    if row is None:
        abort(404)

    resp = Response(bytes(row.data), mimetype=row.mime)  # bytes(): psycopg2 returns memoryview
    resp.headers["X-Content-Type-Options"] = "nosniff"
    if request.args.get("v"):
        # The URL changes on every replacement, so it can be cached "forever".
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    else:
        resp.headers["Cache-Control"] = "public, max-age=300"
    resp.set_etag(f"{slot}-{_version(row.updated_at)}")
    return resp.make_conditional(request)


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------
@site_photos_bp.get("/admin/site-photos")
@admin_required
def admin_list_photos():
    rows = {r.slot: r for r in _metadata_rows()}
    links = _link_rows()
    return jsonify({
        "slots": [_slot_payload(s, rows.get(s["slot"]), links.get(s["slot"], "")) for s in SLOTS],
        "max_upload_bytes": MAX_UPLOAD_BYTES,
    })


@site_photos_bp.put("/admin/site-photos/<slot>")
@admin_required
def admin_upload_photo(slot):
    if slot not in SLOT_INDEX:
        return jsonify({"error": "Unknown photo slot."}), 404

    if request.content_length and request.content_length > MAX_UPLOAD_BYTES:
        return jsonify({"error": "Photo is too large (limit 4 MB)."}), 413
    data = request.get_data(cache=False)
    if not data:
        return jsonify({"error": "No image received."}), 400
    if len(data) > MAX_UPLOAD_BYTES:
        return jsonify({"error": "Photo is too large (limit 4 MB)."}), 413

    mime = _sniff_mime(data)
    if not mime:
        return jsonify({"error": "Unsupported file. Please upload a JPG, PNG or WEBP photo."}), 415

    row = SitePhoto.query.filter_by(slot=slot).first()
    alt_arg = request.args.get("alt")
    if row is None:
        row = SitePhoto(slot=slot, data=data, mime=mime, size=len(data),
                        alt=(alt_arg or "").strip()[:200])
        db.session.add(row)
    else:
        row.data, row.mime, row.size = data, mime, len(data)
        if alt_arg is not None:
            row.alt = alt_arg.strip()[:200]
    db.session.commit()

    return jsonify(_slot_payload(SLOT_INDEX[slot], row, _link_rows().get(slot, "")))


@site_photos_bp.patch("/admin/site-photos/<slot>")
@admin_required
def admin_update_slot(slot):
    """Update the description (needs a photo) and/or the link (slots with has_link only)."""
    if slot not in SLOT_INDEX:
        return jsonify({"error": "Unknown photo slot."}), 404
    body = request.get_json(silent=True) or {}
    row = SitePhoto.query.filter_by(slot=slot).first()

    if "link" in body:
        if not SLOT_INDEX[slot].get("has_link"):
            return jsonify({"error": "This photo spot does not have a link."}), 400
        url, error = _clean_link(body.get("link"))
        if error:
            return jsonify({"error": error}), 400
        _save_link(slot, url)

    if "alt" in body:
        if row is None:
            return jsonify({"error": "Upload a photo first."}), 404
        row.alt = str(body.get("alt", "")).strip()[:200]

    db.session.commit()
    return jsonify(_slot_payload(SLOT_INDEX[slot], row, _link_rows().get(slot, "")))


@site_photos_bp.delete("/admin/site-photos/<slot>")
@admin_required
def admin_delete_photo(slot):
    if slot not in SLOT_INDEX:
        return jsonify({"error": "Unknown photo slot."}), 404
    row = SitePhoto.query.filter_by(slot=slot).first()
    if row is not None:
        db.session.delete(row)
        db.session.commit()
    # The video link is kept: removing the thumbnail should not lose the link.
    return jsonify(_slot_payload(SLOT_INDEX[slot], None, _link_rows().get(slot, "")))
