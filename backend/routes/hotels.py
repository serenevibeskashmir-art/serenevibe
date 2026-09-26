"""
Hotel photos — public endpoint
===============================
Powers the "Where You'll Stay" slideshow on the public website.

The hotel list itself is NOT duplicated here. It is read from wherever the
itinerary PDF already reads it from:

    1. backend/services/pdf_service.py -> HOTEL_LOOKUP (name, place, and any
       image URLs written directly into the source). Read via pdf_content.py,
       which only parses the file's text with `ast.literal_eval` — exactly
       the same safe, read-only technique the AI Travel Assistant already
       uses. pdf_service.py is never imported, run, or changed.
    2. The `hotel_images` table (model: HotelImages) — photos an admin has
       uploaded per hotel from the admin panel. This is the same table
       pdf_service.py merges into HOTEL_LOOKUP at PDF-build time; reading it
       again here is independent and changes nothing about how the PDF works.

A hotel is only returned if it ends up with at least one image, since an
empty hotel has nothing to put in a photo slideshow.

Public endpoint
    GET /api/hotels -> {"hotels": [{"id", "name", "place", "images": [...]}]}
"""
import json
import logging

from flask import Blueprint, jsonify

from backend.services import pdf_content

log = logging.getLogger(__name__)

hotels_bp = Blueprint("hotels", __name__)


def _admin_uploaded_images() -> dict:
    """{hotel_id: [images]} for every hotel with admin-saved photos in the DB."""
    try:
        from backend.models import HotelImages
        out = {}
        for row in HotelImages.query.all():
            try:
                imgs = json.loads(row.images_json)
            except (TypeError, ValueError):
                continue
            if isinstance(imgs, list):
                clean = [i for i in imgs if isinstance(i, str) and i.strip()]
                if clean:
                    out[row.hotel_id] = clean
        return out
    except Exception as exc:   # never let this break the public site
        log.warning("hotels: could not read hotel_images table: %s", exc)
        return {}


@hotels_bp.get("/hotels")
def get_public_hotels():
    base = pdf_content.get()["hotels"]     # {id: {"name","place","images"}} — read-only
    admin_images = _admin_uploaded_images()

    hotels = []
    for hotel_id, info in base.items():
        # Admin-uploaded photos (if any) take priority over the ones hardcoded in pdf_service.py.
        images = admin_images.get(hotel_id) or info.get("images") or []
        if images:
            hotels.append({
                "id": hotel_id,
                "name": info["name"],
                "place": info["place"],
                "images": images,
            })

    hotels.sort(key=lambda h: (h["place"], h["name"]))

    resp = jsonify({"hotels": hotels})
    resp.headers["Cache-Control"] = "no-cache"
    return resp
