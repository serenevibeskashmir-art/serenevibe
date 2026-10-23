import json
import uuid

from flask import Blueprint, jsonify, request

from backend.auth import admin_required, create_admin_token
from backend.config import Config
from backend.extensions import db
from backend.models import CustomHotel, HotelImages
from backend.services.custom_hotels import PLACES

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
    Merges with existing data so partial updates are safe.
    """
    incoming = request.get_json(silent=True) or {}
    existing = _load_hotel_images()
    existing.update(incoming)
    _save_hotel_images(existing)
    return jsonify({"ok": True, "saved": list(incoming.keys())})


# ── Admin-added hotels ────────────────────────────────────────────────────────
def _hotel_json(row):
    return {"id": row.hotel_id, "name": row.name, "place": row.place, "custom": True}


def _clean_hotel_body():
    data = request.get_json(silent=True) or {}
    name = " ".join(str(data.get("name", "")).split())
    place = str(data.get("place", "")).strip().title()
    if not name or len(name) > 150:
        return None, None, "Hotel name is required (max 150 characters)."
    if place not in PLACES:
        return None, None, "Place must be one of: " + ", ".join(PLACES) + "."
    return name, place, None


@admin_bp.get("/hotels")
@admin_required
def list_custom_hotels():
    rows = CustomHotel.query.order_by(CustomHotel.id).all()
    return jsonify({"hotels": [_hotel_json(r) for r in rows]})


@admin_bp.post("/hotels")
@admin_required
def add_custom_hotel():
    name, place, error = _clean_hotel_body()
    if error:
        return jsonify({"error": error}), 400
    row = CustomHotel(hotel_id="c" + uuid.uuid4().hex[:10], name=name, place=place)
    db.session.add(row)
    db.session.commit()
    return jsonify({"ok": True, "hotel": _hotel_json(row)}), 201


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
