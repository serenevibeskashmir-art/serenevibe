import json

from flask import Blueprint, jsonify, request

from backend.auth import admin_required, create_admin_token
from backend.config import Config
from backend.extensions import db
from backend.models import HotelImages

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
