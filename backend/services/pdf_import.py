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


_LABELS = ("START POINT", "END POINT", "TOUR DURATION", "TRAVEL DATE", "TOTAL PACKAGE PRICE", "TRIP SUMMARY",
           "YOUR STAYS AT A GLANCE", "SIGNATURE EXPERIENCES", "MEAL PLAN", "ROOM TYPE")


def _normalize(text):
    """The headings are letter-spaced, and some readers return them as 'S T A R T' / 'P O I N T' on separate lines.
    Join the letters back into words and the words back into the labels we look for."""
    out = []
    for ln in (text or "").splitlines():
        ln = ln.strip()
        if re.fullmatch(r"(?:\S ){2,}\S", ln):
            ln = ln.replace(" ", "")
        if ln:
            out.append(ln)
    joined = "\n".join(out)
    for label in _LABELS:
        joined = re.sub(r"(?m)^" + re.escape(label.replace(" ", "")) + r"$", label, joined)     # 'STARTPOINT' -> 'START POINT'
        joined = re.sub(r"\n".join(map(re.escape, label.split())), label, joined)
    return joined


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


def _pdf_date(raw):
    """'D:20261115081222+05'30'' (PDF date) -> datetime, or None."""
    m = re.match(r"D?:?(\d{4})(\d{2})(\d{2})(\d{2})?(\d{2})?", str(raw or ""))
    if not m:
        return None
    try:
        return datetime.datetime(int(m[1]), int(m[2]), int(m[3]), int(m[4] or 0), int(m[5] or 0))
    except ValueError:
        return None


def _generated_at(created, quote_no):
    if created:
        return created.strftime("%d %b %Y %H:%M")
    m = re.match(r"SVK-(\d{2})(\d{2})(\d{2})-", quote_no or "")
    if m:
        try:
            return datetime.date(2000 + int(m[1]), int(m[2]), int(m[3])).strftime("%d %b %Y")
        except ValueError:
            pass
    return ""


def parse_quote_pdf(data: bytes, filename="") -> dict:
    """Read a whole PDF file (used when the PDF itself is uploaded)."""
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = [(p.extract_text() or "") for p in reader.pages]
        created = reader.metadata.creation_date if reader.metadata else None
    except Exception as exc:
        raise ValueError(f"Could not read this PDF ({exc}).")
    return parse_pages(pages, created, filename)


def parse_pages(pages, created=None, filename="") -> dict:
    """Returns {"fields": {...}, "missing": [...]}; raises ValueError when the text is not one of our quotes.
    `pages` is the text of each PDF page, one text piece per line (the browser sends this, so big PDFs need no upload)."""
    pages = [_normalize(str(p or "")) for p in (pages or [])][:40]
    if not pages or not any(p.strip() for p in pages):
        raise ValueError("This PDF has no readable text (it may be a scan or a photo).")
    if isinstance(created, str):
        created = _pdf_date(created)

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
    notes = []
    if not name:                                                   # older layout: "CLIENT NAME" label
        name = _after(first, "CLIENT NAME")
    if not name:                                                   # line after "... FOR"
        for i, ln in enumerate(first):
            if ln.upper().endswith(" FOR") and i + 1 < len(first):
                name = first[i + 1]
                break
    if not name and filename:                                      # last resort: Kashmir_Tour_Mr.Deepak_Prajapat.pdf
        stem = re.sub(r"\.pdf$", "", str(filename), flags=re.I)
        stem = re.sub(r"^Kashmir[_ ]Tour[_ -]*", "", stem, flags=re.I)
        name = re.sub(r"[_\s]+", " ", stem).strip()
        if name:
            notes.append("Client name taken from the file name.")

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
    if not cost:                                                   # older layout: the biggest INR amount is the total
        amounts = [int(a.replace(",", "")) for a in re.findall(r"(?:INR|Rs\.?|\u20b9)\s*([\d][\d,]{3,})", full)]
        amounts = [a for a in amounts if 1000 <= a <= 100_000_000]
        if amounts:
            cost = max(amounts)
            notes.append("Cost taken as the largest amount in the PDF - please check it.")

    if not quote_no and name and created:                          # same format the site prints: SVK-yymmdd-initials
        initials = "".join(w[0] for w in re.findall(r"[A-Za-z]+", name)[:3]).upper() or "GU"
        quote_no = f"SVK-{created.strftime('%y%m%d')}-{initials}"
        notes.append("This PDF has no quote number, so one was made from its date and the client's initials.")

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
        "generated_at": _generated_at(created, quote_no),
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
    return {"fields": fields, "missing": missing, "notes": notes}
