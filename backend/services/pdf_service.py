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
    HRFlowable, KeepTogether, PageBreak, CondPageBreak
)
from reportlab.platypus.flowables import Flowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Circle
from reportlab.graphics import renderPDF
import datetime

try:                                   # real satellite imagery for the route map
    from backend.services import satellite_map
except Exception:                      # never let imagery break PDF generation
    satellite_map = None

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

# ─── Fonts ───────────────────────────────────────────────────────────────────
# Lato (SIL OFL) lives in backend/assets/fonts and is *embedded* in the PDF, so
# the output looks identical on every device and supports ₹, – — “ ” → etc.
# If the font files cannot be found we fall back to the built-in Helvetica
# family (same layout, plainer look) instead of failing PDF generation.
_FONT_DIRS = [
    Path(__file__).resolve().parent.parent / "assets" / "fonts",
    Path(__file__).resolve().parent / "fonts",
    Path.cwd() / "backend" / "assets" / "fonts",
    Path.cwd() / "assets" / "fonts",
]
_FACES = {
    "Lato":            ("Lato-Regular.ttf",    "Helvetica"),
    "Lato-Bold":       ("Lato-Bold.ttf",       "Helvetica-Bold"),
    "Lato-Italic":     ("Lato-Italic.ttf",     "Helvetica-Oblique"),
    "Lato-BoldItalic": ("Lato-BoldItalic.ttf", "Helvetica-BoldOblique"),
}

def _register_fonts():
    font_dir = next((d for d in _FONT_DIRS
                     if all((d / f).exists() for f, _ in _FACES.values())), None)
    for name, (fname, fallback) in _FACES.items():
        if name in pdfmetrics.getRegisteredFontNames():
            continue
        if font_dir is not None:
            pdfmetrics.registerFont(TTFont(name, str(font_dir / fname)))
        else:
            # alias our face name to the matching built-in Helvetica face
            pdfmetrics.registerFont(pdfmetrics.Font(name, fallback, "WinAnsiEncoding"))
    if font_dir is None:
        print("WARNING: Lato fonts not found in backend/assets/fonts - using Helvetica fallback")
    # Needed so <b>/<i> inside Paragraphs resolve for *every* face name
    # (e.g. <b> inside a style whose fontName is "Lato-Bold").
    pdfmetrics.registerFontFamily(
        "Lato", normal="Lato", bold="Lato-Bold",
        italic="Lato-Italic", boldItalic="Lato-BoldItalic")

_register_fonts()

# ─── Text Sanitiser ──────────────────────────────────────────────────────────
# Characters the embedded Lato font has no glyph for (they print as black boxes).
# AI-written text in particular likes the non-breaking hyphen (U+2011).
_GLYPH_FIXES = {
    0x00A0: " ", 0x202F: " ", 0x2007: " ", 0x2009: " ", 0x200A: " ", 0x2002: " ", 0x2003: " ",
    0x2010: "-", 0x2011: "-", 0x2012: "-", 0x2212: "-", 0x00AD: None,
    0x200B: None, 0x200C: None, 0x200D: None, 0x2060: None, 0xFEFF: None,
}


def clean(text):
    """Escape ReportLab XML special characters. Typography (– — “ ” ₹ →) is
    kept as-is because the embedded Lato font supports it."""
    if not text:
        return ""
    s = str(text).translate(_GLYPH_FIXES)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _raw(text):
    """Plain text for direct canvas drawing (clean() escapes for Paragraphs, which would print '&amp;')."""
    import html
    return html.unescape(clean(text))


# ─── Hotel Image Fetcher ─────────────────────────────────────────────────────
_IMAGE_CACHE = {}
_MAX_IMG_PX = 1400      # longest side kept in the PDF (plenty for a ~85 mm print slot)
_JPEG_QUALITY = 82


def _compress_image(raw: bytes) -> "io.BytesIO":
    """Downscale + re-encode a photo as JPEG so a single 4500x3000 upload
    doesn't turn an 8-page PDF into a 39 MB file."""
    from PIL import Image
    im = Image.open(io.BytesIO(raw))
    im.load()
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    elif im.mode != "RGB":
        im = im.convert("RGB")
    im.thumbnail((_MAX_IMG_PX, _MAX_IMG_PX), Image.LANCZOS)
    out = io.BytesIO()
    im.save(out, "JPEG", quality=_JPEG_QUALITY, optimize=True, progressive=False)
    out.seek(0)
    return out

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
            reader = ImageReader(_compress_image(img_bytes))
        elif src.startswith("http://") or src.startswith("https://"):
            resp = requests.get(src, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            reader = ImageReader(_compress_image(resp.content))
        else:
            # Treat as a local file path (e.g. output/hotel_photos/xyz.jpg)
            p = Path(src)
            if p.exists():
                reader = ImageReader(_compress_image(p.read_bytes()))
    except Exception as e:
        print(f"Hotel image fetch failed for '{src[:80]}...': {e}")
        reader = None

    _IMAGE_CACHE[cache_key] = reader
    return reader

# ─── Custom Flowables ────────────────────────────────────────────────────────
# ─── Website hero photo for the cover banner ─────────────────────────────────
_HERO_SHADE = None


def _hero_shade_reader():
    """The website's .hero-shade overlay (rgb 7,28,38) as a small transparent PNG."""
    global _HERO_SHADE
    if _HERO_SHADE is None:
        from PIL import Image
        W, H = 360, 90
        im = Image.new("RGBA", (W, H))
        px = im.load()
        for y in range(H):
            v = y / (H - 1)                                        # 0 top .. 1 bottom
            a_top = 0.72 * max(0.0, 1 - v / 0.24)
            a_bot = 0.92 * max(0.0, 1 - (1 - v) / 0.46)
            for x in range(W):
                u = x / (W - 1)
                a_left = 0.86 + (0.58 - 0.86) * (u / 0.48) if u < 0.48 else 0.58 + (0.12 - 0.58) * ((u - 0.48) / 0.52)
                a = 1 - (1 - a_top) * (1 - a_left) * (1 - a_bot)
                px[x, y] = (7, 28, 38, int(255 * min(1.0, a)))
        buf = io.BytesIO(); im.save(buf, "PNG"); buf.seek(0)
        _HERO_SHADE = ImageReader(buf)
    return _HERO_SHADE


def _load_hero_photo():
    """ImageReader for the website's main banner photo (site photo slot 'hero'), or None."""
    try:
        from backend.models import SitePhoto
        row = SitePhoto.query.filter_by(slot="hero").first()
        if row is not None and row.data:
            return ImageReader(_compress_image(bytes(row.data)))
    except Exception as exc:
        print(f"Warning: could not load hero photo: {exc}")
    return None


class HeroHeader(Flowable):
    """Full-width branded cover banner (compact layout)."""
    def __init__(self, width, client_name, days, start_date, adults, kids,
                 budget_tier, vehicle_type, total_cost, bg_reader=None):
        super().__init__()
        self.width  = width
        self.bg_reader = bg_reader          # website "hero" photo, or None -> classic navy banner
        self.height = 62 * mm if bg_reader is not None else 52 * mm
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

        photo = self.bg_reader is not None
        if photo:
            # Same look as the website banner: the hero photo with its dark shade
            # (darker at top, left and bottom so the white text stays readable).
            iw, ih = self.bg_reader.getSize()
            sc = max(w / iw, h / ih)
            dw, dh = iw * sc, ih * sc
            c.saveState()
            clip = c.beginPath(); clip.rect(0, 0, w, h); c.clipPath(clip, stroke=0, fill=0)
            c.drawImage(self.bg_reader, -(dw - w) / 2, -(dh - h) * 0.45, width=dw, height=dh)
            c.restoreState()
            c.drawImage(_hero_shade_reader(), 0, 0, width=w, height=h, mask="auto")
        else:
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
        c.setFont("Lato-Bold", 16.5)
        c.drawString(6*mm, h - 13*mm, "SERENE VIBES KASHMIR")

        # Tagline with small decorative bars
        c.setFillColor(colors.HexColor("#7dd3fc") if photo else SKY)
        c.setFont("Lato-Italic", 8.5)
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
        c.setFillColor(colors.HexColor("#e2e8f0") if photo else GRAY_400)
        c.setFont("Lato", 7)
        c.drawString(6*mm, h - 24.5*mm, "CUSTOMISED TOUR ITINERARY")

        # ── Client name ─────────────────────────────────────────────────────
        c.setFillColor(WHITE)
        c.setFont("Lato-Bold", 14)
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
            lw = c.stringWidth(label, "Lato-Bold", 8) + 12
            # Pill shadow
            c.setFillColor(colors.HexColor("#00000033"))
            c.roundRect(px + 0.5, py - 2*mm, lw, pill_h, 2.2*mm, fill=1, stroke=0)
            # Pill fill
            c.setFillColor(bg)
            c.roundRect(px, py - 1.5*mm, lw, pill_h, 2.2*mm, fill=1, stroke=0)
            # Pill text
            c.setFillColor(WHITE)
            c.setFont("Lato-Bold", 8)
            c.drawString(px + 6, py + 1*mm, label)
            px += lw + 5

        # ── Budget badge — ribbon style (top-right) ──────────────────────────
        badge_label = clean(str(self.budget_tier)) + " Package"
        bw = c.stringWidth(badge_label, "Lato-Bold", 9) + 18
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
        c.setFont("Lato-Bold", 9)
        c.drawString(bx + 9, by + 0.8*mm, badge_label)

        # ── Total cost (bottom-right) with emerald pill ───────────────────────
        cost_str = f"INR {int(self.total_cost):,}" if str(self.total_cost).replace(",","").isdigit() else clean(str(self.total_cost))
        # Cost label
        c.setFillColor(colors.HexColor("#e2e8f0") if photo else GRAY_400)
        c.setFont("Lato", 7)
        c.drawRightString(w - 6*mm, h - 38*mm, "ESTIMATED TOTAL COST")
        # Cost value in emerald pill
        cw = c.stringWidth(cost_str, "Lato-Bold", 11.5) + 14
        cx = w - cw - 6*mm
        cy = h - 34.5*mm
        c.setFillColor(EMERALD)
        c.roundRect(cx, cy - 1.5*mm, cw, 7*mm, 2*mm, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Lato-Bold", 11.5)
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
        c.setFont("Lato-Bold", 9.5)
        c.drawCentredString(7.5*mm, pill_y + 2.2*mm, str(self.day_num))

        # Title
        c.setFillColor(WHITE)
        c.setFont("Lato-Bold", 9.5)
        title = clean(self.title)
        max_w = w - 18*mm - 34*mm
        while c.stringWidth(title, "Lato-Bold", 9.5) > max_w and len(title) > 10:
            title = title[:-2].rstrip() + "…"
        c.drawString(17*mm, h/2 - 3, title)

        # Overnight badge with moon symbol
        if self.overnight and self.overnight.lower() not in ("departure", ""):
            moon = "\u25D0"  # half circle as moon approximation
            ov_label = f"Stay: {clean(self.overnight)}"
            ov_w = c.stringWidth(ov_label, "Lato-Bold", 7.5) + 9.5 * mm
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
            c.circle(ox + 3.6*mm, oy + 3.5*mm, 1.15*mm, fill=1, stroke=0)
            c.setFillColor(WHITE)
            c.setFont("Lato-Bold", 7.5)
            c.drawString(ox + 6.4*mm, oy + 2.25*mm, ov_label)


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
        c.setFont("Lato-Bold", 8)
        c.drawString(8, self.height/2 - 3, "ROUTE:")
        c.setFillColor(BLACK)
        c.setFont("Lato", 8)
        route_txt = clean(self.route)
        max_w = self.width - 40
        while c.stringWidth(route_txt, "Lato", 8) > max_w and len(route_txt) > 6:
            route_txt = route_txt[:-4] + "..."
        c.drawString(38, self.height/2 - 3, route_txt)


class HotelPhotoStrip(Flowable):
    """
    Hotel name / place header followed by exactly TWO photos side by side.

    Every photo tile in the PDF is the same size (half the page width, fixed
    aspect ratio) no matter which hotel or what the original picture's shape is:
    each photo is scaled to FILL its tile and centre-cropped, so there are no
    white bars and no stretched or tiny pictures. A missing photo becomes a
    neat "Photo unavailable" tile instead of breaking the layout.
    """
    TILE_RATIO = 0.62          # tile height = tile width * ratio (about 16:10)
    FOCUS_Y    = 0.42          # crop slightly above centre (keeps rooflines / headboards)

    def __init__(self, width, hotel_name, hotel_place, image_sources, photo_h=None):
        super().__init__()
        self.width       = width
        self.hotel_name  = hotel_name
        self.hotel_place = hotel_place
        self.header_h    = 8 * mm
        self.gap         = 4 * mm
        self.tile_w      = (width - self.gap) / 2
        self.photo_h     = self.tile_w * self.TILE_RATIO

        readers = []
        for src in (image_sources or []):
            r = fetch_image_reader(src)
            if r is not None:
                readers.append(r)
            if len(readers) == 2:
                break
        self.readers = readers
        self.height = self.header_h + 1.5 * mm + self.photo_h + 3 * mm

    def draw(self):
        c = self.canv
        w = self.width
        top = self.height

        # Header bar: accent edge + hotel name (left) + place (right)
        c.setFillColor(GRAY_100)
        c.roundRect(0, top - self.header_h, w, self.header_h, 1.5 * mm, fill=1, stroke=0)
        c.setFillColor(NAVY)
        c.roundRect(0, top - self.header_h, 1.4 * mm, self.header_h, 0.7 * mm, fill=1, stroke=0)
        c.setFont("Lato-Bold", 9)
        c.drawString(4 * mm, top - self.header_h + 2.5 * mm, clean(self.hotel_name))
        c.setFillColor(GRAY_600)
        c.setFont("Lato", 7.8)
        c.drawRightString(w - 3 * mm, top - self.header_h + 2.5 * mm, clean(self.hotel_place))

        y = top - self.header_h - 1.5 * mm - self.photo_h
        for i in range(2):
            x = i * (self.tile_w + self.gap)
            if i < len(self.readers):
                try:
                    self._draw_photo(c, self.readers[i], x, y)
                except Exception:
                    self._placeholder(c, x, y)
            else:
                self._placeholder(c, x, y)

    def _draw_photo(self, c, reader, x, y):
        iw, ih = reader.getSize()
        scale = max(self.tile_w / iw, self.photo_h / ih)          # fill the tile
        dw, dh = iw * scale, ih * scale
        ox = x - (dw - self.tile_w) / 2                           # centred horizontally
        oy = y - (dh - self.photo_h) * (1 - self.FOCUS_Y)         # biased crop vertically
        c.saveState()
        clip = c.beginPath()
        clip.roundRect(x, y, self.tile_w, self.photo_h, 1.6 * mm)
        c.clipPath(clip, stroke=0, fill=0)
        c.drawImage(reader, ox, oy, width=dw, height=dh, mask="auto")
        c.restoreState()
        c.setStrokeColor(GRAY_200)
        c.setLineWidth(0.6)
        c.roundRect(x, y, self.tile_w, self.photo_h, 1.6 * mm, fill=0, stroke=1)

    def _placeholder(self, c, x, y):
        c.setFillColor(GRAY_100)
        c.setStrokeColor(GRAY_200)
        c.setLineWidth(0.6)
        c.roundRect(x, y, self.tile_w, self.photo_h, 1.6 * mm, fill=1, stroke=1)
        c.setFillColor(GRAY_400)
        c.setFont("Lato-Italic", 8)
        c.drawCentredString(x + self.tile_w / 2, y + self.photo_h / 2 - 2, "Photo unavailable")


# ─── Destination background photos (soft, faded, behind each day's activities) ─
# Source: the website's own destination photos (admin > Website Photos, slots
# dest-srinagar / dest-gulmarg / ...). A day uses the photo of the place it goes to.
_DEST_KEYS = ("srinagar", "gulmarg", "pahalgam", "sonamarg", "doodhpathri")
# Two looks (change _BG_STYLE):
#   "dark"  - photo stays vivid under a navy tint, activity text is WHITE on dark bands
#   "light" - photo stays bright with a light veil, activity text is BLACK on pale bands
_BG_STYLE = "dark"
_BG_LOOK = {
    #          photo tint colour, tint strength, band colour (rgb), band alpha
    "dark":  {"tint": (7, 28, 38),    "tint_a": 0.34, "band": (7, 28, 38),    "band_a": 0.50},
    "light": {"tint": (255, 255, 255), "tint_a": 0.12, "band": (255, 255, 255), "band_a": 0.46},
}


def _bg_look():
    return _BG_LOOK.get(_BG_STYLE, _BG_LOOK["dark"])


def _faded_reader(raw: bytes):
    """Destination photo prepared for use behind text (tinted per _BG_STYLE); small JPEG."""
    from PIL import Image
    look = _bg_look()
    im = Image.open(io.BytesIO(raw))
    im.load()
    im = im.convert("RGB")
    im.thumbnail((1400, 1400), Image.LANCZOS)
    im = Image.blend(im, Image.new("RGB", im.size, look["tint"]), look["tint_a"])
    out = io.BytesIO()
    im.save(out, "JPEG", quality=82, optimize=True)
    out.seek(0)
    return ImageReader(out)


def _load_destination_backgrounds():
    """{destination key: faded ImageReader} for every website destination photo that exists."""
    found = {}
    try:
        from backend.models import SitePhoto
        for key in _DEST_KEYS:
            row = SitePhoto.query.filter_by(slot=f"dest-{key}").first()
            if row is not None and row.data:
                try:
                    found[key] = _faded_reader(bytes(row.data))
                except Exception as exc:
                    print(f"Destination photo '{key}' unreadable: {exc}")
    except Exception as exc:
        print(f"Warning: could not load destination photos: {exc}")
    return found


def _day_photo_key(day_info):
    """Which destination photo a day belongs to: where the day's route ends up."""
    route = str(day_info.get("transit_route") or day_info.get("title") or "").strip()
    overnight = str(day_info.get("overnight_stay") or "").lower()
    key = KashmirRouteMap._destination(KashmirRouteMap, route) if route else None
    if key in (None, "departure"):
        key = next((k for k in _DEST_KEYS if k in overnight), "srinagar")
    return key


class BgBlock(Flowable):
    """Draws a (cover-cropped) background picture, then the inner flowable on top."""
    def __init__(self, width, inner, reader):
        super().__init__()
        self.width, self.inner, self.reader = width, inner, reader

    def wrap(self, aw, ah):
        _, self.height = self.inner.wrap(self.width, 10000)
        return self.width, self.height

    def draw(self):
        c, w, h = self.canv, self.width, self.height
        iw, ih = self.reader.getSize()
        sc = max(w / iw, h / ih)
        dw, dh = iw * sc, ih * sc
        c.saveState()
        p = c.beginPath(); p.rect(0, 0, w, h); c.clipPath(p, stroke=0, fill=0)
        c.drawImage(self.reader, -(dw - w) / 2, -(dh - h) * 0.5, width=dw, height=dh)
        c.restoreState()
        # white "frosted" band behind every activity row (thin gaps let the photo show between them)
        rows = getattr(self.inner, "_rowHeights", None) or []
        y, gap = h, 0.7 * mm
        _lk = _bg_look()
        c.setFillColor(colors.Color(_lk["band"][0] / 255, _lk["band"][1] / 255, _lk["band"][2] / 255, alpha=_lk["band_a"]))
        for rh in rows:
            c.rect(0, y - rh + gap / 2, w, rh - gap, fill=1, stroke=0)
            y -= rh
        self.inner.drawOn(c, 0, 0)
        c.setStrokeColor(GRAY_200); c.setLineWidth(0.5); c.rect(0, 0, w, h, fill=0, stroke=1)


class StayRouteStrip(Flowable):
    """'Your stays at a glance': Start -> each stay (nights + hotel) -> End, drawn as a route line."""
    def __init__(self, width, start_point, end_point, segments):
        super().__init__()
        self.width, self.start_point, self.end_point, self.segs = width, start_point, end_point, segments
        self.height = (40 if len(segments) <= 4 else 48) * mm

    @staticmethod
    def _wrap(c, text, font, size, max_w, max_lines=2):
        words, lines, cur = str(text).split(), [], ""
        for wd in words:
            t = (cur + " " + wd).strip()
            if c.stringWidth(t, font, size) <= max_w or not cur:
                cur = t
            else:
                lines.append(cur); cur = wd
        if cur:
            lines.append(cur)
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            while c.stringWidth(lines[-1] + "...", font, size) > max_w and len(lines[-1]) > 3:
                lines[-1] = lines[-1][:-1]
            lines[-1] += "..."
        return lines

    def draw(self):
        c, w, h = self.canv, self.width, self.height
        c.setFillColor(GRAY_50); c.setStrokeColor(GRAY_200); c.setLineWidth(0.5)
        c.roundRect(0, 0, w, h, 2 * mm, fill=1, stroke=1)
        c.setFillColor(SKY); c.roundRect(0, 0, 1.4 * mm, h, 0.7 * mm, fill=1, stroke=0)
        total = sum(sg["nights"] for sg in self.segs)
        c.setFillColor(NAVY); c.setFont("Lato-Bold", 8)
        c.drawString(5 * mm, h - 6.2 * mm, "YOUR STAYS AT A GLANCE")
        c.setFillColor(GRAY_600); c.setFont("Lato", 7.5)
        c.drawRightString(w - 5 * mm, h - 6.2 * mm, f"{total} night{'s' if total != 1 else ''} in total")

        nodes = [("START", self.start_point, None, KashmirRouteMap.START_COL)] + \
                [(None, sg["city"], sg, KashmirRouteMap.PIN_COLORS.get(sg["city"].lower(), KashmirRouteMap.PIN_COLORS["srinagar"])[1])
                 for sg in self.segs] + \
                [("END", self.end_point, None, KashmirRouteMap.END_COL)]
        n = len(nodes)
        pad = 17 * mm
        xs = [pad + i * (w - 2 * pad) / max(n - 1, 1) for i in range(n)]
        cell = min(34 * mm, (w - 2 * pad) / max(n - 1, 1) - 2 * mm)
        ly = h - 15 * mm

        c.setStrokeColor(SKY_MID); c.setLineWidth(1.3); c.setDash(3.2, 2.4)
        c.line(xs[0], ly, xs[-1], ly); c.setDash()
        for i in range(n - 1):                                    # direction arrows mid-way
            mx = (xs[i] + xs[i + 1]) / 2
            c.setFillColor(SKY_MID)
            ap = c.beginPath(); ap.moveTo(mx + 1.6 * mm, ly); ap.lineTo(mx - 1.0 * mm, ly + 1.3 * mm); ap.lineTo(mx - 1.0 * mm, ly - 1.3 * mm); ap.close()
            c.drawPath(ap, fill=1, stroke=0)

        for x, (tag, name, seg, col) in zip(xs, nodes):
            c.setFillColor(WHITE); c.circle(x, ly, 3.9 * mm, fill=1, stroke=0)
            c.setFillColor(col);   c.circle(x, ly, 3.1 * mm, fill=1, stroke=0)
            c.setFillColor(WHITE); c.circle(x, ly, 1.1 * mm, fill=1, stroke=0)
            y = ly - 7.4 * mm
            if seg is None:                                       # start / end
                c.setFillColor(col); c.setFont("Lato-Bold", 6.6); c.drawCentredString(x, y, tag)
                y -= 3.6 * mm
                c.setFillColor(BLACK)
                for ln in self._wrap(c, name, "Lato-Bold", 7.2, cell, max_lines=3):
                    c.setFont("Lato-Bold", 7.2); c.drawCentredString(x, y, ln); y -= 3.3 * mm
            else:
                c.setFillColor(BLACK); c.setFont("Lato-Bold", 8.4); c.drawCentredString(x, y, seg["city"])
                y -= 3.0 * mm
                lab = f"{seg['nights']} night{'s' if seg['nights'] != 1 else ''}"
                pw = c.stringWidth(lab, "Lato-Bold", 6.6) + 4 * mm
                c.setFillColor(WHITE); c.setStrokeColor(col); c.setLineWidth(0.6)
                c.roundRect(x - pw / 2, y - 3.8 * mm, pw, 4.2 * mm, 2.1 * mm, fill=1, stroke=1)
                c.setFillColor(col); c.setFont("Lato-Bold", 6.6); c.drawCentredString(x, y - 2.4 * mm, lab)
                y -= 7.4 * mm
                c.setFillColor(GRAY_600)
                for hn in seg["hotels"][:2]:
                    for ln in self._wrap(c, hn, "Lato", 6.5, cell, max_lines=2):
                        c.setFont("Lato", 6.5); c.drawCentredString(x, y, ln); y -= 3.0 * mm


# One highlight per destination: (title, one-liner, tag, icon). Cities not listed are skipped.
SIGNATURE_EXPERIENCES = {
    "srinagar":    ("Shikara ride on Dal Lake", "Glide past floating gardens and painted houseboats as the light turns golden.", "1 hour complimentary", "boat"),
    "gulmarg":     ("Gulmarg Gondola", "Ride one of the world's highest cable cars up to Apharwat's snowy ridge.", "Optional, pay locally", "peak"),
    "pahalgam":    ("Betaab Valley walk", "Stroll open meadows and pine forest beside the Lidder River.", "Union cab, extra", "tree"),
    "sonamarg":    ("Thajiwas Glacier", "Meadow of Gold: ponies or a short trek to a glacier under the peaks.", "Pony ride, extra", "peak"),
    "doodhpathri": ("Valley of Milk", "Rolling green meadows and a cold stream, away from the crowds.", "Union cab, extra", "tree"),
}


class SignatureExperiences(Flowable):
    """'Signature experiences': one highlight card per distinct destination, colour-matched to the stay strip."""
    def __init__(self, width, segments):
        super().__init__()
        self.width = width
        seen, self.items = set(), []
        for sg in segments:
            key = sg["city"].lower()
            if key in SIGNATURE_EXPERIENCES and key not in seen:
                seen.add(key)
                self.items.append((sg["city"], key) + SIGNATURE_EXPERIENCES[key])
        self.items = self.items[:4]
        self.height = 46 * mm if self.items else 0

    @staticmethod
    def _icon(c, kind, cx, cy):
        c.setFillColor(WHITE); c.setStrokeColor(WHITE); c.setLineWidth(0.9)
        if kind == "boat":
            hull = c.beginPath(); hull.moveTo(cx - 3.0*mm, cy - 0.6*mm); hull.lineTo(cx + 3.0*mm, cy - 0.6*mm)
            hull.lineTo(cx + 1.8*mm, cy - 2.0*mm); hull.lineTo(cx - 1.8*mm, cy - 2.0*mm); hull.close()
            c.drawPath(hull, fill=1, stroke=0)
            sail = c.beginPath(); sail.moveTo(cx, cy + 2.8*mm); sail.lineTo(cx + 2.2*mm, cy); sail.lineTo(cx, cy); sail.close()
            c.drawPath(sail, fill=1, stroke=0)
            c.line(cx - 0.1*mm, cy + 2.8*mm, cx - 0.1*mm, cy - 0.6*mm)
        elif kind == "tree":
            for dy, hw in ((0.2*mm, 2.2*mm), (1.4*mm, 1.6*mm)):
                t = c.beginPath(); t.moveTo(cx - hw, cy + dy - 0.8*mm); t.lineTo(cx + hw, cy + dy - 0.8*mm); t.lineTo(cx, cy + dy + 1.6*mm); t.close()
                c.drawPath(t, fill=1, stroke=0)
            c.rect(cx - 0.35*mm, cy - 2.4*mm, 0.7*mm, 1.6*mm, fill=1, stroke=0)
        else:  # peak
            m = c.beginPath(); m.moveTo(cx - 3.2*mm, cy - 2.0*mm); m.lineTo(cx - 0.6*mm, cy + 2.4*mm); m.lineTo(cx + 0.6*mm, cy + 0.4*mm)
            m.lineTo(cx + 1.6*mm, cy + 1.4*mm); m.lineTo(cx + 3.4*mm, cy - 2.0*mm); m.close()
            c.drawPath(m, fill=1, stroke=0)

    def wrap(self, aw, ah):
        return self.width, self.height

    def draw(self):
        if not self.items:
            return
        c, w, h = self.canv, self.width, self.height
        # Section header bar (same look as SectionTitle)
        bar_h = 8 * mm
        c.setFillColor(NAVY_DEEP); c.roundRect(0, h - bar_h, w, bar_h, 2 * mm, fill=1, stroke=0)
        c.setFillColor(SKY);       c.roundRect(0, h - bar_h, 3 * mm, bar_h, 1.2 * mm, fill=1, stroke=0)
        c.setFillColor(WHITE);     c.setFont("Lato-Bold", 9.5)
        c.drawString(7 * mm, h - bar_h + 2.7 * mm, "SIGNATURE EXPERIENCES")

        n, gap = len(self.items), 3.5 * mm
        cw = (w - gap * (n - 1)) / n
        ch = h - bar_h - 4 * mm
        for i, (city, key, title, desc, tag, icon) in enumerate(self.items):
            x = i * (cw + gap)
            col = KashmirRouteMap.PIN_COLORS[key][1]
            c.setFillColor(GRAY_50); c.setStrokeColor(GRAY_200); c.setLineWidth(0.5)
            c.roundRect(x, 0, cw, ch, 2 * mm, fill=1, stroke=1)
            c.setFillColor(col); c.roundRect(x, ch - 1.0 * mm, cw, 1.0 * mm, 0.5 * mm, fill=1, stroke=0)
            cy = ch - 8.5 * mm
            c.setFillColor(col); c.circle(x + 7 * mm, cy, 4.2 * mm, fill=1, stroke=0)
            self._icon(c, icon, x + 7 * mm, cy)
            c.setFillColor(NAVY); c.setFont("Lato-Bold", 7.6)
            c.drawString(x + 13 * mm, cy - 1.2 * mm, city.upper())
            ty = cy - 8 * mm
            c.setFillColor(BLACK)
            for ln in StayRouteStrip._wrap(c, title, "Lato-Bold", 8.6, cw - 6 * mm, max_lines=2):
                c.setFont("Lato-Bold", 8.6); c.drawString(x + 3 * mm, ty, ln); ty -= 3.7 * mm
            ty -= 0.6 * mm
            c.setFillColor(GRAY_600)
            for ln in StayRouteStrip._wrap(c, desc, "Lato", 7.2, cw - 6 * mm, max_lines=3):
                c.setFont("Lato", 7.2); c.drawString(x + 3 * mm, ty, ln); ty -= 3.2 * mm
            tw = c.stringWidth(tag, "Lato-Bold", 6.6) + 4 * mm
            c.setFillColor(WHITE); c.setStrokeColor(col); c.setLineWidth(0.6)
            c.roundRect(x + 3 * mm, 2.6 * mm, tw, 4.2 * mm, 2.1 * mm, fill=1, stroke=1)
            c.setFillColor(KashmirRouteMap.PIN_COLORS[key][0]); c.setFont("Lato-Bold", 6.6)
            c.drawString(x + 5 * mm, 4.0 * mm, tag)


def _stay_segments(timeline, hotel_selections, lookup):
    """Consecutive nights in the same place become one stop: [{city, nights, hotels}]."""
    segs = []
    for idx, day in enumerate(timeline, start=1):
        night = str(day.get("overnight_stay") or "").strip()
        sig = f"{day.get('title', '')} {day.get('transit_route', '')}".lower()
        if not night or night.lower() == "departure" or "departure" in sig or "airport drop" in sig:
            continue
        hid = hotel_selections.get(str(idx - 1)) or hotel_selections.get(str(idx)) or hotel_selections.get(idx)
        if isinstance(hid, dict):
            hid = hid.get("id")
        hname = lookup.get(str(hid), {}).get("name") if hid else None
        city = night.split(":")[0].strip().title()
        if segs and segs[-1]["city"].lower() == city.lower():
            segs[-1]["nights"] += 1
            if hname and hname not in segs[-1]["hotels"]:
                segs[-1]["hotels"].append(hname)
        else:
            segs.append({"city": city, "nights": 1, "hotels": [hname] if hname else []})
    return segs


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
        c.setFont("Lato-Bold", font_sz)
        for i, ch in enumerate(label):
            a  = math.radians(start + i * step)
            lx = cx + arc_r * math.cos(a)
            ly = cy + arc_r * math.sin(a)
            c.saveState()
            c.translate(lx, ly)
            c.rotate(math.degrees(a) - 90)
            c.drawString(-c.stringWidth(ch, "Lato-Bold", font_sz) / 2, 0, ch)
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
        c.setFont("Lato-Italic", sub_sz)
        for i, ch in enumerate(sub):
            a  = math.radians(start2 + i * step2)
            lx = cx + arc_r2 * math.cos(a)
            ly = cy + arc_r2 * math.sin(a)
            c.saveState()
            c.translate(lx, ly)
            c.rotate(math.degrees(a) + 90)
            c.drawString(-c.stringWidth(ch, "Lato-Italic", sub_sz) / 2, 0, ch)
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
        c.setFont("Lato-Bold", 11)
        label = (self.icon + "  " if self.icon else "") + self.title
        c.drawString(10*mm, self.height - 5*mm, label)


# ─── Kashmir Route Map (Layout 3: map top + legend table below) ──────────────
DEFAULT_POINT = "Srinagar Airport"   # default tour start / end point


class KashmirRouteMap(Flowable):
    """
    Full-width route map + day-by-day legend table.

    * Real satellite imagery (Web-Mercator tiles, see satellite_map.py) with the
      pins / roads projected from real lat/lon on the same projection, so
      distances are true and the 50 km scale bar is accurate.  If imagery is
      unavailable it falls back to a stylised terrain drawing.
    * Every distinct stop gets ONE pin (Srinagar is the hub for arrival, day
      trips and departure), roads are drawn as spokes from the hub, and each
      road carries a "Day n" chip - so nothing overlaps and the story reads
      at a glance.
    Everything except the basemap is drawn with ReportLab canvas primitives.
    """

    # Real GPS coordinates (lat, lon)
    STOPS = {
        "srinagar":    (34.0837, 74.7973),
        "gulmarg":     (34.0484, 74.3805),
        "pahalgam":    (34.0161, 75.3147),
        "sonamarg":    (34.3088, 75.2969),
        "doodhpathri": (33.8700, 74.3700),
    }
    DISPLAY = {"srinagar": "Srinagar", "gulmarg": "Gulmarg", "pahalgam": "Pahalgam",
               "sonamarg": "Sonamarg", "doodhpathri": "Doodhpathri"}
    GPS_LABEL = {
        "srinagar":    "34.08°N  74.80°E",
        "gulmarg":     "34.05°N  74.38°E",
        "pahalgam":    "34.02°N  75.31°E",
        "sonamarg":    "34.31°N  75.30°E",
        "doodhpathri": "33.87°N  74.37°E",
    }
    # Road geometry, hub (Srinagar) -> destination.  These waypoints follow the real
    # highways (via Magam/Tangmarg, Ganderbal/Kangan/Gund, Awantipora/Anantnag,
    # Budgam).  `python scripts/build_map_assets.py` can replace them with exact
    # road geometry in backend/assets/maps/routes.json.
    ROADS = {
        "gulmarg":     [(34.0837, 74.7973), (34.060, 74.700), (34.030, 74.610), (34.022, 74.500),
                        (34.030, 74.430), (34.0484, 74.3805)],
        "pahalgam":    [(34.0837, 74.7973), (34.020, 74.930), (33.920, 75.010), (33.800, 75.110),
                        (33.775, 75.165), (33.820, 75.235), (33.900, 75.260), (34.0161, 75.3147)],
        "sonamarg":    [(34.0837, 74.7973), (34.140, 74.790), (34.226, 74.775), (34.262, 74.955),
                        (34.275, 75.110), (34.3088, 75.2969)],
        "doodhpathri": [(34.0837, 74.7973), (34.010, 74.720), (33.940, 74.660), (33.900, 74.560),
                        (33.8700, 74.3700)],
    }
    # Known tour start / end points (lat, lon). Matched by keywords in the admin's text.
    # Anything not listed here is still shown on the map, as a tag without a position.
    POINT_COORDS = [
        (("srinagar", "airport"),      (33.9871, 74.7742)),
        (("srinagar", "railway"),      (34.0236, 74.8471)),
        (("srinagar", "station"),      (34.0236, 74.8471)),
        (("jammu", "airport"),         (32.6891, 74.8374)),
        (("jammu", "tawi"),            (32.7057, 74.8714)),
        (("jammu", "railway"),         (32.7057, 74.8714)),
        (("jammu", "station"),         (32.7057, 74.8714)),
        (("katra",),                   (32.9916, 74.9455)),
        (("pathankot",),               (32.2733, 75.6522)),
        (("udhampur",),                (32.9160, 75.1416)),
        (("amritsar",),                (31.7096, 74.7973)),
        (("chandigarh",),              (30.6735, 76.7885)),
        (("delhi",),                   (28.5562, 77.1000)),
        (("jammu",),                   (32.7266, 74.8570)),
    ]
    START_COL = colors.HexColor("#16a34a")
    END_COL   = colors.HexColor("#dc2626")
    BOTH_COL  = colors.HexColor("#0f766e")

    def _resolve(self, name, info):
        """(lat, lon) for a start/end point: admin-confirmed coordinates first, then the built-in list."""
        if info and info.get("lat") is not None and info.get("lon") is not None:
            return (info["lat"], info["lon"])
        return self._point_latlon(name)

    @classmethod
    def _point_latlon(cls, text):
        t = (text or "").lower()
        if not t.strip():
            return None
        for kws, ll in cls.POINT_COORDS:
            if all(k in t for k in kws):
                return ll
        return None

    _baked_routes = None
    # Where each pin label sits relative to its pin
    LABEL_SIDE = {"srinagar": "above-left", "gulmarg": "above", "pahalgam": "right",
                  "sonamarg": "right", "doodhpathri": "right"}

    # Map viewport (cos-corrected to the panel aspect ratio in __init__)
    LAT_MIN, LAT_MAX = 33.76, 34.46
    LON_MIN, LON_MAX = 73.93, 75.77

    # Palette (map only)
    HILL_BG    = colors.HexColor("#e9eef3")
    VALLEY     = colors.HexColor("#dcefdc")
    VALLEY_EDG = colors.HexColor("#b9dcbc")
    WATER      = colors.HexColor("#8ec5f0")
    WATER_EDG  = colors.HexColor("#6aaee6")
    PEAK       = colors.HexColor("#c3ccd6")
    PEAK_SNOW  = colors.HexColor("#f8fafc")
    GRID       = colors.Color(1, 1, 1, alpha=0.75)

    PIN_COLORS = {                      # (dark, bright)
        "srinagar":    (colors.HexColor("#1e3a5f"), colors.HexColor("#3b82f6")),
        "gulmarg":     (colors.HexColor("#0f4c3a"), colors.HexColor("#14b8a6")),
        "pahalgam":    (colors.HexColor("#78350f"), colors.HexColor("#f59e0b")),
        "sonamarg":    (colors.HexColor("#3b0764"), colors.HexColor("#8b5cf6")),
        "doodhpathri": (colors.HexColor("#374151"), colors.HexColor("#9ca3af")),
    }
    ROW_TINT = {
        "srinagar":    colors.HexColor("#eff6ff"),
        "gulmarg":     colors.HexColor("#f0fdfa"),
        "pahalgam":    colors.HexColor("#fffbeb"),
        "sonamarg":    colors.HexColor("#f5f3ff"),
        "doodhpathri": colors.HexColor("#f9fafb"),
    }

    MAP_H   = 88 * mm
    TABLE_H = 8.5 * mm
    HDR_H   = 7 * mm

    MIN_ROW_H, MIN_MAP_H, MAX_MAP_H = 4.2 * mm, 58 * mm, 100 * mm

    def __init__(self, width, timeline, max_height=None,
                 start_point=DEFAULT_POINT, end_point=DEFAULT_POINT,
                 start_info=None, end_info=None):
        """max_height: total height the whole block (map + legend table) may use.
        The legend rows shrink for long trips and the map takes the rest."""
        super().__init__()
        self.width    = width
        self.timeline = timeline
        self.start_point = start_point or DEFAULT_POINT
        self.end_point = end_point or DEFAULT_POINT
        self.start_info = start_info or {}
        self.end_info = end_info or {}
        self._build_rows()
        n = max(len(self._rows), 1)
        if max_height:
            fixed = self.HDR_H + 2 * mm
            self.TABLE_H = max(self.MIN_ROW_H, min(self.TABLE_H, (max_height - fixed - self.MIN_MAP_H) / n))
            self.MAP_H = max(self.MIN_MAP_H, min(self.MAX_MAP_H, max_height - fixed - n * self.TABLE_H))
        self.height = self.MAP_H + self.HDR_H + self.TABLE_H * len(self._rows) + 2 * mm
        self._sat = None            # JPEG bytes once loaded
        self._sat_tried = False
        self._fit_viewport()

    def _fit_viewport(self):
        """Zoom the satellite view to the places this itinerary actually visits
        (more places / farther apart -> wider view), Web-Mercator, true scale."""
        import math
        S, W, N, E = (satellite_map.master_bounds() if satellite_map else (33.62, 73.80, 34.56, 75.90))
        keys = {r["key"] for r in self._rows if r["key"] in self.STOPS} | {"srinagar"}
        pts = [self.STOPS[k] for k in keys]
        for k in keys:
            if k in self.ROADS:
                pts += self._road_pts(k)
        hub = self.STOPS["srinagar"]
        for name, info in ((self.start_point, self.start_info), (self.end_point, self.end_info)):   # start/end close to Srinagar stay on the map
            ll = self._resolve(name, info)
            if ll and abs(ll[0] - hub[0]) < 0.3 and abs(ll[1] - hub[1]) < 0.3:
                pts.append(ll)
        lat_lo, lat_hi = min(p[0] for p in pts), max(p[0] for p in pts)
        lon_lo, lon_hi = min(p[1] for p in pts), max(p[1] for p in pts)
        my_lo, my_hi = self._merc_y(lat_lo), self._merc_y(lat_hi)
        my_ext, lon_ext = my_hi - my_lo, lon_hi - lon_lo
        aspect = self.width / self.MAP_H

        # room for pin labels (they sit right / above) and the footer + scale bar (below)
        lon_a = lon_lo - max(0.12, 0.16 * lon_ext)
        lon_b = lon_hi + max(0.28, 0.26 * lon_ext)
        pad_top, pad_bot = 0.30 * my_ext + math.radians(0.035), 0.45 * my_ext + math.radians(0.05)
        my_need = my_ext + pad_top + pad_bot

        lon_span = max(lon_b - lon_a, math.degrees(my_need * aspect), 0.9)
        my_n, my_s = self._merc_y(N), self._merc_y(S)
        lon_span = min(lon_span, (E - W) - 0.02, math.degrees((my_n - my_s) * aspect) - 0.02)
        my_span = math.radians(lon_span) / aspect
        # imagery coverage is the limit: shrink the label padding rather than cut off a stop
        room = my_span - my_ext
        if room < pad_top + pad_bot:
            k = max(room, 0.0) / (pad_top + pad_bot)
            pad_top, pad_bot = pad_top * k, pad_bot * k

        lon_c = (lon_a + lon_b) / 2
        my_c = (my_lo - pad_bot + my_hi + pad_top) / 2
        lon_c = max(W + lon_span / 2, min(lon_c, E - lon_span / 2))
        my_c = max(my_s + my_span / 2, min(my_c, my_n - my_span / 2))

        self.LON_MIN, self.LON_MAX = lon_c - lon_span / 2, lon_c + lon_span / 2
        self._my_span, self._my_min = my_span, my_c - my_span / 2
        self.LAT_MIN = self._inv_merc_y(my_c - my_span / 2)
        self.LAT_MAX = self._inv_merc_y(my_c + my_span / 2)
        self._coslat = math.cos(math.radians(self._inv_merc_y(my_c)))

    @staticmethod
    def _merc_y(lat):
        import math
        return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))

    @staticmethod
    def _inv_merc_y(my):
        import math
        return math.degrees(2 * math.atan(math.exp(my)) - math.pi / 2)

    def _satellite(self):
        """Satellite JPEG for this viewport, or None (-> stylised fallback)."""
        if not self._sat_tried:
            self._sat_tried = True
            if satellite_map is not None:
                try:
                    self._sat = satellite_map.get_viewport_jpeg(
                        self.LAT_MIN, self.LON_MIN, self.LAT_MAX, self.LON_MAX)
                except Exception as exc:
                    print(f"WARNING: satellite basemap unavailable ({exc}); using stylised map")
        return self._sat

    @classmethod
    def _road_pts(cls, key):
        """Baked real road geometry if present, else smoothed waypoints."""
        if cls._baked_routes is None:
            cls._baked_routes = {}
            try:
                import json
                f = Path(__file__).resolve().parent.parent / "assets" / "maps" / "routes.json"
                if f.exists():
                    cls._baked_routes = {k: [tuple(p) for p in v] for k, v in json.loads(f.read_text()).items()}
            except Exception as exc:
                print(f"WARNING: could not read routes.json ({exc})")
        if key in cls._baked_routes and len(cls._baked_routes[key]) > 1:
            return cls._baked_routes[key]
        return cls._smooth_pts(cls.ROADS[key], 3)

    # ── data ────────────────────────────────────────────────────────────────
    def _destination(self, route_str):
        """Which pin a day belongs to.  Srinagar is the hub and appears in almost
        every route string ("Srinagar to Gulmarg to Srinagar"), so it must never
        win over a real destination that is also mentioned."""
        r = (route_str or "").lower().strip()
        if "departure" in r or "airport drop" in r:
            return "departure"

        def first_stop(text, skip_hub):
            hits = [(text.find(k), k) for k in self.STOPS if k in text]
            if skip_hub:
                hits = [h for h in hits if h[1] != "srinagar"]
            return min(hits)[1] if hits else None

        head = r.split(":")[0]
        if " to " in head:
            # legs after the first "to": prefer the first non-Srinagar stop
            for leg in head.split(" to ")[1:]:
                k = first_stop(leg, skip_hub=True)
                if k:
                    return k
            k = first_stop(head.split(" to ", 1)[1], skip_hub=False)
            if k:
                return k
        return first_stop(head, skip_hub=True) or first_stop(r, skip_hub=True) or "srinagar"

    def _build_rows(self):
        self._rows = []
        for idx, day in enumerate(self.timeline, start=1):
            overnight = str(day.get("overnight_stay", "") or "").strip()
            route = str(day.get("transit_route") or day.get("title") or "").strip()
            if route:
                key = self._destination(route)
            else:
                key = "srinagar"
                for k in self.STOPS:
                    if k in overnight.lower():
                        key = k
                        break
                if "departure" in overnight.lower() or not overnight:
                    key = "departure"

            is_dep = key == "departure"
            hub_key = "srinagar" if is_dep else key
            loc = self.end_point if is_dep else self.DISPLAY.get(hub_key, hub_key.capitalize())

            # Activity = the route/title without the trailing ": Overnight X"
            title = str(day.get("title") or day.get("date") or f"Day {idx}")
            activity = (route or title).split(":")[0].strip() or title
            self._rows.append({
                "day": idx, "loc": loc, "key": hub_key, "is_dep": is_dep,
                "gps": ("-" if is_dep and not _is_srinagar_point(self.end_point)
                        else self.GPS_LABEL.get(hub_key, self.GPS_LABEL["srinagar"])),
                "activity": activity,
                "night": "-" if (is_dep or overnight.lower() in ("", "departure")) else overnight,
            })
        # A day starts from where the guest slept the night before (a Sonamarg day
        # trip with "Overnight Srinagar" starts the next day from Srinagar).
        prev = "srinagar"
        for r in self._rows:
            r["origin"] = prev
            night = r["night"].lower()
            prev = next((k for k in self.STOPS if k in night), r["key"] if not r["is_dep"] else "srinagar")

    # ── projection / primitives ─────────────────────────────────────────────
    def _proj(self, lat, lon):
        x = (lon - self.LON_MIN) / (self.LON_MAX - self.LON_MIN) * self.width
        y = self._map_y0 + (self._merc_y(lat) - self._my_min) / self._my_span * self.MAP_H
        return x, y

    def _path(self, c, pts, close=False):
        p = c.beginPath()
        for i, (lat, lon) in enumerate(pts):
            x, y = self._proj(lat, lon)
            (p.moveTo if i == 0 else p.lineTo)(x, y)
        if close:
            p.close()
        return p

    @staticmethod
    def _smooth_pts(pts, n=2):
        """Chaikin corner-cutting so roads/rivers look organic, not polyline-ish."""
        pts = list(pts)
        for _ in range(n):
            out = [pts[0]]
            for a, b in zip(pts, pts[1:]):
                out.append((0.75 * a[0] + 0.25 * b[0], 0.75 * a[1] + 0.25 * b[1]))
                out.append((0.25 * a[0] + 0.75 * b[0], 0.25 * a[1] + 0.75 * b[1]))
            out.append(pts[-1])
            pts = out
        return pts

    def _smooth(self, pts, n=2):
        return self._smooth_pts(pts, n)

    def _point_along(self, pts, frac):
        """Point at `frac` of the way along a polyline (screen space)."""
        import math
        xy = [self._proj(*p) for p in pts]
        seg = [math.dist(a, b) for a, b in zip(xy, xy[1:])]
        target, acc = sum(seg) * frac, 0.0
        for (a, b), L in zip(zip(xy, xy[1:]), seg):
            if acc + L >= target and L > 0:
                t = (target - acc) / L
                return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            acc += L
        return xy[-1]

    def _peak(self, c, x, y, w, h):
        c.setFillColor(self.PEAK)
        p = c.beginPath(); p.moveTo(x - w / 2, y); p.lineTo(x, y + h); p.lineTo(x + w / 2, y); p.close()
        c.drawPath(p, fill=1, stroke=0)
        c.setFillColor(self.PEAK_SNOW)
        p = c.beginPath(); p.moveTo(x - w * 0.16, y + h * 0.68); p.lineTo(x, y + h)
        p.lineTo(x + w * 0.16, y + h * 0.68); p.lineTo(x, y + h * 0.58); p.close()
        c.drawPath(p, fill=1, stroke=0)

    def _chip(self, c, cx, cy, text, col):
        c.setFont("Lato-Bold", 6.3)
        tw = c.stringWidth(text, "Lato-Bold", 6.3)
        w, h = tw + 3.4 * mm, 4.2 * mm
        c.setFillColor(WHITE); c.setStrokeColor(col); c.setLineWidth(0.9)
        c.roundRect(cx - w / 2, cy - h / 2, w, h, h / 2, fill=1, stroke=1)
        c.setFillColor(col)
        c.drawCentredString(cx, cy - 2.1, text)

    def _pin(self, c, key, days_txt, sub_txt=None):
        lat, lon = self.STOPS[key]
        px, py = self._proj(lat, lon)
        dark, bright = self.PIN_COLORS[key]
        hub = key == "srinagar"
        R = 3.6 * mm if hub else 2.9 * mm
        c.setFillColor(colors.Color(0, 0, 0, alpha=0.18)); c.circle(px + 0.6, py - 0.9, R, fill=1, stroke=0)
        c.setFillColor(WHITE);  c.circle(px, py, R + 0.9, fill=1, stroke=0)
        c.setFillColor(bright); c.circle(px, py, R, fill=1, stroke=0)
        c.setFillColor(dark);   c.circle(px, py, R * 0.46, fill=1, stroke=0)

        name = self.DISPLAY[key]
        lines = [(name, "Lato-Bold", 7.6, dark), (days_txt, "Lato", 6.2, GRAY_600)]
        if sub_txt:
            lines.append((sub_txt, "Lato-Italic", 5.8, GRAY_400))
        bw = max(c.stringWidth(t, f, s) for t, f, s, _ in lines) + 4.4 * mm
        bh = (3.3 * mm * len(lines)) + 1.6 * mm
        gap = R + 2.2

        def place(side):
            if side == "above":        bx, by = px - bw / 2, py + gap
            elif side == "below":      bx, by = px - bw / 2, py - gap - bh
            elif side == "right":      bx, by = px + gap + 1, py - bh / 2
            elif side == "left":       bx, by = px - gap - 1 - bw, py - bh / 2
            elif side == "above-left": bx, by = px - bw - 3 * mm, py + gap * 0.6
            elif side == "above-right": bx, by = px + gap, py + gap * 0.6
            elif side == "below-right": bx, by = px + gap, py - gap * 0.6 - bh
            else:                      bx, by = px - bw + 2 * mm, py - gap - bh   # below-left
            # keep inside the panel
            bx = max(1.5 * mm, min(bx, self.width - bw - 1.5 * mm))
            by = max(self._map_y0 + 1.5 * mm + getattr(self, "_foot", 0),
                     min(by, self._map_y0 + self.MAP_H - bh - 1.5 * mm))
            return bx, by

        def cost(bx, by):
            """Lower is better: huge for hitting labels/chips/pins, small per road sample covered."""
            box = (bx - 1, by - 1, bx + bw + 1, by + bh + 1)
            total = 0.0
            for (qx, qy, qw, qh) in getattr(self, "_placed", []):          # labels + day chips
                if box[0] < qx + qw and box[2] > qx and box[1] < qy + qh and box[3] > qy:
                    total += 1000
            for (ox, oy, orad) in getattr(self, "_pin_pts", []):           # every pin (incl. own)
                if box[0] < ox + orad and box[2] > ox - orad and box[1] < oy + orad and box[3] > oy - orad:
                    total += 1000
            for (rx, ry) in getattr(self, "_road_dots", []):               # don't bury the route
                if box[0] < rx < box[2] and box[1] < ry < box[3]:
                    total += 1
            return total

        pref = self.LABEL_SIDE.get(key, "above")
        order = [pref] + [x for x in ("above", "right", "left", "below", "above-right", "above-left",
                                      "below-right", "below-left") if x != pref]
        best = None
        for idx, side in enumerate(order):
            cx_, cy_ = place(side)
            sc = cost(cx_, cy_) + idx * 0.4
            if best is None or sc < best[0]:
                best = (sc, cx_, cy_)
        _, bx, by = best
        self._placed = getattr(self, "_placed", []) + [(bx, by, bw, bh)]
        c.setFillColor(colors.Color(0, 0, 0, alpha=0.10)); c.roundRect(bx + 0.5, by - 0.7, bw, bh, 1.4 * mm, fill=1, stroke=0)
        c.setFillColor(WHITE); c.setStrokeColor(GRAY_200); c.setLineWidth(0.4)
        c.roundRect(bx, by, bw, bh, 1.4 * mm, fill=1, stroke=1)
        c.setFillColor(bright); c.roundRect(bx, by, 1.3 * mm, bh, 0.6 * mm, fill=1, stroke=0)
        ty = by + bh - 3.5 * mm
        for t, f, s, col in lines:
            c.setFillColor(col); c.setFont(f, s)
            c.drawString(bx + 2.9 * mm, ty, t)
            ty -= 3.3 * mm

    def _draw_endpoints(self, c, foot):
        """START / END tags. A point near Srinagar is pinned at its real position;
        one far away (Jammu, Delhi...) is a tag on the map edge pointing its way."""
        import math
        w, mh, y0 = self.width, self.MAP_H, self._map_y0
        hub_x, hub_y = self._proj(*self.STOPS["srinagar"])
        same = (self.start_point or "").strip().lower() == (self.end_point or "").strip().lower()
        items = [("START / END", self.start_point, self.BOTH_COL, self.start_info)] if same else \
                [("START", self.start_point, self.START_COL, self.start_info), ("END", self.end_point, self.END_COL, self.end_info)]

        # Areas the tags must avoid: placed labels, pins, key, scale bar, compass
        base = y0 + foot
        avoid = list(getattr(self, "_placed", []))
        avoid += [(ox - r, oy - r, 2 * r, 2 * r) for ox, oy, r in getattr(self, "_pin_pts", [])]
        avoid.append((3 * mm, y0 + mh - 3 * mm - 6.6 * mm, 36 * mm, 6.6 * mm))
        bar_w = (50.0 / (111.32 * self._coslat)) / (self.LON_MAX - self.LON_MIN) * w
        avoid.append((1.6 * mm, base + 1.5 * mm, bar_w + 12 * mm, 7.2 * mm))
        avoid.append((w - 16 * mm, base + 2 * mm, 14 * mm, 14 * mm))

        def free(bx, by, bw, bh):
            if bx < 1.5 * mm or bx + bw > w - 1.5 * mm or by < base + 1 * mm or by + bh > y0 + mh - 1.5 * mm:
                return False
            return not any(bx < qx + qw and bx + bw > qx and by < qy + qh and by + bh > qy
                           for qx, qy, qw, qh in avoid)

        def tag(bx, by, bw, bh, head, name, col, sub=None):
            c.setFillColor(colors.Color(0, 0, 0, alpha=0.12)); c.roundRect(bx + 0.5, by - 0.7, bw, bh, 1.4 * mm, fill=1, stroke=0)
            c.setFillColor(WHITE); c.setStrokeColor(GRAY_200); c.setLineWidth(0.4)
            c.roundRect(bx, by, bw, bh, 1.4 * mm, fill=1, stroke=1)
            c.setFillColor(col); c.roundRect(bx, by, 1.3 * mm, bh, 0.6 * mm, fill=1, stroke=0)
            c.setFillColor(col); c.setFont("Lato-Bold", 6.0); c.drawString(bx + 2.9 * mm, by + bh - 3.3 * mm, head)
            c.setFillColor(BLACK); c.setFont("Lato-Bold", 7.0); c.drawString(bx + 2.9 * mm, by + bh - 6.6 * mm, name)
            if sub:
                c.setFillColor(GRAY_600); c.setFont("Lato", 5.8); c.drawString(bx + 2.9 * mm, by + 1.5 * mm, sub)
            avoid.append((bx, by, bw, bh))

        edge_i = 0
        for head, name, col, info in items:
            name_txt = _raw(name)
            sub = None
            if info and info.get("km"):
                sub = f"approx. {int(round(info['km']))} km by road to Srinagar"
            c.setFont("Lato-Bold", 7.0)
            bw = max(c.stringWidth(name_txt, "Lato-Bold", 7.0), c.stringWidth(head, "Lato-Bold", 6.0),
                     c.stringWidth(sub or "", "Lato", 5.8)) + 5.4 * mm
            bh = 11.6 * mm if sub else 8.6 * mm
            ll = self._resolve(name, info)
            if ll is None:                                   # unknown place: tag only, top-right corner
                bx, by = w - bw - 3 * mm, y0 + mh - 3 * mm - bh - edge_i * (bh + 1.5 * mm)
                edge_i += 1
                tag(bx, by, bw, bh, head, name_txt, col, sub)
                continue
            px, py = self._proj(*ll)
            inside = 4 * mm < px < w - 4 * mm and base + 4 * mm < py < y0 + mh - 4 * mm
            if inside:
                if math.dist((px, py), (hub_x, hub_y)) > 2.5 * mm:
                    c.setStrokeColor(WHITE); c.setLineWidth(2.6); c.line(px, py, hub_x, hub_y)
                    c.setStrokeColor(col); c.setLineWidth(1.0); c.setDash(2.2, 1.8); c.line(px, py, hub_x, hub_y); c.setDash()
                R = 1.9 * mm
                c.setFillColor(WHITE); c.circle(px, py, R + 0.8, fill=1, stroke=0)
                c.setFillColor(col); c.circle(px, py, R, fill=1, stroke=0)
                c.setFillColor(WHITE); c.circle(px, py, R * 0.4, fill=1, stroke=0)
                avoid.append((px - R - 1, py - R - 1, 2 * R + 2, 2 * R + 2))
                for dx, dy in ((-bw - R - 1.2 * mm, -bh / 2), (R + 1.2 * mm, -bh / 2),
                               (-bw / 2, -R - 1.2 * mm - bh), (-bw / 2, R + 1.2 * mm)):
                    if free(px + dx, py + dy, bw, bh):
                        tag(px + dx, py + dy, bw, bh, head, name_txt, col, sub)
                        break
                continue
            # off the map: put the tag on the border, on the line from Srinagar toward the place
            ang = math.atan2(py - hub_y, px - hub_x)
            ux, uy = math.cos(ang), math.sin(ang)
            lo_x, hi_x, lo_y, hi_y = 1.5 * mm + bw / 2, w - 1.5 * mm - bw / 2, base + 10.5 * mm + bh / 2, y0 + mh - 1.5 * mm - bh / 2
            t = min(((hi_x if ux > 0 else lo_x) - hub_x) / ux if abs(ux) > 1e-9 else 1e9,
                    ((hi_y if uy > 0 else lo_y) - hub_y) / uy if abs(uy) > 1e-9 else 1e9)
            ex, ey = hub_x + ux * t, hub_y + uy * t
            placed = False
            for off in (0, 1, -1, 2, -2, 3, -3, 4, -4):      # slide along the border until clear
                tx = ex + (-uy * off * (bw + 2 * mm) * 0.6 if abs(uy) < abs(ux) else off * (bw + 2 * mm) * 0.9)
                ty = ey + (off * (bh + 2 * mm) if abs(uy) < abs(ux) else 0)
                tx = max(lo_x, min(tx, hi_x)); ty = max(lo_y, min(ty, hi_y))
                if free(tx - bw / 2, ty - bh / 2, bw, bh):
                    placed = True
                    break
            if not placed:
                tx, ty = max(lo_x, min(ex, hi_x)), max(lo_y, min(ey, hi_y))
            # dashed guide from the hub to the tag, ending in an arrow that points at the tag
            half = min((bw / 2) / abs(ux) if abs(ux) > 1e-9 else 1e9, (bh / 2) / abs(uy) if abs(uy) > 1e-9 else 1e9)
            gx, gy = tx - ux * (half + 0.4 * mm), ty - uy * (half + 0.4 * mm)    # where the arrow tip touches the tag
            c.setStrokeColor(col); c.setLineWidth(0.8); c.setDash(1.6, 1.8)
            c.line(hub_x, hub_y, gx - ux * 2.6 * mm, gy - uy * 2.6 * mm); c.setDash()
            nx, ny = -uy, ux
            c.setFillColor(col)
            hp = c.beginPath()
            hp.moveTo(gx, gy)
            hp.lineTo(gx - ux * 2.8 * mm + nx * 1.4 * mm, gy - uy * 2.8 * mm + ny * 1.4 * mm)
            hp.lineTo(gx - ux * 2.8 * mm - nx * 1.4 * mm, gy - uy * 2.8 * mm - ny * 1.4 * mm)
            hp.close(); c.drawPath(hp, fill=1, stroke=0)
            tag(tx - bw / 2, ty - bh / 2, bw, bh, head, name_txt, col, sub)

    def _draw_stylised_terrain(self, c):
        """Fallback basemap (used only when satellite imagery is unavailable)."""
        w, mh, y0 = self.width, self.MAP_H, self._map_y0
        c.setFillColor(self.HILL_BG); c.rect(0, y0, w, mh, fill=1, stroke=0)

        # Graticule + degree labels
        c.setStrokeColor(self.GRID); c.setLineWidth(0.5); c.setDash(1.5, 2.5)
        for lat in (34.0, 34.25):
            _, y = self._proj(lat, self.LON_MIN); c.line(0, y, w, y)
        for lon in (74.5, 75.0, 75.5):
            x, _ = self._proj(34.0, lon); c.line(x, y0, x, y0 + mh)
        c.setDash()

        # Ridges (decorative peaks along the top and west edges)
        import random
        rnd = random.Random(7)
        x = 3 * mm
        while x < w - 3 * mm:
            ph = rnd.uniform(3.0, 5.6) * mm
            c.saveState(); c.setFillAlpha(0.8)
            self._peak(c, x, y0 + mh - ph - rnd.uniform(0.8, 3.0) * mm, rnd.uniform(5, 8) * mm, ph)
            c.restoreState()
            x += rnd.uniform(5.5, 8.5) * mm
        yy = y0 + 6 * mm
        while yy < y0 + mh - 14 * mm:
            ph = rnd.uniform(2.6, 4.6) * mm
            c.saveState(); c.setFillAlpha(0.75)
            self._peak(c, rnd.uniform(2.5, 6) * mm, yy, rnd.uniform(4.5, 7) * mm, ph)
            c.restoreState()
            yy += rnd.uniform(7, 10) * mm

        # Valley floor
        valley = self._smooth([
            (34.30, 74.30), (34.36, 74.60), (34.30, 74.95), (34.22, 75.18), (34.00, 75.24),
            (33.82, 75.20), (33.76, 75.00), (33.80, 74.70), (33.92, 74.45), (34.10, 74.30),
        ][:], 2)
        c.setFillColor(self.VALLEY); c.setStrokeColor(self.VALLEY_EDG); c.setLineWidth(0.8)
        c.drawPath(self._path(c, valley, close=True), fill=1, stroke=1)

        # Degree labels (drawn after terrain so peaks never sit on top of them)
        c.setFillColor(GRAY_400); c.setFont("Lato", 5.2)
        for lat in (34.0, 34.25):
            _, y = self._proj(lat, self.LON_MIN); c.drawString(9 * mm, y + 0.8, f"{lat:g}°N")
        for lon in (74.5, 75.0, 75.5):
            x, _ = self._proj(34.0, lon); c.drawString(x + 1.0, y0 + 11 * mm, f"{lon:g}°E")

        # Jhelum river + lakes
        river = self._smooth([(33.70, 75.18), (33.85, 75.00), (34.00, 74.86), (34.09, 74.77),
                              (34.22, 74.62), (34.31, 74.575)], 2)
        c.setStrokeColor(self.WATER_EDG); c.setLineWidth(1.3)
        c.drawPath(self._path(c, river), fill=0, stroke=1)
        for pts in ([(34.150, 74.855), (34.185, 74.905), (34.150, 74.945), (34.105, 74.905)],     # Dal
                    [(34.335, 74.52), (34.375, 74.565), (34.355, 74.62), (34.31, 74.585)]):             # Wular
            c.setFillColor(self.WATER); c.setStrokeColor(self.WATER_EDG); c.setLineWidth(0.6)
            c.drawPath(self._path(c, self._smooth(pts, 2), close=True), fill=1, stroke=1)
        c.setFillColor(colors.HexColor("#4a90c9")); c.setFont("Lato-Italic", 5.4)
        dx, dy = self._proj(34.105, 74.945); c.drawString(dx, dy, "Dal Lake")

    # ── satellite overlays ──────────────────────────────────────────────────
    def _halo_text(self, c, x, y, text, font, size, align="left"):
        """White label with a soft dark outline, legible on any imagery."""
        draw = {"left": c.drawString, "center": c.drawCentredString, "right": c.drawRightString}[align]
        c.setFont(font, size)
        c.setFillColor(colors.Color(0.04, 0.09, 0.16, alpha=0.55))
        for dx, dy in ((-.45, 0), (.45, 0), (0, -.45), (0, .45), (-.35, -.35), (.35, .35), (-.35, .35), (.35, -.35)):
            draw(x + dx, y + dy, text)
        c.setFillColor(WHITE)
        draw(x, y, text)

    def _draw_satellite(self, c, jpeg):
        w, mh, y0 = self.width, self.MAP_H, self._map_y0
        c.drawImage(ImageReader(io.BytesIO(jpeg)), 0, y0, w, mh)
        # whisper-thin navy wash: lifts white labels/lines without hiding the terrain
        c.setFillColor(colors.Color(0.03, 0.08, 0.16, alpha=0.10)); c.rect(0, y0, w, mh, fill=1, stroke=0)

        # graticule + degree labels
        import math
        lon_step = 0.5 if (self.LON_MAX - self.LON_MIN) > 1.3 else 0.25
        lats = [round(v * 0.25, 2) for v in range(math.ceil(self.LAT_MIN / 0.25), int(self.LAT_MAX / 0.25) + 1)]
        lons = [round(v * lon_step, 2) for v in range(math.ceil(self.LON_MIN / lon_step), int(self.LON_MAX / lon_step) + 1)]
        c.setStrokeColor(colors.Color(1, 1, 1, alpha=0.38)); c.setLineWidth(0.4); c.setDash(1.5, 2.5)
        for lat in lats:
            _, y = self._proj(lat, self.LON_MIN); c.line(0, y, w, y)
        for lon in lons:
            x, _ = self._proj(34.0, lon); c.line(x, y0, x, y0 + mh)
        c.setDash()
        for lat in lats:                     # skip labels that would sit under the key or footer
            _, y = self._proj(lat, self.LON_MIN)
            if y0 + 7 * mm < y < y0 + mh - 12 * mm:
                self._halo_text(c, 2.5 * mm, y + 1.0, f"{lat:g}°N", "Lato", 5.4)
        for lon in lons:
            x, _ = self._proj(34.0, lon)
            if x > 41 * mm and x < w - 12 * mm:
                self._halo_text(c, x + 1.2, y0 + mh - 3.4 * mm, f"{lon:g}°E", "Lato", 5.4)

    def _draw_sat_captions(self, c):
        """Lake names - drawn last and only where they don't collide with a label, chip or pin."""
        for lat, lon, text in ((34.098, 74.905, "Dal Lake"), (34.345, 74.625, "Wular Lake")):
            x, y = self._proj(lat, lon)
            tw = c.stringWidth(text, "Lato-Italic", 6.2)
            box = (x - 1, y - 2, x + tw + 1, y + 7)
            if not (self._map_y0 + self._foot + 2 * mm < y < self._map_y0 + self.MAP_H - 11 * mm
                    and 2 * mm < x < self.width - tw - 2 * mm):
                continue
            hit = any(box[0] < qx + qw and box[2] > qx and box[1] < qy + qh and box[3] > qy
                      for qx, qy, qw, qh in self._placed)
            hit = hit or any(box[0] < ox + r and box[2] > ox - r and box[1] < oy + r and box[3] > oy - r
                             for ox, oy, r in self._pin_pts)
            if not hit:
                self._halo_text(c, x, y, text, "Lato-Italic", 6.2)

    # ── main draw ───────────────────────────────────────────────────────────
    def draw(self):
        c, w, mh = self.canv, self.width, self.MAP_H
        self._map_y0 = self.height - mh
        y0 = self._map_y0
        sat = self._satellite()
        foot = 3.8 * mm if sat else 0          # attribution strip height

        # Clip everything map-related to the rounded panel
        c.saveState()
        clip = c.beginPath(); clip.roundRect(0, y0, w, mh, 3 * mm)
        c.clipPath(clip, stroke=0, fill=0)

        if sat:
            self._draw_satellite(c, sat)
        else:
            self._draw_stylised_terrain(c)

        # Roads actually used on this itinerary
        used = {}                                   # road key -> list of day numbers
        through = []                                # (day, from, to) legs that pass via the hub
        for r in self._rows:
            k, o = r["key"], r.get("origin", "srinagar")
            if (k != "srinagar" and k in self.ROADS and o != "srinagar"
                    and o != k and o in self.ROADS):
                # place -> Srinagar -> place: drawn as its own line below
                through.append((r["day"], o, k))
                used.setdefault(k, []); used.setdefault(o, [])
                continue
            if k != "srinagar" and k in self.ROADS:
                used.setdefault(k, []).append(r["day"])             # hub -> destination
            if o != "srinagar" and o != k and o in self.ROADS:
                used.setdefault(o, []).append(r["day"])             # starting place -> hub
        for k, days in used.items():
            pts = self._road_pts(k)
            dark, bright = self.PIN_COLORS[k]
            c.setLineCap(1); c.setLineJoin(1)
            if sat:                                  # soft shadow so the route lifts off the imagery
                c.setStrokeColor(colors.Color(0, 0, 0, alpha=0.35)); c.setLineWidth(6.2)
                c.drawPath(self._path(c, pts), fill=0, stroke=1)
            c.setStrokeColor(WHITE); c.setLineWidth(4.6 if sat else 4.2)
            c.drawPath(self._path(c, pts), fill=0, stroke=1)
            c.setStrokeColor(bright); c.setLineWidth(2.1); c.setDash(5, 2.6)
            c.drawPath(self._path(c, pts), fill=0, stroke=1)
            c.setDash(); c.setLineCap(0); c.setLineJoin(0)

        # Legs between two outer places (e.g. Gulmarg -> Pahalgam) run through Srinagar:
        # draw each as its own line, offset beside the shared roads so it can be followed.
        import math
        self._through_chips, self._pre_placed = [], []
        for day, o, k in through:
            pts = list(reversed(self._road_pts(o))) + list(self._road_pts(k))[1:]
            xy = [self._proj(*q) for q in pts]
            off, out = 1.9 * mm, []
            for i, (x, y) in enumerate(xy):
                a = xy[max(i - 1, 0)]; b = xy[min(i + 1, len(xy) - 1)]
                dx, dy = b[0] - a[0], b[1] - a[1]
                L = math.hypot(dx, dy) or 1.0
                out.append((x - dy / L * off, y + dx / L * off))
            pp = c.beginPath()
            for i, (x, y) in enumerate(out):
                (pp.moveTo if i == 0 else pp.lineTo)(x, y)
            dark, bright = self.PIN_COLORS[k]
            c.setLineCap(1); c.setLineJoin(1)
            c.setStrokeColor(WHITE); c.setLineWidth(3.4); c.drawPath(pp, fill=0, stroke=1)
            c.setStrokeColor(dark); c.setLineWidth(1.5); c.setDash(1.2, 2.2)
            c.drawPath(pp, fill=0, stroke=1)
            c.setDash(); c.setLineCap(0); c.setLineJoin(0)
            seg = [math.dist(a, b) for a, b in zip(out, out[1:])]
            target, acc, pos = sum(seg) * 0.90, 0.0, out[-1]
            for (a, b), L in zip(zip(out, out[1:]), seg):
                if acc + L >= target and L > 0:
                    t = (target - acc) / L
                    pos = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t); break
                acc += L
            self._through_chips.append((pos, f"Day {day}", dark))
            c.setFont("Lato-Bold", 6.3)
            cw = c.stringWidth(f"Day {day}", "Lato-Bold", 6.3) + 3.4 * mm
            self._pre_placed += [(pos[0] - cw / 2, pos[1] - 2.1 * mm, cw, 4.2 * mm)]

        # Pins first, chips after so chips are never covered
        seen = {}
        for r in self._rows:
            seen.setdefault(r["key"], []).append(r["day"])
        for r in self._rows:
            o = r.get("origin", "srinagar")
            if o != "srinagar" and o != r["key"] and o in self.STOPS:
                seen.setdefault(o, []).append(r["day"])
        seen = {k: sorted(set(v)) for k, v in seen.items()}

        def _fmt(days):
            return ("Day " if len(days) == 1 else "Days ") + " · ".join(str(d) for d in days)

        self._foot, self._placed = foot, list(self._pre_placed)
        self._pin_pts = []
        for k in seen:
            if k in self.STOPS:
                px_, py_ = self._proj(*self.STOPS[k])
                self._pin_pts.append((px_, py_, (3.6 if k == "srinagar" else 2.9) * mm + 1.5))
        self._road_dots = []                       # sampled route points (labels avoid them)
        import math
        for k, days in used.items():
            xy = [self._proj(*q) for q in self._road_pts(k)]
            for (ax, ay), (bx2, by2) in zip(xy, xy[1:]):
                n = max(1, int(math.dist((ax, ay), (bx2, by2)) / 4))
                for i in range(n):
                    dx_, dy_ = ax + (bx2 - ax) * i / n, ay + (by2 - ay) * i / n
                    if all(math.dist((dx_, dy_), (ox, oy)) > orad + 6 for ox, oy, orad in self._pin_pts):
                        self._road_dots.append((dx_, dy_))
            if not days:
                continue
            fx, fy = self._point_along(self._road_pts(k), 0.5)           # reserve the day chip
            c.setFont("Lato-Bold", 6.3)
            cw = c.stringWidth(_fmt(sorted(set(days))), "Lato-Bold", 6.3) + 3.4 * mm
            self._placed.append((fx - cw / 2, fy - 2.1 * mm, cw, 4.2 * mm))
        for k, days in seen.items():
            if k not in self.STOPS:
                continue
            sub = None
            if k == "srinagar":
                arr = _is_srinagar_point(self.start_point)
                dep = any(r["is_dep"] for r in self._rows) and _is_srinagar_point(self.end_point)
                sub = "Arrival & departure" if (arr and dep) else "Arrival" if arr else "Departure" if dep else None
            self._pin(c, k, _fmt(days), sub)

        for k, days in used.items():
            if not days:
                continue
            fx, fy = self._point_along(self._road_pts(k), 0.5)
            self._chip(c, fx, fy, _fmt(sorted(set(days))), self.PIN_COLORS[k][0])
        for (fx, fy), txt, col in self._through_chips:
            self._chip(c, fx, fy, txt, col)

        self._draw_endpoints(c, foot)

        if sat:
            self._draw_sat_captions(c)

        # Attribution strip (required by the imagery provider)
        if sat:
            c.setFillColor(colors.Color(0.04, 0.09, 0.16, alpha=0.62)); c.rect(0, y0, w, foot, fill=1, stroke=0)
            c.setFillColor(colors.Color(1, 1, 1, alpha=0.92)); c.setFont("Lato", 4.6)
            attrib = satellite_map.attribution() if satellite_map else ""
            c.drawString(3 * mm, y0 + 1.2 * mm, attrib)
            c.drawRightString(w - 3 * mm, y0 + 1.2 * mm, "Routes are indicative")
        base = y0 + foot

        # Scale bar (true 50 km at this latitude) - bottom-left
        km_per_deg_lon = 111.32 * self._coslat
        bar = (50.0 / km_per_deg_lon) / (self.LON_MAX - self.LON_MIN) * w
        sx, sy = 3 * mm, base + 3 * mm
        c.setFillColor(colors.Color(1, 1, 1, alpha=0.90))
        c.roundRect(sx - 1.4 * mm, sy - 1.5 * mm, bar + 12 * mm, 7.2 * mm, 1.2 * mm, fill=1, stroke=0)
        by = sy + 2.0 * mm
        c.setFillColor(NAVY);  c.rect(sx, by, bar, 1.4 * mm, fill=1, stroke=0)
        c.setFillColor(WHITE); c.rect(sx, by, bar / 2, 1.4 * mm, fill=1, stroke=0)
        c.setStrokeColor(NAVY); c.setLineWidth(0.3); c.rect(sx, by, bar, 1.4 * mm, fill=0, stroke=1)
        c.setFillColor(GRAY_600); c.setFont("Lato", 5.6)
        c.drawString(sx - 0.6, sy - 0.2 * mm, "0")
        c.drawCentredString(sx + bar / 2, sy - 0.2 * mm, "25")
        c.drawString(sx + bar + 1.6 * mm, by - 0.1 * mm, "50 km")

        # Compass - bottom-right
        cx_c, cy_c = w - 9 * mm, base + 9 * mm
        c.setFillColor(colors.Color(1, 1, 1, alpha=0.92)); c.circle(cx_c, cy_c, 5.6 * mm, fill=1, stroke=0)
        c.setStrokeColor(GRAY_400); c.setLineWidth(0.3); c.circle(cx_c, cy_c, 5.6 * mm, fill=0, stroke=1)
        for lab, dx_, dy_ in (("N", 0, 1), ("S", 0, -1), ("E", 1, 0), ("W", -1, 0)):
            c.setFillColor(colors.HexColor("#dc2626") if lab == "N" else GRAY_600)
            c.setFont("Lato-Bold" if lab == "N" else "Lato", 5.4)
            c.drawCentredString(cx_c + dx_ * 3.9 * mm, cy_c + dy_ * 3.9 * mm - 1.6, lab)
        c.setFillColor(colors.HexColor("#dc2626"))
        p2 = c.beginPath(); p2.moveTo(cx_c, cy_c + 2.3 * mm); p2.lineTo(cx_c + 1.0 * mm, cy_c); p2.lineTo(cx_c - 1.0 * mm, cy_c); p2.close()
        c.drawPath(p2, fill=1, stroke=0)
        c.setFillColor(GRAY_400)
        p3 = c.beginPath(); p3.moveTo(cx_c, cy_c - 2.3 * mm); p3.lineTo(cx_c + 1.0 * mm, cy_c); p3.lineTo(cx_c - 1.0 * mm, cy_c); p3.close()
        c.drawPath(p3, fill=1, stroke=0)

        # Key - top-left (keeps the road corridors clear)
        kx, ky = 3 * mm, y0 + mh - 3 * mm - 6.6 * mm
        c.setFillColor(colors.Color(1, 1, 1, alpha=0.90))
        c.roundRect(kx, ky, 36 * mm, 6.6 * mm, 1.2 * mm, fill=1, stroke=0)
        c.setStrokeColor(self.PIN_COLORS["srinagar"][1]); c.setLineWidth(1.8); c.setDash(3.5, 2)
        c.line(kx + 2.2 * mm, ky + 3.3 * mm, kx + 9 * mm, ky + 3.3 * mm); c.setDash()
        c.setFillColor(GRAY_600); c.setFont("Lato", 5.8)
        c.drawString(kx + 10.5 * mm, ky + 2.4 * mm, "Driving route")
        c.drawString(kx + 25 * mm, ky + 2.4 * mm, "Day n")

        c.restoreState()

        # Panel border (outside the clip so it is crisp)
        c.setStrokeColor(GRAY_200); c.setLineWidth(0.7)
        c.roundRect(0, y0, w, mh, 3 * mm, fill=0, stroke=1)

        # ── Legend table ────────────────────────────────────────────────────
        col_w = [w * 0.07, w * 0.19, w * 0.19, w * 0.37, w * 0.18]
        headers = ["Day", "Location", "GPS", "Activity / Route", "Overnight"]
        col_x = [sum(col_w[:i]) for i in range(len(col_w))]
        hy = y0 - self.HDR_H
        c.setFillColor(NAVY); c.rect(0, hy, w, self.HDR_H, fill=1, stroke=0)
        c.setFillColor(WHITE); c.setFont("Lato-Bold", 7)
        for i, hdr in enumerate(headers):
            if i == 0:
                c.drawCentredString(col_x[0] + col_w[0] / 2, hy + self.HDR_H / 2 - 2.3, hdr)
            else:
                c.drawString(col_x[i] + 3 * mm, hy + self.HDR_H / 2 - 2.3, hdr)

        for ri, row in enumerate(self._rows):
            ry = hy - (ri + 1) * self.TABLE_H
            key = row["key"]
            _, accent = self.PIN_COLORS.get(key, self.PIN_COLORS["srinagar"])
            c.setFillColor(self.ROW_TINT.get(key, GRAY_50)); c.rect(0, ry, w, self.TABLE_H, fill=1, stroke=0)
            c.setStrokeColor(GRAY_200); c.setLineWidth(0.3); c.line(0, ry, w, ry)
            mid = ry + self.TABLE_H / 2

            cx2 = col_x[0] + col_w[0] / 2
            c.setFillColor(accent); c.circle(cx2, mid, min(3 * mm, self.TABLE_H * 0.38), fill=1, stroke=0)
            c.setFillColor(WHITE); c.setFont("Lato-Bold", 7.2); c.drawCentredString(cx2, mid - 2.5, str(row["day"]))

            c.setFillColor(BLACK); c.setFont("Lato-Bold", 7.4)
            c.drawString(col_x[1] + 3 * mm, mid - 2.5, _raw(row["loc"]))
            c.setFillColor(GRAY_600); c.setFont("Lato", 6.8)
            c.drawString(col_x[2] + 3 * mm, mid - 2.4, row["gps"])

            act, maxw = _raw(row["activity"]), col_w[3] - 6 * mm
            c.setFont("Lato", 7)
            while c.stringWidth(act, "Lato", 7) > maxw and len(act) > 4:
                act = act[:-2].rstrip() + "…"
            c.setFillColor(SLATE); c.drawString(col_x[3] + 3 * mm, mid - 2.4, act)

            night = _raw(row["night"])
            if night == "-":
                c.setFillColor(GRAY_400); c.setFont("Lato", 7); c.drawString(col_x[4] + 3 * mm, mid - 2.4, "—")
            else:
                nw = c.stringWidth(night, "Lato-Bold", 6.4) + 4.4 * mm
                ph = min(4.2 * mm, self.TABLE_H * 0.7)
                nx, ny = col_x[4] + 3 * mm, mid - ph / 2
                c.setFillColor(WHITE); c.setStrokeColor(accent); c.setLineWidth(0.5)
                c.roundRect(nx, ny, nw, ph, ph / 2, fill=1, stroke=1)
                c.setFillColor(accent); c.setFont("Lato-Bold", 6.4)
                c.drawString(nx + 2.2 * mm, ny + ph / 2 - 2.2, night)

        bot = hy - len(self._rows) * self.TABLE_H
        c.setStrokeColor(GRAY_200); c.setLineWidth(0.3); c.line(0, bot, w, bot)
        for i in range(1, len(col_x)):
            c.line(col_x[i], bot, col_x[i], hy + self.HDR_H)


# ─── Helper: build styles ─────────────────────────────────────────────────────
def make_styles():
    base = getSampleStyleSheet()

    def P(name, **kw):
        return ParagraphStyle(name, **kw)

    return {
        "activity_time": P("AT",
            fontName="Lato-Bold", fontSize=8.5, textColor=SKY,
            leftIndent=4, spaceAfter=1),
        "activity_desc": P("AD",
            fontName="Lato", fontSize=8.5, textColor=BLACK,
            leftIndent=4, spaceAfter=4, leading=13.5),
        "activity_dot": P("ADT",
            fontName="Lato", fontSize=6, textColor=SKY, alignment=TA_CENTER,
            leading=13.5),
        "hotel_cell": P("HC",
            fontName="Lato", fontSize=8, textColor=BLACK, leading=11),
        "hotel_cell_bold": P("HCB",
            fontName="Lato-Bold", fontSize=8.5, textColor=NAVY, leading=11),
        "footer_note": P("FN",
            fontName="Lato-Italic", fontSize=7.5, textColor=GRAY_400,
            alignment=TA_CENTER),
        "inclusion": P("INC",
            fontName="Lato", fontSize=8.5, textColor=BLACK, leftIndent=8,
            spaceAfter=3, leading=13),
        "summary_label": P("SL",
            fontName="Lato-Bold", fontSize=8, textColor=GRAY_600),
        "summary_value": P("SV",
            fontName="Lato", fontSize=8.5, textColor=BLACK),
    }


# ─── Page decorators ─────────────────────────────────────────────────────────
def _draw_watermark(canvas, w, h):
    """Very light diagonal wordmark behind the content.

    Kept deliberately quiet: small, letter-spaced, ~5 % opacity and centred on
    the page body, so it reads as a brand/anti-copy mark without ever fighting
    with the text, tables or photos that sit on top of it."""
    canvas.saveState()
    canvas.translate(w / 2, h / 2 + 4 * mm)
    canvas.rotate(35)
    col = colors.Color(0.008, 0.518, 0.780, alpha=0.055)
    canvas.setFillColor(col)
    canvas.setStrokeColor(col)

    text, size, tracking = "SERENE VIBES KASHMIR", 30, 5.0
    canvas.setFont("Lato-Bold", size)
    total = canvas.stringWidth(text, "Lato-Bold", size) + tracking * (len(text) - 1)
    x = -total / 2
    for ch in text:                                   # manual letter-spacing
        canvas.drawString(x, 0, ch)
        x += canvas.stringWidth(ch, "Lato-Bold", size) + tracking

    canvas.setLineWidth(0.7)
    canvas.line(-total / 2, -6 * mm, total / 2, -6 * mm)
    canvas.setFont("Lato-Italic", 12)
    canvas.drawCentredString(0, -13 * mm, "A Poem In Motion")
    canvas.restoreState()


BORDER_GOLD = colors.HexColor("#c8a24a")


def _diamond(canvas, cx, cy, r, fill):
    p = canvas.beginPath()
    p.moveTo(cx, cy + r); p.lineTo(cx + r, cy); p.lineTo(cx, cy - r); p.lineTo(cx - r, cy); p.close()
    canvas.setFillColor(fill)
    canvas.drawPath(p, fill=1, stroke=0)


def _draw_page_border(canvas, w, h):
    """Professional page frame: header band, double-line border with gold
    corner brackets + diamonds, and a gold-trimmed footer. Everything sits
    outside the 18 mm content margin so it never touches text or tables."""
    canvas.saveState()

    # ── Header band (navy, sky accent, gold hairline) ────────────────────────
    band_h = 5 * mm
    canvas.setFillColor(NAVY)
    canvas.rect(0, h - band_h, w, band_h, fill=1, stroke=0)
    canvas.setFillColor(SKY)
    canvas.rect(0, h - band_h, 46 * mm, band_h, fill=1, stroke=0)
    canvas.setFillColor(NAVY_DEEP)
    canvas.rect(46 * mm, h - band_h, 3 * mm, band_h, fill=1, stroke=0)
    canvas.setStrokeColor(BORDER_GOLD)
    canvas.setLineWidth(0.9)
    canvas.line(0, h - band_h - 0.9 * mm, w, h - band_h - 0.9 * mm)

    # ── Double-line frame ────────────────────────────────────────────────────
    left, right = 7 * mm, w - 7 * mm
    top, bottom = h - 10 * mm, 14.5 * mm
    canvas.setStrokeColor(NAVY)
    canvas.setLineWidth(1.1)
    canvas.rect(left, bottom, right - left, top - bottom, fill=0, stroke=1)
    ins = 1.7 * mm
    canvas.setStrokeColor(SKY_MID)
    canvas.setLineWidth(0.45)
    canvas.rect(left + ins, bottom + ins, right - left - 2 * ins, top - bottom - 2 * ins, fill=0, stroke=1)

    # ── Gold corner brackets + diamonds ──────────────────────────────────────
    arm = 11 * mm
    canvas.setStrokeColor(BORDER_GOLD)
    canvas.setLineWidth(2.2)
    canvas.setLineCap(0)
    for cx, cy, sx, sy in ((left, top, 1, -1), (right, top, -1, -1),
                           (left, bottom, 1, 1), (right, bottom, -1, 1)):
        p = canvas.beginPath()
        p.moveTo(cx + sx * arm, cy)
        p.lineTo(cx, cy)
        p.lineTo(cx, cy + sy * arm)
        canvas.drawPath(p, fill=0, stroke=1)
        _diamond(canvas, cx + sx * 3.4 * mm, cy + sy * 3.4 * mm, 1.15 * mm, BORDER_GOLD)

    # ── Small centred diamonds on the top and bottom rules ───────────────────
    for yy in (top, bottom):
        canvas.setFillColor(WHITE)
        canvas.rect(w / 2 - 9 * mm, yy - 1.4 * mm, 18 * mm, 2.8 * mm, fill=1, stroke=0)
        _diamond(canvas, w / 2, yy, 1.3 * mm, BORDER_GOLD)
        _diamond(canvas, w / 2 - 5 * mm, yy, 0.7 * mm, SKY)
        _diamond(canvas, w / 2 + 5 * mm, yy, 0.7 * mm, SKY)

    # ── Footer band with gold trim ───────────────────────────────────────────
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, w, 10 * mm, fill=1, stroke=0)
    canvas.setFillColor(SKY)
    canvas.rect(0, 0, 46 * mm, 10 * mm, fill=1, stroke=0)
    canvas.setFillColor(NAVY_DEEP)
    canvas.rect(46 * mm, 0, 3 * mm, 10 * mm, fill=1, stroke=0)
    canvas.setStrokeColor(BORDER_GOLD)
    canvas.setLineWidth(0.9)
    canvas.line(0, 10.9 * mm, w, 10.9 * mm)
    canvas.restoreState()


def _page_frame(canvas, doc):
    """Watermark (not on the branded cover) + border + footer on every page."""
    canvas.saveState()
    w, h = A4
    if doc.page > 1:
        _draw_watermark(canvas, w, h)
    _draw_page_border(canvas, w, h)
    canvas.setFillColor(WHITE)
    canvas.setFont("Lato-Bold", 7.4)
    canvas.drawString(6 * mm, 3.7 * mm, "SERENE VIBES KASHMIR")
    canvas.setFont("Lato", 7)
    canvas.drawString(53 * mm, 3.7 * mm, "serenevibeskashmir@gmail.com   |   +91-9419766510   |   www.serenevibeskashmir.com")
    canvas.restoreState()


from reportlab.pdfgen import canvas as _rl_canvas


class NumberedCanvas(_rl_canvas.Canvas):
    """Two-pass canvas so the footer can say "Page 3 of 8"."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_pages = []

    def showPage(self):
        self._saved_pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_pages)
        for state in self._saved_pages:
            self.__dict__.update(state)
            self._draw_page_number(total)
            super().showPage()
        super().save()

    def _draw_page_number(self, total):
        w, _ = A4
        label = f"Page {self._pageNumber} of {total}"
        self.saveState()
        self.setFont("Lato-Bold", 7.5)
        tw = self.stringWidth(label, "Lato-Bold", 7.5)
        pw = tw + 8 * mm
        px = w - pw - MARGIN + 6 * mm
        self.setFillColor(SKY)
        self.roundRect(px, 2 * mm, pw, 6 * mm, 1.5 * mm, fill=1, stroke=0)
        self.setFillColor(WHITE)
        self.drawCentredString(px + pw / 2, 4.1 * mm, label)
        self.restoreState()


def _is_srinagar_point(p):
    return "srinagar" in (p or "").lower()


def _apply_points(timeline, start, end):
    """Copy of the timeline with the tour start / end point written in.

    Day 1 pickup text and the departure-day text say "Srinagar (International)
    Airport" by default; swap in the chosen point.  Safe to run on text the admin
    already localised (it only touches the default wording)."""
    import copy, re
    airport_re = re.compile(r"Srinagar International Airport|Srinagar Airport")
    tl = copy.deepcopy(timeline or [])
    for i, day in enumerate(tl):
        sig = f"{day.get('title', '')} {day.get('transit_route', '')}".lower()
        is_dep = "departure" in sig or "airport drop" in sig
        point = end if is_dep else start
        if is_dep or i == 0:
            if point != DEFAULT_POINT:
                for slot in day.get("schedule", []) or []:
                    for k in ("description", "activity", "activity_title"):
                        if isinstance(slot.get(k), str):
                            slot[k] = airport_re.sub(point, slot[k])
        # titles: "Airport Pickup ..." / "Airport Drop-Departure"
        for k in ("title", "transit_route"):
            v = day.get(k)
            if not isinstance(v, str):
                continue
            if start != DEFAULT_POINT:
                v = re.sub(r"^Airport Pickup", f"{start} Pickup", v)
            if end != DEFAULT_POINT:
                v = re.sub(r"^Airport Drop-Departure", f"{end} Drop-Departure", v)
            day[k] = v
    return tl


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
    start_point  = str(itinerary_data.get("start_point") or "").strip() or DEFAULT_POINT
    end_point    = str(itinerary_data.get("end_point") or "").strip() or DEFAULT_POINT
    itinerary_data = dict(itinerary_data)
    itinerary_data["timeline"] = _apply_points(itinerary_data.get("timeline", []), start_point, end_point)
    custom_cost  = itinerary_data.get("custom_cost") or \
                   itinerary_data.get("financial_summary", {}).get("total_payable_inr", "On Request")

    # ── 1. Hero header ────────────────────────────────────────────────────────
    story.append(HeroHeader(
        usable_w, client_name, days, start_date, adults, kids,
        budget_tier, vehicle_type, custom_cost, bg_reader=_load_hero_photo()
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
            Paragraph("START POINT", styles["summary_label"]),
            Paragraph(clean(start_point), styles["summary_value"]),
            Paragraph("END POINT", styles["summary_label"]),
            Paragraph(clean(end_point), styles["summary_value"]),
        ],
        [
            Paragraph("BUDGET TIER", styles["summary_label"]),
            Paragraph(clean(str(budget_tier)), styles["summary_value"]),
            Paragraph("ESTIMATED COST", styles["summary_label"]),
            Paragraph(
                f"<b><font color='#059669'>INR {int(custom_cost):,}</font></b>"
                if str(custom_cost).replace(".", "").isdigit()
                else clean(str(custom_cost)),
                ParagraphStyle("cv", fontName="Lato-Bold", fontSize=9, textColor=EMERALD)
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

    # ── 2b. Tour Route Map - ALWAYS the lower part of page 1 ──────────────────
    # Measure what is already on page 1 (hero + summary), give the map block the
    # remaining height (legend rows shrink for long trips, the map takes the rest)
    # and push the block to the bottom of the page with a spacer.  A PageBreak
    # follows so the Day-by-Day section starts cleanly on page 2.
    timeline_for_map = itinerary_data.get("timeline", [])
    used_h = sum(f.wrap(usable_w, 10000)[1] for f in story)
    avail  = (doc.height - 12) - used_h - 4 * mm          # frame has 6pt padding top+bottom
    map_title = SectionTitle(usable_w, "TOUR ROUTE MAP", icon="")
    gap_h  = 3 * mm
    route_map = KashmirRouteMap(usable_w, timeline_for_map,
                                max_height=avail - map_title.height - gap_h,
                                start_point=start_point, end_point=end_point,
                                start_info=itinerary_data.get("start_info"), end_info=itinerary_data.get("end_info"))
    spare = avail - (map_title.height + gap_h + route_map.height)
    if spare > 1 * mm:
        story.append(Spacer(1, spare))
    story.append(KeepTogether([map_title, Spacer(1, gap_h), route_map]))
    story.append(PageBreak())

    # ── 3. Day-by-day itinerary ───────────────────────────────────────────────
    story.append(SectionTitle(usable_w, "DAY-BY-DAY ITINERARY", icon=""))
    story.append(Spacer(1, 4*mm))

    timeline = itinerary_data.get("timeline", [])
    dest_bgs = _load_destination_backgrounds()

    for idx, day_info in enumerate(timeline, start=1):
        title     = day_info.get("title") or day_info.get("date") or f"Day {idx}"
        overnight = day_info.get("overnight_stay", "")
        route     = day_info.get("transit_route", "")
        schedule  = day_info.get("schedule", [])

        # "Srinagar to Sonamarg: Overnight Srinagar" -> banner shows the trip,
        # the right-hand badge already shows where the guests sleep.
        banner_title = title
        if ":" in title and title.split(":", 1)[1].strip().lower().startswith("overnight"):
            banner_title = title.split(":", 1)[0].strip()

        block = []
        block.append(DayBanner(usable_w, idx, banner_title, overnight))
        block.append(Spacer(1, 2*mm))

        # Only show the ROUTE strip when it adds something the banner doesn't say
        if route and route.strip().lower() != str(title).strip().lower():
            block.append(RouteBadge(usable_w, route))
            block.append(Spacer(1, 2*mm))

        if schedule:
            # Build a 2-col activity table: [time | description]
            act_rows = []
            has_real_label = False
            day_bg = dest_bgs.get(_day_photo_key(day_info))
            # on photo days the text colour is matched to the photo look (white on dark bands, black on pale ones)
            dark_look = day_bg is not None and _BG_STYLE == "dark"
            if day_bg is None:
                desc_style, dot_style, time_style = styles["activity_desc"], styles["activity_dot"], styles["activity_time"]
            else:
                txt = colors.white if dark_look else colors.black
                acc = colors.HexColor("#7dd3fc") if dark_look else SKY
                desc_style = ParagraphStyle("AD_photo", parent=styles["activity_desc"], textColor=txt)
                dot_style  = ParagraphStyle("ADT_photo", parent=styles["activity_dot"], textColor=acc)
                time_style = ParagraphStyle("AT_photo", parent=styles["activity_time"], textColor=acc)
            for slot in schedule:
                time_val = slot.get("time_slot") or slot.get("time", "")
                desc_val = slot.get("description") or slot.get("activity") or ""
                act_title = slot.get("activity_title", "")
                time_txt = str(time_val or "").strip()
                if time_txt in ("", "***", "*", "—", "–", "-"):
                    # placeholder label from the admin form -> neat bullet
                    cell_time = Paragraph("&#9679;", dot_style)
                else:
                    has_real_label = True
                    cell_time = Paragraph(clean(time_txt), time_style)
                desc_text = (f"<b>{clean(act_title)}</b><br/>" if act_title else "") + clean(str(desc_val))
                cell_desc = Paragraph(desc_text, desc_style)
                act_rows.append([cell_time, cell_desc])

            _lw = 0.17 if has_real_label else 0.055
            act_col_w = [usable_w * _lw, usable_w * (1 - _lw)]
            act_table = Table(act_rows, colWidths=act_col_w, hAlign="LEFT")
            if day_bg is not None:
                # photo shows through: transparent rows, softly tinted bullet column
                main_bg = colors.Color(1, 1, 1, alpha=0.0)
                if dark_look:
                    dot_bg, line_col, box_w = colors.Color(0.03, 0.11, 0.15, alpha=0.30), colors.Color(1, 1, 1, alpha=0.30), 0
                else:
                    dot_bg, line_col, box_w = colors.Color(0.88, 0.95, 0.99, alpha=0.55), colors.Color(0.5, 0.55, 0.62, alpha=0.35), 0
            else:
                main_bg, dot_bg, line_col, box_w = WHITE, SKY_LIGHT, GRAY_200, 0.5
            act_table.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, -1), main_bg),
                ("BACKGROUND",    (0, 0), (0, -1), dot_bg),
                ("BOX",           (0, 0), (-1, -1), box_w, GRAY_200),
                ("LINEBELOW",     (0, 0), (-1, -2), 0.3, line_col),
                ("LINEBEFORE",    (0, 0), (0, -1), 2.5, SKY),
                ("LEFTPADDING",   (0, 0), (-1, -1), 6),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
                ("TOPPADDING",    (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ]))
            block.append(BgBlock(usable_w, act_table, day_bg) if day_bg is not None else act_table)
        else:
            block.append(Paragraph(
                "<i>Details to be confirmed with your travel coordinator.</i>",
                ParagraphStyle("na", fontName="Lato-Italic", fontSize=8,
                               textColor=GRAY_400, leftIndent=6)
            ))

        block.append(Spacer(1, 5*mm))
        story.append(KeepTogether(block))

    # Sections now flow straight on after the last day card (no forced page
    # break) so the page after the itinerary isn't left mostly empty.
    story.append(Spacer(1, 2*mm))

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
        "hgm":  {"name": "Hotel Golden Maple",             "place": "Srinagar", "images": []},
        "sghb": {"name": "Srinagar Group of House-Boats",  "place": "Srinagar", "images": []},
        "hicl": {"name": "Hotel Iceland",                  "place": "Srinagar", "images": []},
        "hpp":  {"name": "Hotel Pocket Paradise",          "place": "Srinagar", "images": []},
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
        "ggr":  {"name": "Gulmarg Gateway Resorts",              "place": "Gulmarg",  "images": []},
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

    photo_flow = None
    if selected_hotel_ids:
        # Every photo tile is the same size (see HotelPhotoStrip). Up to 3 hotels
        # fit on one page and are kept together; with more hotels each one is kept
        # whole and the list flows onto the next page.
        title_flow = [SectionTitle(usable_w, "HOTEL REFERENCE PHOTOS", icon=""), Spacer(1, 4*mm)]
        strips = []
        for hid in selected_hotel_ids:
            info = HOTEL_LOOKUP[hid]
            strips.append(KeepTogether([
                HotelPhotoStrip(usable_w, info["name"], info["place"], info.get("images", [])),
                Spacer(1, 3*mm),
            ]))
        if len(strips) <= 3:
            photo_flow = KeepTogether(title_flow + strips)
        else:
            photo_flow = [KeepTogether(title_flow + strips[:1])] + strips[1:]

    # ── 4–6. Hotel Assignments + Inclusions/Exclusions + Payment Schedule ───────
    # Rule 1: These three sections always live on ONE page together.
    page_block_1 = []   # Hotel Assignments first, flushed below
    page_block_1.append(SectionTitle(usable_w, "HOTEL ASSIGNMENTS", icon=""))
    page_block_1.append(Spacer(1, 4*mm))

    # Header row
    hotel_header = [
        Paragraph("<b>Day</b>", ParagraphStyle("hh", fontName="Lato-Bold",
                  fontSize=8.5, textColor=WHITE, alignment=TA_CENTER)),
        Paragraph("<b>Hotel / Property</b>", ParagraphStyle("hh2", fontName="Lato-Bold",
                  fontSize=8.5, textColor=WHITE)),
        Paragraph("<b>Location</b>", ParagraphStyle("hh3", fontName="Lato-Bold",
                  fontSize=8.5, textColor=WHITE, alignment=TA_CENTER)),
        Paragraph("<b>Meal Plan</b>", ParagraphStyle("hh4", fontName="Lato-Bold",
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
            Paragraph(f"<b>Day {idx}</b>", ParagraphStyle("dc", fontName="Lato-Bold",
                      fontSize=8.5, textColor=NAVY, alignment=TA_CENTER)),
            Paragraph(clean(hotel_name), styles["hotel_cell_bold"]),
            Paragraph(clean(hotel_place), ParagraphStyle("hp", fontName="Lato",
                      fontSize=8, textColor=GRAY_600, alignment=TA_CENTER)),
            Paragraph(meal_plan, ParagraphStyle("mp", fontName="Lato",
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
    _segs = _stay_segments(timeline, hotel_selections, HOTEL_LOOKUP)
    if _segs:
        page_block_1.append(StayRouteStrip(usable_w, start_point, end_point, _segs))
        page_block_1.append(Spacer(1, 5*mm))
        # Only for compact itineraries, so the Hotel Assignments page never overflows.
        _exp = SignatureExperiences(usable_w, _segs)
        if _exp.items and len(timeline) <= 6 and len(_segs) <= 4:
            page_block_1.append(_exp)
            page_block_1.append(Spacer(1, 4*mm))
    # Hotel Assignments sit right after the itinerary; the reference photos
    # follow them (on their own page if they don't fit), then Inclusions/Payment.
    # Hotel Assignments ALWAYS start on a fresh page (no-op when already at the top of one)
    # and are kept together so the table is never split.
    story.append(CondPageBreak(doc.height - 24))
    story.append(KeepTogether(page_block_1))
    if photo_flow is not None:
        if isinstance(photo_flow, list):
            story.extend(photo_flow)
        else:
            story.append(photo_flow)
        story.append(Spacer(1, 4*mm))
    page_block_1 = []

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
                          ParagraphStyle("ic", fontName="Lato-Bold",
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
        Paragraph("<b>INCLUSIONS</b>", ParagraphStyle("ih", fontName="Lato-Bold",
                  fontSize=9.5, textColor=WHITE)),
        Paragraph("<b>EXCLUSIONS</b>", ParagraphStyle("eh", fontName="Lato-Bold",
                  fontSize=9.5, textColor=WHITE)),
    ]], colWidths=[usable_w/2, usable_w/2])
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
    ]], colWidths=[usable_w/2, usable_w/2])
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

    pay_header_style = ParagraphStyle("pyh", fontName="Lato-Bold",
                                      fontSize=8.5, textColor=WHITE, alignment=TA_CENTER)
    pay_body_style   = ParagraphStyle("pyb", fontName="Lato",
                                      fontSize=8.5, textColor=BLACK, alignment=TA_CENTER)
    pay_amt_style    = ParagraphStyle("pya", fontName="Lato-Bold",
                                      fontSize=9.5, textColor=EMERALD, alignment=TA_CENTER)
    pay_note_style   = ParagraphStyle("pyn", fontName="Lato-Italic",
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
            Paragraph(clean(label), ParagraphStyle("pl", fontName="Lato",
                      fontSize=8.5, textColor=BLACK)),
            Paragraph(f"<b>{clean(amt)}</b>", pay_amt_style),
            Paragraph(clean(due),  pay_body_style),
            Paragraph(clean(mode), pay_body_style),
            Paragraph(f"<font color='#b45309'>{clean(status)}</font>",
                      ParagraphStyle("ps", fontName="Lato-Bold",
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
    bank_note_style = ParagraphStyle("bn", fontName="Lato", fontSize=7.5,
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
    page_block_2 = []
    page_block_2.append(SectionTitle(usable_w, "CANCELLATION POLICY", icon=""))
    page_block_2.append(Spacer(1, 4*mm))

    canc_header_st = ParagraphStyle("cnh", fontName="Lato-Bold",
                                    fontSize=8.5, textColor=WHITE)
    canc_body_st   = ParagraphStyle("cnb", fontName="Lato",
                                    fontSize=8.5, textColor=BLACK, alignment=TA_CENTER)
    canc_pct_st    = ParagraphStyle("cnp", fontName="Lato-Bold",
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
            Paragraph(clean(timeline_txt), ParagraphStyle("cntl", fontName="Lato",
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

    note_heading_st = ParagraphStyle("noh", fontName="Lato-Bold",
                                     fontSize=8.2, textColor=GOLD, spaceBefore=6, spaceAfter=1.5)
    note_body_st    = ParagraphStyle("nob", fontName="Lato",
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
    # Each outer cell has 10pt padding on both sides, so the inner column
    # tables must be 20pt narrower than the cell or text spills over the edge.
    note_cell_w = usable_w / 2
    note_col_w  = note_cell_w - 20
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
        colWidths=[note_cell_w, note_cell_w],
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
        ("RIGHTPADDING", (0,0),(-1,-1), 10),
    ]))
    page_block_2.append(notes_outer)
    page_block_2.append(Spacer(1, 5*mm))

    # ── 9. Contact Card ───────────────────────────────────────────────────────
    page_block_2.append(SectionTitle(usable_w, "GET IN TOUCH WITH US", icon=""))
    page_block_2.append(Spacer(1, 3*mm))

    contact_label_st = ParagraphStyle("ctl", fontName="Lato-Bold",
                                      fontSize=7.5, textColor=GRAY_600)
    contact_val_st   = ParagraphStyle("ctv", fontName="Lato",
                                      fontSize=8.5, textColor=BLACK)
    contact_link_st  = ParagraphStyle("ctlnk", fontName="Lato",
                                      fontSize=8.5, textColor=SKY)

    contact_rows = [
        [
            Paragraph("Company", contact_label_st),
            Paragraph("Serene Vibes Kashmir", ParagraphStyle("cvb", fontName="Lato-Bold",
                      fontSize=9, textColor=NAVY)),
            Paragraph("Tagline", contact_label_st),
            Paragraph("A Poem In Motion", ParagraphStyle("cvi", fontName="Lato-Italic",
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
        fontName="Lato-Bold", fontSize=8, textColor=NAVY,
        spaceBefore=6, spaceAfter=2)
    tc_body = ParagraphStyle("tcb",
        fontName="Lato", fontSize=7.5, textColor=GRAY_600,
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
        ParagraphStyle("gth", fontName="Lato-Bold", fontSize=8,
                       textColor=NAVY, spaceAfter=4)
    ))
    bullet_rows = []
    for b in general_bullets:
        bullet_rows.append([
            Paragraph("-", ParagraphStyle("bd", fontName="Lato-Bold",
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

    ack_body_st = ParagraphStyle("ackb", fontName="Lato", fontSize=8,
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
    sig_label_st = ParagraphStyle("sigl", fontName="Lato-Bold",
                                  fontSize=7.5, textColor=GRAY_600, alignment=TA_CENTER)
    sig_line_st  = ParagraphStyle("sigln", fontName="Lato",
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
    validity_st = ParagraphStyle("vld", fontName="Lato-Italic", fontSize=7.5,
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
    doc.build(story, onFirstPage=_page_frame, onLaterPages=_page_frame,
              canvasmaker=NumberedCanvas)
    return f"output/{filename}"
