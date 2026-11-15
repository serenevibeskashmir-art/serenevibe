"""Reads a quote PDF that this site generated earlier and pulls out the fields the Google Sheet needs.

The PDFs are made by backend/services/pdf_service.py, so their wording is fixed ("QUOTE NO.", "TOUR DURATION",
"YOUR STAYS AT A GLANCE" ...). We read the text with pypdf (pure Python, no system tools) and look for those labels.
Whatever cannot be found is returned empty so the admin can type it in on the preview screen.
"""
import datetime
import io
import re

from pypdf import PdfReader

OWN_EMAILS = {"serenevibeskashmir@gmail.com"}
TIERS = ("BUDGET", "MID-RANGE", "LUXURY", "PREMIUM", "DELUXE", "ECONOMY", "STANDARD")

# Included-list lines the PDF always prints. Anything else in "What's included" is an optional extra.
_STANDARD_INCLUDED = (
    re.compile(r"^0?1\s+.+\s+for all tours and transfers", re.I),
    re.compile(r"^Sightseeing tours as per the itinerary", re.I),
    re.compile(r"^Stay at the hotels mentioned", re.I),
    re.compile(r"^Meal Plan\b", re.I),
    re.compile(r"^Accommodation (as per|on)\b", re.I),
    re.compile(r"^0?1 Hour complimentary Shikara", re.I),
    re.compile(r"^Toll taxes, fuel charges", re.I),
)


def _lines(text):
    return [ln.strip() for ln in (text or "").splitlines() if ln.strip()]


def _after(lines, label, skip=()):
    """The line right after a label line (e.g. 'START POINT' -> 'Srinagar Airport')."""
    for i, ln in enumerate(lines):
        if ln.upper() == label and i + 1 < len(lines):
            nxt = lines[i + 1]
            return "" if nxt.upper() in skip else nxt
    return ""


def _extras(all_lines):
    """Optional extras printed in 'What's included' (Union cab, Snow chain, Gondola, couple items ...)."""
    try:
        start = next(i for i, ln in enumerate(all_lines) if ln.lower() == "what's included")
        end = next(i for i in range(start, len(all_lines)) if all_lines[i].lower() == "not included")
    except StopIteration:
        return []
    items = []
    for ln in all_lines[start + 1:end]:
        if re.match(r"^\d+\s+items?\s+in your price", ln, re.I):
            continue
        if items and (ln[0].islower() or ln[0] in ")(&"):      # wrapped line: belongs to the item above
            items[-1] += " " + ln
        else:
            items.append(ln)
    return [it for it in items if not any(p.match(it) for p in _STANDARD_INCLUDED)]


def _hotels(all_lines):
    """Hotel names from 'YOUR STAYS AT A GLANCE' (one per stay, in order, no repeats)."""
    try:
        start = next(i for i, ln in enumerate(all_lines) if ln.upper() == "YOUR STAYS AT A GLANCE")
    except StopIteration:
        return []
    names = []
    for i in range(start + 1, len(all_lines) - 1):
        ln = all_lines[i]
        if ln.upper() in ("END", "SIGNATURE EXPERIENCES"):
            break
        if re.match(r"^\d+\s+nights?$", ln, re.I):
            name = all_lines[i + 1]
            if (not name.isdigit() and name.upper() not in ("END", "SIGNATURE EXPERIENCES")
                    and name.lower() not in ("hotel to be confirmed", "to be confirmed") and name not in names):
                names.append(name)
    return names


def _generated_at(reader, quote_no):
    created = None
    try:
        created = reader.metadata.creation_date if reader.metadata else None
    except Exception:
        created = None
    if created:
        return created.strftime("%d %b %Y %H:%M")
    m = re.match(r"SVK-(\d{2})(\d{2})(\d{2})-", quote_no or "")
    if m:
        try:
            return datetime.date(2000 + int(m[1]), int(m[2]), int(m[3])).strftime("%d %b %Y")
        except ValueError:
            pass
    return ""


def parse_quote_pdf(data: bytes) -> dict:
    """Returns {"fields": {...}, "missing": [...]}; raises ValueError when the file is not one of our quotes."""
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [(p.extract_text() or "") for p in reader.pages]
    except Exception as exc:
        raise ValueError(f"Could not read this PDF ({exc}).")
    if not pages or not any(pages):
        raise ValueError("This PDF has no readable text (it may be a scan or a photo).")

    full = "\n".join(pages)
    first = _lines(pages[0])
    all_lines = _lines(full)

    m = re.search(r"QUOTE NO\.\s*(SVK-[A-Z0-9-]+)", full)
    quote_no = m.group(1) if m else ""
    if not quote_no and "SERENE VIBES" not in full.upper():
        raise ValueError("This does not look like a Serene Vibes quote PDF.")

    name = ""
    m = re.search(r"Prepared for\s+(.+)", full)
    if m:
        name = m.group(1).strip()
    if not name:                                                   # one-page fallback: line after "... FOR"
        for i, ln in enumerate(first):
            if ln.upper().endswith(" FOR") and i + 1 < len(first):
                name = first[i + 1]
                break

    emails = [e for e in re.findall(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", pages[0]) if e.lower() not in OWN_EMAILS]
    email = next((e for e in emails if not e.startswith("@")), "")

    days = 0
    m = re.search(r"(\d+)\s*N\s*/\s*(\d+)\s*D", pages[0])
    if m:
        days = int(m.group(2))

    guests_txt = _after(first, "GUESTS")
    adults, kids = 0, 0
    if guests_txt.lower().startswith("couple"):
        adults = 2
    m = re.search(r"(\d+)\s*Adult", guests_txt, re.I)
    if m:
        adults = int(m.group(1))
    m = re.search(r"(\d+)\s*Kid", guests_txt, re.I)
    if m:
        kids = int(m.group(1))

    cost = ""
    m = re.search(r"TOTAL PACKAGE PRICE.*?\n\s*INR\s*\n?\s*([\d,]+)", pages[0], re.S)
    if m:
        cost = int(m.group(1).replace(",", ""))

    meal = ""
    m = re.search(r"Meal Plan\s+(EP|CP|MAP|AP)\b", full) or re.search(r"MEAL PLAN\s*\n\s*(EP|CP|MAP|AP)\b", full)
    if m:
        meal = m.group(1)

    tier = ""
    if quote_no:
        m = re.search(r"QUOTE\s+" + re.escape(quote_no) + r"\s*([A-Za-z -]+)", pages[0])
        if m:
            cand = m.group(1).strip().upper()
            tier = next((t.title() if t != "MID-RANGE" else "Mid-Range" for t in TIERS if cand.startswith(t)), "")

    fields = {
        "name": name,
        "quote_no": quote_no,
        "cost": cost,
        "travel_date": _after(first, "TRAVEL DATE"),
        "generated_at": _generated_at(reader, quote_no),
        "email": email,
        "days": days or "",
        "adults": adults or "",
        "kids": kids,
        "budget_tier": tier,
        "vehicle": _after(first, "VEHICLE"),
        "meal_plan": meal,
        "pickup": _after(first, "START POINT"),
        "drop": _after(first, "END POINT"),
        "hotels": ", ".join(_hotels(all_lines)),
        "inclusions": ", ".join(_extras(all_lines)),
    }
    missing = [k for k in ("name", "quote_no", "cost", "travel_date") if not fields[k]]
    return {"fields": fields, "missing": missing}
