"""
Structured Itineraries ("Packages" section on the homepage)
=============================================================
Fully editable from the admin panel (/admin, tab "Packages"): the card
text (name, duration, badge, description, features, price) and the photo
at the top of each card. Everything is stored in the database (table
`site_packages`) so it survives redeploys, the same way SitePhoto does.

Public endpoints
    GET  /api/site-packages           -> {"packages": [ {...} ]}
    GET  /api/media/package/<id>      -> the image bytes for that package

Admin endpoints (Bearer token required)
    GET    /api/admin/site-packages         -> every package (admin shape)
    POST   /api/admin/site-packages         -> create a new package
    PUT    /api/admin/site-packages/<id>    -> update text fields
    DELETE /api/admin/site-packages/<id>    -> remove a package
    PUT    /api/admin/site-packages/reorder -> {"order": [id, id, ...]}
    PUT    /api/admin/site-packages/<id>/photo   -> raw image body (jpeg/png/webp)
    DELETE /api/admin/site-packages/<id>/photo   -> remove just the photo
"""
import json

from flask import Blueprint, Response, abort, jsonify, request

from backend.auth import admin_required
from backend.extensions import db
from backend.models import SitePackage, SitePhoto

site_packages_bp = Blueprint("site_packages", __name__)

MAX_UPLOAD_BYTES = 4 * 1024 * 1024
PLACEHOLDERS = {"lake", "pine", "slate"}

# The three cards that used to be hardcoded in index.html. Used only to seed
# the table the first time this feature runs, so nothing on the live site
# changes until someone edits it in the admin panel.
DEFAULT_PACKAGES = [
    {
        "position": 0, "badge": "Essential", "duration": "5 Nights / 6 Days",
        "name": "Valley Discovery",
        "description": "Srinagar, Gulmarg, and Pahalgam — an ideal introduction to Kashmir for first-time visitors.",
        "features": ["Deluxe hotel & houseboat stay", "Private airport transfers", "Shikara ride on Dal Lake", "Gulmarg Gondola (Phase 1)"],
        "price_label": "24,999", "price_note": "/ person", "featured": False, "placeholder": "lake",
        "legacy_slot": "pkg-valley",
    },
    {
        "position": 1, "badge": "Recommended", "duration": "7 Nights / 8 Days",
        "name": "Grand Kashmir Circuit",
        "description": "Complete valley experience covering all five destinations with dedicated local guides at each stop.",
        "features": ["All five destinations included", "Mughal garden & temple tours", "Breakfast & dinner daily", "Permits & entry fees covered"],
        "price_label": "38,999", "price_note": "/ person", "featured": True, "placeholder": "pine",
        "legacy_slot": "pkg-circuit",
    },
    {
        "position": 2, "badge": "Premium", "duration": "Custom Duration",
        "name": "Heritage & Houseboat",
        "description": "Premium Srinagar experience with luxury houseboat accommodation and private curated excursions.",
        "features": ["Premium houseboat suite", "Private chauffeur & guide", "Heritage walk & craft tours", "Personal trip coordinator"],
        "price_label": "64,999", "price_note": "/ person", "featured": False, "placeholder": "slate",
        "legacy_slot": "pkg-heritage",
    },
]


def _seed_if_empty():
    """First run only: create the three original cards, pulling across any
    photo already uploaded to the old pkg-valley / pkg-circuit / pkg-heritage
    website-photo slots so existing uploads are not lost."""
    if SitePackage.query.first() is not None:
        return
    legacy_photos = {p.slot: p for p in SitePhoto.query.filter(
        SitePhoto.slot.in_([d["legacy_slot"] for d in DEFAULT_PACKAGES])
    ).all()}
    for d in DEFAULT_PACKAGES:
        legacy = legacy_photos.get(d["legacy_slot"])
        pkg = SitePackage(
            position=d["position"], badge=d["badge"], duration=d["duration"],
            name=d["name"], description=d["description"],
            features=json.dumps(d["features"]), price_label=d["price_label"],
            price_note=d["price_note"], featured=d["featured"], placeholder=d["placeholder"],
        )
        if legacy is not None:
            pkg.photo_data = legacy.data
            pkg.photo_mime = legacy.mime
            pkg.photo_size = legacy.size
            pkg.photo_alt = legacy.alt or ""
        db.session.add(pkg)
    db.session.commit()


def _sniff_mime(data: bytes):
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _version(updated_at) -> int:
    return int(updated_at.timestamp() * 1000) if updated_at else 0


def _photo_url(pkg):
    if not pkg.photo_mime:
        return None
    return f"/api/media/package/{pkg.id}?v={_version(pkg.updated_at)}"


def _features(pkg):
    try:
        value = json.loads(pkg.features or "[]")
        return [str(f) for f in value] if isinstance(value, list) else []
    except (TypeError, ValueError):
        return []


def _public_shape(pkg):
    return {
        "id": pkg.id,
        "badge": pkg.badge,
        "duration": pkg.duration,
        "name": pkg.name,
        "description": pkg.description,
        "features": _features(pkg),
        "price_label": pkg.price_label,
        "price_note": pkg.price_note,
        "featured": pkg.featured,
        "placeholder": pkg.placeholder if pkg.placeholder in PLACEHOLDERS else "lake",
        "photo": {"url": _photo_url(pkg), "alt": pkg.photo_alt or pkg.name} if pkg.photo_mime else None,
    }


def _admin_shape(pkg):
    payload = _public_shape(pkg)
    payload["has_photo"] = bool(pkg.photo_mime)
    payload["photo_size_bytes"] = pkg.photo_size or 0
    payload["updated_at"] = pkg.updated_at.isoformat() + "Z" if pkg.updated_at else None
    return payload


def _apply_fields(pkg, data):
    if "badge" in data: pkg.badge = str(data["badge"]).strip()[:60]
    if "duration" in data: pkg.duration = str(data["duration"]).strip()[:60]
    if "name" in data: pkg.name = str(data["name"]).strip()[:150]
    if "description" in data: pkg.description = str(data["description"]).strip()
    if "features" in data:
        feats = data["features"]
        if isinstance(feats, str):
            feats = [line.strip() for line in feats.splitlines() if line.strip()]
        if isinstance(feats, list):
            pkg.features = json.dumps([str(f).strip() for f in feats if str(f).strip()][:12])
    if "price_label" in data: pkg.price_label = str(data["price_label"]).strip()[:40]
    if "price_note" in data: pkg.price_note = str(data["price_note"]).strip()[:40]
    if "featured" in data: pkg.featured = bool(data["featured"])
    if "placeholder" in data and data["placeholder"] in PLACEHOLDERS:
        pkg.placeholder = data["placeholder"]


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------
def public_packages_manifest() -> dict:
    """{"packages": [ {...} ]} — used by this endpoint and embedded server-side
    into the homepage so the cards render without an extra round-trip."""
    _seed_if_empty()
    packages = SitePackage.query.order_by(SitePackage.position, SitePackage.id).all()
    return {"packages": [_public_shape(p) for p in packages]}


@site_packages_bp.get("/site-packages")
def get_public_packages():
    resp = jsonify(public_packages_manifest())
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@site_packages_bp.get("/media/package/<int:pkg_id>")
def get_package_photo(pkg_id):
    pkg = SitePackage.query.filter_by(id=pkg_id).first()
    if pkg is None or not pkg.photo_mime:
        abort(404)
    resp = Response(bytes(pkg.photo_data), mimetype=pkg.photo_mime)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    if request.args.get("v"):
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    else:
        resp.headers["Cache-Control"] = "public, max-age=300"
    resp.set_etag(f"pkg-{pkg_id}-{_version(pkg.updated_at)}")
    return resp.make_conditional(request)


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------
@site_packages_bp.get("/admin/site-packages")
@admin_required
def admin_list_packages():
    _seed_if_empty()
    packages = SitePackage.query.order_by(SitePackage.position, SitePackage.id).all()
    return jsonify({
        "packages": [_admin_shape(p) for p in packages],
        "max_upload_bytes": MAX_UPLOAD_BYTES,
    })


@site_packages_bp.post("/admin/site-packages")
@admin_required
def admin_create_package():
    data = request.get_json(silent=True) or {}
    max_pos = db.session.query(db.func.max(SitePackage.position)).scalar() or 0
    pkg = SitePackage(
        position=max_pos + 1,
        badge=str(data.get("badge", "")).strip()[:60] or "New",
        duration=str(data.get("duration", "")).strip()[:60],
        name=str(data.get("name", "")).strip()[:150] or "Untitled Package",
        description=str(data.get("description", "")).strip(),
        features=json.dumps(data.get("features") or []),
        price_label=str(data.get("price_label", "")).strip()[:40],
        price_note=str(data.get("price_note", "/ person")).strip()[:40] or "/ person",
        featured=bool(data.get("featured", False)),
        placeholder=data.get("placeholder") if data.get("placeholder") in PLACEHOLDERS else "lake",
    )
    db.session.add(pkg)
    db.session.commit()
    return jsonify(_admin_shape(pkg)), 201


@site_packages_bp.put("/admin/site-packages/reorder")
@admin_required
def admin_reorder_packages():
    data = request.get_json(silent=True) or {}
    order = data.get("order") or []
    rows = {p.id: p for p in SitePackage.query.filter(SitePackage.id.in_(order)).all()}
    for index, pkg_id in enumerate(order):
        row = rows.get(pkg_id)
        if row is not None:
            row.position = index
    db.session.commit()
    packages = SitePackage.query.order_by(SitePackage.position, SitePackage.id).all()
    return jsonify({"packages": [_admin_shape(p) for p in packages]})


@site_packages_bp.put("/admin/site-packages/<int:pkg_id>")
@admin_required
def admin_update_package(pkg_id):
    pkg = SitePackage.query.filter_by(id=pkg_id).first()
    if pkg is None:
        return jsonify({"error": "Package not found."}), 404
    data = request.get_json(silent=True) or {}
    _apply_fields(pkg, data)
    db.session.commit()
    return jsonify(_admin_shape(pkg))


@site_packages_bp.delete("/admin/site-packages/<int:pkg_id>")
@admin_required
def admin_delete_package(pkg_id):
    pkg = SitePackage.query.filter_by(id=pkg_id).first()
    if pkg is not None:
        db.session.delete(pkg)
        db.session.commit()
    return jsonify({"deleted": pkg_id})


@site_packages_bp.put("/admin/site-packages/<int:pkg_id>/photo")
@admin_required
def admin_upload_package_photo(pkg_id):
    pkg = SitePackage.query.filter_by(id=pkg_id).first()
    if pkg is None:
        return jsonify({"error": "Package not found."}), 404

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

    pkg.photo_data, pkg.photo_mime, pkg.photo_size = data, mime, len(data)
    alt_arg = request.args.get("alt")
    if alt_arg is not None:
        pkg.photo_alt = alt_arg.strip()[:200]
    db.session.commit()
    return jsonify(_admin_shape(pkg))


@site_packages_bp.delete("/admin/site-packages/<int:pkg_id>/photo")
@admin_required
def admin_delete_package_photo(pkg_id):
    pkg = SitePackage.query.filter_by(id=pkg_id).first()
    if pkg is None:
        return jsonify({"error": "Package not found."}), 404
    pkg.photo_data, pkg.photo_mime, pkg.photo_size = None, None, 0
    db.session.commit()
    return jsonify(_admin_shape(pkg))
