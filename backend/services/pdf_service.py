import io
import os
import requests
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, PageBreak
)
from reportlab.platypus.flowables import Flowable
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Circle
from reportlab.graphics import renderPDF
import datetime

# India Standard Time is a fixed UTC+5:30 offset (no DST), so a simple
# timezone object is sufficient and avoids an extra dependency (e.g. pytz/zoneinfo tzdata).
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30), name="IST")

# ─── Brand Palette ───────────────────────────────────────────────────────────
NAVY      = colors.HexColor("#1e293b")
NAVY_DEEP = colors.HexColor("#0f172a")
NAVY_MID  = colors.HexColor("#0f3460")
SLATE     = colors.HexColor("#334155")
SKY       = colors.HexColor("#0284c7")
SKY_LIGHT = colors.HexColor("#e0f2fe")
SKY_MID   = colors.HexColor("#0ea5e9")
TEAL      = colors.HexColor("#0f766e")
TEAL_LITE = colors.HexColor("#ccfbf1")
GOLD      = colors.HexColor("#b45309")
GOLD_LITE = colors.HexColor("#fef3c7")
GOLD_MID  = colors.HexColor("#d97706")
EMERALD   = colors.HexColor("#059669")
EMERALD_LITE = colors.HexColor("#d1fae5")
ROSE      = colors.HexColor("#e11d48")
GRAY_50   = colors.HexColor("#f8fafc")
GRAY_100  = colors.HexColor("#f1f5f9")
GRAY_200  = colors.HexColor("#e2e8f0")
GRAY_400  = colors.HexColor("#94a3b8")
GRAY_600  = colors.HexColor("#475569")
WHITE     = colors.white
BLACK     = colors.HexColor("#0f172a")

PAGE_W, PAGE_H = A4          # 210 × 297 mm
MARGIN = 18 * mm

# ─── Text Sanitiser ──────────────────────────────────────────────────────────
def clean(text):
    if not text:
        return ""
    replacements = {
        "\u2014": "-", "\u2013": "-", "\u2022": "-",
        "\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'"
    }
    s = str(text)
    for orig, rep in replacements.items():
        s = s.replace(orig, rep)
    # Escape ReportLab XML special chars
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return s


# ─── Hotel Image Fetcher ─────────────────────────────────────────────────────
_IMAGE_CACHE = {}

def fetch_image_reader(src):
    """
    Load an image (URL, base64 data URL, or local file path) into a ReportLab ImageReader.
    Returns None on any failure so a bad/missing photo never breaks the PDF.
    Results are cached per-source for the lifetime of the process so the same
    hotel photo isn't re-downloaded for every day it appears on.
    """
    if not src:
        return None
    # Use a short cache key for base64 strings (they can be huge)
    cache_key = src if len(src) < 500 else src[:100] + str(len(src))
    if cache_key in _IMAGE_CACHE:
        return _IMAGE_CACHE[cache_key]

    reader = None
    try:
        if src.startswith("data:"):
            # Base64 data URL — e.g. "data:image/jpeg;base64,/9j/4AAQ..."
            # This is what the admin panel stores when photos are uploaded from device.
            import base64 as _b64
            header, encoded = src.split(",", 1)
            img_bytes = _b64.b64decode(encoded)
            reader = ImageReader(io.BytesIO(img_bytes))
        elif src.startswith("http://") or src.startswith("https://"):
            resp = requests.get(src, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            reader = ImageReader(io.BytesIO(resp.content))
        else:
            # Treat as a local file path (e.g. output/hotel_photos/xyz.jpg)
            p = Path(src)
            if p.exists():
                reader = ImageReader(str(p))
    except Exception as e:
        print(f"Hotel image fetch failed for '{src[:80]}...': {e}")
        reader = None

    _IMAGE_CACHE[cache_key] = reader
    return reader

# ─── Custom Flowables ────────────────────────────────────────────────────────
class HeroHeader(Flowable):
    """Full-width branded cover banner (compact layout)."""
    def __init__(self, width, client_name, days, start_date, adults, kids,
                 budget_tier, vehicle_type, total_cost):
        super().__init__()
        self.width  = width
        self.height = 52 * mm
        self.client_name  = client_name
        self.days         = days
        self.start_date   = start_date
        self.adults       = adults
        self.kids         = kids
        self.budget_tier  = budget_tier
        self.vehicle_type = vehicle_type
        self.total_cost   = total_cost

    def draw(self):
        c = self.canv
        w, h = self.width, self.height

        # ── Base navy fill ───────────────────────────────────────────────────
        c.setFillColor(NAVY)
        c.rect(0, 0, w, h, fill=1, stroke=0)

        # ── Decorative mountain silhouette (right side, subtle) ─────────────
        c.saveState()
        c.setFillColor(NAVY_MID)
        p = c.beginPath()
        # mountain peaks overlapping right half
        p.moveTo(w * 0.48, 0)
        p.lineTo(w * 0.60, h * 0.70)
        p.lineTo(w * 0.68, h * 0.45)
        p.lineTo(w * 0.76, h * 0.78)
        p.lineTo(w * 0.83, h * 0.38)
        p.lineTo(w * 0.90, h * 0.62)
        p.lineTo(w * 0.95, h * 0.52)
        p.lineTo(w, h * 0.65)
        p.lineTo(w, 0)
        p.close()
        c.drawPath(p, fill=1, stroke=0)
        c.restoreState()

        # ── Stronger diagonal right swatch ──────────────────────────────────
        c.saveState()
        c.setFillColor(colors.HexColor("#0a1628"))
        p2 = c.beginPath()
        p2.moveTo(w * 0.58, 0)
        p2.lineTo(w, 0)
        p2.lineTo(w, h)
        p2.lineTo(w * 0.73, h)
        p2.close()
        c.drawPath(p2, fill=1, stroke=0)
        c.restoreState()

        # ── Top accent bar (SKY stripe) ──────────────────────────────────────
        c.setFillColor(SKY)
        c.rect(0, h - 3*mm, w, 3*mm, fill=1, stroke=0)

        # ── Bottom accent bar ────────────────────────────────────────────────
        c.setFillColor(SKY)
        c.rect(0, 0, w, 1.2*mm, fill=1, stroke=0)

        # ── Brand name ──────────────────────────────────────────────────────
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 16.5)
        c.drawString(6*mm, h - 13*mm, "SERENE VIBES KASHMIR")

        # Tagline with small decorative bars
        c.setFillColor(SKY)
        c.setFont("Helvetica-Oblique", 8.5)
        tagline = "  A Poem In Motion  "
        c.drawString(6*mm, h - 18.5*mm, tagline)

        # Thin separator line (dual-tone)
        c.setStrokeColor(SKY)
        c.setLineWidth(0.8)
        c.line(6*mm, h - 20.5*mm, w * 0.38, h - 20.5*mm)
        c.setStrokeColor(TEAL)
        c.setLineWidth(0.4)
        c.line(w * 0.38 + 1, h - 20.5*mm, w * 0.50, h - 20.5*mm)

        # ── Document label ──────────────────────────────────────────────────
        c.setFillColor(GRAY_400)
        c.setFont("Helvetica", 7)
        c.drawString(6*mm, h - 24.5*mm, "CUSTOMISED TOUR ITINERARY")

        # ── Client name ─────────────────────────────────────────────────────
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(6*mm, h - 32*mm, clean(self.client_name))

        # ── Stat pills (Days / Pax / Date / Vehicle) ────────────────────────
        pills = [
            (f"{self.days} Days", SKY),
            (f"{self.adults} Adults" + (f" + {self.kids} Kids" if int(self.kids or 0) else ""), TEAL),
            (clean(str(self.start_date)), GOLD_MID),
            (clean(str(self.vehicle_type)), colors.HexColor("#7c3aed")),
        ]
        px, py = 6*mm, h - 43.5*mm
        pill_h = 6.5*mm
        for label, bg in pills:
            lw = c.stringWidth(label, "Helvetica-Bold", 8) + 12
            # Pill shadow
            c.setFillColor(colors.HexColor("#00000033"))
            c.roundRect(px + 0.5, py - 2*mm, lw, pill_h, 2.2*mm, fill=1, stroke=0)
            # Pill fill
            c.setFillColor(bg)
            c.roundRect(px, py - 1.5*mm, lw, pill_h, 2.2*mm, fill=1, stroke=0)
            # Pill text
            c.setFillColor(WHITE)
            c.setFont("Helvetica-Bold", 8)
            c.drawString(px + 6, py + 1*mm, label)
            px += lw + 5

        # ── Budget badge — ribbon style (top-right) ──────────────────────────
        badge_label = clean(str(self.budget_tier)) + " Package"
        bw = c.stringWidth(badge_label, "Helvetica-Bold", 9) + 18
        bx = w - bw - 6*mm
        by = h - 19*mm
        # Badge shadow
        c.setFillColor(colors.HexColor("#00000033"))
        c.roundRect(bx + 0.8, by - 2.8*mm, bw, 9*mm, 3*mm, fill=1, stroke=0)
        # Badge fill
        c.setFillColor(GOLD_MID)
        c.roundRect(bx, by - 2.5*mm, bw, 9*mm, 3*mm, fill=1, stroke=0)
        # Ribbon notch on left edge
        c.setFillColor(GOLD)
        c.roundRect(bx, by - 2.5*mm, 5*mm, 9*mm, 0, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(bx + 9, by + 0.8*mm, badge_label)

        # ── Total cost (bottom-right) with emerald pill ───────────────────────
        cost_str = f"INR {int(self.total_cost):,}" if str(self.total_cost).replace(",","").isdigit() else clean(str(self.total_cost))
        # Cost label
        c.setFillColor(GRAY_400)
        c.setFont("Helvetica", 7)
        c.drawRightString(w - 6*mm, h - 38*mm, "ESTIMATED TOTAL COST")
        # Cost value in emerald pill
        cw = c.stringWidth(cost_str, "Helvetica-Bold", 11.5) + 14
        cx = w - cw - 6*mm
        cy = h - 34.5*mm
        c.setFillColor(EMERALD)
        c.roundRect(cx, cy - 1.5*mm, cw, 7*mm, 2*mm, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 11.5)
        c.drawString(cx + 7, cy + 0.8*mm, cost_str)


class DayBanner(Flowable):
    """Styled banner for each day heading."""
    def __init__(self, width, day_num, title, overnight=""):
        super().__init__()
        self.width    = width
        self.height   = 11 * mm
        self.day_num  = day_num
        self.title    = title
        self.overnight = overnight

    def draw(self):
        c = self.canv
        w, h = self.width, self.height

        # Main bar with slight rounding
        c.setFillColor(NAVY)
        c.roundRect(0, 0, w, h, 2*mm, fill=1, stroke=0)

        # Left accent strip (wider, deeper blue)
        c.setFillColor(SKY)
        c.roundRect(0, 0, 15*mm, h, 2*mm, fill=1, stroke=0)
        # Fill right side of accent so left edge is fully rounded
        c.setFillColor(NAVY)
        c.rect(11*mm, 0, 4*mm, h, fill=1, stroke=0)

        # Thin sky accent rule below the banner
        c.setStrokeColor(SKY_MID)
        c.setLineWidth(0.8)
        c.line(0, -1*mm, w, -1*mm)

        # Day number pill (rounded rect instead of just text)
        pill_x, pill_y = 1.5*mm, h/2 - 3.5*mm
        pill_w, pill_h2 = 12*mm, 7*mm
        c.setFillColor(colors.HexColor("#0369a1"))
        c.roundRect(pill_x, pill_y, pill_w, pill_h2, 1.8*mm, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 9.5)
        c.drawCentredString(7.5*mm, pill_y + 2.2*mm, str(self.day_num))

        # Title
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 9.5)
        title = clean(self.title)
        max_w = w - 18*mm - 34*mm
        while c.stringWidth(title, "Helvetica-Bold", 9.5) > max_w and len(title) > 10:
            title = title[:-4] + "..."
        c.drawString(17*mm, h/2 - 3, title)

        # Overnight badge with moon symbol
        if self.overnight and self.overnight.lower() not in ("departure", ""):
            moon = "\u25D0"  # half circle as moon approximation
            ov_label = f"Stay: {clean(self.overnight)}"
            ov_w = c.stringWidth(ov_label, "Helvetica-Bold", 7.5) + 14
            ox = w - ov_w - 4*mm
            oy = 2*mm
            # Badge shadow
            c.setFillColor(colors.HexColor("#00000033"))
            c.roundRect(ox + 0.5, oy - 0.5, ov_w, 7*mm, 2*mm, fill=1, stroke=0)
            # Badge fill
            c.setFillColor(TEAL)
            c.roundRect(ox, oy, ov_w, 7*mm, 2*mm, fill=1, stroke=0)
            # Moon dot accent
            c.setFillColor(colors.HexColor("#99f6e4"))
            c.circle(ox + 5, oy + 3.5*mm, 2*mm, fill=1, stroke=0)
            c.setFillColor(WHITE)
            c.setFont("Helvetica-Bold", 7.5)
            c.drawString(ox + 10, oy + 2*mm, ov_label)


class RouteBadge(Flowable):
    """Highlighted route label."""
    def __init__(self, width, route):
        super().__init__()
        self.width  = width
        self.height = 8 * mm
        self.route  = route

    def draw(self):
        c = self.canv
        c.setFillColor(GOLD_LITE)
        c.setStrokeColor(GOLD)
        c.setLineWidth(0.5)
        c.roundRect(0, 0, self.width, self.height, 2*mm, fill=1, stroke=1)
        c.setFillColor(GOLD)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(8, self.height/2 - 3, "ROUTE:")
        c.setFillColor(BLACK)
        c.setFont("Helvetica", 8)
        route_txt = clean(self.route)
        max_w = self.width - 40
        while c.stringWidth(route_txt, "Helvetica", 8) > max_w and len(route_txt) > 6:
            route_txt = route_txt[:-4] + "..."
        c.drawString(38, self.height/2 - 3, route_txt)


class HotelPhotoStrip(Flowable):
    """
    Renders a hotel name/place header followed by a row of reference photos
    (2+ images side by side). Images that fail to load are simply skipped;
    if fewer than 2 images load successfully, a "photo unavailable" tile
    fills the remaining slot so the layout never breaks.
    """
    def __init__(self, width, hotel_name, hotel_place, image_sources, photo_h=42*mm):
        super().__init__()
        self.width       = width
        self.hotel_name  = hotel_name
        self.hotel_place = hotel_place
        self.photo_h     = photo_h
        self.header_h    = 8 * mm
        self.gap         = 3 * mm

        # Resolve images up front so we know the real height before drawing
        readers = []
        for src in (image_sources or []):
            r = fetch_image_reader(src)
            if r is not None:
                readers.append(r)
        self.readers = readers
        # Show at least 2 slots (real photos + placeholder fallback tiles)
        self.slot_count = max(2, len(readers))
        self.height = self.header_h + self.photo_h + 4*mm

    def draw(self):
        c = self.canv
        w = self.width

        # Header bar: hotel name + place
        c.setFillColor(GRAY_100)
        c.roundRect(0, self.height - self.header_h, w, self.header_h, 1.5*mm, fill=1, stroke=0)
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(3*mm, self.height - self.header_h + 2.3*mm, clean(self.hotel_name))
        c.setFillColor(GRAY_600)
        c.setFont("Helvetica", 7.5)
        c.drawRightString(w - 3*mm, self.height - self.header_h + 2.3*mm, clean(self.hotel_place))

        # Photo row
        n = self.slot_count
        slot_w = (w - (n - 1) * self.gap) / n
        y = self.height - self.header_h - self.photo_h - 1*mm

        for i in range(n):
            x = i * (slot_w + self.gap)
            if i < len(self.readers):
                reader = self.readers[i]
                try:
                    iw, ih = reader.getSize()
                    scale = min(slot_w / iw, self.photo_h / ih)
                    draw_w, draw_h = iw * scale, ih * scale
                    ox = x + (slot_w - draw_w) / 2
                    oy = y + (self.photo_h - draw_h) / 2
                    c.saveState()
                    # clip to the slot so the border looks clean
                    p = c.beginPath()
                    p.rect(x, y, slot_w, self.photo_h)
                    c.clipPath(p, stroke=0)
                    c.drawImage(reader, ox, oy, width=draw_w, height=draw_h,
                                preserveAspectRatio=True, mask='auto')
                    c.restoreState()
                except Exception:
                    self._placeholder(c, x, y, slot_w)
            else:
                self._placeholder(c, x, y, slot_w)

            # Frame
            c.setStrokeColor(GRAY_200)
            c.setLineWidth(0.6)
            c.rect(x, y, slot_w, self.photo_h, fill=0, stroke=1)

    def _placeholder(self, c, x, y, slot_w):
        c.setFillColor(GRAY_100)
        c.rect(x, y, slot_w, self.photo_h, fill=1, stroke=0)
        c.setFillColor(GRAY_400)
        c.setFont("Helvetica-Oblique", 7.5)
        c.drawCentredString(x + slot_w/2, y + self.photo_h/2, "Photo unavailable")



class OfficialSeal(Flowable):
    """
    Professional circular seal for Serene Vibes Kashmir.
    Outer ring: gold tick marks + navy band with curved arc text.
    Inner circle: company logo image clipped into a circle.
    """

    @staticmethod
    def _find_logo():
        """
        Search for logo.jpeg in several likely locations and return the
        first path that exists, or None if not found anywhere.
        Checked in order:
          1. SEAL_LOGO_PATH environment variable (explicit override)
          2. Same directory as this .py file
          3. Current working directory (where Flask / gunicorn starts)
          4. backend/ subfolder of cwd
        """
        candidates = []
        env_path = os.environ.get("SEAL_LOGO_PATH", "")
        if env_path:
            candidates.append(env_path)
        try:
            candidates.append(
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.jpeg")
            )
        except Exception:
            pass
        candidates.append(os.path.join(os.getcwd(), "logo.jpeg"))
        candidates.append(os.path.join(os.getcwd(), "backend", "logo.jpeg"))
        for path in candidates:
            if path and os.path.exists(path):
                print(f"OfficialSeal: logo found at {path}")
                return path
        print(f"OfficialSeal: logo NOT found. Searched: {candidates}")
        return None

    def __init__(self, size=55*mm):
        super().__init__()
        self.size   = size
        self.width  = size
        self.height = size
        self._logo  = None
        logo_path   = self._find_logo()
        if logo_path:
            try:
                self._logo = ImageReader(logo_path)
                print(f"OfficialSeal: logo loaded OK from {logo_path}")
            except Exception as e:
                print(f"OfficialSeal: ImageReader failed for {logo_path}: {e}")

    def draw(self):
        import math
        c  = self.canv
        cx = self.size / 2
        cy = self.size / 2
        R  = self.size / 2          # outer radius

        # ── Layer 1: white background disc ────────────────────────────────
        c.setFillColor(WHITE)
        c.circle(cx, cy, R, fill=1, stroke=0)

        # ── Layer 2: outermost navy ring border ───────────────────────────
        c.setFillColor(colors.HexColor("#e8f4f8"))
        c.setStrokeColor(colors.HexColor("#1e3a5f"))
        c.setLineWidth(2.5)
        c.circle(cx, cy, R, fill=1, stroke=1)

        # Thin gold outer accent ring
        c.setStrokeColor(colors.HexColor("#c9a227"))
        c.setLineWidth(1.0)
        c.circle(cx, cy, R * 0.965, fill=0, stroke=1)

        # ── Layer 3: gold tick marks every 30° ────────────────────────────
        tick_out = R * 0.955
        tick_in  = R * 0.915
        c.setStrokeColor(colors.HexColor("#c9a227"))
        c.setLineWidth(1.4)
        for deg in range(0, 360, 30):
            a = math.radians(deg)
            c.line(cx + tick_out * math.cos(a), cy + tick_out * math.sin(a),
                   cx + tick_in  * math.cos(a), cy + tick_in  * math.sin(a))

        # Thin sky inner accent ring (separates ticks from arc-text band)
        c.setStrokeColor(SKY)
        c.setLineWidth(0.7)
        c.circle(cx, cy, R * 0.905, fill=0, stroke=1)

        # ── Layer 4: navy arc-text band ────────────────────────────────────
        # Filled navy annulus between R*0.905 and R*0.75
        c.setFillColor(colors.HexColor("#1e3a5f"))
        c.circle(cx, cy, R * 0.905, fill=1, stroke=0)   # fill to band outer
        c.setFillColor(WHITE)
        c.circle(cx, cy, R * 0.748, fill=1, stroke=0)   # punch out inner

        # Thin gold ring separating band from logo circle
        c.setStrokeColor(colors.HexColor("#c9a227"))
        c.setLineWidth(1.2)
        c.circle(cx, cy, R * 0.748, fill=0, stroke=1)

        # ── Layer 5: arc text "SERENE VIBES KASHMIR" (top) ────────────────
        label    = "SERENE VIBES KASHMIR"
        arc_r    = R * 0.826
        font_sz  = R * 0.118
        n        = len(label)
        span     = 158.0
        start    = 90 + span / 2
        step     = -span / (n - 1)

        c.setFillColor(colors.HexColor("#c9a227"))
        c.setFont("Helvetica-Bold", font_sz)
        for i, ch in enumerate(label):
            a  = math.radians(start + i * step)
            lx = cx + arc_r * math.cos(a)
            ly = cy + arc_r * math.sin(a)
            c.saveState()
            c.translate(lx, ly)
            c.rotate(math.degrees(a) - 90)
            c.drawString(-c.stringWidth(ch, "Helvetica-Bold", font_sz) / 2, 0, ch)
            c.restoreState()

        # ── Layer 6: arc text "A POEM IN MOTION" (bottom) ─────────────────
        sub      = "A POEM IN MOTION"
        arc_r2   = R * 0.824
        sub_sz   = R * 0.098
        n2       = len(sub)
        span2    = 126.0
        start2   = -90 - span2 / 2
        step2    = span2 / (n2 - 1)

        c.setFillColor(colors.HexColor("#93c5fd"))
        c.setFont("Helvetica-Oblique", sub_sz)
        for i, ch in enumerate(sub):
            a  = math.radians(start2 + i * step2)
            lx = cx + arc_r2 * math.cos(a)
            ly = cy + arc_r2 * math.sin(a)
            c.saveState()
            c.translate(lx, ly)
            c.rotate(math.degrees(a) + 90)
            c.drawString(-c.stringWidth(ch, "Helvetica-Oblique", sub_sz) / 2, 0, ch)
            c.restoreState()

        # ── Layer 7: logo image clipped into inner circle ──────────────────
        inner_r = R * 0.735          # radius of the logo circle
        img_d   = inner_r * 2        # diameter = side of the square we draw into
        img_x   = cx - inner_r       # bottom-left x of bounding square
        img_y   = cy - inner_r       # bottom-left y of bounding square

        c.saveState()
        # Build a circular clip path centred on (cx, cy)
        p = c.beginPath()
        # Approximate circle with 4-bezier-arc segments
        k = 0.5522847498          # magic constant for circular bezier
        r = inner_r
        p.moveTo(cx + r, cy)
        p.curveTo(cx + r, cy + k*r,  cx + k*r, cy + r,  cx,     cy + r)
        p.curveTo(cx - k*r, cy + r,  cx - r, cy + k*r,  cx - r, cy)
        p.curveTo(cx - r, cy - k*r,  cx - k*r, cy - r,  cx,     cy - r)
        p.curveTo(cx + k*r, cy - r,  cx + r, cy - k*r,  cx + r, cy)
        p.close()
        c.clipPath(p, stroke=0)

        if self._logo:
            # Draw the square logo, it gets clipped to the circle
            c.drawImage(self._logo, img_x, img_y,
                        width=img_d, height=img_d,
                        preserveAspectRatio=False, mask='auto')
        else:
            # Fallback: plain navy fill if logo missing
            c.setFillColor(colors.HexColor("#1e3a5f"))
            c.rect(img_x, img_y, img_d, img_d, fill=1, stroke=0)

        c.restoreState()

        # ── Layer 8: thin gold border over the logo circle edge ────────────
        c.setStrokeColor(colors.HexColor("#c9a227"))
        c.setLineWidth(1.0)
        c.circle(cx, cy, inner_r, fill=0, stroke=1)

        # Centre dot
        c.setFillColor(colors.HexColor("#c9a227"))
        c.circle(cx, cy, R * 0.022, fill=1, stroke=0)


class SectionTitle(Flowable):
    """Bold section divider with accent line."""
    def __init__(self, width, title, icon=""):
        super().__init__()
        self.width  = width
        self.height = 12 * mm
        self.title  = title
        self.icon   = icon

    def draw(self):
        c = self.canv
        # Full bar
        c.setFillColor(NAVY)
        c.roundRect(0, 3*mm, self.width, self.height - 3*mm, 2*mm, fill=1, stroke=0)
        # Left accent – thicker with notch effect
        c.setFillColor(SKY)
        c.roundRect(0, 3*mm, 5*mm, self.height - 3*mm, 1.5*mm, fill=1, stroke=0)
        # Notch cutout (triangle)
        c.setFillColor(NAVY)
        pn = c.beginPath()
        pn.moveTo(5*mm, self.height - 1.5*mm)
        pn.lineTo(9*mm, self.height - 1.5*mm)
        pn.lineTo(5*mm, self.height - 5*mm)
        pn.close()
        c.drawPath(pn, fill=1, stroke=0)
        # SKY underline rule below the section bar
        c.setStrokeColor(SKY)
        c.setLineWidth(1.5)
        c.line(0, 2.2*mm, self.width, 2.2*mm)
        # Text
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 11)
        label = (self.icon + "  " if self.icon else "") + self.title
        c.drawString(10*mm, self.height - 5*mm, label)


# ─── Kashmir Route Map (Layout 3: map top + legend table below) ──────────────
class KashmirRouteMap(Flowable):
    """
    Full-width map panel with real GPS pin positions for Kashmir tour stops,
    topped by a stylised terrain map and followed by a per-day legend table.
    All drawing uses ReportLab canvas primitives — no external image needed.
    """

    # Real GPS coordinates for key Kashmir destinations
    STOPS = {
        "srinagar":    (34.0837, 74.7973),
        "gulmarg":     (34.0484, 74.3805),
        "pahalgam":    (34.0161, 75.3147),
        "sonamarg":    (34.3088, 75.2969),
        "doodhpathri": (33.8700, 74.3700),
    }

    # Bounding box of the map viewport
    LAT_MIN, LAT_MAX = 33.3, 34.85
    LON_MIN, LON_MAX = 73.6, 76.1

    # Colours used only inside this flowable
    MAP_BG      = colors.HexColor("#dbeafe")
    LAND_COL    = colors.HexColor("#bbf7d0")
    SNOW_COL    = colors.HexColor("#e0f2fe")
    LAKE_COL    = colors.HexColor("#60a5fa")
    ROAD_COL    = colors.HexColor("#94a3b8")
    ROUTE_COL   = colors.HexColor("#0284c7")
    PIN_COLORS  = {
        "srinagar":    (colors.HexColor("#1e3a5f"), colors.HexColor("#3b82f6")),
        "gulmarg":     (colors.HexColor("#0f4c3a"), colors.HexColor("#14b8a6")),
        "pahalgam":    (colors.HexColor("#78350f"), colors.HexColor("#f59e0b")),
        "sonamarg":    (colors.HexColor("#3b0764"), colors.HexColor("#8b5cf6")),
        "doodhpathri": (colors.HexColor("#374151"), colors.HexColor("#9ca3af")),
        "departure":   (colors.HexColor("#7f1d1d"), colors.HexColor("#ef4444")),
    }
    ROW_COLORS = [
        colors.HexColor("#eff6ff"),  # blue-50
        colors.HexColor("#f0fdf4"),  # green-50 (teal tone)
        colors.HexColor("#fffbeb"),  # amber-50
        colors.HexColor("#fffbeb"),  # amber-50
        colors.HexColor("#f5f3ff"),  # purple-50
        colors.HexColor("#fff1f2"),  # rose-50
    ]
    HDR_ACCENT = [
        colors.HexColor("#3b82f6"),
        colors.HexColor("#14b8a6"),
        colors.HexColor("#f59e0b"),
        colors.HexColor("#f59e0b"),
        colors.HexColor("#8b5cf6"),
        colors.HexColor("#ef4444"),
    ]

    MAP_H   = 62 * mm   # height of the terrain map panel
    TABLE_H = 9 * mm    # height of each legend row
    HDR_H   = 7 * mm    # height of legend header row

    def __init__(self, width, timeline):
        super().__init__()
        self.width    = width
        self.timeline = timeline
        self._build_legend_rows()
        self.height = self.MAP_H + self.HDR_H + self.TABLE_H * len(self._rows) + 2 * mm

    # ── helpers ──────────────────────────────────────────────────────────────
    def _build_legend_rows(self):
        """Convert timeline entries into legend rows with GPS coords.

        Pin placement uses the *destination* the vehicle actually drives to,
        derived from transit_route (e.g. "Srinagar to Gulmarg: Overnight Srinagar"
        → pin on Gulmarg).  overnight_stay is kept as a fallback for days that
        have no transit_route set, and is always shown in the "Overnight" column.
        """
        GPS_LABEL = {
            "srinagar":    "34.08°N  74.80°E",
            "gulmarg":     "34.05°N  74.38°E",
            "pahalgam":    "34.02°N  75.31°E",
            "sonamarg":    "34.31°N  75.30°E",
            "doodhpathri": "33.87°N  74.37°E",
        }

        def _extract_destination(route_str):
            """
            Parse the travel destination from a transit_route label.
            Handles patterns like:
              "Srinagar to Gulmarg: Overnight Srinagar"  → "gulmarg"
              "Airport Pickup and Local Sightseeing: Overnight Srinagar" → "srinagar"
              "Airport Drop-Departure"                   → "departure"
              "Pahalgam to Srinagar: Overnight Srinagar" → "srinagar"
            Returns a key matching self.STOPS or "departure".
            """
            r = route_str.lower().strip()

            # Departure day — no meaningful destination pin
            if "departure" in r or "airport drop" in r:
                return "departure"

            # "X to Y: ..." — the destination is Y (before any colon)
            if " to " in r:
                after_to = r.split(" to ", 1)[1]
                dest_word = after_to.split(":")[0].split()[0]  # first word after "to"
                for k in self.STOPS:
                    if k in dest_word:
                        return k

            # Arrival / pickup day — pin on the first recognised city in the label
            for k in self.STOPS:
                if k in r:
                    return k

            return "srinagar"  # ultimate fallback

        self._rows = []
        for idx, day in enumerate(self.timeline, start=1):
            overnight = str(day.get("overnight_stay", "")).strip()
            transit_route = str(day.get("transit_route") or day.get("title") or "").strip()

            # Decide which city to PIN on the map (travel destination)
            if transit_route:
                matched = _extract_destination(transit_route)
            else:
                # No route info — fall back to overnight_stay as before
                key = overnight.lower()
                matched = "srinagar"
                for k in self.STOPS:
                    if k in key:
                        matched = k
                        break
                if "departure" in key or overnight in ("Departure", ""):
                    matched = "departure"

            # Display location label = the destination city (capitalised)
            if matched == "departure":
                loc_label = overnight if overnight else "Departure"
            else:
                loc_label = matched.capitalize()

            title = str(day.get("title") or day.get("date") or f"Day {idx}")
            if len(title) > 42:
                title = title[:40] + "..."

            self._rows.append({
                "day":      idx,
                "loc":      loc_label,
                "gps":      GPS_LABEL.get(matched, "34.08°N  74.80°E"),
                "activity": title,
                "night":    overnight if overnight else "Srinagar",
                "key":      matched,
            })

    def _proj(self, lat, lon, map_w, map_h):
        """Project (lat, lon) → (x, y) within the map rectangle."""
        x = (lon - self.LON_MIN) / (self.LON_MAX - self.LON_MIN) * map_w
        y = (1.0 - (lat - self.LAT_MIN) / (self.LAT_MAX - self.LAT_MIN)) * map_h
        return x, y

    def _poly(self, c, pts, map_w, map_h, ox, oy, fill=None, stroke=None, lw=0.5):
        p = c.beginPath()
        for i, (lat, lon) in enumerate(pts):
            x, y = self._proj(lat, lon, map_w, map_h)
            if i == 0:
                p.moveTo(ox + x, oy + y)
            else:
                p.lineTo(ox + x, oy + y)
        p.close()
        fs = 1 if fill else 0
        ss = 1 if stroke else 0
        if fill:
            c.setFillColor(fill)
        if stroke:
            c.setStrokeColor(stroke)
            c.setLineWidth(lw)
        c.drawPath(p, fill=fs, stroke=ss)

    def _line(self, c, pts, map_w, map_h, ox, oy, color, lw, dash=None):
        if dash:
            c.setDash(*dash)
        p = c.beginPath()
        for i, (lat, lon) in enumerate(pts):
            x, y = self._proj(lat, lon, map_w, map_h)
            if i == 0:
                p.moveTo(ox + x, oy + y)
            else:
                p.lineTo(ox + x, oy + y)
        c.setStrokeColor(color)
        c.setLineWidth(lw)
        c.drawPath(p, fill=0, stroke=1)
        if dash:
            c.setDash()

    def _pin(self, c, lat, lon, map_w, map_h, ox, oy, inner_col, ring_col, label, day_str):
        x, y = self._proj(lat, lon, map_w, map_h)
        px, py = ox + x, oy + y
        R, r = 4.2 * mm, 2.8 * mm
        # Shadow (offset circle)
        c.setFillColor(colors.HexColor("#00000022"))
        c.circle(px + 0.5, py - 0.8, R, fill=1, stroke=0)
        # Outer ring
        c.setFillColor(ring_col)
        c.circle(px, py, R, fill=1, stroke=0)
        # Inner circle
        c.setFillColor(inner_col)
        c.circle(px, py, r, fill=1, stroke=0)
        # Day number
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 5.5)
        c.drawCentredString(px, py - 1.8, day_str)
        # Name bubble above pin
        bubble_w = c.stringWidth(label, "Helvetica-Bold", 6) + 6
        bx = px - bubble_w / 2
        by = py + R + 1
        c.setFillColor(colors.HexColor("#ffffffee"))
        c.setStrokeColor(ring_col)
        c.setLineWidth(0.5)
        c.roundRect(bx, by, bubble_w, 4.5 * mm, 1 * mm, fill=1, stroke=1)
        c.setFillColor(inner_col)
        c.setFont("Helvetica-Bold", 6)
        c.drawCentredString(px, by + 2.8 * mm, label)

    # ── main draw ─────────────────────────────────────────────────────────────
    def draw(self):
        c    = self.canv
        w    = self.width
        mh   = self.MAP_H          # map panel height
        pad  = 3 * mm
        map_w = w - 2 * pad
        map_h = mh - 2 * pad
        ox   = pad
        oy_base = self.height - mh  # map sits at top of flowable

        # ── MAP PANEL background ─────────────────────────────────────────────
        c.setFillColor(self.MAP_BG)
        c.roundRect(0, oy_base, w, mh, 3 * mm, fill=1, stroke=0)

        # ── Terrain polygons ─────────────────────────────────────────────────
        # Snow / high peaks band
        self._poly(c, [
            (34.7, 73.9), (35.0, 74.5), (34.9, 75.4),
            (34.6, 75.9), (34.4, 75.7), (34.5, 75.0),
            (34.6, 74.3), (34.7, 73.9),
        ], map_w, map_h, ox, oy_base + pad, fill=self.SNOW_COL)

        # Kashmir valley land
        self._poly(c, [
            (34.6, 73.9), (34.7, 74.5), (34.5, 75.5),
            (34.1, 75.9), (33.7, 75.7), (33.4, 75.1),
            (33.5, 74.2), (34.0, 73.8), (34.4, 73.9),
        ], map_w, map_h, ox, oy_base + pad, fill=self.LAND_COL,
           stroke=colors.HexColor("#6ee7b7"), lw=0.6)

        # Dal Lake
        self._poly(c, [
            (34.14, 74.85), (34.18, 74.92),
            (34.12, 74.95), (34.08, 74.90),
        ], map_w, map_h, ox, oy_base + pad, fill=self.LAKE_COL)

        # Wular Lake
        self._poly(c, [
            (34.35, 74.52), (34.42, 74.58),
            (34.38, 74.64), (34.30, 74.60),
        ], map_w, map_h, ox, oy_base + pad, fill=self.LAKE_COL)

        # ── Roads ────────────────────────────────────────────────────────────
        # NH44 Jammu–Srinagar
        self._line(c, [
            (33.3, 74.5), (33.6, 74.6), (33.9, 74.7), (34.09, 74.82),
        ], map_w, map_h, ox, oy_base + pad, self.ROAD_COL, 1.2)

        # Srinagar–Gulmarg
        self._line(c, [
            (34.09, 74.82), (34.05, 74.60), (34.05, 74.40), (34.048, 74.38),
        ], map_w, map_h, ox, oy_base + pad, self.ROAD_COL, 0.8)

        # Srinagar–Pahalgam
        self._line(c, [
            (34.09, 74.82), (33.95, 75.10), (33.80, 75.20), (34.016, 75.31),
        ], map_w, map_h, ox, oy_base + pad, self.ROAD_COL, 0.8)

        # Srinagar–Sonamarg
        self._line(c, [
            (34.09, 74.82), (34.20, 74.92), (34.28, 75.15), (34.31, 75.29),
        ], map_w, map_h, ox, oy_base + pad, self.ROAD_COL, 0.8)

        # Srinagar–Doodhpathri
        self._line(c, [
            (34.09, 74.82), (34.00, 74.60), (33.92, 74.44), (33.87, 74.37),
        ], map_w, map_h, ox, oy_base + pad, self.ROAD_COL, 0.6, dash=[2, 2])

        # ── Journey route (dashed blue) ───────────────────────────────────────
        # Build ordered route from timeline
        route_pts = []
        for row in self._rows:
            key = row["key"]
            if key in self.STOPS:
                route_pts.append(self.STOPS[key])
            else:
                route_pts.append(self.STOPS["srinagar"])

        # Glow under route
        self._line(c, route_pts, map_w, map_h, ox, oy_base + pad,
                   colors.HexColor("#93c5fd"), 5)
        # Route itself
        self._line(c, route_pts, map_w, map_h, ox, oy_base + pad,
                   self.ROUTE_COL, 1.5, dash=[4, 3])

        # ── Pins ─────────────────────────────────────────────────────────────
        # Collect unique stops (show each location once, label with all days)
        seen = {}
        for row in self._rows:
            key = row["key"]
            if key not in seen:
                seen[key] = []
            seen[key].append(str(row["day"]))

        placed = set()
        for row in self._rows:
            key = row["key"]
            if key in placed:
                continue
            placed.add(key)
            lat, lon = self.STOPS.get(key, self.STOPS["srinagar"])
            inner, ring = self.PIN_COLORS.get(key, self.PIN_COLORS["srinagar"])
            days_str = ",".join(seen[key])
            loc_label = row["loc"].split()[0]  # first word e.g. "Srinagar"
            self._pin(c, lat, lon, map_w, map_h, ox, oy_base + pad,
                      inner, ring, loc_label, "D" + days_str)

        # ── Map header label ─────────────────────────────────────────────────
        c.setFillColor(colors.HexColor("#ffffffee"))
        c.setStrokeColor(GRAY_200)
        c.setLineWidth(0.4)
        c.roundRect(pad + 2 * mm, oy_base + mh - 9 * mm, 52 * mm, 7 * mm, 1.5 * mm, fill=1, stroke=1)
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 8)
        c.drawString(pad + 4 * mm, oy_base + mh - 5.5 * mm, "TOUR ROUTE  |  KASHMIR VALLEY")

        # ── Compass rose ─────────────────────────────────────────────────────
        cx_c = w - pad - 7 * mm
        cy_c = oy_base + mh - 9 * mm
        c.setFillColor(colors.HexColor("#ffffffdd"))
        c.circle(cx_c, cy_c, 5.5 * mm, fill=1, stroke=0)
        c.setStrokeColor(GRAY_400)
        c.setLineWidth(0.3)
        c.circle(cx_c, cy_c, 5.5 * mm, fill=0, stroke=1)
        for label, (dx, dy) in [("N", (0, 1)), ("S", (0, -1)), ("E", (1, 0)), ("W", (-1, 0))]:
            lx = cx_c + dx * 3.8 * mm
            ly = cy_c + dy * 3.8 * mm - 1.5
            c.setFillColor(colors.HexColor("#dc2626") if label == "N" else GRAY_600)
            c.setFont("Helvetica-Bold" if label == "N" else "Helvetica", 5.5)
            c.drawCentredString(lx, ly, label)
        # North arrow
        c.setFillColor(colors.HexColor("#dc2626"))
        p2 = c.beginPath()
        p2.moveTo(cx_c, cy_c + 2.5 * mm)
        p2.lineTo(cx_c + 1.2 * mm, cy_c)
        p2.lineTo(cx_c - 1.2 * mm, cy_c)
        p2.close()
        c.drawPath(p2, fill=1, stroke=0)

        # ── Scale bar ────────────────────────────────────────────────────────
        # 0.5 lon degrees at lat 34 ≈ 46 km
        lon_span = self.LON_MAX - self.LON_MIN
        scale_px = (0.5 / lon_span) * map_w
        sx = pad + 2 * mm
        sy = oy_base + 3 * mm
        c.setFillColor(colors.HexColor("#ffffffcc"))
        c.roundRect(sx - 1 * mm, sy - 1 * mm, scale_px + 20 * mm, 5 * mm, 1 * mm, fill=1, stroke=0)
        c.setFillColor(NAVY)
        c.rect(sx, sy + 1 * mm, scale_px, 1.5 * mm, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.rect(sx, sy + 1 * mm, scale_px / 2, 1.5 * mm, fill=1, stroke=0)
        c.setFillColor(GRAY_600)
        c.setFont("Helvetica", 5.5)
        c.drawString(sx + scale_px + 1.5 * mm, sy + 1.2 * mm, "~46 km")
        c.drawString(sx, sy - 0.2 * mm, "0")

        # ── LEGEND TABLE ─────────────────────────────────────────────────────
        col_w = [
            w * 0.07,   # Day
            w * 0.15,   # Location
            w * 0.20,   # GPS
            w * 0.40,   # Activity
            w * 0.18,   # Overnight
        ]
        headers = ["Day", "Location", "GPS Coordinates", "Activity / Route", "Overnight"]
        col_x = [sum(col_w[:i]) for i in range(len(col_w))]

        # Header bar
        hy = oy_base - self.HDR_H
        c.setFillColor(NAVY)
        c.rect(0, hy, w, self.HDR_H, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Helvetica-Bold", 7)
        for i, hdr in enumerate(headers):
            tx = col_x[i] + (col_w[i] / 2 if i == 0 else 3 * mm)
            align = "centre" if i == 0 else "left"
            if align == "centre":
                c.drawCentredString(tx, hy + self.HDR_H / 2 - 2, hdr)
            else:
                c.drawString(tx, hy + self.HDR_H / 2 - 2, hdr)

        # Data rows
        for ri, row in enumerate(self._rows):
            ry = hy - (ri + 1) * self.TABLE_H
            row_bg = self.ROW_COLORS[ri] if ri < len(self.ROW_COLORS) else GRAY_50
            c.setFillColor(row_bg)
            c.rect(0, ry, w, self.TABLE_H, fill=1, stroke=0)

            # Row border
            c.setStrokeColor(GRAY_200)
            c.setLineWidth(0.3)
            c.line(0, ry, w, ry)

            accent = self.HDR_ACCENT[ri] if ri < len(self.HDR_ACCENT) else SKY

            # Day circle
            cx2 = col_x[0] + col_w[0] / 2
            cy2 = ry + self.TABLE_H / 2
            c.setFillColor(accent)
            c.circle(cx2, cy2, 3 * mm, fill=1, stroke=0)
            c.setFillColor(WHITE)
            c.setFont("Helvetica-Bold", 7)
            c.drawCentredString(cx2, cy2 - 2, str(row["day"]))

            # Location
            c.setFillColor(BLACK)
            c.setFont("Helvetica-Bold", 7)
            c.drawString(col_x[1] + 3 * mm, ry + self.TABLE_H / 2 - 1.5, clean(row["loc"]))

            # GPS
            c.setFillColor(GRAY_600)
            c.setFont("Helvetica", 6.5)
            c.drawString(col_x[2] + 3 * mm, ry + self.TABLE_H / 2 - 1.5, row["gps"])

            # Activity (truncate to fit)
            act = clean(row["activity"])
            max_act_w = col_w[3] - 6 * mm
            c.setFont("Helvetica", 6.5)
            while c.stringWidth(act, "Helvetica", 6.5) > max_act_w and len(act) > 6:
                act = act[:-4] + "..."
            c.setFillColor(SLATE)
            c.drawString(col_x[3] + 3 * mm, ry + self.TABLE_H / 2 - 1.5, act)

            # Overnight badge
            night = clean(row["night"])
            nw = c.stringWidth(night, "Helvetica-Bold", 6) + 4 * mm
            nx2 = col_x[4] + 3 * mm
            ny2 = ry + self.TABLE_H / 2 - 2.2 * mm
            c.setFillColor(colors.HexColor("#e0f2fe"))
            c.setStrokeColor(accent)
            c.setLineWidth(0.4)
            c.roundRect(nx2, ny2, nw, 4 * mm, 1 * mm, fill=1, stroke=1)
            c.setFillColor(accent)
            c.setFont("Helvetica-Bold", 6)
            c.drawString(nx2 + 2 * mm, ny2 + 1.2 * mm, night)

        # Bottom border of table
        bot_y = hy - len(self._rows) * self.TABLE_H
        c.setStrokeColor(GRAY_200)
        c.setLineWidth(0.3)
        c.line(0, bot_y, w, bot_y)

        # Column dividers across full table height
        table_top = hy + self.HDR_H
        table_bot = bot_y
        for i in range(1, len(col_x)):
            c.setStrokeColor(GRAY_200)
            c.setLineWidth(0.3)
            c.line(col_x[i], table_bot, col_x[i], table_top)


# ─── Helper: build styles ─────────────────────────────────────────────────────
def make_styles():
    base = getSampleStyleSheet()

    def P(name, **kw):
        return ParagraphStyle(name, **kw)

    return {
        "activity_time": P("AT",
            fontName="Helvetica-Bold", fontSize=8.5, textColor=SKY,
            leftIndent=4, spaceAfter=1),
        "activity_desc": P("AD",
            fontName="Helvetica", fontSize=8.5, textColor=BLACK,
            leftIndent=4, spaceAfter=4, leading=13.5),
        "hotel_cell": P("HC",
            fontName="Helvetica", fontSize=8, textColor=BLACK, leading=11),
        "hotel_cell_bold": P("HCB",
            fontName="Helvetica-Bold", fontSize=8.5, textColor=NAVY, leading=11),
        "footer_note": P("FN",
            fontName="Helvetica-Oblique", fontSize=7.5, textColor=GRAY_400,
            alignment=TA_CENTER),
        "inclusion": P("INC",
            fontName="Helvetica", fontSize=8.5, textColor=BLACK, leftIndent=8,
            spaceAfter=3, leading=13),
        "summary_label": P("SL",
            fontName="Helvetica-Bold", fontSize=8, textColor=GRAY_600),
        "summary_value": P("SV",
            fontName="Helvetica", fontSize=8.5, textColor=BLACK),
    }


# ─── Page decorators ─────────────────────────────────────────────────────────
def _draw_watermark(canvas, w, h):
    canvas.saveState()
    canvas.translate(w / 2, h / 2)
    canvas.rotate(-38)
    wm_color = colors.Color(0.008, 0.518, 0.780, alpha=0.09)
    canvas.setFillColor(wm_color)
    canvas.setFont("Helvetica-Bold", 46)
    canvas.drawCentredString(0, 8*mm, "Serene Vibes Kashmir")
    canvas.setFont("Helvetica-Oblique", 18)
    canvas.drawCentredString(0, -10*mm, "A Poem In Motion")
    rule_w = 110 * mm
    canvas.setStrokeColor(wm_color)
    canvas.setLineWidth(0.8)
    canvas.line(-rule_w / 2, 3*mm, rule_w / 2, 3*mm)
    canvas.restoreState()


def _page_frame(canvas, doc):
    """Watermark + footer on every page."""
    canvas.saveState()
    w, h = A4
    _draw_watermark(canvas, w, h)
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, w, 10*mm, fill=1, stroke=0)
    canvas.setFillColor(SKY)
    canvas.rect(0, 0, 4*mm, 10*mm, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(8*mm, 3.5*mm, "Serene Vibes Kashmir  |  serenevibeskashmir@gmail.com  |  +91-9419766510")
    page_str = f"  {doc.page}  "
    pw = canvas.stringWidth(page_str, "Helvetica-Bold", 7.5) + 4
    px = w - pw - MARGIN
    canvas.setFillColor(SKY)
    canvas.roundRect(px, 2*mm, pw, 6*mm, 1.5*mm, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.setFont("Helvetica-Bold", 7.5)
    canvas.drawCentredString(px + pw/2, 4*mm, str(doc.page))
    canvas.setStrokeColor(NAVY)
    canvas.setLineWidth(0.5)
    canvas.line(0, h - 1*mm, w, h - 1*mm)
    canvas.restoreState()


# ─── Main generator ──────────────────────────────────────────────────────────
def generate_pdf(itinerary_data: dict) -> str:
    import os as _os; _out = _os.environ.get("OUTPUT_DIR", "/tmp/output"); Path(_out).mkdir(exist_ok=True)
    client_name = str(itinerary_data.get("client_name", "Client"))
    filename  = f"Kashmir_Tour_{client_name.replace(' ', '_')}.pdf"
    file_path = Path(_out) / filename

    doc = SimpleDocTemplate(
        str(file_path),
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=18*mm,
        title=f"Kashmir Tour – {client_name}",
        author="Serene Vibes Kashmir",
        subject="Custom Tour Itinerary",
    )

    usable_w = PAGE_W - 2 * MARGIN
    styles   = make_styles()
    story    = []

    # ── Pull data ─────────────────────────────────────────────────────────────
    days         = int(itinerary_data.get("days", 5))
    start_date   = itinerary_data.get("start_date") or "Flexible"
    adults       = itinerary_data.get("adults", 2)
    kids         = itinerary_data.get("kids", 0)
    budget_tier  = itinerary_data.get("budget_tier", "Mid-Range")
    vehicle_type = itinerary_data.get("vehicle_type", "Sedan")
    client_email = itinerary_data.get("client_email", "N/A")
    custom_cost  = itinerary_data.get("custom_cost") or \
                   itinerary_data.get("financial_summary", {}).get("total_payable_inr", "On Request")

    # ── 1. Hero header ────────────────────────────────────────────────────────
    story.append(HeroHeader(
        usable_w, client_name, days, start_date, adults, kids,
        budget_tier, vehicle_type, custom_cost
    ))
    story.append(Spacer(1, 6*mm))

    # ── 2. Quick-summary grid ─────────────────────────────────────────────────
    summary_rows = [
        [
            Paragraph("CLIENT NAME", styles["summary_label"]),
            Paragraph(clean(client_name), styles["summary_value"]),
            Paragraph("EMAIL", styles["summary_label"]),
            Paragraph(clean(str(client_email)), styles["summary_value"]),
        ],
        [
            Paragraph("TOUR DURATION", styles["summary_label"]),
            Paragraph(f"{days} Days", styles["summary_value"]),
            Paragraph("TRAVEL DATE", styles["summary_label"]),
            Paragraph(clean(str(start_date)), styles["summary_value"]),
        ],
        [
            Paragraph("GUESTS", styles["summary_label"]),
            Paragraph(f"{adults} Adults" + (f", {kids} Kids" if int(kids or 0) else ""), styles["summary_value"]),
            Paragraph("VEHICLE", styles["summary_label"]),
            Paragraph(clean(str(vehicle_type)), styles["summary_value"]),
        ],
        [
            Paragraph("BUDGET TIER", styles["summary_label"]),
            Paragraph(clean(str(budget_tier)), styles["summary_value"]),
            Paragraph("ESTIMATED COST", styles["summary_label"]),
            Paragraph(
                f"<b><font color='#059669'>INR {int(custom_cost):,}</font></b>"
                if str(custom_cost).replace(".", "").isdigit()
                else clean(str(custom_cost)),
                ParagraphStyle("cv", fontName="Helvetica-Bold", fontSize=9, textColor=EMERALD)
            ),
        ],
    ]

    summary_col_w = [usable_w * 0.18, usable_w * 0.32, usable_w * 0.18, usable_w * 0.32]
    summary_table = Table(summary_rows, colWidths=summary_col_w, hAlign="LEFT")
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GRAY_50),
        ("BACKGROUND", (0, 0), (0, -1), GRAY_100),
        ("BACKGROUND", (2, 0), (2, -1), GRAY_100),
        ("BOX",        (0, 0), (-1, -1), 0.5, GRAY_200),
        ("INNERGRID",  (0, 0), (-1, -1), 0.3, GRAY_200),
        ("LINEBEFORE", (0, 0), (0, -1), 2.5, SKY),
        ("LINEBEFORE", (2, 0), (2, -1), 2.5, TEAL),
        ("LEFTPADDING",  (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING",   (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
        ("ROUNDEDCORNERS", [3]),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 7*mm))

    # ── 2b. Tour Route Map (Layout 3: terrain map + GPS legend table) ─────────
    # Wrapped in KeepTogether so the heading and the map graphic are always
    # rendered together (never split across a page break). A PageBreak
    # follows so the Day-by-Day section always starts cleanly on the next
    # page, regardless of how many days/legend rows the map has.
    timeline_for_map = itinerary_data.get("timeline", [])
    story.append(KeepTogether([
        SectionTitle(usable_w, "TOUR ROUTE MAP", icon=""),
        Spacer(1, 3*mm),
        KashmirRouteMap(usable_w, timeline_for_map),
    ]))
    story.append(PageBreak())

    # ── 3. Day-by-day itinerary ───────────────────────────────────────────────
    story.append(SectionTitle(usable_w, "DAY-BY-DAY ITINERARY", icon=""))
    story.append(Spacer(1, 4*mm))

    timeline = itinerary_data.get("timeline", [])

    for idx, day_info in enumerate(timeline, start=1):
        title     = day_info.get("title") or day_info.get("date") or f"Day {idx}"
        overnight = day_info.get("overnight_stay", "")
        route     = day_info.get("transit_route", "")
        schedule  = day_info.get("schedule", [])

        block = []
        block.append(DayBanner(usable_w, idx, title, overnight))
        block.append(Spacer(1, 2*mm))

        if route:
            block.append(RouteBadge(usable_w, route))
            block.append(Spacer(1, 2*mm))

        if schedule:
            # Build a 2-col activity table: [time | description]
            act_rows = []
            for slot in schedule:
                time_val = slot.get("time_slot") or slot.get("time", "")
                desc_val = slot.get("description") or slot.get("activity") or ""
                act_title = slot.get("activity_title", "")
                if not time_val:
                    time_val = "—"
                cell_time = Paragraph(clean(str(time_val)), styles["activity_time"])
                desc_text = (f"<b>{clean(act_title)}</b><br/>" if act_title else "") + clean(str(desc_val))
                cell_desc = Paragraph(desc_text, styles["activity_desc"])
                act_rows.append([cell_time, cell_desc])

            act_col_w = [usable_w * 0.17, usable_w * 0.83]
            act_table = Table(act_rows, colWidths=act_col_w, hAlign="LEFT")
            act_table.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), WHITE),
                ("BACKGROUND",    (0, 0), (0, -1), SKY_LIGHT),
                ("BOX",           (0, 0), (-1, -1), 0.5, GRAY_200),
                ("LINEBELOW",     (0, 0), (-1, -2), 0.3, GRAY_200),
                ("LINEBEFORE",    (0, 0), (0, -1), 2.5, SKY),
                ("LEFTPADDING",   (0, 0), (-1, -1), 6),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
                ("TOPPADDING",    (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ]))
            block.append(act_table)
        else:
            block.append(Paragraph(
                "<i>Details to be confirmed with your travel coordinator.</i>",
                ParagraphStyle("na", fontName="Helvetica-Oblique", fontSize=8,
                               textColor=GRAY_400, leftIndent=6)
            ))

        block.append(Spacer(1, 5*mm))
        story.append(KeepTogether(block))

    # Rule 5: Itinerary occupies pages 2–3; force next section to new page
    story.append(PageBreak())

    # ── Hotel data + selections (used by both the photo section and the
    #    Hotel Assignments table below) ─────────────────────────────────────
    # NOTE: "images" holds 2+ direct, hotlinkable photo URLs (or local file paths
    # under output/) per hotel. Fill these in with real URLs/files — the PDF
    # will fetch each one at build time and skip any that fail to load.
    HOTEL_LOOKUP = {
        "ngm":  {"name": "Hotel New Green Meadows",        "place": "Srinagar", "images": [
            "https://newgreenmeadows.com/wp-content/uploads/2025/11/restrornt.jpg",
            "https://newgreenmeadows.com/wp-content/uploads/2025/07/ngm-room2-min.jpg"
        ]},
        "nclr": {"name": "New Classic Luxury Resorts",     "place": "Srinagar", "images": [
            "https://newclassicluxuryresorts.com/upload/gallery/gallery-17c4f612b007807026adf06c113df2c0.jpg",
	        "https://newclassicluxuryresorts.com/upload/gallery/gallery-8c43d98dc19540a49a0f1ee3c587793a.jpg"]},
        "hsp":  {"name": "Hotel Sideeq Palace",            "place": "Srinagar", "images": []},
        "htv":  {"name": "Hotel The Victory",              "place": "Srinagar", "images": [
			"https://thevictory.in/wp-content/uploads/2017/08/DSC_8023.jpg",
			"https://thevictory.in/wp-content/uploads/2017/08/DSC_8024.jpg"
		]},
        "htk":  {"name": "Hotel The Karims",               "place": "Srinagar", "images": []},
        "hgr":  {"name": "Hotel Gurcoo Residency",         "place": "Srinagar", "images": []},
        "hdw":  {"name": "Hotel Deewan",                   "place": "Srinagar", "images": []},
        "hsd":  {"name": "Hotel Sadaf",                    "place": "Srinagar", "images": []},
        "sghb": {"name": "Srinagar Group of House-Boats",  "place": "Srinagar", "images": []},
        "hri":  {"name": "Hotel Riverside Inn",            "place": "Pahalgam", "images": []},
        "hsr":  {"name": "Hotel Supreme Resorts",          "place": "Pahalgam", "images": [
			"https://www.supremeresortspahalgam.com/img/villa.jpg",
			"https://www.supremeresortspahalgam.com/img/resort.jpg"
		]},
        "hhr":  {"name": "Hotel Highland Resorts",         "place": "Pahalgam", "images": [
			"https://www.hotelhighlandresort.com/assets/Roomgallery/gallery2.jpg",
			"https://www.hotelhighlandresort.com/assets/diningImages/19.jpg"
		]},
        "hfh":  {"name": "Hotel Falcon Heights",           "place": "Pahalgam", "images": []},
        "hlr":  {"name": "Hotel Lavish Residency",         "place": "Pahalgam", "images": []},
        "hil":  {"name": "Hotel Ice Land",                 "place": "Pahalgam", "images": []},
        "her":  {"name": "Hotel Eden Resorts and Spa",     "place": "Pahalgam", "images": []},
        "hatr": {"name": "Hotel Apple Tree Resorts",       "place": "Gulmarg",  "images": []},
        "ggr":  {"name": "Gateway Resorts",                "place": "Gulmarg",  "images": []},
        "hghv": {"name": "Hotel Grand Hill View",          "place": "Gulmarg",  "images": []},
        "hmsp": {"name": "Hotel Marina By Stay Pattern",   "place": "Gulmarg",  "images": []},
		"nrs":  {"name": "Namrose Resorts",                 "place": "Sonamarg", "images": []},
    	"bdr":  {"name": "Badar Resorts",                   "place": "Sonamarg", "images": []},
   		"cibsp": {"name": "Country Inn-By Stay Pattern",    "place": "Sonamarg", "images": []},
    	"hmi": {"name": "Hotel Mughal India",               "place": "Sonamarg", "images": []},
    }

    # ── Merge admin-saved hotel images into HOTEL_LOOKUP ──────────────────
    # Photos are stored permanently in the database (HotelImages model).
    # Photos uploaded from device are base64 data URLs; URL-added photos
    # are https:// strings. Both are handled by fetch_image_reader() above.
    try:
        from backend.models import HotelImages as _HotelImages
        import json as _json
        _rows = _HotelImages.query.all()
        _loaded = 0
        for _row in _rows:
            _imgs = _json.loads(_row.images_json)
            if _row.hotel_id in HOTEL_LOOKUP and isinstance(_imgs, list) and _imgs:
                HOTEL_LOOKUP[_row.hotel_id]["images"] = _imgs
                _loaded += 1
        print(f"Loaded hotel images for {_loaded} hotel(s) from database")
    except Exception as _e:
        print(f"Warning: could not load hotel images from DB: {_e}")

    hotel_selections = itinerary_data.get("selected_hotels") or \
                       itinerary_data.get("hotelSelections") or {}
    if not isinstance(hotel_selections, dict):
        hotel_selections = {}

    # ── 3b. Hotel Reference Photos ─────────────────────────────────────────
    # Shows 2+ reference photos for every hotel actually selected anywhere
    # in this itinerary, right below the day-by-day plan.
    selected_hotel_ids = []
    for raw_id in hotel_selections.values():
        hid = raw_id.get("id") if isinstance(raw_id, dict) else raw_id
        if hid and str(hid) in HOTEL_LOOKUP and str(hid) not in selected_hotel_ids:
            selected_hotel_ids.append(str(hid))

    if selected_hotel_ids:
        # ── Rule 6: ALL hotels (up to 3) must fit on ONE page ─────────────
        # A4 usable body height ≈ 257mm (297 - top margin 18 - bottom footer 22).
        # Fixed overhead per page: SectionTitle≈14mm + spacer 4mm = 18mm.
        # Per-hotel overhead: header bar 8mm + spacer 3mm = 11mm each.
        # Remaining height split equally across hotels for photos.
        # Hard floor 26mm (legible), hard ceiling 55mm.
        _n = len(selected_hotel_ids)
        _usable_body_h = 257   # mm
        _overhead_total = 18 + _n * 11
        _photo_h_mm = max(26, min(55, (_usable_body_h - _overhead_total) / _n))

        # Build all strips into one KeepTogether block so they never split
        photo_block = [
            SectionTitle(usable_w, "HOTEL REFERENCE PHOTOS", icon=""),
            Spacer(1, 4*mm),
        ]
        for hid in selected_hotel_ids:
            info = HOTEL_LOOKUP[hid]
            photo_block.append(HotelPhotoStrip(
                usable_w, info["name"], info["place"], info.get("images", []),
                photo_h=_photo_h_mm * mm
            ))
            photo_block.append(Spacer(1, 3*mm))
        # KeepTogether forces the entire photos section onto one page.
        # If it doesn't fit on the current page it triggers its own page break.
        story.append(KeepTogether(photo_block))

    # ── 4–6. Hotel Assignments + Inclusions/Exclusions + Payment Schedule ───────
    # Rule 1: These three sections always live on ONE page together.
    story.append(PageBreak())
    page_block_1 = []   # collect all three sections into this list
    page_block_1.append(SectionTitle(usable_w, "HOTEL ASSIGNMENTS", icon=""))
    page_block_1.append(Spacer(1, 4*mm))

    # Header row
    hotel_header = [
        Paragraph("<b>Day</b>", ParagraphStyle("hh", fontName="Helvetica-Bold",
                  fontSize=8.5, textColor=WHITE, alignment=TA_CENTER)),
        Paragraph("<b>Hotel / Property</b>", ParagraphStyle("hh2", fontName="Helvetica-Bold",
                  fontSize=8.5, textColor=WHITE)),
        Paragraph("<b>Location</b>", ParagraphStyle("hh3", fontName="Helvetica-Bold",
                  fontSize=8.5, textColor=WHITE, alignment=TA_CENTER)),
        Paragraph("<b>Meal Plan</b>", ParagraphStyle("hh4", fontName="Helvetica-Bold",
                  fontSize=8.5, textColor=WHITE, alignment=TA_CENTER)),
    ]

    hotel_rows = [hotel_header]
    day_place_map = {}

    for idx, day_info in enumerate(timeline, start=1):
        hotel_id   = (hotel_selections.get(str(idx - 1)) or
                      hotel_selections.get(str(idx)) or
                      hotel_selections.get(idx))
        if isinstance(hotel_id, dict):
            hotel_id = hotel_id.get("id")

        overnight_raw = str(day_info.get("overnight_stay", "") or "").strip()
        title_raw     = str(day_info.get("title", "") or "").strip()
        route_raw     = str(day_info.get("transit_route", "") or "").strip()
        dep_signal    = f"{title_raw} {route_raw}".lower()

        # A departure day has no hotel night: either explicitly flagged as
        # "departure" in the title/route, or there is simply no overnight
        # stay recorded for that day.
        is_departure_day = (
            "departure" in dep_signal
            or "airport drop" in dep_signal
            or not overnight_raw
            or overnight_raw.lower() == "departure"
        )

        if hotel_id and str(hotel_id) in HOTEL_LOOKUP:
            match = HOTEL_LOOKUP[str(hotel_id)]
            hotel_name  = match["name"]
            hotel_place = match["place"]
        elif is_departure_day:
            hotel_name  = "Departure"
            hotel_place = "-"
        else:
            hotel_name  = "To be confirmed"
            hotel_place = clean(str(overnight_raw)) if overnight_raw else "-"

        meal_plan = "-" if is_departure_day else "Breakfast &amp; Dinner"

        hotel_rows.append([
            Paragraph(f"<b>Day {idx}</b>", ParagraphStyle("dc", fontName="Helvetica-Bold",
                      fontSize=8.5, textColor=NAVY, alignment=TA_CENTER)),
            Paragraph(clean(hotel_name), styles["hotel_cell_bold"]),
            Paragraph(clean(hotel_place), ParagraphStyle("hp", fontName="Helvetica",
                      fontSize=8, textColor=GRAY_600, alignment=TA_CENTER)),
            Paragraph(meal_plan, ParagraphStyle("mp", fontName="Helvetica",
                      fontSize=8, textColor=TEAL, alignment=TA_CENTER)),
        ])

    hotel_col_w = [usable_w*0.10, usable_w*0.50, usable_w*0.20, usable_w*0.20]
    hotel_table = Table(hotel_rows, colWidths=hotel_col_w, hAlign="LEFT", repeatRows=1)
    hotel_table.setStyle(TableStyle([
        # Header
        ("BACKGROUND",    (0, 0), (-1, 0), NAVY_DEEP),
        ("BACKGROUND",    (0, 0), (0, 0), SKY),
        ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
        # Alternating rows
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, GRAY_50]),
        # Borders
        ("BOX",           (0, 0), (-1, -1), 0.5, GRAY_200),
        ("INNERGRID",     (0, 0), (-1, -1), 0.3, GRAY_200),
        ("LINEBEFORE",    (0, 0), (0, -1), 2.5, SKY),
        # Padding
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        # Left accent column
        ("BACKGROUND",    (0, 1), (0, -1), SKY_LIGHT),
    ]))
    page_block_1.append(hotel_table)
    page_block_1.append(Spacer(1, 5*mm))

    # ── 5. Inclusions / Exclusions ────────────────────────────────────────────
    inc_items = [
        "01 SEDAN for all tours and transfers including pick up and drop",
        "Sightseeing tours as per the itinerary by individual car",
        "Stay at the hotels mentioned in the itinerary or similar",
        "Meals - Breakfast and Dinner",
        "Celebration Cake",
        "Accommodation on triple sharing basis",
        "01 Hour complimentary Shikara ride",
        "Toll taxes, fuel charges, parking fees and driver's allowance",
    ]
    exc_items = [
        "Any Airfare or Train fare",
        "Entrances, Lunch and Snacks",
        "Activities: River Rafting, Paragliding and Skiing, Gondola (Phase I INR 800 & Phase II INR 1000 per person)",
        "All personal expenses such as tips, laundry, telephone bills, beverages and camera fees",
        "Union cabs for ABC Pahalgam and snow chain vehicle if required for Gulmarg",
        "Any claim due to road blocks, curfews, accidents etc.",
    ]

    def bullet_list(items, icon, color):
        rows = []
        for item in items:
            rows.append([
                Paragraph(f"<font color='#{color}'><b>{icon}</b></font>",
                          ParagraphStyle("ic", fontName="Helvetica-Bold",
                                        fontSize=11, alignment=TA_CENTER)),
                Paragraph(clean(item), styles["inclusion"]),
            ])
        t = Table(rows, colWidths=[8*mm, usable_w/2 - 8*mm - 3*mm])
        t.setStyle(TableStyle([
            ("LEFTPADDING",  (0,0),(-1,-1), 2),
            ("RIGHTPADDING", (0,0),(-1,-1), 2),
            ("TOPPADDING",   (0,0),(-1,-1), 2),
            ("BOTTOMPADDING",(0,0),(-1,-1), 3),
            ("VALIGN",       (0,0),(-1,-1), "TOP"),
        ]))
        return t

    inc_header = Table([[
        Paragraph("<b>INCLUSIONS</b>", ParagraphStyle("ih", fontName="Helvetica-Bold",
                  fontSize=9.5, textColor=WHITE)),
        Paragraph("<b>EXCLUSIONS</b>", ParagraphStyle("eh", fontName="Helvetica-Bold",
                  fontSize=9.5, textColor=WHITE)),
    ]], colWidths=[usable_w/2 - 2*mm, usable_w/2 - 2*mm])
    inc_header.setStyle(TableStyle([
        ("BACKGROUND", (0,0),(0,0), EMERALD),
        ("BACKGROUND", (1,0),(1,0), ROSE),
        ("TOPPADDING", (0,0),(-1,-1), 8),
        ("BOTTOMPADDING",(0,0),(-1,-1), 8),
        ("LEFTPADDING", (0,0),(-1,-1), 12),
        ("LINEBEFORE", (0,0),(0,0), 3, colors.HexColor("#047857")),
        ("LINEBEFORE", (1,0),(1,0), 3, colors.HexColor("#be123c")),
    ]))

    inc_body = Table([[
        bullet_list(inc_items, "+", "059669"),
        bullet_list(exc_items, "x", "e11d48"),
    ]], colWidths=[usable_w/2 - 2*mm, usable_w/2 - 2*mm])
    inc_body.setStyle(TableStyle([
        ("BACKGROUND", (0,0),(0,0), colors.HexColor("#f0fdf4")),
        ("BACKGROUND", (1,0),(1,0), colors.HexColor("#fff1f2")),
        ("BOX",        (0,0),(-1,-1), 0.5, GRAY_200),
        ("TOPPADDING", (0,0),(-1,-1), 6),
        ("BOTTOMPADDING",(0,0),(-1,-1), 6),
        ("LEFTPADDING", (0,0),(-1,-1), 4),
        ("VALIGN",     (0,0),(-1,-1), "TOP"),
    ]))

    page_block_1.append(SectionTitle(usable_w, "INCLUSIONS & EXCLUSIONS", icon=""))
    page_block_1.append(Spacer(1, 3*mm))
    page_block_1.append(inc_header)
    page_block_1.append(inc_body)
    page_block_1.append(Spacer(1, 5*mm))

    # ── 6. Payment Schedule ───────────────────────────────────────────────────
    page_block_1.append(SectionTitle(usable_w, "PAYMENT SCHEDULE", icon=""))
    page_block_1.append(Spacer(1, 3*mm))

    # Calculate payment milestones dynamically (25% / 25% / 50% split per policy)
    total_amt   = int(custom_cost) if str(custom_cost).replace(".", "").isdigit() else 0
    inst1_amt   = round(total_amt * 0.25)
    inst2_amt   = round(total_amt * 0.25)
    inst3_amt   = total_amt - inst1_amt - inst2_amt

    pay_header_style = ParagraphStyle("pyh", fontName="Helvetica-Bold",
                                      fontSize=8.5, textColor=WHITE, alignment=TA_CENTER)
    pay_body_style   = ParagraphStyle("pyb", fontName="Helvetica",
                                      fontSize=8.5, textColor=BLACK, alignment=TA_CENTER)
    pay_amt_style    = ParagraphStyle("pya", fontName="Helvetica-Bold",
                                      fontSize=9.5, textColor=EMERALD, alignment=TA_CENTER)
    pay_note_style   = ParagraphStyle("pyn", fontName="Helvetica-Oblique",
                                      fontSize=7.5, textColor=GRAY_600, alignment=TA_CENTER)

    pay_rows = [[
        Paragraph("<b>Instalment</b>",   pay_header_style),
        Paragraph("<b>Amount (INR)</b>", pay_header_style),
        Paragraph("<b>Due Date</b>",     pay_header_style),
        Paragraph("<b>Mode</b>",         pay_header_style),
        Paragraph("<b>Status</b>",       pay_header_style),
    ]]

    pay_data = [
        ("1st Instalment (25%)",
         f"INR {inst1_amt:,}" if total_amt else "As Quoted",
         "On Confirmation",
         "NEFT / UPI / Cheque",
         "Pending"),
        ("2nd Instalment (25%)",
         f"INR {inst2_amt:,}" if total_amt else "As Quoted",
         "A month before travel date",
         "NEFT / UPI / Cheque",
         "Pending"),
        ("3rd Instalment (50%)",
         f"INR {inst3_amt:,}" if total_amt else "As Quoted",
         "On Arrival",
         "NEFT / UPI / Cheque",
         "Pending"),
    ]

    for label, amt, due, mode, status in pay_data:
        pay_rows.append([
            Paragraph(clean(label), ParagraphStyle("pl", fontName="Helvetica",
                      fontSize=8.5, textColor=BLACK)),
            Paragraph(f"<b>{clean(amt)}</b>", pay_amt_style),
            Paragraph(clean(due),  pay_body_style),
            Paragraph(clean(mode), pay_body_style),
            Paragraph(f"<font color='#b45309'>{clean(status)}</font>",
                      ParagraphStyle("ps", fontName="Helvetica-Bold",
                                     fontSize=8, textColor=GOLD, alignment=TA_CENTER)),
        ])

    pay_col_w = [usable_w*0.28, usable_w*0.20, usable_w*0.22, usable_w*0.18, usable_w*0.12]
    pay_table = Table(pay_rows, colWidths=pay_col_w, hAlign="LEFT")
    pay_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), NAVY_DEEP),
        ("BACKGROUND",    (0, 0), (0, 0), SKY),
        ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.HexColor("#f0fdf4"), WHITE]),
        ("BOX",           (0, 0), (-1, -1), 0.5, GRAY_200),
        ("INNERGRID",     (0, 0), (-1, -1), 0.3, GRAY_200),
        ("LINEBEFORE",    (0, 0), (0, -1), 2.5, SKY),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    page_block_1.append(pay_table)
    page_block_1.append(Spacer(1, 3*mm))

    # Bank details sub-note
    bank_note_style = ParagraphStyle("bn", fontName="Helvetica", fontSize=7.5,
                                     textColor=GRAY_600, leading=11)
    page_block_1.append(Paragraph(
        "<b>Bank Transfer Details:</b>  Account Name: Serene Vibes Kashmir  |  "
        "Bank: J&amp;K Bank  |  Account No: XXXXXXXXXX  |  IFSC: JAKA0XXXXXX  |  "
        "UPI: serenevibeskashmir@upi",
        bank_note_style
    ))
    # Flush page_block_1 (Hotel Assignments + Inc/Exc + Payment) to story
    story.append(KeepTogether(page_block_1))

    # ── 7–9. Cancellation Policy + Travel Notes + Contact Card ────────────────
    # Rule 2: These three sections always live on ONE page together.
    story.append(PageBreak())
    page_block_2 = []
    page_block_2.append(SectionTitle(usable_w, "CANCELLATION POLICY", icon=""))
    page_block_2.append(Spacer(1, 4*mm))

    canc_header_st = ParagraphStyle("cnh", fontName="Helvetica-Bold",
                                    fontSize=8.5, textColor=WHITE)
    canc_body_st   = ParagraphStyle("cnb", fontName="Helvetica",
                                    fontSize=8.5, textColor=BLACK, alignment=TA_CENTER)
    canc_pct_st    = ParagraphStyle("cnp", fontName="Helvetica-Bold",
                                    fontSize=9, textColor=ROSE, alignment=TA_CENTER)

    canc_rows = [[
        Paragraph("<b>Cancellation Timeline</b>",   canc_header_st),
        Paragraph("<b>Cancellation Charge</b>",     canc_header_st),
        Paragraph("<b>Refund %</b>",               canc_header_st),
        Paragraph("<b>Processing Time</b>",         canc_header_st),
    ]]

    canc_data = [
        ("30 days or more before departure",  "Nil (Token forfeited)",          "70%",  "7–10 working days"),
        ("15–29 days before departure",       "25% of total tour cost",          "45%",  "7–10 working days"),
        ("7–14 days before departure",        "50% of total tour cost",          "20%",  "10–14 working days"),
        ("Less than 7 days / No Show",        "100% of total tour cost",         "Nil",  "Not applicable"),
        ("Natural Calamity / Force Majeure",  "Credit note for future travel",   "—",    "As per T&C"),
    ]

    for i, (timeline_txt, charge, refund, proc) in enumerate(canc_data):
        row_bg = colors.HexColor("#fff1f2") if refund == "Nil" else WHITE
        canc_rows.append([
            Paragraph(clean(timeline_txt), ParagraphStyle("cntl", fontName="Helvetica",
                      fontSize=8.5, textColor=BLACK)),
            Paragraph(clean(charge),  canc_body_st),
            Paragraph(f"<b>{clean(refund)}</b>", canc_pct_st),
            Paragraph(clean(proc),    canc_body_st),
        ])

    canc_col_w = [usable_w*0.34, usable_w*0.28, usable_w*0.16, usable_w*0.22]
    canc_table = Table(canc_rows, colWidths=canc_col_w, hAlign="LEFT")
    canc_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), colors.HexColor("#7f1d1d")),
        ("LINEBEFORE",    (0, 0), (0, 0), 3, colors.HexColor("#fca5a5")),
        ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [GRAY_50, WHITE]),
        ("BACKGROUND",    (0, 4), (-1, 4), colors.HexColor("#fff1f2")),
        ("BOX",           (0, 0), (-1, -1), 0.5, GRAY_200),
        ("INNERGRID",     (0, 0), (-1, -1), 0.3, GRAY_200),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    page_block_2.append(canc_table)
    page_block_2.append(Spacer(1, 5*mm))

    # ── 8. Important Travel Notes ─────────────────────────────────────────────
    page_block_2.append(SectionTitle(usable_w, "IMPORTANT TRAVEL NOTES", icon=""))
    page_block_2.append(Spacer(1, 4*mm))

    note_heading_st = ParagraphStyle("noh", fontName="Helvetica-Bold",
                                     fontSize=8, textColor=GOLD, spaceBefore=2, spaceAfter=1)
    note_body_st    = ParagraphStyle("nob", fontName="Helvetica",
                                     fontSize=8, textColor=BLACK, leading=12, spaceAfter=3)

    travel_notes = [
        ("ID & Documentation",
         "Every guest must carry a valid government-issued photo ID (Aadhaar / Passport / Voter ID) "
         "at all times. Copies will not be accepted at security checkpoints. Foreign nationals must "
         "carry their passport and valid Indian visa."),
        ("Travel Insurance (Strongly Recommended)",
         "We strongly advise all guests to purchase a comprehensive travel insurance policy covering "
         "medical emergencies, trip cancellations, and baggage loss. Serene Vibes Kashmir does not "
         "provide insurance and will not be liable for uncovered losses."),
        ("Health & Medical Advisory",
         "Kashmir's altitude can cause mild breathlessness for some guests. Guests with pre-existing "
         "cardiac or respiratory conditions should consult their physician before travel. Carry all "
         "personal medications in your hand luggage."),
        ("Weather & Seasonal Advisory",
         "Kashmir experiences extreme weather changes across seasons. Pack warm layers even in summer "
         "as evenings can be cold. Check weather forecasts 48 hours before departure. Snow or rain may "
         "cause road diversions — alternate routes will be arranged at no extra cost where possible."),
        ("Connectivity",
         "Only post-paid SIM cards (Airtel / BSNL / Jio) work in the Kashmir Valley. Pre-paid SIMs "
         "are blocked for non-residents. Roaming charges may apply. Inform your service provider "
         "about your travel dates before departure."),
        ("Photography & Restricted Zones",
         "Photography near military establishments, bridges, and border areas is strictly prohibited "
         "under Indian law. Please follow all instructions from local authorities and your guide."),
    ]

    # Two-column layout for notes
    note_col_w = (usable_w - 6*mm) / 2
    left_notes  = travel_notes[:3]
    right_notes = travel_notes[3:]

    def make_note_col(notes):
        items = []
        for heading, body in notes:
            items.append(Paragraph(heading, note_heading_st))
            items.append(Paragraph(clean(body), note_body_st))
        rows = [[item] for item in items]
        t = Table(rows, colWidths=[note_col_w])
        t.setStyle(TableStyle([
            ("LEFTPADDING",  (0,0),(-1,-1), 0),
            ("RIGHTPADDING", (0,0),(-1,-1), 0),
            ("TOPPADDING",   (0,0),(-1,-1), 0),
            ("BOTTOMPADDING",(0,0),(-1,-1), 0),
        ]))
        return t

    notes_outer = Table(
        [[make_note_col(left_notes), make_note_col(right_notes)]],
        colWidths=[note_col_w, note_col_w],
        hAlign="LEFT"
    )
    notes_outer.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), GOLD_LITE),
        ("BOX",          (0,0),(-1,-1), 0.5, colors.HexColor("#fde68a")),
        ("LINEAFTER",    (0,0),(0,-1), 0.4, colors.HexColor("#fde68a")),
        ("VALIGN",       (0,0),(-1,-1), "TOP"),
        ("TOPPADDING",   (0,0),(-1,-1), 8),
        ("BOTTOMPADDING",(0,0),(-1,-1), 8),
        ("LEFTPADDING",  (0,0),(-1,-1), 10),
        ("RIGHTPADDING", (0,0),(0,-1), 8),
        ("LEFTPADDING",  (1,0),(1,-1), 12),
        ("RIGHTPADDING", (1,0),(1,-1), 10),
    ]))
    page_block_2.append(notes_outer)
    page_block_2.append(Spacer(1, 5*mm))

    # ── 9. Contact Card ───────────────────────────────────────────────────────
    page_block_2.append(SectionTitle(usable_w, "GET IN TOUCH WITH US", icon=""))
    page_block_2.append(Spacer(1, 3*mm))

    contact_label_st = ParagraphStyle("ctl", fontName="Helvetica-Bold",
                                      fontSize=7.5, textColor=GRAY_600)
    contact_val_st   = ParagraphStyle("ctv", fontName="Helvetica",
                                      fontSize=8.5, textColor=BLACK)
    contact_link_st  = ParagraphStyle("ctlnk", fontName="Helvetica",
                                      fontSize=8.5, textColor=SKY)

    contact_rows = [
        [
            Paragraph("Company", contact_label_st),
            Paragraph("Serene Vibes Kashmir", ParagraphStyle("cvb", fontName="Helvetica-Bold",
                      fontSize=9, textColor=NAVY)),
            Paragraph("Tagline", contact_label_st),
            Paragraph("A Poem In Motion", ParagraphStyle("cvi", fontName="Helvetica-Oblique",
                      fontSize=8.5, textColor=SKY)),
        ],
        [
            Paragraph("Email", contact_label_st),
            Paragraph("serenevibeskashmir@gmail.com", contact_link_st),
            Paragraph("Website", contact_label_st),
            Paragraph("www.serenevibeskashmir.com", contact_link_st),
        ],
        [
            Paragraph("Phone / WhatsApp", contact_label_st),
            Paragraph("+91-9419766510,+91-9858355260", contact_val_st),
            Paragraph("Operating Hours", contact_label_st),
            Paragraph("Mon–Sat, 9:00 AM – 7:00 PM IST", contact_val_st),
        ],
        [
            Paragraph("Office Address", contact_label_st),
            Paragraph("NH-44, Lethpora, Jammu &amp; Kashmir – 192122", contact_val_st),
            Paragraph("GST No.", contact_label_st),
            Paragraph("01XXXXXXXXX1ZX", contact_val_st),
        ],
    ]

    contact_col_w = [usable_w*0.15, usable_w*0.35, usable_w*0.15, usable_w*0.35]
    contact_table = Table(contact_rows, colWidths=contact_col_w)
    contact_table.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), SKY_LIGHT),
        ("BACKGROUND",   (0,0),(0,-1), colors.HexColor("#bae6fd")),
        ("BACKGROUND",   (2,0),(2,-1), colors.HexColor("#bae6fd")),
        ("BOX",          (0,0),(-1,-1), 0.5, colors.HexColor("#7dd3fc")),
        ("INNERGRID",    (0,0),(-1,-1), 0.3, colors.HexColor("#bae6fd")),
        ("LINEBEFORE",   (0,0),(0,-1), 3, SKY),
        ("TOPPADDING",   (0,0),(-1,-1), 7),
        ("BOTTOMPADDING",(0,0),(-1,-1), 7),
        ("LEFTPADDING",  (0,0),(-1,-1), 10),
        ("RIGHTPADDING", (0,0),(-1,-1), 10),
        ("VALIGN",       (0,0),(-1,-1), "MIDDLE"),
    ]))
    page_block_2.append(contact_table)
    # Flush page_block_2 (Cancellation + Travel Notes + Contact) to story
    story.append(KeepTogether(page_block_2))

    # ── 10. Terms & Conditions — always on its own page (Rule 3) ──────────────
    story.append(PageBreak())
    story.append(SectionTitle(usable_w, "TERMS & CONDITIONS", icon=""))
    story.append(Spacer(1, 5*mm))

    # Compact style definitions for T&C
    tc_heading = ParagraphStyle("tch",
        fontName="Helvetica-Bold", fontSize=8, textColor=NAVY,
        spaceBefore=6, spaceAfter=2)
    tc_body = ParagraphStyle("tcb",
        fontName="Helvetica", fontSize=7.5, textColor=GRAY_600,
        leading=11.5, spaceAfter=1)

    # T&C data: (heading, body_text)
    tc_sections = [
        ("Bookings",
         "All bookings are processed after receiving the token amount. This amount is refundable "
         "in case The Traveler is unable to confirm your booking on the requested date."),

        ("Travel Plan / Itinerary",
         "These are sample itineraries intended to give a general idea of our standard tour. External "
         "factors such as weather, road conditions, natural hazards and physical ability of participants "
         "may dictate changes before or during the trip. Serene Vibes is not responsible for delays or "
         "expenses incurred due to natural calamities, flight cancellations, accidents, transport "
         "breakdown, sickness, political closures or any untoward incidents."),

        ("Child Policy",
         "Children up to age 5 are not charged. Children aged 6-10 are not charged in the package "
         "but meal charges apply. Children aged 11 and above are considered adults and charged accordingly."),

        ("Hotel Policy",
         "Extra bed requests (adult/child) may be fulfilled with a rollaway bed or mattress subject "
         "to availability. Adjacent/adjoining room requests are also subject to availability. "
         "Twin or double bed allocation is at the hotel's discretion."),

        ("Check-In & Check-Out",
         "Standard check-in/out time is 12:00 Noon. Early check-in or late check-out requests can "
         "be made directly with hotel management and settled on-site."),

        ("Documents Required",
         "Government-issued ID (Aadhar Card / Passport) is mandatory for all guests. Age proof is "
         "required for children aged 2-10 years and infants below 2 years."),

        ("Billing",
         "In case of billing errors the agency reserves the right to re-invoice. Dishonoured cheques "
         "attract a penalty of INR 500 per instance; the agency reserves the right to take legal action."),

        ("Alterations / Cancellations",
         "Any alteration or cancellation after commencement of the holiday may incur penalties. "
         "Refunds are not applicable for unused services."),

        ("Refunds",
         "All refund claims must be raised within 7 days of booking completion via email to "
         "serenevibeskashmir@gmail.com. Requests after trip commencement will not be entertained. "
         "Amounts held by airlines or hotels are refunded only upon recovery from the respective vendor."),

        ("Pandemic Limitation",
         "If the tour cannot be availed due to a pandemic, the agency will provide either a refund or "
         "a credit note for future travel, subject to third-party vendor (airline/hotel) conditions."),

        ("Extra Costs",
         "If the Government of India revises taxes or fuel costs after tour finalisation, the incremental "
         "amount will be added to the tour cost after due intimation to the guests."),

        ("Telecom Services",
         "Only post-paid mobile connections are operable in Kashmir. Please verify with your provider "
         "before departure."),

        ("Law & Jurisdiction",
         "All disputes, claims, and legal suits relating to any services offered by Serene Vibes are "
         "under the exclusive jurisdiction of Srinagar & Delhi Courts."),

        ("Complaints",
         "For any complaints, contact our nearest operations team member or write to "
         "serenevibeskashmir@gmail.com. We will resolve your concern at the earliest."),
    ]

    # General terms as a compact bulleted block
    general_bullets = [
        "All flight tickets are booked on minimum available fare.",
        "Please reach the airport 3 hours prior to scheduled departure.",
        "Government-issued IDs are required to process reservations.",
        "Carry a confirmed hotel voucher at the time of check-in.",
        "Number of meals corresponds to number of nights booked; breakfast not provided on day of arrival.",
        "The hotel has the right to claim damages incurred by guests.",
        "Mini-bar (if available) is on a chargeable basis.",
        "Cost of additional services outside the package must be settled directly at the hotel.",
        "Face mask / cover is mandatory during boarding and travel on airlines.",
        "No seat is provided to infants on airlines.",
    ]

    # Render in 2-column grid for compactness
    col_w = (usable_w - 5*mm) / 2

    left_sections  = tc_sections[:7]
    right_sections = tc_sections[7:]

    def make_tc_items(sections):
        items = []
        for heading, body in sections:
            items.append(Paragraph(heading, tc_heading))
            items.append(Paragraph(clean(body), tc_body))
        return items

    left_items  = make_tc_items(left_sections)
    right_items = make_tc_items(right_sections)


    # Wrap each column in a single-cell Table to control width
    def wrap_col(items, w):
        rows = [[item] for item in items]
        t = Table(rows, colWidths=[w])
        t.setStyle(TableStyle([
            ("LEFTPADDING",  (0,0),(-1,-1), 0),
            ("RIGHTPADDING", (0,0),(-1,-1), 0),
            ("TOPPADDING",   (0,0),(-1,-1), 0),
            ("BOTTOMPADDING",(0,0),(-1,-1), 0),
        ]))
        return t

    two_col = Table(
        [[wrap_col(left_items, col_w), wrap_col(right_items, col_w)]],
        colWidths=[col_w, col_w],
        hAlign="LEFT"
    )
    two_col.setStyle(TableStyle([
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
        ("LEFTPADDING",   (0,0),(-1,-1), 0),
        ("RIGHTPADDING",  (0,0),(-1,-1), 0),
        ("TOPPADDING",    (0,0),(-1,-1), 0),
        ("BOTTOMPADDING", (0,0),(-1,-1), 0),
        ("LINEAFTER",     (0,0),(0,-1), 0.4, GRAY_200),
        ("RIGHTPADDING",  (0,0),(0,-1), 6),
        ("LEFTPADDING",   (1,0),(1,-1), 6),
    ]))
    story.append(two_col)
    story.append(Spacer(1, 6*mm))

    # General Terms compact box
    story.append(Paragraph(
        "<b>GENERAL TERMS</b>",
        ParagraphStyle("gth", fontName="Helvetica-Bold", fontSize=8,
                       textColor=NAVY, spaceAfter=4)
    ))
    bullet_rows = []
    for b in general_bullets:
        bullet_rows.append([
            Paragraph("-", ParagraphStyle("bd", fontName="Helvetica-Bold",
                      fontSize=8, textColor=SKY, alignment=TA_CENTER)),
            Paragraph(clean(b), tc_body),
        ])
    gen_table = Table(bullet_rows, colWidths=[5*mm, usable_w - 5*mm])
    gen_table.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), GRAY_50),
        ("BOX",          (0,0),(-1,-1), 0.4, GRAY_200),
        ("LEFTPADDING",  (0,0),(-1,-1), 4),
        ("RIGHTPADDING", (0,0),(-1,-1), 6),
        ("TOPPADDING",   (0,0),(-1,-1), 3),
        ("BOTTOMPADDING",(0,0),(-1,-1), 3),
        ("VALIGN",       (0,0),(-1,-1), "TOP"),
    ]))
    story.append(gen_table)
    story.append(Spacer(1, 6*mm))

    # ── Client Acknowledgement / Signature Block ──────────────────────────────
    story.append(PageBreak())
    story.append(SectionTitle(usable_w, "CLIENT ACKNOWLEDGEMENT", icon=""))
    story.append(Spacer(1, 5*mm))

    ack_body_st = ParagraphStyle("ackb", fontName="Helvetica", fontSize=8,
                                 textColor=GRAY_600, leading=12, spaceAfter=4)
    story.append(Paragraph(
        "I / We, the undersigned, confirm that I / We have read, understood, and agree to all the "
        "terms and conditions, cancellation policy, and payment schedule outlined in this itinerary "
        "document issued by Serene Vibes Kashmir. I / We understand that this constitutes a binding "
        "booking agreement upon payment of the token amount.",
        ack_body_st
    ))
    story.append(Spacer(1, 10*mm))

    # Signature boxes — 3 columns: client name, signature, date
    sig_label_st = ParagraphStyle("sigl", fontName="Helvetica-Bold",
                                  fontSize=7.5, textColor=GRAY_600, alignment=TA_CENTER)
    sig_line_st  = ParagraphStyle("sigln", fontName="Helvetica",
                                  fontSize=9, textColor=BLACK, alignment=TA_CENTER)

    sig_col_w = usable_w / 3 - 4*mm

    def sig_box(label, prefill=""):
        """Standard blank signature box for client name / date columns."""
        inner = Table(
            [[Paragraph("&nbsp;" * 30, sig_line_st)],
             [Paragraph(clean(prefill) if prefill else "&nbsp;", sig_line_st)],
             [Paragraph(label, sig_label_st)]],
            colWidths=[sig_col_w]
        )
        inner.setStyle(TableStyle([
            ("LINEABOVE",    (0,1),(0,1), 0.6, NAVY),
            ("TOPPADDING",   (0,0),(-1,-1), 4),
            ("BOTTOMPADDING",(0,0),(-1,-1), 4),
            ("ALIGN",        (0,0),(-1,-1), "CENTER"),
        ]))
        return inner

    # ── Authorised Signatory box — seal centred above the line ──────────
    seal_sz = 36 * mm
    auth_box = Table(
        [
            [OfficialSeal(size=seal_sz)],                                     # seal graphic
            [Paragraph("&nbsp;", sig_line_st)],                               # spacer row / sign here
            [Paragraph("Authorised Signatory &ndash; Serene Vibes Kashmir",   # label
                       sig_label_st)],
        ],
        colWidths=[sig_col_w]
    )
    auth_box.setStyle(TableStyle([
        ("ALIGN",        (0,0),(-1,-1), "CENTER"),
        ("VALIGN",       (0,0),(0,0),   "MIDDLE"),
        ("LINEABOVE",    (0,1),(0,1), 0.6, NAVY),
        ("TOPPADDING",   (0,0),(-1,-1), 3),
        ("BOTTOMPADDING",(0,0),(-1,-1), 3),
    ]))

    sig_row = Table([[
        sig_box("Client Name &amp; Signature", clean(client_name)),
        sig_box("Date of Agreement"),
        auth_box,
    ]], colWidths=[sig_col_w + 4*mm, sig_col_w + 4*mm, sig_col_w + 4*mm])
    sig_row.setStyle(TableStyle([
        ("LEFTPADDING",  (0,0),(-1,-1), 4),
        ("RIGHTPADDING", (0,0),(-1,-1), 4),
        ("VALIGN",       (0,0),(-1,-1), "BOTTOM"),
    ]))
    story.append(sig_row)
    story.append(Spacer(1, 8*mm))

    # Quote validity notice
    validity_st = ParagraphStyle("vld", fontName="Helvetica-Oblique", fontSize=7.5,
                                 textColor=GRAY_400, alignment=TA_CENTER)
    ts_gen = datetime.datetime.now(IST)
    ts_valid = (ts_gen + datetime.timedelta(days=7)).strftime("%d %b %Y")
    story.append(Paragraph(
        f"This quotation is valid until <b>{ts_valid}</b>. Rates are subject to change after this date "
        "due to hotel availability and seasonal pricing. Please confirm your booking to lock in the quoted price.",
        validity_st
    ))
    story.append(Spacer(1, 4*mm))

    # Timestamp
    ts = ts_gen.strftime("%d %b %Y, %I:%M %p") + " IST"
    story.append(HRFlowable(width=usable_w, thickness=0.4, color=GRAY_200))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph(
        f"Document generated on {ts}  |  Serene Vibes Kashmir  |  serenevibeskashmir@gmail.com",
        styles["footer_note"]
    ))

    # ── Build PDF ─────────────────────────────────────────────────────────────
    doc.build(story, onFirstPage=_page_frame, onLaterPages=_page_frame)
    return f"output/{filename}"
