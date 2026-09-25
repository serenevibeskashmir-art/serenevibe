"""
Reads the trip content that is already written inside backend/services/pdf_service.py.

pdf_service.py is NOT changed and NOT run. This module only reads its text and picks out the
lists the itinerary PDF prints, so the AI Travel Assistant always says what the PDF says:

    hotel list (HOTEL_LOOKUP)   inclusions (inc_items)         exclusions (exc_items)
    cancellation (canc_data)    travel notes (travel_notes)    terms & conditions (tc_sections)
    general terms (general_bullets)

Edit those lists in pdf_service.py as you always have; the assistant picks up the change on the next
request. If a list is ever turned into something other than plain text/lists (for example built with a
loop or a function call), it can't be read safely. That list then comes back empty, a warning is logged,
and the assistant tells travellers "our team will confirm" instead of guessing.
"""
import ast
import logging
from pathlib import Path

log = logging.getLogger(__name__)

_PDF_SERVICE = Path(__file__).resolve().parent / "pdf_service.py"

# name inside pdf_service.py -> name used here
_WANTED = {
    "HOTEL_LOOKUP": "hotels",
    "inc_items": "inclusions",
    "exc_items": "exclusions",
    "canc_data": "cancellation",
    "travel_notes": "travel_notes",
    "tc_sections": "terms",
    "general_bullets": "general_terms",
}

_cache = {"mtime": None, "data": None}


def _text_list(value) -> list:
    return [x.strip() for x in value if isinstance(x, str) and x.strip()] if isinstance(value, (list, tuple)) else []


def _pairs(value, size: int) -> list:
    """Rows of exactly `size` text cells: (heading, text) or (timeline, charge, refund, processing)."""
    rows = []
    for row in value if isinstance(value, (list, tuple)) else []:
        if isinstance(row, (list, tuple)) and len(row) == size and all(isinstance(c, str) for c in row):
            rows.append(tuple(c.strip() for c in row))
    return rows


def _hotels(value) -> dict:
    hotels = {}
    for hotel_id, info in value.items() if isinstance(value, dict) else []:
        if isinstance(hotel_id, str) and isinstance(info, dict) and info.get("name") and info.get("place"):
            hotels[hotel_id] = {
                "name": str(info["name"]).strip(),
                "place": str(info["place"]).strip(),
                "images": [i for i in info.get("images", []) if isinstance(i, str)],
            }
    return hotels


def _empty() -> dict:
    return {"hotels": {}, "inclusions": [], "exclusions": [], "cancellation": [],
            "travel_notes": [], "terms": [], "general_terms": []}


def _read() -> dict:
    data = _empty()
    tree = ast.parse(_PDF_SERVICE.read_text(encoding="utf-8"))
    found = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in _WANTED and target.id not in found:
                    try:
                        found[target.id] = ast.literal_eval(node.value)   # plain data only: nothing is executed
                    except (ValueError, SyntaxError):
                        log.warning("pdf_content: %s in pdf_service.py is not plain text/lists, so it was skipped", target.id)

    data["hotels"] = _hotels(found.get("HOTEL_LOOKUP"))
    data["inclusions"] = _text_list(found.get("inc_items"))
    data["exclusions"] = _text_list(found.get("exc_items"))
    data["cancellation"] = _pairs(found.get("canc_data"), 4)
    data["travel_notes"] = _pairs(found.get("travel_notes"), 2)
    data["terms"] = _pairs(found.get("tc_sections"), 2)
    data["general_terms"] = _text_list(found.get("general_bullets"))

    missing = [name for name, key in _WANTED.items() if not data[key]]
    if missing:
        log.warning("pdf_content: nothing usable found in pdf_service.py for: %s", ", ".join(missing))
    return data


def get() -> dict:
    """The PDF's content. Re-read automatically whenever pdf_service.py changes."""
    try:
        mtime = _PDF_SERVICE.stat().st_mtime
        if _cache["data"] is None or _cache["mtime"] != mtime:
            _cache.update(mtime=mtime, data=_read())
        return _cache["data"]
    except Exception as exc:   # never let this break the chat
        log.warning("pdf_content: could not read pdf_service.py: %s", exc)
        return _cache["data"] or _empty()
