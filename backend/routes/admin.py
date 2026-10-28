import json
import uuid

from flask import Blueprint, jsonify, request

from backend.auth import admin_required, create_admin_token
from backend.config import Config
from backend.extensions import db
from backend.models import CustomHotel, HotelImages
from backend.services.custom_hotels import clean_place_name, ensure_place, get_places, place_key

admin_bp = Blueprint("admin", __name__)


def _load_hotel_images() -> dict:
    """Return {hotel_id: [img_src, ...]} for all hotels stored in the DB."""
    rows = HotelImages.query.all()
    return {row.hotel_id: json.loads(row.images_json) for row in rows}


def _save_hotel_images(data: dict):
    """
    Upsert hotel image lists into the DB.
    data = {hotel_id: [img_src, ...], ...}
    """
    for hotel_id, images in data.items():
        row = HotelImages.query.filter_by(hotel_id=hotel_id).first()
        if row:
            row.images_json = json.dumps(images)
        else:
            db.session.add(HotelImages(hotel_id=hotel_id, images_json=json.dumps(images)))
    db.session.commit()


@admin_bp.post("/login")
def admin_login():
    data = request.get_json(silent=True) or {}
    password = data.get("password", "")

    if password != Config.ADMIN_PASSWORD:
        return jsonify({"error": "Invalid admin credentials."}), 401

    return jsonify({"token": create_admin_token(), "message": "Authenticated"})


@admin_bp.get("/verify")
def admin_verify():
    from backend.auth import verify_admin_token

    auth_header = request.headers.get("Authorization", "")
    token = auth_header.removeprefix("Bearer ").strip() if auth_header else ""
    if not verify_admin_token(token):
        return jsonify({"authenticated": False}), 401
    return jsonify({"authenticated": True})


@admin_bp.get("/hotel-images")
@admin_required
def get_hotel_images():
    """Return the saved hotel → images mapping."""
    return jsonify(_load_hotel_images())


@admin_bp.post("/hotel-images")
@admin_required
def save_hotel_images():
    """
    Body: { "hotelId": ["url1", "url2", ...], ... }
    Only the hotels in the request are written; other hotels are left untouched.
    """
    incoming = request.get_json(silent=True)
    if not isinstance(incoming, dict) or not incoming:
        return jsonify({"error": "Invalid request body."}), 400

    clean = {}
    for hotel_id, images in incoming.items():
        if not isinstance(images, list):
            return jsonify({"error": "Images must be a list."}), 400
        clean[str(hotel_id)[:20]] = [i for i in images if isinstance(i, str) and i.strip()]

    try:
        _save_hotel_images(clean)
    except Exception as exc:
        db.session.rollback()
        return jsonify({"error": f"Database error: {exc.__class__.__name__}"}), 500
    return jsonify({"ok": True, "saved": list(clean.keys())})


# ── Admin-added hotels ────────────────────────────────────────────────────────
def _hotel_json(row):
    return {"id": row.hotel_id, "name": row.name, "place": row.place, "custom": True}


def _clean_hotel_body():
    data = request.get_json(silent=True) or {}
    name = " ".join(str(data.get("name", "")).split())
    place = clean_place_name(data.get("place"))
    if not name or len(name) > 150:
        return None, None, "Hotel name is required (max 150 characters)."
    if not place:
        return None, None, "Place is required (max 40 characters)."
    ensure_place(place, data.get("lat"), data.get("lon"))   # a new location becomes available everywhere
    return name, place, None


def _photo_counts() -> dict:
    """{hotel_id: number of photos} without pulling every base64 image into memory when possible."""
    from sqlalchemy import text
    try:
        if db.engine.dialect.name == "postgresql":
            rows = db.session.execute(text(
                "SELECT hotel_id, jsonb_array_length(images_json::jsonb) FROM hotel_images"
            )).all()
            return {hid: int(n or 0) for hid, n in rows}
    except Exception:
        db.session.rollback()          # fall back to the slower, portable way below
    counts = {}
    for row in HotelImages.query.all():
        try:
            counts[row.hotel_id] = len(json.loads(row.images_json))
        except (TypeError, ValueError):
            pass
    return counts


@admin_bp.get("/hotels")
@admin_required
def list_custom_hotels():
    """Every hotel: the built-in ones (custom=False, read-only) plus those added from the admin."""
    from backend.services import pdf_content

    try:
        custom_ids = {r.hotel_id for r in CustomHotel.query.all()}
    except Exception as exc:
        db.session.rollback()
        # The table may simply not exist yet (startup create_all can fail on a cold start): try once to create it.
        try:
            db.create_all()
            custom_ids = {r.hotel_id for r in CustomHotel.query.all()}
        except Exception as exc2:
            db.session.rollback()
            detail = str(getattr(exc2, "orig", exc2)).strip().splitlines()[0][:200]
            return jsonify({"error": f"Could not read hotels table ({exc2.__class__.__name__}): {detail}. "
                                     "Check DATABASE_URL on Vercel."}), 500
    try:
        photo_counts = _photo_counts()
    except Exception:
        db.session.rollback()
        photo_counts = {}
    try:
        base = pdf_content.get()["hotels"]
    except Exception as exc:
        return jsonify({"error": f"Could not read hotel list ({exc.__class__.__name__})."}), 500

    hotels = []
    for hid, info in base.items():
        hotels.append({
            "id": hid, "name": info["name"], "place": info["place"],
            "custom": hid in custom_ids,
            "photos": photo_counts.get(hid) or len(info.get("images") or []),
        })
    hotels.sort(key=lambda h: (h["place"], h["name"]))
    return jsonify({"hotels": hotels})


@admin_bp.post("/hotels")
@admin_required
def add_custom_hotel():
    name, place, error = _clean_hotel_body()
    if error:
        return jsonify({"error": error}), 400
    for attempt in (1, 2):
        try:
            row = CustomHotel(hotel_id="c" + uuid.uuid4().hex[:10], name=name, place=place)
            db.session.add(row)
            db.session.commit()
            return jsonify({"ok": True, "hotel": _hotel_json(row)}), 201
        except Exception as exc:
            db.session.rollback()
            if attempt == 1:
                try:
                    db.create_all()      # table may be missing on a fresh database
                except Exception:
                    db.session.rollback()
                continue
            detail = str(getattr(exc, "orig", exc)).strip().splitlines()[0][:200]
            return jsonify({"error": f"Could not save hotel ({exc.__class__.__name__}): {detail}"}), 500


@admin_bp.put("/hotels/<hotel_id>")
@admin_required
def update_custom_hotel(hotel_id):
    row = CustomHotel.query.filter_by(hotel_id=hotel_id).first()
    if row is None:
        return jsonify({"error": "Hotel not found."}), 404
    name, place, error = _clean_hotel_body()
    if error:
        return jsonify({"error": error}), 400
    row.name, row.place = name, place
    db.session.commit()
    return jsonify({"ok": True, "hotel": _hotel_json(row)})


@admin_bp.delete("/hotels/<hotel_id>")
@admin_required
def delete_custom_hotel(hotel_id):
    row = CustomHotel.query.filter_by(hotel_id=hotel_id).first()
    if row is None:
        return jsonify({"error": "Hotel not found."}), 404
    HotelImages.query.filter_by(hotel_id=hotel_id).delete()
    db.session.delete(row)
    db.session.commit()
    return jsonify({"ok": True})


# ── Locations (itinerary builder + Hotels tab) ───────────────────────────────
@admin_bp.get("/places")
@admin_required
def list_places():
    return jsonify({"places": get_places()})


@admin_bp.post("/places")
@admin_required
def add_place():
    data = request.get_json(silent=True) or {}
    name = clean_place_name(data.get("name"))
    if not name or len(name) > 40:
        return jsonify({"error": "Place name is required (max 40 characters)."}), 400
    row = ensure_place(name, data.get("lat"), data.get("lon"))
    if row is None:
        existing = next((p for p in get_places() if p["key"] == place_key(name)), None)
        if existing:                       # a built-in location: nothing to store
            return jsonify({"ok": True, "place": existing}), 200
        return jsonify({"error": "Could not save this location. Please try again."}), 500
    place = {"name": row.name, "key": row.key, "lat": row.lat, "lon": row.lon, "builtin": False}
    return jsonify({"ok": True, "place": place}), 201
