"""
Hotels added from the admin panel (table: custom_hotels).

The built-in hotels still live in pdf_service.py (HOTEL_LOOKUP). This module returns the extra ones in the
same shape -- {hotel_id: {"name", "place", "images"}} -- so every consumer can simply merge them in.
Photos are NOT stored here: they use the existing hotel_images table, exactly like built-in hotels.
Any database problem returns {} so the PDF, the website and the chat keep working with the built-in list.
"""
import logging

log = logging.getLogger(__name__)

PLACES = ("Srinagar", "Pahalgam", "Gulmarg", "Sonamarg")


def get_all() -> dict:
    try:
        from backend.models import CustomHotel
        return {
            row.hotel_id: {"name": row.name, "place": row.place, "images": []}
            for row in CustomHotel.query.order_by(CustomHotel.id).all()
        }
    except Exception as exc:
        log.warning("custom_hotels: could not read custom_hotels table: %s", exc)
        return {}
