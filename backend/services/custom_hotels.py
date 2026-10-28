"""
Hotels and locations added from the admin panel.

* Hotels live in the table custom_hotels. Built-in hotels still live in pdf_service.py (HOTEL_LOOKUP).
  get_all() returns the extra hotels in the same shape -- {hotel_id: {"name", "place", "images"}} --
  so every consumer can simply merge them in. Photos use the existing hotel_images table.
* Locations live in the table custom_places. Any place can be added (Sopore, Dal Lake, Yusmarg ...),
  and a hotel can be attached to any of them.

Any database problem returns an empty result so the PDF, the website and the chat keep working.
"""
import logging

log = logging.getLogger(__name__)

# Locations the app knows without the admin adding them.
PLACES = ("Srinagar", "Pahalgam", "Gulmarg", "Sonamarg", "Doodhpathri")
BUILT_IN_KEYS = frozenset(p.lower() for p in PLACES)


def clean_place_name(raw) -> str:
    """Display form of a place name: single spaces, no colons (they separate the parts of a route title), Title Case, max 40 characters."""
    return " ".join(str(raw or "").replace(":", " ").split())[:40].title()


def place_key(name) -> str:
    """Matching key for a place name: lower case, single spaces."""
    return " ".join(str(name or "").split()).lower()


def _coord(value, lo, hi):
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if lo <= number <= hi else None


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


def get_places() -> list:
    """Built-in locations first, then the admin-added ones: [{name, key, lat, lon, builtin}]."""
    out = [{"name": p, "key": p.lower(), "lat": None, "lon": None, "builtin": True} for p in PLACES]
    try:
        from backend.models import CustomPlace
        rows = CustomPlace.query.order_by(CustomPlace.name).all()
        out += [{"name": r.name, "key": r.key, "lat": r.lat, "lon": r.lon, "builtin": False} for r in rows]
    except Exception as exc:
        log.warning("custom_hotels: could not read custom_places table: %s", exc)
    return out


def ensure_place(name, lat=None, lon=None):
    """
    Store a location if it is new. Built-in names are never stored.
    Coordinates are kept only as a pair, and are filled in when a stored place has none yet.
    Returns the CustomPlace row, or None (built-in name, or the database could not be written).
    """
    from backend.extensions import db
    from backend.models import CustomPlace

    name = clean_place_name(name)
    key = place_key(name)
    if not name or key in BUILT_IN_KEYS:
        return None
    la, lo = _coord(lat, -90, 90), _coord(lon, -180, 180)
    have_pair = la is not None and lo is not None
    for attempt in (1, 2):
        try:
            row = CustomPlace.query.filter_by(key=key).first()
            if row is None:
                row = CustomPlace(key=key, name=name,
                                  lat=la if have_pair else None, lon=lo if have_pair else None)
                db.session.add(row)
            elif row.lat is None and have_pair:
                row.lat, row.lon = la, lo
            db.session.commit()
            return row
        except Exception as exc:
            db.session.rollback()
            if attempt == 1:
                try:
                    db.create_all()          # table may be missing on a fresh database
                except Exception:
                    db.session.rollback()
                continue
            log.warning("custom_hotels: could not save place %r: %s", name, exc)
    return None
