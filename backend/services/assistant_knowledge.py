"""
What the AI Kashmir Travel Assistant knows about your trips, hotels and policies.

Nothing here is written twice. The content comes from the same places your clients already see:

  * Inclusions, exclusions, hotels, cancellation table, travel notes, terms & conditions
        -> read straight from backend/services/pdf_service.py (via pdf_content.py), so it is exactly
           what the itinerary PDF prints. pdf_service.py itself is untouched.
  * Hotel photos
        -> the photos you upload in the admin panel (the HotelImages table the PDF also uses)
  * Privacy policy
        -> read live from the "Privacy Policy" section of index.html, so editing the website
           text updates the assistant too

The big policy text is only added to the prompt when the traveller's recent messages look like
they are asking about it. That keeps every request small and quick (and inside Groq's per-minute
token limits) without changing what the assistant is able to answer.
"""
import base64
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path

from flask import current_app
from sqlalchemy import func

from backend.extensions import db
from backend.models import HotelImages
from backend.services import pdf_content

MAX_HOTELS_SHOWN = 3        # hotel cards in one reply
MAX_PHOTOS_PER_HOTEL = 3
MAX_PHOTO_INDEX = 8         # sanity limit for the photo endpoint
PHOTO_URL = "/api/assistant/hotel-photo/{hotel_id}/{index}"


def hotels() -> dict:
    """{hotel_id: {name, place, images}} exactly as listed in the PDF service."""
    return pdf_content.get()["hotels"]

_INDEX_HTML = Path(__file__).resolve().parents[2] / "index.html"

# Only https links and ordinary image data-URLs are ever shown. Never SVG (it can carry scripts),
# never javascript:, never local file paths.
_DATA_URL = re.compile(r"^data:image/(jpeg|jpg|png|webp|gif);base64,(.+)$", re.S | re.I)


# ---------------------------------------------------------------------------
# Hotel photos
# ---------------------------------------------------------------------------
def _usable_sources(raw) -> list:
    out = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, str):
            continue
        item = item.strip()
        if item.startswith("https://") or _DATA_URL.match(item):
            out.append(item)
    return out


def hotel_photo_sources(hotel_id: str) -> list:
    """Photos for one hotel. Admin uploads win; the built-in defaults are the fallback (same rule as the PDF)."""
    hotel = hotels().get(hotel_id)
    if hotel is None:
        return []
    saved = []
    try:
        row = HotelImages.query.filter_by(hotel_id=hotel_id).first()
        if row is not None:
            saved = _usable_sources(json.loads(row.images_json))
    except Exception as exc:  # a DB hiccup must never break the chat
        current_app.logger.warning("Assistant: could not load photos for %s: %s", hotel_id, exc)
    return saved or _usable_sources(hotel.get("images"))


def hotels_with_photos() -> set:
    """Ids of hotels that have photos. Cheap: asks the database for the length only, never the image data."""
    ids = {hid for hid, hotel in hotels().items() if _usable_sources(hotel.get("images"))}
    try:
        rows = db.session.query(HotelImages.hotel_id).filter(func.length(HotelImages.images_json) > 2).all()
        ids |= {row[0] for row in rows if row[0] in hotels()}
    except Exception as exc:
        current_app.logger.warning("Assistant: could not check hotel photos: %s", exc)
    return ids


def clean_hotel_ids(raw) -> list:
    """Whatever the model returned -> a short list of real hotel ids, in order, no repeats."""
    if not isinstance(raw, list):
        return []
    ids = []
    for item in raw:
        hid = str(item or "").strip()
        if hid in hotels() and hid not in ids:
            ids.append(hid)
    return ids[:MAX_HOTELS_SHOWN]


def hotel_cards(hotel_ids: list) -> list:
    """Hotel cards for the chat: name, place and photo links. Photo links are built here, never by the model."""
    cards = []
    for hid in clean_hotel_ids(hotel_ids):
        hotel = hotels()[hid]
        urls = []
        for index, src in enumerate(hotel_photo_sources(hid)[:MAX_PHOTOS_PER_HOTEL]):
            if src.startswith("https://"):
                urls.append(src)
            else:   # an uploaded photo: served by our own endpoint, cached until the photo changes
                version = hashlib.sha1(src.encode("utf-8", "ignore")).hexdigest()[:10]
                urls.append(PHOTO_URL.format(hotel_id=hid, index=index) + "?v=" + version)
        cards.append({"id": hid, "name": hotel["name"], "place": hotel["place"], "photos": urls})
    return cards


def hotel_photo_bytes(hotel_id: str, index: int):
    """(bytes, mimetype) for an uploaded photo, or None."""
    sources = hotel_photo_sources(hotel_id)
    if not 0 <= index < len(sources):
        return None
    match = _DATA_URL.match(sources[index])
    if not match:
        return None
    kind = match.group(1).lower()
    try:
        return base64.b64decode(match.group(2)), "image/jpeg" if kind == "jpg" else f"image/{kind}"
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Privacy policy (read from the live website text)
# ---------------------------------------------------------------------------
class _DetailsText(HTMLParser):
    """Pulls the text out of one <details id="..."> block (minus its <summary> title)."""
    BLOCKS = {"p", "h4", "li", "tr", "div", "br"}

    def __init__(self, target_id: str):
        super().__init__(convert_charrefs=True)
        self.target, self.depth, self.done, self.in_summary, self.parts = target_id, 0, False, False, []

    def handle_starttag(self, tag, attrs):
        if self.done:
            return
        if tag == "details":
            if self.depth:
                self.depth += 1
            elif dict(attrs).get("id") == self.target:
                self.depth = 1
            return
        if not self.depth:
            return
        if tag == "summary":
            self.in_summary = True
        elif tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if self.done or not self.depth:
            return
        if tag == "summary":
            self.in_summary = False
        elif tag == "details":
            self.depth -= 1
            self.done = self.depth == 0

    def handle_data(self, data):
        if self.depth and not self.in_summary and not self.done:
            self.parts.append(data)

    def text(self) -> str:
        lines = (re.sub(r"\s+", " ", part).strip() for part in "".join(self.parts).split("\n"))
        return "\n".join(line for line in lines if line)


_privacy_cache = {"mtime": None, "text": ""}


def privacy_policy_text() -> str:
    try:
        mtime = _INDEX_HTML.stat().st_mtime
        if _privacy_cache["mtime"] == mtime:
            return _privacy_cache["text"]
        parser = _DetailsText("privacy-policy")
        parser.feed(_INDEX_HTML.read_text(encoding="utf-8"))
        text = parser.text()[:2000]
        _privacy_cache.update(mtime=mtime, text=text)
        return text
    except Exception as exc:
        current_app.logger.warning("Assistant: could not read the privacy policy from index.html: %s", exc)
        return ""


# ---------------------------------------------------------------------------
# Prompt blocks
# ---------------------------------------------------------------------------
def inclusions_block() -> str:
    content = pdf_content.get()
    if not content["inclusions"] and not content["exclusions"]:
        return "(Not available right now. If asked what is included or excluded, say our team will confirm.)"
    lines = ["INCLUDED in the standard tour price:"]
    lines += [f"- {item}" for item in content["inclusions"]]
    lines += ["NOT INCLUDED (paid separately by the traveller):"]
    lines += [f"- {item}" for item in content["exclusions"]]
    return "\n".join(lines)


def hotels_block() -> str:
    if not hotels():
        return "(The hotel list is not available right now. Do not name any hotel; say our team will confirm the stay.)"
    with_photos = hotels_with_photos()
    by_place = {}
    for hid, hotel in hotels().items():
        by_place.setdefault(hotel["place"], []).append(
            f"{hid} = {hotel['name']}" + (" [photos]" if hid in with_photos else "")
        )
    return "\n".join(f"- {place}: " + "; ".join(items) for place, items in by_place.items())


# Boilerplate about airline tickets is in the PDF's general terms, but we do not sell flights.
_AIRLINE_LINE = re.compile(r"flight|airline|airport|seat|mask", re.I)

# Words that suggest the traveller is asking about a policy. Broad on purpose: a miss only means the
# assistant says "our team will confirm", it never means a wrong answer.
_POLICY_WORDS = re.compile(
    r"cancel|refund|polic(?:y|ies)|terms|condition|t\s?&\s?c|privacy|\bdata\b|confidential|"
    r"child|children|\bkids?\b|infant|toddler|\bage\b|"
    r"document|\bid\b|aadhaar|aadhar|passport|visa|"
    r"check[\s-]?in|check[\s-]?out|extra bed|rollaway|adjoining|adjacent|"
    r"\bbill|invoice|cheque|payment|advance|token|deposit|"
    r"insurance|medical|health|altitude|"
    r"weather|snow|road ?block|diversion|"
    r"\bsim\b|network|connectivity|post-?paid|pre-?paid|"
    r"photograph|camera|restricted|"
    r"complain|jurisdiction|court|legal|pandemic|covid|calamity|force majeure|"
    r"\btax|\bgst\b|fuel|surcharge|damage|mini-?bar|voucher|liab",
    re.I,
)


def wants_policies(recent_text: str) -> bool:
    return bool(_POLICY_WORDS.search(recent_text or ""))


def policies_block(recent_text: str = "") -> str:
    if not wants_policies(recent_text):
        return ("(Full policy text is not loaded for this message. If the traveller asks about a policy, "
                "do not guess: say our team will confirm it.)")

    content = pdf_content.get()
    lines = ["CANCELLATION POLICY (charges are on the total tour cost):"]
    for timeline, charge, refund, processing in content["cancellation"]:
        lines.append(f"- {timeline}: charge {charge}; refund {refund}; processing {processing}")

    lines += ["", "TERMS AND CONDITIONS:"]
    lines += [f"- {heading}: {text}" for heading, text in content["terms"]]
    lines += [f"- {text}" for text in content["general_terms"] if not _AIRLINE_LINE.search(text)]

    lines += ["", "TRAVEL NOTES:"]
    lines += [f"- {heading}: {text}" for heading, text in content["travel_notes"]]

    privacy = privacy_policy_text()
    lines += ["", "PRIVACY POLICY (as published on our website):"]
    lines += [privacy] if privacy else [
        "(Text not available right now. Say it is in the Policies section of our website and our team can answer.)"
    ]
    return "\n".join(lines)
