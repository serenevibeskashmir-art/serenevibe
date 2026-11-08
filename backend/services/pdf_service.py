import io
import re
import os
import requests
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader, simpleSplit
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
        if row is not None:
            raw = bytes(row.data) if row.data else None
            if raw is None:   # photo lives on Cloudinary
                from backend.services import cloud_media
                raw = cloud_media.fetch_bytes("site_photo", "hero")
            if raw:
                return ImageReader(_compress_image(raw))
    except Exception as exc:
        print(f"Warning: could not load hero photo: {exc}")
    return None


WHATSAPP_NUMBER = "919419766510"
INSTAGRAM_URL   = "https://instagram.com/serenevibeskashmir"
INSTAGRAM_HANDLE = "@serenevibeskashmir"
# Your Facebook page link, e.g. "https://facebook.com/yourpage". Leave empty to hide the Facebook button.
FACEBOOK_URL = os.environ.get("FACEBOOK_URL", "https://www.facebook.com/Serenevibeskashmir")


def _whatsapp_url(client_name="", ref=""):
    from urllib.parse import quote
    who = f"I'm {_raw(client_name)}. " if client_name else ""
    about = f"I have a question about my quote {ref}." if ref else "I have a question about my itinerary."
    return f"https://wa.me/{WHATSAPP_NUMBER}?text=" + quote(f"Hello Serene Vibes Kashmir! {who}{about}")


def _draw_whatsapp_button(c, x, y, w, h, url, label="WhatsApp"):
    """Green pill with a vector chat-bubble icon; the whole pill is a clickable link."""
    green = colors.HexColor("#25D366")
    c.setFillColor(colors.Color(0, 0, 0, alpha=0.18))
    c.roundRect(x + 0.4, y - 0.5, w, h, h / 2, fill=1, stroke=0)
    c.setFillColor(green)
    c.roundRect(x, y, w, h, h / 2, fill=1, stroke=0)
    # icon: white ring + tail, green handset arc inside
    r = h * 0.30
    cx, cy = x + h * 0.52, y + h / 2
    c.setStrokeColor(WHITE); c.setLineWidth(1.2)
    c.circle(cx, cy, r, fill=0, stroke=1)
    t = c.beginPath()
    t.moveTo(cx - r * 0.95, cy - r * 0.55); t.lineTo(cx - r * 1.35, cy - r * 1.25); t.lineTo(cx - r * 0.35, cy - r * 0.9); t.close()
    c.setFillColor(WHITE); c.drawPath(t, fill=1, stroke=0)
    c.setLineWidth(1.3)
    c.arc(cx - r * 0.45, cy - r * 0.45, cx + r * 0.45, cy + r * 0.45, 200, 120)
    c.setFillColor(WHITE)
    c.setFont("Lato-Bold", 8)
    c.drawString(x + h * 1.05, y + h / 2 - 2.7, label)
    c.linkURL(url, (x, y, x + w, y + h), relative=1)


def _draw_call_button(c, x, y, w, h, url="tel:+" + WHATSAPP_NUMBER, label="Call Us"):
    """Blue pill with a vector phone-handset icon; tapping it starts a call on a phone."""
    import math
    c.setFillColor(colors.Color(0, 0, 0, alpha=0.18))
    c.roundRect(x + 0.4, y - 0.5, w, h, h / 2, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#0284c7"))
    c.roundRect(x, y, w, h, h / 2, fill=1, stroke=0)
    cx, cy, r = x + h * 0.62, y + h * 0.58, h * 0.30
    c.saveState()
    c.setStrokeColor(WHITE); c.setFillColor(WHITE)
    c.setLineWidth(1.9); c.setLineCap(1)
    c.arc(cx - r, cy - r, cx + r, cy + r, 160, 125)       # handset body (curved bar, opening to the upper right)
    for a in (160, 285):                                  # earpiece / mouthpiece
        ex, ey = cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))
        c.circle(ex, ey, h * 0.075, fill=1, stroke=0)
    c.restoreState()
    c.setFillColor(WHITE)
    c.setFont("Lato-Bold", 8)
    c.drawString(x + h * 1.05, y + h / 2 - 2.7, label)
    c.linkURL(url, (x, y, x + w, y + h), relative=1)


def _draw_facebook_button(c, x, y, w, h, url, label="Facebook"):
    """Facebook-blue pill with a vector 'f' badge; the whole pill is a clickable link."""
    c.setFillColor(colors.Color(0, 0, 0, alpha=0.18))
    c.roundRect(x + 0.4, y - 0.5, w, h, h / 2, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#1877F2"))
    c.roundRect(x, y, w, h, h / 2, fill=1, stroke=0)
    r = h * 0.33
    cx, cy = x + h * 0.55, y + h / 2
    c.setFillColor(WHITE)
    c.circle(cx, cy, r, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#1877F2"))
    c.setFont("Lato-Bold", h * 0.62 / 0.75 * 0.72)
    c.drawCentredString(cx + r * 0.12, cy - r * 0.42, "f")
    c.setFillColor(WHITE)
    c.setFont("Lato-Bold", 8)
    c.drawString(x + h * 1.05, y + h / 2 - 2.7, label)
    c.linkURL(url, (x, y, x + w, y + h), relative=1)


def _draw_instagram_button(c, x, y, w, h, url=INSTAGRAM_URL, label=INSTAGRAM_HANDLE):
    """Instagram-coloured pill with a vector camera icon; the whole pill is a clickable link."""
    c.setFillColor(colors.Color(0, 0, 0, alpha=0.18))
    c.roundRect(x + 0.4, y - 0.5, w, h, h / 2, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#E1306C"))           # solid base, then a smooth purple -> orange gradient on top
    c.roundRect(x, y, w, h, h / 2, fill=1, stroke=0)
    c.saveState()
    clip = c.beginPath(); clip.roundRect(x, y, w, h, h / 2); c.clipPath(clip, stroke=0, fill=0)
    c.linearGradient(x, y, x + w, y,
                     (colors.HexColor("#833AB4"), colors.HexColor("#E1306C"), colors.HexColor("#F77737")),
                     (0.0, 0.5, 1.0), extend=False)
    c.restoreState()
    s_ = h * 0.56
    ix, iy = x + h * 0.26, y + (h - s_) / 2
    c.setStrokeColor(WHITE); c.setLineWidth(1.2)
    c.roundRect(ix, iy, s_, s_, s_ * 0.3, fill=0, stroke=1)
    c.circle(ix + s_ / 2, iy + s_ / 2, s_ * 0.22, fill=0, stroke=1)
    c.setFillColor(WHITE)
    c.circle(ix + s_ * 0.80, iy + s_ * 0.80, s_ * 0.06, fill=1, stroke=0)
    c.setFont("Lato-Bold", 8)
    c.drawString(x + h * 1.05, y + h / 2 - 2.7, label)
    c.linkURL(url, (x, y, x + w, y + h), relative=1)


class SocialButtons(Flowable):
    """Row: 'Questions? Talk to us' + clickable WhatsApp and Instagram buttons."""
    def __init__(self, width, client_name="", ref=""):
        super().__init__()
        self.width, self.height = width, 11 * mm
        self.client_name, self.ref = client_name, ref

    def draw(self):
        c, w, h = self.canv, self.width, self.height
        bh = 8 * mm
        c.setFillColor(NAVY)
        c.setFont("Lato-Bold", 8.5)
        c.drawString(0, h / 2 + 0.5, "QUESTIONS? TALK TO US")
        c.setFillColor(GRAY_600)
        c.setFont("Lato", 7.2)
        c.drawString(0, h / 2 - 8, "Call or message us directly.")
        gap = 3 * mm
        btns = [
            (24 * mm, lambda x, y, bw: _draw_call_button(c, x, y, bw, bh)),
            (31 * mm, lambda x, y, bw: _draw_whatsapp_button(c, x, y, bw, bh, _whatsapp_url(self.client_name, self.ref), label="WhatsApp")),
            (31 * mm, lambda x, y, bw: _draw_instagram_button(c, x, y, bw, bh, label="Instagram")),
        ]
        if FACEBOOK_URL:
            btns.append((31 * mm, lambda x, y, bw: _draw_facebook_button(c, x, y, bw, bh, FACEBOOK_URL)))
        x = w - sum(b[0] for b in btns) - gap * (len(btns) - 1)
        for bw, draw in btns:
            draw(x, (h - bh) / 2, bw)
            x += bw + gap


class HeroHeader(Flowable):
    """Full-width branded cover banner (compact layout)."""
    def __init__(self, width, client_name, days, start_date, adults, kids,
                 budget_tier, vehicle_type, total_cost, bg_reader=None, ref="", route=""):
        super().__init__()
        self.ref = ref
        self.route = route
        self.width  = width
        self.bg_reader = bg_reader          # website "hero" photo, or None -> classic navy banner
        self.height = 78 * mm if bg_reader is not None else 68 * mm
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

        # ── Route strip along the bottom of the cover ────────────────────────
        if self.route:
            c.setStrokeColor(colors.Color(1, 1, 1, alpha=0.30))
            c.setLineWidth(0.4)
            c.line(6*mm, 14.5*mm, w - 6*mm, 14.5*mm)
            c.setFillColor(colors.HexColor("#93c5fd"))
            c.setFont("Lato-Bold", 6.8)
            c.drawString(6*mm, 8.2*mm, "YOUR JOURNEY")
            c.setFillColor(WHITE)
            c.setFont("Lato-Bold", 10)
            route = _raw(self.route)
            max_rw = w - 12*mm - 24*mm
            # show EVERY stop: shrink the font (and arrow spacing) until the whole journey fits
            _stops = route.split("  \u2192  ")
            _fs = 10.0
            _sep = "  \u2192  "
            while c.stringWidth(_sep.join(_stops), "Lato-Bold", _fs) > max_rw and _fs > 5.6:
                _fs -= 0.2
                if _fs < 8.6:
                    _sep = " \u2192 "
            route = _sep.join(_stops)
            c.setFont("Lato-Bold", _fs)
            c.drawString(6*mm + 24*mm, 8*mm + (10 - _fs) * 0.15, route)

        # ── Clickable WhatsApp + Instagram buttons (bottom-right of the cover) ─
        if self.route:
            bh = 7.2*mm
            _draw_instagram_button(c, w - 6*mm - 46*mm, 18.2*mm, 46*mm, bh)
            _draw_whatsapp_button(c, w - 6*mm - 46*mm - 3*mm - 28*mm, 18.2*mm, 28*mm, bh,
                                  _whatsapp_url(self.client_name, self.ref))

        # ── Quote reference (top-right, understated) ─────────────────────────
        if self.ref:
            c.setFillColor(colors.HexColor("#cbd5e1"))
            c.setFont("Lato", 7)
            c.drawRightString(w - 6*mm, h - 8.5*mm, "QUOTE NO.  " + _raw(self.ref))

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
        c.drawString(6*mm, h - 32*mm, _raw(self.client_name))

        # ── Stat pills (Days / Pax / Date / Vehicle) ────────────────────────
        pills = [
            (f"{self.days} Days / {max(int(self.days) - 1, 1)} Nights", SKY),
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
        cost_str = f"INR {_amount_int(self.total_cost):,}" if _is_amount(self.total_cost) else "TBD"
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
    TRAVEL_H = 6.6 * mm      # slim route / distance strip attached under the banner

    def __init__(self, width, day_num, title, overnight="", hotel="", date_label="", travel=None):
        super().__init__()
        self.width    = width
        self.travel   = travel if (travel and travel.get("text")) else None   # {"stops": [...], "text": "80 km · about 2.5 h"}
        self.height   = 11 * mm + (self.TRAVEL_H if self.travel else 0)
        self.day_num  = day_num
        self.title    = title
        self.overnight = overnight
        self.date_label = date_label
        self.hotel     = hotel      # hotel name for this night (callable or str); shown in the Stay pill

    def _draw_travel(self, c, w, th):
        """'Srinagar -> Sonamarg  ·  80 km  ·  about 2.5 h' on a pale strip under the banner."""
        r = 2 * mm
        c.setFillColor(SKY_LIGHT)
        c.roundRect(0, 0, w, th + r, r, fill=1, stroke=0)          # square the top edge: it joins the banner
        c.rect(0, th - 0.5 * mm, w, r + 0.5 * mm, fill=1, stroke=0)
        c.setFillColor(SKY_MID); c.roundRect(0, 0, 15 * mm, th, r, fill=1, stroke=0)
        c.rect(0, th - r, 15 * mm, r, fill=1, stroke=0)
        mid = th / 2
        # little road icon: two dashes between a start ring and an end dot
        c.setStrokeColor(WHITE); c.setFillColor(WHITE); c.setLineWidth(0.8)
        c.circle(4.2 * mm, mid, 0.9 * mm, fill=0, stroke=1)
        c.setDash(1.1, 1.1); c.line(5.4 * mm, mid, 9.6 * mm, mid); c.setDash()
        c.circle(10.8 * mm, mid, 0.95 * mm, fill=1, stroke=0)

        names = [_raw(n) for n in self.travel["stops"]]
        tail = "  \u00b7  " + _raw(self.travel["text"])
        size, arrow = 7.8, 5.2 * mm
        avail = w - 17 * mm - 3 * mm
        while size > 5.6:
            total = sum(c.stringWidth(n, "Lato-Bold", size) for n in names) + arrow * (len(names) - 1) \
                    + c.stringWidth(tail, "Lato-Bold", size)
            if total <= avail:
                break
            size -= 0.3
        x, y = 17 * mm, mid - size * 0.34
        c.setFont("Lato-Bold", size)
        for i, n in enumerate(names):
            if i:                                                    # vector arrow: no font glyph needed
                ax = x + 0.9 * mm
                c.setStrokeColor(SKY); c.setFillColor(SKY); c.setLineWidth(0.7)
                c.line(ax, mid, ax + arrow - 2.6 * mm, mid)
                hp = c.beginPath(); hp.moveTo(ax + arrow - 1.4 * mm, mid)
                hp.lineTo(ax + arrow - 2.9 * mm, mid + 0.9 * mm); hp.lineTo(ax + arrow - 2.9 * mm, mid - 0.9 * mm)
                hp.close(); c.drawPath(hp, fill=1, stroke=0)
                x += arrow
            c.setFillColor(NAVY); c.setFont("Lato-Bold", size)
            c.drawString(x, y, n)
            x += c.stringWidth(n, "Lato-Bold", size)
        c.setFillColor(TEAL); c.setFont("Lato-Bold", size)
        c.drawString(x, y, tail)

    def draw(self):
        c = self.canv
        w, h = self.width, 11 * mm
        tb = self.TRAVEL_H if self.travel else 0
        if tb:
            self._draw_travel(c, w, tb)
            c.saveState()
            c.translate(0, tb)

        # Main bar with slight rounding
        c.setFillColor(NAVY)
        c.roundRect(0, 0, w, h, 2*mm, fill=1, stroke=0)

        # Left accent strip (wider, deeper blue)
        c.setFillColor(SKY)
        c.roundRect(0, 0, 15*mm, h, 2*mm, fill=1, stroke=0)
        # Fill right side of accent so left edge is fully rounded
        c.setFillColor(NAVY)
        c.rect(11*mm, 0, 4*mm, h, fill=1, stroke=0)

        # Thin sky accent rule below the banner (the travel strip replaces it when present)
        if not tb:
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
        title = _raw(self.title)

        # Overnight badge with moon symbol
        show_badge = bool(self.overnight and self.overnight.lower() not in ("departure", ""))
        ov_label = ""
        if show_badge:
            hotel = self.hotel() if callable(self.hotel) else self.hotel
            ov_label = f"Stay: {_raw(hotel or self.overnight)}"
            while c.stringWidth(ov_label, "Lato-Bold", 7.5) > 78*mm and len(ov_label) > 12:
                ov_label = ov_label[:-2].rstrip() + "…"
        badge_w = (c.stringWidth(ov_label, "Lato-Bold", 7.5) + 9.5*mm + 4*mm) if show_badge else 4*mm
        max_w = w - 18*mm - badge_w - 2*mm
        while c.stringWidth(title, "Lato-Bold", 9.5) > max_w and len(title) > 10:
            title = title[:-2].rstrip() + "…"
        if self.date_label:                                  # two lines: title + travel date
            c.drawString(17*mm, h - 4.7*mm, title)
            c.setFillColor(colors.HexColor("#93c5fd"))
            c.setFont("Lato", 6.8)
            c.drawString(17*mm, 2.2*mm, self.date_label.upper())
            c.setFillColor(WHITE)
        else:
            c.drawString(17*mm, h/2 - 3, title)

        if show_badge:
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
        if tb:
            c.restoreState()


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
        max_w = self.width - 52
        while c.stringWidth(route_txt, "Lato", 8) > max_w and len(route_txt) > 6:
            route_txt = route_txt[:-4] + "..."
        c.drawString(46, self.height/2 - 3, route_txt)


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
        if readers:
            self.height = self.header_h + 1.5 * mm + self.photo_h + 3 * mm
        else:                       # no photos yet: slim name card instead of two empty grey tiles
            self.height = self.header_h + 1 * mm

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
        c.drawString(4 * mm, top - self.header_h + 2.5 * mm, _raw(self.hotel_name))
        c.setFillColor(GRAY_600)
        c.setFont("Lato", 7.8)
        c.drawRightString(w - 3 * mm, top - self.header_h + 2.5 * mm, _raw(self.hotel_place))
        if not self.readers:
            c.setFillColor(GRAY_400)
            c.setFont("Lato-Italic", 7.5)
            c.drawString(4 * mm + c.stringWidth(_raw(self.hotel_name), "Lato-Bold", 9) + 4 * mm,
                         top - self.header_h + 2.5 * mm, "Photos shared on request")
            return

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


# ─── Best-photo picker + hotel stay card ─────────────────────────────────────
_PHOTO_MIN_SCORE = 0.45      # below this a photo is left out ("best photos only")
_PHOTO_MAX_TRIES = 6         # candidates examined per hotel


def _photo_quality(reader):
    """0..1 quality score for a hotel photo, or None to reject it outright.

    Rewards large, sharp, well-exposed landscape pictures and marks down the
    things that make a stay look cheap: tiny or blurry files, very dark night
    shots, blown-out frames and neon / over-saturated colour."""
    try:
        from PIL import ImageFilter, ImageStat
        im = getattr(reader, "_image", None)
        if im is None:
            return 0.6
        iw, ih = im.size
        if min(iw, ih) < 350:
            return None
        t = im.convert("RGB")
        t.thumbnail((320, 320))
        hsv = list(t.convert("HSV").getdata())
        neon = sum(1 for _h, sat, val in hsv if sat > 205 and val > 205) / max(len(hsv), 1)
        if neon > 0.35:
            return None
        grey = t.convert("L")
        mean, spread = ImageStat.Stat(grey).mean[0], ImageStat.Stat(grey).stddev[0]
        edges = ImageStat.Stat(grey.filter(ImageFilter.FIND_EDGES)).mean[0]
        score = 1.0
        score *= max(0.0, 1.0 - 2.5 * neon)              # neon / garish colour
        if min(iw, ih) < 500:  score *= 0.6              # small file
        if ih > iw * 1.05:     score *= 0.6              # portrait: crops badly into a landscape tile
        if mean < 55:          score *= 0.5              # dark night shot
        elif mean > 232:       score *= 0.6              # blown out
        if spread < 25:        score *= 0.7              # flat / washed out
        if edges < 4:          score *= 0.7              # blurry
        return score
    except Exception as exc:
        print(f"Photo quality check skipped: {exc}")
        return 0.6


def _pick_best_photos(sources, n=2):
    """Up to `n` ImageReaders: the best-scoring photos of a hotel, best first.

    Photos that fail to load or score too low are dropped, so a hotel with only
    poor pictures shows none rather than something that looks cheap."""
    scored = []
    for order, src in enumerate(list(sources or [])[:_PHOTO_MAX_TRIES]):
        r = fetch_image_reader(src)
        if r is None:
            continue
        q = _photo_quality(r)
        if q is not None and q >= _PHOTO_MIN_SCORE:
            scored.append((-q, order, r))
    scored.sort(key=lambda x: (round(x[0], 2), x[1]))      # near-ties keep the admin's order
    return [r for _q, _o, r in scored[:n]]


_MEAL_SHORT = {"EP": ("EP", "Room only"), "CP": ("CP", "Breakfast"),
               "MAP": ("MAP", "Breakfast + dinner"), "AP": ("AP", "All meals")}


class HotelStayCard(Flowable):
    """One stay as a hotel 'page': big hero photo with a bookmark ribbon for the nights, a second photo
    (or a check-in / check-out strip), and four icon cells: stay, room type, rooms, meal plan.

    Same book look as the day cards (navy cover, cream page, crimson ribbon). Same constructor as before."""
    PAD    = 1.5 * mm
    SPLIT  = 0.53          # share of the width taken by the hero photo

    def __init__(self, width, stay, readers):
        super().__init__()
        self.width, self.stay = width, stay
        self.readers = list(readers or [])[:2]
        self.has_p2 = len(self.readers) >= 2
        self.height = (64 if self.has_p2 else 56) * mm

    def wrap(self, aw, ah):
        return self.width, self.height

    # ── small drawing helpers ───────────────────────────────────────────────
    @staticmethod
    def _cover_image(c, reader, x, y, w, h, focus=0.42):
        iw, ih = reader.getSize()
        sc = max(w / iw, h / ih)
        dw, dh = iw * sc, ih * sc
        c.drawImage(reader, x - (dw - w) / 2, y - (dh - h) * (1 - focus), width=dw, height=dh, mask="auto")

    @staticmethod
    def _moon(c, cx, cy, col, bg):
        c.setFillColor(col); c.circle(cx, cy, 1.9 * mm, fill=1, stroke=0)
        c.setFillColor(bg);  c.circle(cx + 1.0 * mm, cy + 0.7 * mm, 1.65 * mm, fill=1, stroke=0)

    @staticmethod
    def _key(c, cx, cy, col):
        c.setStrokeColor(col); c.setFillColor(col); c.setLineWidth(0.8); c.setLineCap(1)
        c.circle(cx - 1.2 * mm, cy + 0.9 * mm, 1.2 * mm, fill=0, stroke=1)
        c.line(cx - 0.4 * mm, cy + 0.1 * mm, cx + 2.1 * mm, cy - 2.2 * mm)
        c.line(cx + 1.0 * mm, cy - 1.1 * mm, cx + 1.9 * mm, cy - 0.2 * mm)
        c.line(cx + 1.6 * mm, cy - 1.8 * mm, cx + 2.5 * mm, cy - 0.9 * mm)

    def _medal(self, c, kind, cx, cy, ring, tint):
        r = 3.5 * mm
        c.setFillColor(WHITE); c.setStrokeColor(ring); c.setLineWidth(1.3)
        c.circle(cx, cy, r, fill=1, stroke=1)
        c.setFillColor(tint); c.circle(cx, cy, r - 0.8 * mm, fill=1, stroke=0)
        if kind == "moon":
            self._moon(c, cx - 0.2 * mm, cy, ring, tint)
        elif kind == "key":
            self._key(c, cx, cy, ring)
        else:
            DayBookSpread._icon(None, c, kind, cx, cy, ring)

    def _cell(self, c, x, y, w, kind, ring, tint, label, value, sub=""):
        self._medal(c, kind, x + 3.5 * mm, y + 5.0 * mm, ring, tint)
        tx, tw = x + 8.3 * mm, w - 8.8 * mm
        c.setFillColor(GRAY_400); c.setFont("Lato-Bold", 5.6)
        c.drawString(tx, y + 8.6 * mm, label)
        size, txt = 8.6, _raw(value)
        while pdfmetrics.stringWidth(txt, "Lato-Bold", size) > tw and size > 6.4:
            size -= 0.3
        while pdfmetrics.stringWidth(txt, "Lato-Bold", size) > tw and len(txt) > 6:
            txt = txt[:-2].rstrip() + "…"
        c.setFillColor(NAVY); c.setFont("Lato-Bold", size)
        c.drawString(tx, y + 5.0 * mm, txt)
        if sub:
            s = _raw(sub)
            while pdfmetrics.stringWidth(s, "Lato", 6.6) > tw and len(s) > 6:
                s = s[:-2].rstrip() + "…"
            c.setFillColor(GRAY_600); c.setFont("Lato", 6.6)
            c.drawString(tx, y + 1.9 * mm, s)

    # ── draw ────────────────────────────────────────────────────────────────
    def draw(self):
        c, W, H, st = self.canv, self.width, self.height, self.stay
        pad = self.PAD
        px0, py0, pw, ph = pad, pad, W - 2 * pad, H - 2 * pad
        split = px0 + pw * self.SPLIT

        # cover + page
        c.setFillColor(_BOOK_COVER); c.roundRect(0, 0, W, H, 2.6 * mm, fill=1, stroke=0)
        c.setFillColor(_BOOK_PAGE);  c.roundRect(px0, py0, pw, ph, 1.3 * mm, fill=1, stroke=0)

        # ── hero (left) ─────────────────────────────────────────────────────
        hw = split - px0
        c.saveState()
        cp = c.beginPath(); cp.roundRect(px0, py0, pw, ph, 1.3 * mm); c.clipPath(cp, stroke=0, fill=0)
        hp = c.beginPath(); hp.rect(px0, py0, hw, ph); c.clipPath(hp, stroke=0, fill=0)
        c.translate(px0, py0)
        if self.readers:
            try:
                self._cover_image(c, self.readers[0], 0, 0, hw, ph)
            except Exception:
                DayBookSpread._landscape(None, c, hw, ph)
        else:
            DayBookSpread._landscape(None, c, hw, ph)
        for i in range(22):                                  # soft dark fade for the name
            t = i / 21.0
            c.setFillColor(colors.Color(0.03, 0.07, 0.14, alpha=0.82 * (1 - t) ** 1.7))
            c.rect(0, i * ph * 0.62 / 22, hw, ph * 0.62 / 22 + 0.2, fill=1, stroke=0)
        for i in range(10):                                  # and a light one up top
            c.setFillColor(colors.Color(0.03, 0.07, 0.14, alpha=0.30 * (1 - i / 9.0) ** 1.5))
            c.rect(0, ph - (i + 1) * ph * 0.22 / 10, hw, ph * 0.22 / 10 + 0.2, fill=1, stroke=0)
        # hotel name, bottom left
        name = _raw(st["name"])
        size = 13.2
        lines = simpleSplit(name, "Lato-Bold", size, hw - 8 * mm)
        while len(lines) > 2 and size > 9:
            size -= 0.6; lines = simpleSplit(name, "Lato-Bold", size, hw - 8 * mm)
        lines = lines[:2]
        y = 3.6 * mm + (len(lines) - 1) * (size * 0.43 * mm)
        if not self.readers and st.get("known"):
            c.setFillColor(colors.Color(1, 1, 1, alpha=0.9)); c.setFont("Lato-Italic", 6.8)
            c.drawString(4 * mm, 3.4 * mm, "Photos shared on request"); y += 4.4 * mm
        c.setFillColor(WHITE); c.setFont("Lato-Bold", size)
        for ln in reversed(lines):
            c.drawString(4 * mm, y, ln); y += size * 0.43 * mm * 1.02
        # place pill (top right of hero)
        place = _raw(st["place"]).upper()
        tw = pdfmetrics.stringWidth(place, "Lato-Bold", 7.2)
        bx = hw - tw - 11.5 * mm
        c.setFillColor(colors.Color(1, 1, 1, alpha=0.94))
        c.roundRect(bx, ph - 8.6 * mm, tw + 8 * mm, 5.6 * mm, 2.8 * mm, fill=1, stroke=0)
        c.setFillColor(SKY); c.circle(bx + 3.1 * mm, ph - 5.8 * mm, 0.95 * mm, fill=1, stroke=0)
        c.setFillColor(NAVY); c.setFont("Lato-Bold", 7.2); c.drawString(bx + 5.3 * mm, ph - 6.7 * mm, place)
        c.restoreState()

        # bookmark ribbon (nights), hanging from the top edge over the hero
        n0, n1 = st["first"], st["last"]
        top_txt = "NIGHT" if n0 == n1 else "NIGHTS"
        num_txt = f"{n0}" if n0 == n1 else f"{n0}–{n1}"
        rw, rh, rx = 12.5 * mm, 15.5 * mm, px0 + 4.5 * mm
        c.setFillColor(colors.Color(0, 0, 0, alpha=0.18))
        c.rect(rx + 0.6 * mm, H - rh - 0.2 * mm, rw, rh, fill=1, stroke=0)
        c.setFillColor(_BOOK_RIBBON)
        p = c.beginPath()
        p.moveTo(rx, H); p.lineTo(rx, H - rh); p.lineTo(rx + rw / 2, H - rh + 3 * mm)
        p.lineTo(rx + rw, H - rh); p.lineTo(rx + rw, H); p.close()
        c.drawPath(p, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#fecdd3")); c.setFont("Lato-Bold", 5.3)
        c.drawCentredString(rx + rw / 2, H - 6.2 * mm, top_txt)
        c.setFillColor(WHITE)
        nsz = 11 if len(num_txt) <= 2 else 8.8
        c.setFont("Lato-Bold", nsz); c.drawCentredString(rx + rw / 2, H - 6.2 * mm - nsz * 0.42 * mm - 1.2 * mm, num_txt)

        # ── fold between hero and info page ─────────────────────────────────
        for i in range(10):
            c.setFillColor(colors.Color(0.05, 0.08, 0.15, alpha=0.13 * (1 - i / 9.0) ** 2))
            c.rect(split + i * 0.38 * mm, py0, 0.42 * mm, ph, fill=1, stroke=0)
        c.setFillColor(WHITE)                                # back to opaque (the last stripe has alpha 0)

        # ── info page (right) ───────────────────────────────────────────────
        ix0 = split + 4.5 * mm
        iw = (px0 + pw) - ix0 - 4 * mm
        top = py0 + ph - 4 * mm
        top_h = 28 * mm if self.has_p2 else 20 * mm
        ty0 = top - top_h
        if self.has_p2:
            c.saveState()
            cp2 = c.beginPath(); cp2.roundRect(ix0, ty0, iw, top_h, 1.8 * mm); c.clipPath(cp2, stroke=0, fill=0)
            try:
                self._cover_image(c, self.readers[1], ix0, ty0, iw, top_h)
            except Exception:
                c.setFillColor(GRAY_100); c.rect(ix0, ty0, iw, top_h, fill=1, stroke=0)
            c.restoreState()
            c.setStrokeColor(GRAY_200); c.setLineWidth(0.6); c.roundRect(ix0, ty0, iw, top_h, 1.8 * mm, fill=0, stroke=1)
        else:                                               # check-in -> check-out strip
            c.setFillColor(_BOOK_BAND); c.roundRect(ix0, ty0, iw, top_h, 2 * mm, fill=1, stroke=0)
            stay_full = _raw(st.get("stay_txt", ""))
            parts = [s.strip() for s in stay_full.split("·")]
            nights_txt = parts[0] if parts else ""
            d_in = d_out = ""
            if len(parts) > 1 and "–" in parts[1]:
                d_in, d_out = [s.strip() for s in parts[1].split("–", 1)]
            my = ty0 + top_h / 2
            c.setFillColor(GRAY_600); c.setFont("Lato-Bold", 5.8)
            if d_in:
                c.drawString(ix0 + 4 * mm, my + 4.6 * mm, "CHECK-IN")
                c.drawRightString(ix0 + iw - 4 * mm, my + 4.6 * mm, "CHECK-OUT")
                c.setFillColor(NAVY); c.setFont("Lato-Bold", 11)
                c.drawString(ix0 + 4 * mm, my - 1.2 * mm, d_in)
                c.drawRightString(ix0 + iw - 4 * mm, my - 1.2 * mm, d_out)
                lx1 = ix0 + 4 * mm + pdfmetrics.stringWidth(d_in, "Lato-Bold", 11) + 3 * mm
                lx2 = ix0 + iw - 4 * mm - pdfmetrics.stringWidth(d_out, "Lato-Bold", 11) - 3 * mm
            else:
                lx1, lx2 = ix0 + 6 * mm, ix0 + iw - 6 * mm
            if lx2 - lx1 > 14 * mm:
                mx = (lx1 + lx2) / 2
                c.setStrokeColor(SKY); c.setLineWidth(0.9); c.setDash(1.5, 1.4)
                c.line(lx1, my + 0.2 * mm, mx - 3.8 * mm, my + 0.2 * mm)
                c.line(mx + 3.8 * mm, my + 0.2 * mm, lx2, my + 0.2 * mm); c.setDash()
                self._medal(c, "moon", mx, my + 0.2 * mm, SKY, SKY_LIGHT)
            c.setFillColor(TEAL); c.setFont("Lato-Bold", 7.4)
            c.drawCentredString(ix0 + iw / 2, ty0 + 2.6 * mm, nights_txt)

        # icon cells, 2 x 2
        cw, ch, gx = iw / 2, 11.5 * mm, 0
        grid_top = ty0 - 3 * mm
        stay_full = _raw(st.get("stay_txt", ""))
        parts = [s.strip() for s in stay_full.split("·")]
        meal = [s.strip() for s in _raw(st.get("meal_txt", "")).split("·", 1)]
        cells = [
            ("moon", SKY,       SKY_LIGHT,    "STAY",      parts[0] if parts else "", (parts[1] if (len(parts) > 1 and self.has_p2) else "")),
            ("bed",  GOLD_MID,  GOLD_LITE,    "ROOM TYPE", st["room_type"], ""),
            ("key",  EMERALD,   EMERALD_LITE, "ROOMS",     st["rooms_txt"], ""),
            ("fork", colors.HexColor("#e11d48"), colors.HexColor("#ffe4e6"), "MEAL PLAN", meal[0], meal[1] if len(meal) > 1 else ""),
        ]
        for i, (kind, ring, tint, lab, val, sub) in enumerate(cells):
            col, row = i % 2, i // 2
            cx_ = ix0 + col * cw
            cy_ = grid_top - (row + 1) * ch - row * 0.5 * mm
            self._cell(c, cx_, cy_, cw - 1.5 * mm, kind, ring, tint, lab, val, sub)
        c.setStrokeColor(GRAY_200); c.setLineWidth(0.4)
        gy1, gy0 = grid_top - 0.6 * mm, grid_top - 2 * ch - 0.9 * mm
        c.line(ix0 + cw - 1.2 * mm, gy0 + 1 * mm, ix0 + cw - 1.2 * mm, gy1 - 0.5 * mm)
        c.line(ix0, grid_top - ch - 0.2 * mm, ix0 + iw, grid_top - ch - 0.2 * mm)


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
            raw = None
            if row is not None:
                raw = bytes(row.data) if row.data else None
                if raw is None:   # photo lives on Cloudinary
                    from backend.services import cloud_media
                    raw = cloud_media.fetch_bytes("site_photo", f"dest-{key}")
            if raw:
                try:
                    found[key] = _faded_reader(raw)
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


class DayPhotoStrip(Flowable):
    """Slim destination photo that sits directly under the day banner (text never goes on the photo)."""
    def __init__(self, width, reader, label="", height=24 * mm):
        super().__init__()
        self.width, self.height, self.reader, self.label = width, height, reader, label

    def wrap(self, aw, ah):
        return self.width, self.height

    def draw(self):
        c, w, h = self.canv, self.width, self.height
        iw, ih = self.reader.getSize()
        sc = max(w / iw, h / ih)
        dw, dh = iw * sc, ih * sc
        c.saveState()
        p = c.beginPath(); p.rect(0, 0, w, h); c.clipPath(p, stroke=0, fill=0)
        c.drawImage(self.reader, -(dw - w) / 2, -(dh - h) * 0.5, width=dw, height=dh)
        # soft dark fade along the bottom so the place label is always readable
        steps = 14
        for i in range(steps):
            c.setFillColor(colors.Color(0.03, 0.09, 0.15, alpha=0.55 * (1 - i / steps) ** 1.6))
            c.rect(0, i * (h * 0.7 / steps), w, h * 0.7 / steps + 0.2, fill=1, stroke=0)
        c.restoreState()
        if self.label:
            txt = clean(self.label).upper()
            c.setFont("Lato-Bold", 8)
            tw = c.stringWidth(txt, "Lato-Bold", 8)
            c.setFillColor(colors.Color(1, 1, 1, alpha=0.92))
            c.roundRect(4 * mm, 3 * mm, tw + 9 * mm, 6 * mm, 3 * mm, fill=1, stroke=0)
            c.setFillColor(SKY)
            c.circle(7 * mm, 6 * mm, 1 * mm, fill=1, stroke=0)
            c.setFillColor(NAVY)
            c.drawString(9.2 * mm, 4.9 * mm, txt)
        c.setStrokeColor(GRAY_200); c.setLineWidth(0.5)
        c.line(0, 0, 0, h); c.line(w, 0, w, h)


class StepDot(Flowable):
    """Numbered circle marking one step of the day."""
    def __init__(self, n, size=5.4 * mm):
        super().__init__()
        self.n, self.size = n, size
        self.hAlign = "CENTER"

    def wrap(self, aw, ah):
        return self.size, self.size

    def draw(self):
        c, s = self.canv, self.size
        c.setFillColor(SKY)
        c.circle(s / 2, s / 2, s / 2, fill=1, stroke=0)
        c.setFillColor(WHITE)
        c.setFont("Lato-Bold", 6.8)
        c.drawCentredString(s / 2, s / 2 - 2.3, str(self.n))


# ─── Day card: open-book spread ──────────────────────────────────────────────
# One day = one open book. Left page: day header, stay, route + distance chips and a
# destination photo. Right page: the day's steps on a vertical timeline. A shaded centre
# fold and a ribbon marker finish the look. Height grows with the number of steps.
_BOOK_COVER  = colors.HexColor("#14213d")
_BOOK_PAGE   = colors.HexColor("#fffdf8")
_BOOK_RIBBON = colors.HexColor("#b4173f")
_BOOK_BAND   = colors.HexColor("#dff1fd")

# kind -> (ring/kicker colour, tint, title colour)
_STEP_STYLE = {
    "Transfer":    (SKY,                           SKY_LIGHT,                     TEAL),
    "Sightseeing": (EMERALD,                       EMERALD_LITE,                  TEAL),
    "Stay":        (GOLD_MID,                      GOLD_LITE,                     GOLD),
    "Meal":        (colors.HexColor("#e11d48"),    colors.HexColor("#ffe4e6"),    colors.HexColor("#be123c")),
    "Activity":    (colors.HexColor("#7c3aed"),    colors.HexColor("#ede9fe"),    colors.HexColor("#6d28d9")),
    "Plan":        (GRAY_600,                      GRAY_100,                      NAVY),
}
_STEP_ICON = {"Transfer": "car", "Sightseeing": "peak", "Stay": "bed",
              "Meal": "fork", "Activity": "star", "Plan": "star"}
_STEP_SUB  = {"Transfer": "Transfer", "Sightseeing": "Explore", "Stay": "Settle in",
              "Meal": "Dine", "Activity": "Enjoy", "Plan": ""}


def _step_kind(head, desc):
    """Tag a step (Transfer / Sightseeing / Stay / Meal / Activity) from its words; the heading wins."""
    def has(t, words):
        return any(w in t for w in words)
    h, d = str(head or "").lower(), str(desc or "").lower()
    tests = (
        ("Stay",     ("check-in", "check in", "checkin", "overnight", "check-out", "check out", "houseboat stay", "settle in")),
        ("Transfer", ("transfer", "pickup", "pick-up", "pick up", "drop", "drive", "airport", "departure", "arrival", "journey", "proceed")),
        ("Meal",     ("breakfast", "lunch", "dinner", "meal", "kahwa", "wazwan")),
        ("Activity", ("shikara", "gondola", "ride", "trek", "pony", "sledge", "skiing", "rafting", "cable car", "boat")),
        ("Sightseeing", ("sightseeing", "visit", "explore", "garden", "lake", "temple", "valley", "meadow", "tour", "market", "shrine", "view")),
    )
    for t in (h, d):
        if not t:
            continue
        for kind, words in tests:
            if kind == "Stay" and t is d and not has(t, ("check-in", "check in", "checkin", "overnight stay")):
                continue
            if has(t, words):
                return kind
    return "Sightseeing"


class DayBookSpread(Flowable):
    PAD     = 1.5 * mm     # cover border around the pages
    RIB     = 3.0 * mm     # ribbon hanging below the book
    FOOT_H  = 6.6 * mm
    ICON_R  = 3.7 * mm
    LABEL_W = 15.5 * mm
    MIN_H   = 74 * mm

    def __init__(self, width, day_num, title, date_label="", stay="", travel=None, route="",
                 photo=None, photo_label="", steps=None, client_name=""):
        super().__init__()
        self.width, self.day_num, self.title = width, day_num, title
        self.date_label, self.stay_src = date_label, stay
        self.travel = travel if (travel and travel.get("text")) else None
        self.route, self.photo, self.photo_label = route, photo, photo_label
        self.client_name = client_name
        self.steps = list(steps or [])
        if not self.steps:
            self.steps = [{"time": "", "head": "Details to be confirmed",
                           "desc": "Your travel coordinator will confirm the plan for this day.", "kind": "Plan"}]
        self._prepped = False
        self.height = self.MIN_H + self.RIB

    # ── content prep ────────────────────────────────────────────────────────
    def _prep(self):
        if self._prepped:
            return
        self._prepped = True
        stay = self.stay_src() if callable(self.stay_src) else self.stay_src
        self.stay_txt = f"Stay: {_raw(stay)}" if stay else ""
        n = len(self.steps)
        used_travel = False
        self.rows = []
        for i, s in enumerate(self.steps):
            head, desc = _raw(s.get("head", "")), _raw(s.get("desc", ""))
            kind = s.get("kind") or _step_kind(head, desc)
            t = (head + " " + desc).lower()
            time_txt = _raw(s.get("time", ""))
            kicker, sub = time_txt, ""
            if not time_txt:
                if kind == "Transfer" and any(w in t for w in ("pickup", "pick-up", "pick up", "meets you", "welcome")) and i == 0:
                    kicker, sub = "On arrival", "Meet and greet"
                elif kind == "Transfer" and self.travel and self.travel.get("km") and not used_travel:
                    used_travel = True
                    kicker = f"{self.travel['km']} km"
                    sub = _raw(_fmt_drive_time(self.travel["hours"])).capitalize() if self.travel.get("hours") else ""
                elif kind == "Transfer" and any(w in t for w in ("drop", "departure", "depart")):
                    kicker, sub = "On departure", "Safe journey"
                elif kind == "Stay":
                    kicker, sub = "Evening", "Settle in"
                elif kind == "Meal":
                    kicker = "Morning" if "breakfast" in t else "Midday" if "lunch" in t else "Evening"
                    sub = "Dine"
                else:
                    if n == 1:
                        kicker = "All day"
                    else:
                        f = i / (n - 1)
                        kicker = "Morning" if f < 0.34 else "Afternoon" if f < 0.67 else "Evening"
                    sub = _STEP_SUB.get(kind, "")
            self.rows.append({"kind": kind, "head": head, "desc": desc, "kicker": kicker, "sub": sub})

    # ── layout ──────────────────────────────────────────────────────────────
    def _page_w(self):
        return (self.width - 2 * self.PAD) / 2

    def _layout(self, f):
        """Right-page row heights at font scale f; returns the body height the right page needs."""
        self.f = f
        pw = self._page_w()
        self.tx_off = 5 * mm + self.LABEL_W + 2.6 * mm + 2 * self.ICON_R + 2.6 * mm      # text column x inside the page
        self.tw = pw - self.tx_off - 4.5 * mm
        self.hs, self.ds = 8.9 * f, 7.0 * f
        self.hl, self.dl = 4.2 * mm * f, 3.25 * mm * f
        self.pill_h = 3.9 * mm * f
        gap = 3.5 * mm * f
        self.row_h = []
        for r in self.rows:
            r["h_lines"] = simpleSplit(r["head"], "Lato-Bold", self.hs, self.tw) or [""]
            r["d_lines"] = simpleSplit(r["desc"], "Lato", self.ds, self.tw) if r["desc"] else []
            r["pill_w"] = pdfmetrics.stringWidth(r["kind"], "Lato-Bold", 6.3 * f) + 4.6 * mm * f
            last_w = pdfmetrics.stringWidth(r["h_lines"][-1], "Lato-Bold", self.hs)
            r["pill_inline"] = last_w + 2 * mm + r["pill_w"] <= self.tw
            head_h = len(r["h_lines"]) * self.hl + (0 if r["pill_inline"] else self.pill_h + 0.6 * mm)
            body_h = head_h + 0.8 * mm + len(r["d_lines"]) * self.dl
            r["h"] = max(2 * self.ICON_R + 0.6 * mm, body_h)
            self.row_h.append(r["h"] + gap)
        self.gap = gap
        return 4.6 * mm + sum(self.row_h) - gap + 3.6 * mm + self.FOOT_H

    def _left_parts(self):
        pw = self._page_w()
        nbox = 13 * mm
        tl = simpleSplit(_raw(self.title), "Lato-Bold", 11.2, pw - nbox - 7 * mm) or [""]
        tl = tl[:2]
        title_h = max(14 * mm, 6.2 * mm + len(tl) * 4.9 * mm + (3.6 * mm if self.date_label else 0))
        hdr_h = title_h + (9.4 * mm if self.stay_txt else 1.8 * mm)
        if self.travel:
            band_h = 22 * mm if self.travel.get("km") else 10 * mm
        elif self.route:
            band_h = 10 * mm
        else:
            band_h = 0
        return tl, title_h, hdr_h, band_h

    def wrap(self, aw, ah):
        self._prep()
        need = 0
        for f in (1.0, 0.94, 0.88, 0.82, 0.76):
            need = self._layout(f)
            _, _, hdr_h, band_h = self._left_parts()
            left_min = hdr_h + band_h + 24 * mm + self.FOOT_H
            self.book_h = max(need, left_min, self.MIN_H)
            if self.book_h + self.RIB <= ah:
                break
        self.height = self.book_h + self.RIB
        return self.width, self.height

    # ── drawing helpers ─────────────────────────────────────────────────────
    def _icon(self, c, kind, cx, cy, col):
        c.saveState()
        c.setStrokeColor(col); c.setFillColor(col); c.setLineWidth(0.75)
        c.setLineJoin(1); c.setLineCap(1)
        m = mm
        if kind == "car":
            c.roundRect(cx - 2.3*m, cy - 1.1*m, 4.6*m, 1.7*m, 0.55*m, fill=0, stroke=1)
            p = c.beginPath()
            p.moveTo(cx - 1.4*m, cy + 0.6*m); p.lineTo(cx - 0.8*m, cy + 1.6*m)
            p.lineTo(cx + 0.9*m, cy + 1.6*m); p.lineTo(cx + 1.5*m, cy + 0.6*m)
            c.drawPath(p, fill=0, stroke=1)
            c.circle(cx - 1.3*m, cy - 1.2*m, 0.55*m, fill=1, stroke=0)
            c.circle(cx + 1.3*m, cy - 1.2*m, 0.55*m, fill=1, stroke=0)
        elif kind == "peak":
            p = c.beginPath()
            p.moveTo(cx - 2.5*m, cy - 1.4*m); p.lineTo(cx - 0.7*m, cy + 1.3*m)
            p.lineTo(cx + 0.3*m, cy - 0.2*m); p.lineTo(cx + 1.2*m, cy + 0.7*m)
            p.lineTo(cx + 2.5*m, cy - 1.4*m); p.close()
            c.drawPath(p, fill=0, stroke=1)
            c.circle(cx + 1.5*m, cy + 1.7*m, 0.45*m, fill=1, stroke=0)
        elif kind == "bed":
            c.line(cx - 2.4*m, cy - 1.3*m, cx - 2.4*m, cy + 1.4*m)
            c.line(cx - 2.4*m, cy - 0.7*m, cx + 2.4*m, cy - 0.7*m)
            c.roundRect(cx - 2.0*m, cy - 0.7*m, 4.4*m, 1.2*m, 0.4*m, fill=0, stroke=1)
            c.roundRect(cx - 1.7*m, cy + 0.5*m, 1.4*m, 0.8*m, 0.3*m, fill=1, stroke=0)
            c.line(cx + 2.4*m, cy - 1.3*m, cx + 2.4*m, cy - 0.7*m)
        elif kind == "fork":
            c.line(cx - 1.1*m, cy - 1.8*m, cx - 1.1*m, cy + 1.8*m)
            c.line(cx - 1.8*m, cy + 0.3*m, cx - 1.8*m, cy + 1.8*m)
            c.line(cx - 0.4*m, cy + 0.3*m, cx - 0.4*m, cy + 1.8*m)
            c.line(cx - 1.8*m, cy + 0.3*m, cx - 0.4*m, cy + 0.3*m)
            c.line(cx + 1.4*m, cy - 1.8*m, cx + 1.4*m, cy + 1.8*m)
            p = c.beginPath(); p.moveTo(cx + 1.4*m, cy + 1.8*m)
            p.curveTo(cx + 2.4*m, cy + 1.3*m, cx + 2.4*m, cy - 0.2*m, cx + 1.4*m, cy - 0.4*m)
            c.drawPath(p, fill=0, stroke=1)
        else:
            _star(c, cx, cy, 2.2*m, col)
        c.restoreState()

    def _fold_shadow(self, c, cx, hb):
        y0, y1 = self.PAD, hb - self.PAD
        for i in range(16):                                   # left page darkens toward the fold
            a = 0.22 * (i / 15.0) ** 2.2
            c.setFillColor(colors.Color(0.05, 0.08, 0.15, alpha=a))
            c.rect(cx - 7.5 * mm + i * 0.47 * mm, y0, 0.5 * mm, y1 - y0, fill=1, stroke=0)
        for i in range(12):                                   # right page, lighter
            a = 0.15 * (1 - i / 11.0) ** 2.0
            c.setFillColor(colors.Color(0.05, 0.08, 0.15, alpha=a))
            c.rect(cx + i * 0.4 * mm, y0, 0.45 * mm, y1 - y0, fill=1, stroke=0)
        c.setStrokeColor(colors.Color(0.05, 0.08, 0.15, alpha=0.35)); c.setLineWidth(0.4)
        c.line(cx, y0, cx, y1)

    def _landscape(self, c, w, h):
        """No destination photo: a calm sky + mountains + meadow so the page never looks empty."""
        steps = 24
        for i in range(steps):
            t = i / (steps - 1.0)
            c.setFillColor(colors.Color(0.55 + 0.37 * t, 0.74 + 0.20 * t, 0.90 + 0.06 * t))
            c.rect(0, h - (i + 1) * h / steps, w, h / steps + 0.3, fill=1, stroke=0)
        def ridge(col, pts):
            p = c.beginPath(); p.moveTo(0, 0)
            for fx, fy in pts:
                p.lineTo(fx * w, fy * h)
            p.lineTo(w, 0); p.close()
            c.setFillColor(col); c.drawPath(p, fill=1, stroke=0)
        ridge(colors.HexColor("#8fb0cc"), [(0, .55), (.22, .78), (.38, .6), (.58, .88), (.8, .62), (1, .74)])
        ridge(colors.HexColor("#5f8f86"), [(0, .38), (.2, .55), (.45, .36), (.7, .58), (1, .4)])
        ridge(colors.HexColor("#2f6b3f"), [(0, .22), (.3, .3), (.6, .2), (1, .28)])

    # ── draw ────────────────────────────────────────────────────────────────
    def draw(self):
        c = self.canv
        W, hb, pad = self.width, self.book_h, self.PAD
        pw, cx = self._page_w(), self.width / 2
        c.saveState()
        c.translate(0, self.RIB)

        # ribbon (behind the cover edge, hanging below)
        rw, rx = 4.6 * mm, cx - 2.3 * mm
        c.setFillColor(_BOOK_RIBBON)
        p = c.beginPath()
        p.moveTo(rx, 1.2 * mm); p.lineTo(rx, -self.RIB + 0.2 * mm)
        p.lineTo(rx + rw / 2, -self.RIB + 1.7 * mm); p.lineTo(rx + rw, -self.RIB + 0.2 * mm)
        p.lineTo(rx + rw, 1.2 * mm); p.close()
        c.drawPath(p, fill=1, stroke=0)

        # cover + page stack
        c.setFillColor(_BOOK_COVER)
        c.roundRect(0, 0, W, hb, 2.6 * mm, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#e7e2d6"))
        c.roundRect(pad, pad * 0.5, W - 2 * pad, hb - pad * 1.5, 1.4 * mm, fill=1, stroke=0)

        py0, py1 = pad + 0.7 * mm, hb - pad
        ph = py1 - py0

        # page shapes (rounded outer corners only)
        c.setFillColor(_BOOK_PAGE)
        c.roundRect(pad, py0, pw, ph, 1.2 * mm, fill=1, stroke=0)
        c.roundRect(cx, py0, pw, ph, 1.2 * mm, fill=1, stroke=0)
        c.rect(cx - 2 * mm, py0, 4 * mm, ph, fill=1, stroke=0)

        # ── LEFT PAGE ───────────────────────────────────────────────────────
        tl, title_h, hdr_h, band_h = self._left_parts()
        c.saveState()
        cp = c.beginPath(); cp.roundRect(pad, py0, pw, ph, 1.2 * mm)
        cpr = c.beginPath(); cpr.rect(cx - 2 * mm, py0, 2 * mm, ph)
        c.clipPath(cp, stroke=0, fill=0)
        lx, top = pad, py1

        # header
        c.setFillColor(NAVY)
        c.rect(lx, top - hdr_h, pw, hdr_h, fill=1, stroke=0)
        nbox = 13 * mm
        c.setFillColor(colors.HexColor("#0f1b33"))
        c.rect(lx, top - title_h, nbox, title_h, fill=1, stroke=0)
        c.setFillColor(WHITE); c.setFont("Lato-Bold", 15)
        c.drawCentredString(lx + nbox / 2, top - title_h / 2 - 2.0 * mm, str(self.day_num))
        ty = top - 6.4 * mm
        c.setFont("Lato-Bold", 11.2)
        for ln in tl:
            c.drawString(lx + nbox + 4 * mm, ty, ln)
            ty -= 4.9 * mm
        if self.date_label:
            c.setFillColor(colors.HexColor("#7dd3fc")); c.setFont("Lato", 7.2)
            c.drawString(lx + nbox + 4 * mm, ty + 0.3 * mm, _raw(self.date_label).upper())
        if self.stay_txt:
            lab = self.stay_txt
            maxw = pw - 7 * mm - 6.5 * mm
            while pdfmetrics.stringWidth(lab, "Lato-Bold", 7.4) > maxw and len(lab) > 12:
                lab = lab[:-2].rstrip() + "…"
            bw = pdfmetrics.stringWidth(lab, "Lato-Bold", 7.4) + 6.5 * mm
            by = top - title_h - 7.4 * mm
            c.setFillColor(TEAL); c.roundRect(lx + 3 * mm, by, bw, 6.2 * mm, 2.2 * mm, fill=1, stroke=0)
            c.setFillColor(colors.HexColor("#99f6e4")); c.circle(lx + 5.9 * mm, by + 3.1 * mm, 1.0 * mm, fill=1, stroke=0)
            c.setFillColor(WHITE); c.setFont("Lato-Bold", 7.4)
            c.drawString(lx + 8.2 * mm, by + 2.0 * mm, lab)

        # route band
        y = top - hdr_h
        if band_h:
            c.setFillColor(_BOOK_BAND)
            c.rect(lx, y - band_h, pw, band_h, fill=1, stroke=0)
            names = self.travel["stops"] if self.travel else [self.route]
            a, b = _raw(names[0]), _raw(names[-1])
            if len(names) == 1:
                a, b = _raw(names[0]), ""
            ry = y - 5.6 * mm
            nw = pw * 0.34
            def fit(s, w=nw, size=8.2):
                while pdfmetrics.stringWidth(s, "Lato-Bold", size) > w and len(s) > 5:
                    s = s[:-2].rstrip() + "…"
                return s
            c.setFont("Lato-Bold", 8.2); c.setFillColor(NAVY)
            if b:
                a, b = fit(a), fit(b)
                c.setStrokeColor(SKY); c.setLineWidth(1.0); c.setFillColor(WHITE)
                c.circle(lx + 4.2 * mm, ry + 1.0 * mm, 1.35 * mm, fill=1, stroke=1)
                c.setFillColor(NAVY); c.drawString(lx + 7.2 * mm, ry - 0.2 * mm, a)
                ex = lx + pw - 4.2 * mm
                c.setFillColor(TEAL); c.circle(ex, ry + 1.0 * mm, 1.35 * mm, fill=1, stroke=0)
                c.setFillColor(NAVY); c.drawRightString(ex - 3 * mm, ry - 0.2 * mm, b)
                # dashed road with a little car in a ring between the two names
                x1 = lx + 7.2 * mm + pdfmetrics.stringWidth(a, "Lato-Bold", 8.2) + 2.5 * mm
                x2 = ex - 3 * mm - pdfmetrics.stringWidth(b, "Lato-Bold", 8.2) - 2.5 * mm
                if x2 - x1 > 12 * mm:
                    mx = (x1 + x2) / 2
                    c.setStrokeColor(SKY); c.setLineWidth(0.9); c.setDash(1.6, 1.4)
                    c.line(x1, ry + 1.0 * mm, mx - 3.4 * mm, ry + 1.0 * mm)
                    c.line(mx + 3.4 * mm, ry + 1.0 * mm, x2, ry + 1.0 * mm); c.setDash()
                    c.setFillColor(WHITE); c.setStrokeColor(SKY); c.setLineWidth(1.0)
                    c.circle(mx, ry + 1.0 * mm, 3.0 * mm, fill=1, stroke=1)
                    self._icon(c, "car", mx, ry + 1.0 * mm, SKY)
            else:
                c.setFillColor(NAVY); c.drawString(lx + 4 * mm, ry - 0.2 * mm, fit(a, pw - 8 * mm))
            if self.travel and self.travel.get("km"):
                chips = [(f"{self.travel['km']} km", "distance")]
                if self.travel.get("hours"):
                    chips.append(("~" + _raw(_fmt_drive_time(self.travel["hours"])).replace("about ", ""), "drive time"))
                cxp = lx + 3.5 * mm
                for val, lab in chips:
                    cw = max(pdfmetrics.stringWidth(val, "Lato-Bold", 9) + 5 * mm, 16 * mm)
                    cy0 = y - band_h + 2.4 * mm
                    c.setFillColor(colors.Color(0, 0.2, 0.35, alpha=0.18))
                    c.roundRect(cxp, cy0 - 0.5 * mm, cw, 9.2 * mm, 1.8 * mm, fill=1, stroke=0)
                    c.setFillColor(WHITE); c.roundRect(cxp, cy0, cw, 9.2 * mm, 1.8 * mm, fill=1, stroke=0)
                    c.setFillColor(TEAL); c.setFont("Lato-Bold", 9)
                    c.drawCentredString(cxp + cw / 2, cy0 + 4.9 * mm, val)
                    c.setFillColor(GRAY_600); c.setFont("Lato", 6.6)
                    c.drawCentredString(cxp + cw / 2, cy0 + 1.7 * mm, lab)
                    cxp += cw + 2.6 * mm
            y -= band_h

        # photo
        foot = self.FOOT_H
        ph_y0, ph_h = py0 + foot, (y - (py0 + foot))
        c.saveState()
        pp = c.beginPath(); pp.rect(lx, ph_y0, pw, ph_h); c.clipPath(pp, stroke=0, fill=0)
        c.translate(lx, ph_y0)
        if self.photo is not None:
            iw, ih = self.photo.getSize()
            sc = max(pw / iw, ph_h / ih)
            dw, dh = iw * sc, ih * sc
            c.drawImage(self.photo, -(dw - pw) / 2, -(dh - ph_h) * 0.5, width=dw, height=dh)
        else:
            self._landscape(c, pw, ph_h)
        c.restoreState()
        if self.photo_label:
            txt = _raw(self.photo_label).upper()
            tw = pdfmetrics.stringWidth(txt, "Lato-Bold", 7.6)
            c.setFillColor(colors.Color(1, 1, 1, alpha=0.94))
            c.roundRect(lx + 3.5 * mm, ph_y0 + 3 * mm, tw + 9 * mm, 6 * mm, 3 * mm, fill=1, stroke=0)
            c.setFillColor(SKY); c.circle(lx + 6.6 * mm, ph_y0 + 6 * mm, 1.0 * mm, fill=1, stroke=0)
            c.setFillColor(NAVY); c.setFont("Lato-Bold", 7.6)
            c.drawString(lx + 8.8 * mm, ph_y0 + 4.9 * mm, txt)

        # footer
        c.setFillColor(_BOOK_PAGE); c.rect(lx, py0, pw, foot, fill=1, stroke=0)
        c.setStrokeColor(GRAY_200); c.setLineWidth(0.4); c.line(lx + 3 * mm, py0 + foot, lx + pw - 3 * mm, py0 + foot)
        c.setFillColor(GRAY_400); c.setFont("Lato", 6.3)
        c.drawString(lx + 4 * mm, py0 + 2.4 * mm, f"Kashmir Tour Itinerary  |  Prepared for {_raw(self.client_name)}")
        c.drawRightString(lx + pw - 4 * mm, py0 + 2.4 * mm, f"Day {self.day_num}")
        c.restoreState()

        # ── RIGHT PAGE ──────────────────────────────────────────────────────
        rx0 = cx
        f = self.f
        body_top = py1 - 4.6 * mm
        avail = (body_top - (py0 + foot + 3.6 * mm))
        used = sum(self.row_h) - self.gap
        extra = max(0, min((avail - used) / max(len(self.rows), 1), 4.5 * mm))
        icx = rx0 + 5 * mm + self.LABEL_W + 2.6 * mm + self.ICON_R
        txx = rx0 + self.tx_off
        ys, y = [], body_top
        for r, rh in zip(self.rows, self.row_h):
            ys.append(y)
            y -= rh + extra
        # dashed spine between first and last icon
        if len(self.rows) > 1:
            c.setStrokeColor(TEAL); c.setLineWidth(0.9); c.setDash(1.5, 1.6)
            c.line(icx, ys[0] - self.ICON_R, icx, ys[-1] - self.ICON_R); c.setDash()
        for r, ry in zip(self.rows, ys):
            ring, tint, tcol = _STEP_STYLE[r["kind"]]
            icy = ry - self.ICON_R
            # label column (right-aligned)
            lx_r = rx0 + 5 * mm + self.LABEL_W
            ky = ry - 2.4 * mm
            c.setFillColor(ring if r["kind"] != "Transfer" else TEAL)
            for ln in (simpleSplit(r["kicker"], "Lato-Bold", 7.6 * f, self.LABEL_W) or [""]):
                c.setFont("Lato-Bold", 7.6 * f); c.drawRightString(lx_r, ky, ln); ky -= 3.3 * mm * f
            c.setFillColor(GRAY_600); c.setFont("Lato", 6.6 * f)
            for ln in (simpleSplit(r["sub"], "Lato", 6.6 * f, self.LABEL_W) if r["sub"] else []):
                c.drawRightString(lx_r, ky, ln); ky -= 2.9 * mm * f
            # icon medallion
            c.setFillColor(WHITE); c.setStrokeColor(ring); c.setLineWidth(1.5)
            c.circle(icx, icy, self.ICON_R, fill=1, stroke=1)
            c.setFillColor(tint); c.circle(icx, icy, self.ICON_R - 0.9 * mm, fill=1, stroke=0)
            self._icon(c, _STEP_ICON[r["kind"]], icx, icy, ring)
            # title + tag pill
            ty = ry - 3.0 * mm * f
            c.setFillColor(tcol); c.setFont("Lato-Bold", self.hs)
            for ln in r["h_lines"]:
                c.drawString(txx, ty, ln); ty -= self.hl
            ty += self.hl
            px = txx + pdfmetrics.stringWidth(r["h_lines"][-1], "Lato-Bold", self.hs) + 2 * mm
            py = ty - 0.95 * mm * f
            if not r["pill_inline"]:
                px, py = txx, ty - self.hl - 0.6 * mm * f
                ty -= self.pill_h + 0.6 * mm
            c.setFillColor(tint); c.roundRect(px, py, r["pill_w"], self.pill_h, self.pill_h / 2, fill=1, stroke=0)
            c.setFillColor(ring if r["kind"] != "Transfer" else colors.HexColor("#0369a1"))
            c.setFont("Lato-Bold", 6.3 * f)
            c.drawCentredString(px + r["pill_w"] / 2, py + self.pill_h / 2 - 0.85 * mm * f, r["kind"])
            # description
            dy = ty - self.dl - 0.2 * mm
            c.setFillColor(GRAY_600); c.setFont("Lato", self.ds)
            for ln in r["d_lines"]:
                c.drawString(txx, dy, ln); dy -= self.dl

        # right footer
        c.setStrokeColor(GRAY_200); c.setLineWidth(0.4)
        c.line(rx0 + 3 * mm, py0 + foot, rx0 + pw - 3 * mm, py0 + foot)
        c.setFillColor(GRAY_400); c.setFont("Lato", 6.3)
        c.drawString(rx0 + 5 * mm, py0 + 2.4 * mm, "Kashmir Tour Itinerary")
        c.drawRightString(rx0 + pw - 4 * mm, py0 + 2.4 * mm, f"Page {c.getPageNumber()}")

        self._fold_shadow(c, cx, hb)
        c.restoreState()


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


def _book_fold(c, cx, y0, y1, left=7 * mm, right=4.5 * mm):
    """Soft shaded centre fold of an open book."""
    nl, nr = 16, 12
    for i in range(nl):
        c.setFillColor(colors.Color(0.05, 0.08, 0.15, alpha=0.20 * (i / (nl - 1.0)) ** 2.2))
        c.rect(cx - left + i * left / nl, y0, left / nl + 0.05 * mm, y1 - y0, fill=1, stroke=0)
    for i in range(nr):
        c.setFillColor(colors.Color(0.05, 0.08, 0.15, alpha=0.14 * (1 - i / (nr - 1.0)) ** 2.0))
        c.rect(cx + i * right / nr, y0, right / nr + 0.05 * mm, y1 - y0, fill=1, stroke=0)
    c.setStrokeColor(colors.Color(0.05, 0.08, 0.15, alpha=0.30)); c.setLineWidth(0.4)
    c.line(cx, y0, cx, y1)
    c.setFillColor(WHITE)                                    # back to opaque


def _book_cover(c, x, y, w, h, pad=1.4 * mm, r=2.6 * mm):
    c.setFillColor(_BOOK_COVER); c.roundRect(x, y, w, h, r, fill=1, stroke=0)
    c.setFillColor(_BOOK_PAGE);  c.roundRect(x + pad, y + pad, w - 2 * pad, h - 2 * pad, r * 0.5, fill=1, stroke=0)


def _check_tick(c, cx, cy, s, col):
    c.setStrokeColor(col); c.setLineWidth(0.9); c.setLineCap(1); c.setLineJoin(1)
    p = c.beginPath(); p.moveTo(cx - s * 0.9, cy); p.lineTo(cx - s * 0.2, cy - s * 0.7); p.lineTo(cx + s * 0.95, cy + s * 0.7)
    c.drawPath(p, fill=0, stroke=1)


class StayRouteStrip(Flowable):
    """'Your stays at a glance': a journey page. Start -> each stay (numbered, nights, hotel) -> End,
    joined by a dashed road with a little car between stops."""
    def __init__(self, width, start_point, end_point, segments):
        super().__init__()
        self.width, self.start_point, self.end_point, self.segs = width, start_point, end_point, segments
        self.height = (44 if len(segments) <= 4 else 52) * mm

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
        _book_cover(c, 0, 0, w, h)
        # header: title + nights-in-total chip
        total = sum(sg["nights"] for sg in self.segs)
        hy = h - 7.4 * mm
        c.setFillColor(SKY); c.roundRect(5 * mm, hy - 0.6 * mm, 1.3 * mm, 4.4 * mm, 0.6 * mm, fill=1, stroke=0)
        c.setFillColor(NAVY); c.setFont("Lato-Bold", 8.6)
        c.drawString(8 * mm, hy + 0.7 * mm, "YOUR STAYS AT A GLANCE")
        lab = f"{total} night{'s' if total != 1 else ''} in total"
        cw_ = c.stringWidth(lab, "Lato-Bold", 7) + 9 * mm
        c.setFillColor(TEAL_LITE); c.roundRect(w - 5 * mm - cw_, hy - 1.2 * mm, cw_, 5.6 * mm, 2.8 * mm, fill=1, stroke=0)
        HotelStayCard._moon(c, w - 5 * mm - cw_ + 3.6 * mm, hy + 1.6 * mm, TEAL, TEAL_LITE)
        c.setFillColor(TEAL); c.setFont("Lato-Bold", 7)
        c.drawString(w - 5 * mm - cw_ + 7 * mm, hy + 0.5 * mm, lab)
        c.setStrokeColor(GRAY_200); c.setLineWidth(0.4); c.line(5 * mm, hy - 3.4 * mm, w - 5 * mm, hy - 3.4 * mm)

        nodes = [("START", self.start_point, None, KashmirRouteMap.START_COL)] + \
                [(None, sg["city"], sg, KashmirRouteMap.PIN_COLORS.get(sg["city"].lower(), KashmirRouteMap.PIN_COLORS["srinagar"])[1])
                 for sg in self.segs] + \
                [("END", self.end_point, None, KashmirRouteMap.END_COL)]
        n = len(nodes)
        pad = 19 * mm
        xs = [pad + i * (w - 2 * pad) / max(n - 1, 1) for i in range(n)]
        cell = min(34 * mm, (w - 2 * pad) / max(n - 1, 1) - 2 * mm)
        ly = h - 18.6 * mm
        R = 4.3 * mm

        # road + little cars
        for i in range(n - 1):
            x1, x2 = xs[i] + R + 1 * mm, xs[i + 1] - R - 1 * mm
            mx = (x1 + x2) / 2
            c.setStrokeColor(SKY_MID); c.setLineWidth(1.1); c.setDash(2.2, 2.0)
            c.line(x1, ly, mx - 3.5 * mm, ly); c.line(mx + 3.5 * mm, ly, x2, ly); c.setDash()
            c.setFillColor(WHITE); c.setStrokeColor(SKY_MID); c.setLineWidth(0.9)
            c.circle(mx, ly, 3.0 * mm, fill=1, stroke=1)
            DayBookSpread._icon(None, c, "car", mx, ly, SKY)

        for i, (x, (tag, name, seg, col)) in enumerate(zip(xs, nodes)):
            c.setFillColor(colors.Color(0, 0, 0.1, alpha=0.10)); c.circle(x + 0.3 * mm, ly - 0.5 * mm, R + 0.3 * mm, fill=1, stroke=0)
            c.setFillColor(WHITE); c.setStrokeColor(col); c.setLineWidth(1.6); c.circle(x, ly, R, fill=1, stroke=1)
            c.setFillColor(col); c.circle(x, ly, R - 1.0 * mm, fill=1, stroke=0)
            c.setFillColor(WHITE); c.setStrokeColor(WHITE)
            if tag == "START":
                c.circle(x, ly, 1.25 * mm, fill=1, stroke=0)
            elif tag == "END":                                      # little flag
                c.setLineWidth(0.8); c.line(x - 1.0 * mm, ly - 1.9 * mm, x - 1.0 * mm, ly + 1.9 * mm)
                fp = c.beginPath(); fp.moveTo(x - 1.0 * mm, ly + 1.9 * mm); fp.lineTo(x + 1.9 * mm, ly + 0.9 * mm); fp.lineTo(x - 1.0 * mm, ly - 0.1 * mm); fp.close()
                c.drawPath(fp, fill=1, stroke=0)
            else:
                c.setFont("Lato-Bold", 8.4); c.drawCentredString(x, ly - 1.0 * mm, str(i))
            y = ly - 8.2 * mm
            if seg is None:                                       # start / end
                c.setFillColor(col); c.setFont("Lato-Bold", 6.4)
                tw_ = c.stringWidth(tag, "Lato-Bold", 6.4) + 4 * mm
                c.setFillColor(colors.Color(col.red, col.green, col.blue, alpha=0.13))
                c.roundRect(x - tw_ / 2, y - 1.3 * mm, tw_, 4.1 * mm, 2 * mm, fill=1, stroke=0)
                c.setFillColor(col); c.drawCentredString(x, y, tag)
                y -= 4.4 * mm
                c.setFillColor(NAVY)
                for ln in self._wrap(c, name, "Lato-Bold", 7.4, cell, max_lines=3):
                    c.setFont("Lato-Bold", 7.4); c.drawCentredString(x, y, ln); y -= 3.3 * mm
            else:
                c.setFillColor(NAVY); c.setFont("Lato-Bold", 8.8); c.drawCentredString(x, y, seg["city"])
                y -= 2.6 * mm
                lab = f"{seg['nights']} night{'s' if seg['nights'] != 1 else ''}"
                pw = c.stringWidth(lab, "Lato-Bold", 6.6) + 4.4 * mm
                c.setFillColor(colors.Color(col.red, col.green, col.blue, alpha=0.14))
                c.roundRect(x - pw / 2, y - 4.0 * mm, pw, 4.3 * mm, 2.15 * mm, fill=1, stroke=0)
                c.setFillColor(col); c.setFont("Lato-Bold", 6.6); c.drawCentredString(x, y - 2.6 * mm, lab)
                y -= 7.6 * mm
                c.setFillColor(GRAY_600)
                for hn in seg["hotels"][:2]:
                    for ln in self._wrap(c, hn, "Lato", 6.6, cell, max_lines=2):
                        c.setFont("Lato", 6.6); c.drawCentredString(x, y, ln); y -= 3.0 * mm


# One highlight per destination: (title, one-liner, tag, icon). Cities not listed are skipped.
SIGNATURE_EXPERIENCES = {
    "srinagar":    ("Shikara ride on Dal Lake", "Glide past floating gardens and painted houseboats as the light turns golden.", "1 hour complimentary", "boat"),
    "gulmarg":     ("Gulmarg Gondola", "Ride one of the world's highest cable cars up to Apharwat's snowy ridge.", "Optional, pay locally", "peak"),
    "pahalgam":    ("Betaab Valley walk", "Stroll open meadows and pine forest beside the Lidder River.", "Union cab, extra", "tree"),
    "sonamarg":    ("Thajiwas Glacier", "Meadow of Gold: ponies or a short trek to a glacier under the peaks.", "Pony ride, extra", "peak"),
    "doodhpathri": ("Valley of Milk", "Rolling green meadows and a cold stream, away from the crowds.", "Union cab, extra", "tree"),
}


class SignatureExperiences(Flowable):
    """'Signature experiences': one postcard per destination (photo, place pill, icon medallion, one-liner, tag).
    A tag is never 'extra' or 'pay locally' for something the quote already includes: it says 'included'."""
    PHOTO_H = 21 * mm

    def __init__(self, width, segments, extras=(), photos=None):
        super().__init__()
        self.width = width
        self.photos = photos or {}
        ex = set(extras or [])
        seen, self.items = set(), []
        for sg in segments:
            key = sg["city"].lower()
            if key in SIGNATURE_EXPERIENCES and key not in seen:
                seen.add(key)
                title, desc, tag, icon = SIGNATURE_EXPERIENCES[key]
                included = False
                if key == "gulmarg" and ({"gondola_p1", "gondola_p2"} & ex):
                    both = {"gondola_p1", "gondola_p2"} <= ex
                    tag = "Gondola included" if both else ("Phase 1 included" if "gondola_p1" in ex else "Phase 2 included")
                    included = True
                elif key in ("pahalgam", "doodhpathri") and "union_cab" in ex:
                    tag, included = "Union cab included", True
                elif tag == "1 hour complimentary":
                    included = True
                self.items.append((sg["city"], key, title, desc, tag, icon, included))
        self.items = self.items[:4]
        self.bar_h = 8 * mm
        self.card_h = 49 * mm
        self.height = (self.bar_h + 4 * mm + self.card_h) if self.items else 0

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
        bar_h = self.bar_h
        c.setFillColor(NAVY_DEEP); c.roundRect(0, h - bar_h, w, bar_h, 2 * mm, fill=1, stroke=0)
        c.setFillColor(SKY);       c.roundRect(0, h - bar_h, 3 * mm, bar_h, 1.2 * mm, fill=1, stroke=0)
        c.setFillColor(WHITE);     c.setFont("Lato-Bold", 9.5)
        c.drawString(7 * mm, h - bar_h + 2.7 * mm, "SIGNATURE EXPERIENCES")

        n, gap = len(self.items), 3.5 * mm
        cw = (w - gap * (n - 1)) / n
        ch, pad = self.card_h, 1.3 * mm
        ph = self.PHOTO_H
        for i, (city, key, title, desc, tag, icon, included) in enumerate(self.items):
            x = i * (cw + gap)
            col, dark = KashmirRouteMap.PIN_COLORS[key][1], KashmirRouteMap.PIN_COLORS[key][0]
            _book_cover(c, x, 0, cw, ch, pad=pad, r=2.4 * mm)
            # photo (or painted landscape) with rounded top corners
            px, pw_, py = x + pad, cw - 2 * pad, ch - pad - ph
            c.saveState()
            cp = c.beginPath(); cp.roundRect(px, pad, pw_, ch - 2 * pad, 1.2 * mm); c.clipPath(cp, stroke=0, fill=0)
            pp = c.beginPath(); pp.rect(px, py, pw_, ph); c.clipPath(pp, stroke=0, fill=0)
            c.translate(px, py)
            rd = self.photos.get(key)
            if rd is not None:
                try:
                    iw, ih = rd.getSize(); sc = max(pw_ / iw, ph / ih)
                    c.drawImage(rd, -(iw * sc - pw_) / 2, -(ih * sc - ph) * 0.5, width=iw * sc, height=ih * sc)
                except Exception:
                    DayBookSpread._landscape(None, c, pw_, ph)
            else:
                DayBookSpread._landscape(None, c, pw_, ph)
            for k in range(12):                                          # light fade at the foot of the photo
                c.setFillColor(colors.Color(0.03, 0.07, 0.14, alpha=0.30 * (1 - k / 11.0) ** 1.6))
                c.rect(0, k * ph * 0.5 / 12, pw_, ph * 0.5 / 12 + 0.2, fill=1, stroke=0)
            c.setFillColor(WHITE)
            c.restoreState()
            # place pill on the photo
            ptxt = _raw(city).upper()
            tw = pdfmetrics.stringWidth(ptxt, "Lato-Bold", 6.6)
            c.setFillColor(colors.Color(1, 1, 1, alpha=0.94))
            c.roundRect(px + 2.4 * mm, py + ph - 7.4 * mm, tw + 7.6 * mm, 5 * mm, 2.5 * mm, fill=1, stroke=0)
            c.setFillColor(col); c.circle(px + 5.2 * mm, py + ph - 4.9 * mm, 0.9 * mm, fill=1, stroke=0)
            c.setFillColor(NAVY); c.setFont("Lato-Bold", 6.6); c.drawString(px + 7.2 * mm, py + ph - 5.6 * mm, ptxt)
            # icon medallion straddling the photo edge
            mx, my = px + pw_ - 7.2 * mm, py
            c.setFillColor(WHITE); c.circle(mx, my, 5.0 * mm, fill=1, stroke=0)
            c.setFillColor(col);   c.circle(mx, my, 4.0 * mm, fill=1, stroke=0)
            self._icon(c, icon, mx, my)
            # text
            tx, tw_ = px + 2.6 * mm, pw_ - 5.2 * mm
            ty = py - 5.2 * mm
            c.setFillColor(NAVY)
            for ln in StayRouteStrip._wrap(c, title, "Lato-Bold", 8.6, tw_ - 2 * mm, max_lines=2):
                c.setFont("Lato-Bold", 8.6); c.drawString(tx, ty, ln); ty -= 3.7 * mm
            ty -= 0.5 * mm
            c.setFillColor(GRAY_600)
            for ln in StayRouteStrip._wrap(c, desc, "Lato", 7.0, tw_, max_lines=3):
                c.setFont("Lato", 7.0); c.drawString(tx, ty, ln); ty -= 3.15 * mm
            # tag pill
            ty0 = pad + 2.4 * mm
            tw2 = pdfmetrics.stringWidth(tag, "Lato-Bold", 6.6) + (9.6 if included else 5) * mm
            if included:
                c.setFillColor(EMERALD_LITE); c.roundRect(tx, ty0, tw2, 4.6 * mm, 2.3 * mm, fill=1, stroke=0)
                c.setFillColor(EMERALD); c.circle(tx + 2.9 * mm, ty0 + 2.3 * mm, 1.35 * mm, fill=1, stroke=0)
                _check_tick(c, tx + 2.9 * mm, ty0 + 2.3 * mm, 0.62 * mm, WHITE)
                c.setFillColor(colors.HexColor("#047857")); c.setFont("Lato-Bold", 6.6)
                c.drawString(tx + 5.6 * mm, ty0 + 1.5 * mm, tag)
            else:
                c.setFillColor(WHITE); c.setStrokeColor(col); c.setLineWidth(0.6)
                c.roundRect(tx, ty0, tw2, 4.6 * mm, 2.3 * mm, fill=1, stroke=1)
                c.setFillColor(dark); c.setFont("Lato-Bold", 6.6); c.drawString(tx + 2.5 * mm, ty0 + 1.5 * mm, tag)


class TravelEssentials(Flowable):
    """'Before you travel' as an open book: Good to know on the left page, Pack smart on the right.
    Fills leftover page space only; draws nothing if it won't fit."""
    GOOD = [
        "Carry a valid photo ID for every guest. Hotels and checkpoints ask for it.",
        "Only postpaid SIMs work in J&K. Prepaid SIMs from other states do not.",
        "Keep some cash handy. ATMs and card machines can be limited in Gulmarg and Pahalgam.",
        "Road closures or weather may change the plan. Sightseeing is then rearranged for safety.",
    ]
    PACK = [
        "Woollens and thermals. Gulmarg and Pahalgam are much cooler than Srinagar.",
        "Comfortable walking shoes with good grip for meadows and snow.",
        "Rain jacket or umbrella. Mountain weather can turn quickly.",
        "Sunglasses, sunscreen and lip balm for the high-altitude sun.",
        "Power bank, camera and any personal medicines.",
    ]
    PAD, RIB, BAR_H = 1.5 * mm, 4.0 * mm, 8 * mm
    FS, LEAD = 7.2, 3.2 * mm

    def __init__(self, width, show_bar=True):
        super().__init__()
        self.width = width
        self.show_bar = show_bar
        self.tw = (width - 2 * self.PAD) / 2 - 15.5 * mm          # bullet text width
        def need(items):
            tot = 13.5 * mm + 4 * mm
            for it in items:
                tot += min(len(simpleSplit(it, "Lato", self.FS, self.tw)), 2) * self.LEAD + 1.9 * mm
            return tot
        self.book_h = max(need(self.GOOD), need(self.PACK), 56 * mm)
        self.height = (self.BAR_H + 4 * mm if show_bar else 0) + self.book_h + self.RIB
        self._skip = False

    def wrap(self, aw, ah):
        # Never vanish: when the page has no room left, the box simply starts on the next page.
        self._skip = False
        return (self.width, self.height)

    def _page(self, c, x, pw, hb, title, sub, items, ring, tint, kind):
        top = hb - self.PAD
        # heading: medallion + title + subtitle
        mx, my = x + 8.5 * mm, top - 7.4 * mm
        c.setFillColor(WHITE); c.setStrokeColor(ring); c.setLineWidth(1.5); c.circle(mx, my, 4.2 * mm, fill=1, stroke=1)
        c.setFillColor(tint); c.circle(mx, my, 3.3 * mm, fill=1, stroke=0)
        c.setStrokeColor(ring); c.setFillColor(ring); c.setLineWidth(0.9); c.setLineCap(1)
        if kind == "info":
            c.circle(mx, my + 1.9 * mm, 0.5 * mm, fill=1, stroke=0); c.line(mx, my + 0.7 * mm, mx, my - 1.9 * mm)
        else:                                                       # little suitcase
            c.roundRect(mx - 2.2 * mm, my - 1.7 * mm, 4.4 * mm, 3.2 * mm, 0.6 * mm, fill=0, stroke=1)
            c.line(mx - 0.9 * mm, my + 1.5 * mm, mx - 0.9 * mm, my + 2.3 * mm); c.line(mx + 0.9 * mm, my + 1.5 * mm, mx + 0.9 * mm, my + 2.3 * mm)
            c.line(mx - 0.9 * mm, my + 2.3 * mm, mx + 0.9 * mm, my + 2.3 * mm)
        c.setFillColor(NAVY); c.setFont("Lato-Bold", 9.4); c.drawString(x + 14.5 * mm, my + 0.6 * mm, title)
        c.setFillColor(GRAY_400); c.setFont("Lato", 6.6); c.drawString(x + 14.5 * mm, my - 3.0 * mm, sub)
        c.setStrokeColor(GRAY_200); c.setLineWidth(0.4); c.line(x + 4 * mm, my - 5.3 * mm, x + pw - 4 * mm, my - 5.3 * mm)
        y = my - 10.0 * mm
        for it in items:
            lines = simpleSplit(it, "Lato", self.FS, self.tw)[:2]
            c.setFillColor(tint); c.circle(x + 6.4 * mm, y + 1.0 * mm, 2.0 * mm, fill=1, stroke=0)
            _check_tick(c, x + 6.4 * mm, y + 1.0 * mm, 0.95 * mm, ring)
            c.setFillColor(GRAY_600); c.setFont("Lato", self.FS)
            for ln in lines:
                c.drawString(x + 11.4 * mm, y, ln); y -= self.LEAD
            y -= 1.9 * mm

    def draw(self):
        if self._skip:
            return
        c, w, h = self.canv, self.width, self.height
        bar_h = self.BAR_H
        if self.show_bar:
            c.setFillColor(NAVY_DEEP); c.roundRect(0, h - bar_h, w, bar_h, 2 * mm, fill=1, stroke=0)
            c.setFillColor(SKY);       c.roundRect(0, h - bar_h, 3 * mm, bar_h, 1.2 * mm, fill=1, stroke=0)
            c.setFillColor(WHITE);     c.setFont("Lato-Bold", 9.5)
            c.drawString(7 * mm, h - bar_h + 2.7 * mm, "BEFORE YOU TRAVEL")

        hb, pad = self.book_h, self.PAD
        c.saveState(); c.translate(0, self.RIB)
        cx = w / 2
        rw, rx = 4.6 * mm, cx - 2.3 * mm                             # ribbon hanging from the fold
        c.setFillColor(_BOOK_RIBBON)
        p = c.beginPath(); p.moveTo(rx, 1.2 * mm); p.lineTo(rx, -self.RIB + 0.2 * mm); p.lineTo(rx + rw / 2, -self.RIB + 1.7 * mm)
        p.lineTo(rx + rw, -self.RIB + 0.2 * mm); p.lineTo(rx + rw, 1.2 * mm); p.close(); c.drawPath(p, fill=1, stroke=0)
        c.setFillColor(_BOOK_COVER); c.roundRect(0, 0, w, hb, 2.6 * mm, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#e7e2d6")); c.roundRect(pad, pad * 0.5, w - 2 * pad, hb - pad * 1.5, 1.4 * mm, fill=1, stroke=0)
        py0, ph = pad + 0.7 * mm, hb - 2 * pad - 0.7 * mm
        pw = (w - 2 * pad) / 2
        c.setFillColor(_BOOK_PAGE)
        c.roundRect(pad, py0, pw, ph, 1.2 * mm, fill=1, stroke=0); c.roundRect(cx, py0, pw, ph, 1.2 * mm, fill=1, stroke=0)
        c.rect(cx - 2 * mm, py0, 4 * mm, ph, fill=1, stroke=0)
        self._page(c, pad, pw, hb, "Good to know", "Before you land", self.GOOD, SKY, SKY_LIGHT, "info")
        self._page(c, cx, pw, hb, "Pack smart", "What to bring", self.PACK, TEAL, TEAL_LITE, "bag")
        _book_fold(c, cx, py0, py0 + ph)
        c.restoreState()


# Nearest hospitals per destination: (hospital, phone). Phone is optional: fill in once verified.
# Please verify names/numbers before relying on them. Cities not listed here are skipped.
DESTINATION_HOSPITALS = {
    "srinagar":    ("SKIMS, Soura", ""),
    "gulmarg":     ("Sub-District Hospital, Tangmarg", ""),
    "pahalgam":    ("Sub-District Hospital, Pahalgam", ""),
    "sonamarg":    ("Sub-District Hospital, Kangan (nearest)", ""),
    "doodhpathri": ("District Hospital, Budgam (nearest)", ""),
}

KASHMIRI_WORDS = [
    ("Aadaab",      "ah-DAHB",         "Hello"),
    ("Shukriya",    "shook-REE-ya",    "Thank you"),
    ("Khuda hafiz", "khoo-DAH ha-FIZ", "Goodbye"),
    ("Kahwa",       "KAH-wah",         "Saffron and almond tea"),
    ("Noon chai",   "noon-CHAI",       "Salty pink tea"),
    ("Wazwan",      "WAH-zwahn",       "Grand multi-course feast"),
]


class HandyEssentials(Flowable):
    """'Handy numbers & local words': emergency numbers + hospitals for the trip's destinations + a few Kashmiri words.
    Fills leftover page space only; draws nothing if it won't fit."""
    NUMBERS = [
        ("Police / all emergencies", "112"),
        ("Ambulance", "108"),
        ("Fire", "101"),
        ("Tourist helpline (24x7)", "1363"),
        ("Serene Vibes support", "+91-9419766510"),
    ]
    PITCH = 4.8 * mm

    def __init__(self, width, segments, show_bar=True):
        super().__init__()
        self.width = width
        self.show_bar = show_bar
        seen, self.hospitals = set(), []
        for sg in segments:
            key = sg["city"].lower()
            if key in DESTINATION_HOSPITALS and key not in seen:
                seen.add(key)
                self.hospitals.append((sg["city"],) + DESTINATION_HOSPITALS[key])
        self.hospitals = self.hospitals[:4]
        hosp_h = (3 + 4.5) * mm + len(self.hospitals) * 4.2 * mm if self.hospitals else 0
        self.card_h = 10 * mm + len(self.NUMBERS) * self.PITCH + hosp_h + 4 * mm
        self.height = (8 * mm + 4 * mm if show_bar else 0) + self.card_h
        self._skip = False

    def wrap(self, aw, ah):
        # Never vanish: when the page has no room left, the box simply starts on the next page.
        self._skip = False
        return (self.width, self.height)

    @staticmethod
    def _pill(c, x, y, text, col, lite):
        tw = c.stringWidth(text, "Lato-Bold", 7.6) + 6 * mm
        c.setFillColor(lite); c.roundRect(x, y, tw, 5 * mm, 2.5 * mm, fill=1, stroke=0)
        c.setFillColor(col); c.setFont("Lato-Bold", 7.6); c.drawString(x + 3 * mm, y + 1.5 * mm, text)

    def draw(self):
        if self._skip:
            return
        c, w, h, ch = self.canv, self.width, self.height, self.card_h
        bar_h = 8 * mm
        if self.show_bar:
            c.setFillColor(NAVY_DEEP); c.roundRect(0, h - bar_h, w, bar_h, 2 * mm, fill=1, stroke=0)
            c.setFillColor(SKY);       c.roundRect(0, h - bar_h, 3 * mm, bar_h, 1.2 * mm, fill=1, stroke=0)
            c.setFillColor(WHITE);     c.setFont("Lato-Bold", 9.5)
            c.drawString(7 * mm, h - bar_h + 2.7 * mm, "HANDY NUMBERS & LOCAL WORDS")

        gap = 4 * mm
        cw = (w - gap) / 2
        for x, col in ((0, SKY), (cw + gap, TEAL)):
            c.setFillColor(WHITE); c.setStrokeColor(GRAY_200); c.setLineWidth(0.5)
            c.roundRect(x, 0, cw, ch, 2 * mm, fill=1, stroke=1)
            c.setFillColor(col); c.roundRect(x, 0, 1.4 * mm, ch, 0.7 * mm, fill=1, stroke=0)

        # ── Left: numbers + hospitals ──
        x0 = 5 * mm
        self._pill(c, x0, ch - 7.6 * mm, "USEFUL NUMBERS", SKY, SKY_LIGHT)
        y = ch - 12.6 * mm
        for i, (lab, val) in enumerate(self.NUMBERS):
            c.setFillColor(GRAY_600); c.setFont("Lato", 7.4); c.drawString(x0, y, lab)
            c.setFillColor(TEAL if i == len(self.NUMBERS) - 1 else BLACK); c.setFont("Lato-Bold", 7.6)
            c.drawRightString(cw - 4 * mm, y, val)
            if i < len(self.NUMBERS) - 1:
                c.setStrokeColor(GRAY_200); c.setLineWidth(0.4); c.line(x0, y - 1.7 * mm, cw - 4 * mm, y - 1.7 * mm)
            y -= self.PITCH
        if self.hospitals:
            y += 1.0 * mm
            c.setStrokeColor(GRAY_400); c.setLineWidth(0.4); c.setDash(1.5, 1.5)
            c.line(x0, y, cw - 4 * mm, y); c.setDash()
            y -= 4.2 * mm
            c.setFillColor(NAVY); c.setFont("Lato-Bold", 6.8); c.drawString(x0, y, "NEAREST HOSPITALS")
            y -= 4.2 * mm
            for city, hosp, phone in self.hospitals:
                c.setFillColor(BLACK); c.setFont("Lato-Bold", 7.2); c.drawString(x0, y, city + ":")
                lw = c.stringWidth(city + ":", "Lato-Bold", 7.2) + 1.5 * mm
                c.setFillColor(GRAY_600); c.setFont("Lato", 7.2); c.drawString(x0 + lw, y, hosp)
                if phone:
                    c.setFillColor(BLACK); c.setFont("Lato-Bold", 7.2); c.drawRightString(cw - 4 * mm, y, phone)
                y -= 4.2 * mm

        # ── Right: Kashmiri words ──
        rx = cw + gap + 5 * mm
        self._pill(c, rx, ch - 7.6 * mm, "SAY IT THE KASHMIRI WAY", TEAL, TEAL_LITE)
        top, bottom = ch - 12.6 * mm, 8 * mm
        pitch = (top - bottom) / (len(KASHMIRI_WORDS) - 1) if len(KASHMIRI_WORDS) > 1 else 0
        pitch = min(pitch, 6.5 * mm)
        y = top
        for i, (word, pron, meaning) in enumerate(KASHMIRI_WORDS):
            c.setFillColor(BLACK); c.setFont("Lato-Bold", 7.6); c.drawString(rx, y, word)
            ww = c.stringWidth(word, "Lato-Bold", 7.6) + 1.8 * mm
            c.setFillColor(GRAY_400); c.setFont("Lato-Italic", 6.4); c.drawString(rx + ww, y, pron)
            c.setFillColor(GRAY_600); c.setFont("Lato", 7.4); c.drawRightString(cw + gap + cw - 4 * mm, y, meaning)
            if i < len(KASHMIRI_WORDS) - 1:
                c.setStrokeColor(GRAY_200); c.setLineWidth(0.4)
                c.line(rx, y - 1.9 * mm, cw + gap + cw - 4 * mm, y - 1.9 * mm)
            y -= pitch
        c.setFillColor(GRAY_600); c.setFont("Lato-Italic", 7)
        c.drawString(rx, 3.2 * mm, "A smile and a \"Shukriya\" go a long way.")


def _stay_segments(timeline, hotel_selections, lookup):
    """Consecutive nights in the same place become one stop: [{city, nights, hotels}]."""
    segs = []
    for idx, day in enumerate(timeline, start=1):
        night = str(day.get("overnight_stay") or "").strip()
        sig = f"{day.get('title', '')} {day.get('transit_route', '')}".lower()
        if not night or night.lower() == "departure" or "departure" in sig or "airport drop" in sig:
            continue
        hid = hotel_selections.get(str(idx - 1))          # selections are keyed by 0-based day index
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
        # PDF sidebar bookmark for this section
        key = "sec_" + re.sub(r"[^a-z0-9]+", "_", self.title.lower())
        c.bookmarkPage(key)
        c.addOutlineEntry(self.title.title().replace("&", "&"), key, level=0, closed=False)


# ─── Placeholder-safe business details ───────────────────────────────────────
def _is_placeholder(v):
    """True for blank / dummy values (xxx@..., XXXXXXXX, n/a ...) that must never reach a client."""
    t = str(v or "").strip().lower()
    return (t in ("", "n/a", "na", "none", "null", "-", "tbd")
            or bool(re.search(r"x{3,}", t)) or t.startswith("xxx@"))


def _real(v):
    return "" if _is_placeholder(v) else str(v).strip()


# Set these in the environment (or backend config) once; until then they are simply not printed.
BANK_ACCOUNT_NO = _real(os.environ.get("SVK_BANK_ACCOUNT_NO"))
BANK_IFSC       = _real(os.environ.get("SVK_BANK_IFSC"))
BUSINESS_GST_NO = _real(os.environ.get("SVK_GST_NO"))


def _sharing_text(adults):
    try:
        n = int(adults)
    except (TypeError, ValueError):
        n = 2
    word = {1: "single", 2: "double", 3: "triple"}.get(n)
    return f"Accommodation on {word} sharing basis" if word else "Accommodation as per the room plan above"


# ─── Kashmir Route Map (Layout 3: map top + legend table below) ──────────────
DEFAULT_POINT = "Srinagar Airport"   # default tour start / end point

# ─── Road distance and drive time shown on every day header and on the map ───
# Approximate one-way driving figures from Srinagar by the usual tourist route
# (km, hours).  Every route in Kashmir runs out of Srinagar, so a leg between two
# outer places (Gulmarg -> Pahalgam) is the sum of the two spokes.  Edit here to
# change what clients see.  Places not listed (admin-added ones) get no figure
# unless the day carries `distance_km` / `drive_hours`.
ROAD_FROM_SRINAGAR = {
    "gulmarg":     (50, 2.0),
    "pahalgam":    (95, 3.0),
    "sonamarg":    (80, 2.5),
    "doodhpathri": (45, 2.0),
}
SRINAGAR_POINT_ROAD = (15, 0.5)      # Srinagar airport / station <-> the city and Dal Lake area


def _round_km(km):
    return int(round(float(km) / 5.0) * 5) or 5


def _fmt_drive_time(hours):
    """'about 2.5 h' / 'about 30 min' (to the nearest half hour)."""
    h = max(round(float(hours) * 2) / 2, 0.5)
    return "about 30 min" if h < 1 else f"about {h:g} h"


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
        for rx, kind in _ROUTE_SHAPES:
            m = rx.match((route_str or "").strip())
            if m:
                return _place_key(m.group(2) if kind == "to" else m.group(1))

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
                key = _place_key(overnight) or "srinagar"
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
                        else self.GPS_LABEL.get(hub_key, "-")),
                "activity": activity,
                "night": "-" if (is_dep or overnight.lower() in ("", "departure")) else overnight,
            })
        # A day starts from where the guest slept the night before (a Sonamarg day
        # trip with "Overnight Srinagar" starts the next day from Srinagar).
        prev = "srinagar"
        for r in self._rows:
            r["origin"] = prev
            night = "" if r["night"] == "-" else _place_key(r["night"])
            prev = "srinagar" if r["is_dep"] else (night or r["key"])
        self._compute_travel()

    # ── distance and drive time per day ─────────────────────────────────────
    def _point_road(self, name, info):
        """(km, hours) from a tour start / end point to Srinagar, or None when unknown."""
        info = info or {}
        if info.get("km") is not None:
            km = float(info["km"])
            hrs = info.get("hours")
            return km, (float(hrs) if hrs is not None else km / 40.0)
        if _is_srinagar_point(name):
            return SRINAGAR_POINT_ROAD
        return None

    def _hub_road(self, key):
        """(km, hours) from Srinagar to a stop key ('start' / 'end' are the tour points)."""
        if key == "srinagar":
            return 0.0, 0.0
        if key == "start":
            return self._point_road(self.start_point, self.start_info)
        if key == "end":
            return self._point_road(self.end_point, self.end_info)
        return ROAD_FROM_SRINAGAR.get(key)

    def _leg(self, a, b):
        """(km, hours) for one leg, routed through Srinagar; None when it can't be stated honestly."""
        ha, hb = self._hub_road(a), self._hub_road(b)
        if ha is None or hb is None:
            return None
        for far, other, h in ((a, b, ha), (b, a, hb)):
            # a far-away start/end (Jammu, Delhi) heading to anywhere but Srinagar is not routed via Srinagar
            if far in ("start", "end") and other != "srinagar" and h[0] > 40:
                return None
        return ha[0] + hb[0], ha[1] + hb[1]

    def _compute_travel(self):
        """Fill row['travel'] = {stops, km, hours, text} for every day that moves between places."""
        for i, r in enumerate(self._rows):
            day = self.timeline[i] if i < len(self.timeline) else {}
            nm = lambda k: self.DISPLAY.get(k, str(k).title())
            origin = ("start", self.start_point) if i == 0 else (r["origin"], nm(r["origin"]))
            if r["is_dep"]:
                seq = [origin, ("srinagar", "Srinagar"), ("end", self.end_point)]
            else:
                night = _place_key(r["night"]) if r["night"] != "-" else ""
                seq = [origin] + [(k.strip(), nm(k.strip())) for k in re.split(r"\s+to\s+", str(r["key"]))] \
                      + ([(night, nm(night) if night in self.DISPLAY else str(r["night"]))] if night else [])
            stops = []
            for k, label in seq:
                if not stops or stops[-1][0] != k:
                    stops.append((k, label))
            r["travel"] = None
            if len(stops) < 2:
                continue
            names = [lab for _, lab in stops]
            km = hours = None
            try:                                              # a day card can carry its own figures
                if day.get("distance_km") not in (None, ""):
                    km = float(day["distance_km"])
                    hours = float(day["drive_hours"]) if day.get("drive_hours") not in (None, "") else km / 40.0
            except (TypeError, ValueError):
                km = hours = None
            if km is None:
                legs = [self._leg(a[0], b[0]) for a, b in zip(stops, stops[1:])]
                if all(legs):
                    km, hours = sum(x[0] for x in legs), sum(x[1] for x in legs)
            t = {"stops": names, "km": None, "hours": None, "text": ""}
            if km is not None and km > 0:
                t.update(km=_round_km(km), hours=hours,
                         text=f"{_round_km(km)} km  ·  {_fmt_drive_time(hours)}")
            r["travel"] = t

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
        c.setFillColor(colors.Color(0, 0, 0, alpha=0.25))
        c.roundRect(cx - w / 2 + 0.4, cy - h / 2 - 0.6, w, h, h / 2, fill=1, stroke=0)
        c.setFillColor(col); c.setStrokeColor(WHITE); c.setLineWidth(1.0)
        c.roundRect(cx - w / 2, cy - h / 2, w, h, h / 2, fill=1, stroke=1)
        c.setFillColor(WHITE)
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
        c.setFillColor(dark);   c.circle(px, py, R * 0.80, fill=1, stroke=0)
        import re as _re
        nums = _re.findall(r"\d+", days_txt)
        if 0 < len(nums) <= 3:
            lab = "\u00b7".join(nums)
            fs = 8.2 if len(lab) == 1 else 6.4 if len(lab) <= 3 else 5.4
            c.setFillColor(WHITE); c.setFont("Lato-Bold", fs)
            c.drawCentredString(px, py - fs * 0.35, lab)

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
            c.setStrokeColor(WHITE); c.setLineWidth(5.6 if sat else 5.2)
            c.drawPath(self._path(c, pts), fill=0, stroke=1)
            c.setStrokeColor(bright); c.setLineWidth(3.2)
            c.drawPath(self._path(c, pts), fill=0, stroke=1)
            c.setStrokeColor(WHITE); c.setLineWidth(0.8); c.setDash(0.1, 3.0)   # dotted centre line
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
            elif k in ROAD_FROM_SRINAGAR:
                km_, hr_ = ROAD_FROM_SRINAGAR[k]
                sub = f"{_round_km(km_)} km \u00b7 {_fmt_drive_time(hr_)} from Srinagar"
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
        c.setStrokeColor(NAVY); c.setLineWidth(1.0)
        c.roundRect(0, y0, w, mh, 3 * mm, fill=0, stroke=1)

        # ── Legend table ────────────────────────────────────────────────────
        col_w = [w * 0.07, w * 0.18, w * 0.22, w * 0.35, w * 0.18]
        headers = ["Day", "Location", "Drive (approx.)", "Activity / Route", "Overnight"]
        col_x = [sum(col_w[:i]) for i in range(len(col_w))]
        hy = y0 - self.HDR_H
        c.setFillColor(NAVY); c.rect(0, hy, w, self.HDR_H, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#f5b82e")); c.rect(0, hy + self.HDR_H - 0.8 * mm, w, 0.8 * mm, fill=1, stroke=0)
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
            trv = row.get("travel") or {}
            if trv.get("text"):
                c.setFillColor(TEAL); c.setFont("Lato-Bold", 6.8)
                c.drawString(col_x[2] + 3 * mm, mid - 2.4, _raw(trv["text"]).replace("  ", " "))
            else:
                c.setFillColor(GRAY_400); c.setFont("Lato", 7)
                c.drawString(col_x[2] + 3 * mm, mid - 2.4, "\u2014")

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
def _amount_int(v):
    """Whole-rupee amount, or 0 when blank / zero / not a number."""
    try:
        n = int(round(float(str(v).replace(",", "").strip())))
    except (TypeError, ValueError, OverflowError):
        return 0
    return n if n > 0 else 0


def _is_amount(v):
    return _amount_int(v) > 0


_MEAL_PLAN_LABELS = {
    "EP": "EP (Room Only)",
    "CP": "CP (Breakfast)",
    "MAP": "MAP (B&amp;D)",
    "AP": "AP (B, L &amp; D)",
}
_MEAL_INCLUSION = {
    "EP": "Meal Plan EP - Room only, no meals included",
    "CP": "Meal Plan CP - Breakfast",
    "MAP": "Meal Plan MAP - Breakfast and one major meal (Lunch or Dinner)",
    "AP": "Meal Plan AP - Breakfast, Lunch and Dinner (all meals)",
}


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
    run = getattr(doc, "_svk_running", None)
    if run and doc.page > 1:                       # quiet running header on inner pages
        canvas.setFillColor(GRAY_400)
        canvas.setFont("Lato", 6.8)
        canvas.drawString(MARGIN + 5 * mm, h - 14.6 * mm, run[0])
        canvas.drawRightString(w - MARGIN - 5 * mm, h - 14.6 * mm, run[1])
    canvas.setFillColor(WHITE)
    canvas.setFont("Lato-Bold", 7.4)
    canvas.drawString(6 * mm, 3.7 * mm, "SERENE VIBES KASHMIR")
    canvas.setFont("Lato", 7)
    _x = 53 * mm
    for _i, (_txt, _url) in enumerate((("serenevibeskashmir@gmail.com", "mailto:serenevibeskashmir@gmail.com"),
                                      ("+91-9419766510", "tel:+919419766510"),
                                      ("www.serenevibeskashmir.com", "https://www.serenevibeskashmir.com"))):
        canvas.drawString(_x, 3.7 * mm, _txt)
        _tw = canvas.stringWidth(_txt, "Lato", 7)
        canvas.linkURL(_url, (_x, 2.6 * mm, _x + _tw, 5.6 * mm), relative=0)
        _x += _tw
        if _i < 2:
            _sep = "   |   "
            canvas.drawString(_x, 3.7 * mm, _sep)
            _x += canvas.stringWidth(_sep, "Lato", 7)
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


def _start_dt(start_date):
    raw = str(start_date or "").strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d %b %Y", "%d %B %Y", "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _day_date(start_date, day_no) -> str:
    """'Tue, 10 Nov 2026' for day N of the trip, or '' when the start date is flexible / unreadable."""
    raw = str(start_date or "").strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d %b %Y", "%d %B %Y", "%b %d, %Y", "%B %d, %Y"):
        try:
            d = datetime.datetime.strptime(raw, fmt) + datetime.timedelta(days=int(day_no) - 1)
            return d.strftime("%a, %d %b %Y")
        except ValueError:
            continue
    return ""


def _route_text(timeline, start=DEFAULT_POINT, end=DEFAULT_POINT) -> str:
    """Cover 'Your Journey': pickup point -> every place visited each day (day trips AND overnight
    stays, in order) -> departure point.

    e.g. 'Srinagar Airport -> Srinagar -> Sonamarg -> Srinagar -> Gulmarg -> Srinagar -> Pahalgam
    -> Srinagar -> Srinagar Airport'.  Built the same way as the day table: each day contributes
    its destination (from the day's route) and then where the guests sleep, if that differs."""
    def _name(key):
        return KashmirRouteMap.DISPLAY.get(key) or str(key).title()

    out = [start]

    def _add(place):
        place = str(place or "").strip()
        if place and out[-1].lower() != place.lower():
            out.append(place)

    for d in timeline or []:
        overnight = str(d.get("overnight_stay") or "").strip()
        route = str(d.get("transit_route") or d.get("title") or "").strip()
        key = KashmirRouteMap._destination(KashmirRouteMap, route) if route else None
        if key and key != "departure":
            for leg in re.split(r"\s+to\s+", str(key)):      # "gulmarg to srinagar" -> two stops
                _add(_name(leg.strip()))
        if overnight and overnight.lower() not in ("departure", "-"):
            _add(overnight)
    if out[-1].lower() != end.lower():
        out.append(end)
    return "  \u2192  ".join(out)


def _quote_ref(client_name) -> str:
    """Short quote number, e.g. SVK-251015-SG (date + client initials) - printed on the cover."""
    initials = "".join(w[0] for w in re.findall(r"[A-Za-z]+", str(client_name or ""))[:3]).upper() or "GU"
    return f"SVK-{datetime.datetime.now(IST).strftime('%y%m%d')}-{initials}"


# ── Custom locations (added in the admin itinerary builder / Hotels tab) ──────
# Route titles name places by their text ("Sopore to Gulmarg: Overnight Gulmarg"), so any name works.
# For one PDF build, every admin-added place is registered into KashmirRouteMap: it always gets a
# row in the day table, and gets a pin and road on the map when its coordinates are known.
_ROUTE_SHAPES = (
    (re.compile(r"^airport pickup(?: and local sightseeing)?\s*:\s*overnight\s+(.+)$", re.I), "pickup"),
    (re.compile(r"^(.+?)\s+local sightseeing\s*:\s*overnight\s+(.+)$", re.I), "local"),
    (re.compile(r"^(.+?)\s+to\s+(.+?)\s*:\s*overnight\s+(.+)$", re.I), "to"),
)
_CUSTOM_PALETTE = (
    ("#7c2d12", "#fb923c", "#fff7ed"),   # orange
    ("#164e63", "#06b6d4", "#ecfeff"),   # cyan
    ("#831843", "#ec4899", "#fdf2f8"),   # pink
    ("#365314", "#84cc16", "#f7fee5"),   # lime
    ("#312e81", "#6366f1", "#eef2ff"),   # indigo
)
_CUSTOM_MAP_KEYS = set()


def _place_key(name) -> str:
    """Matching key for a place name as it appears in route text: lower case, single spaces."""
    return " ".join(str(name or "").replace(":", " ").split()).lower()


def _register_custom_map_places():
    """Load the admin-added places into the route map tables (repeated on every build)."""
    cls = KashmirRouteMap
    tables = (cls.STOPS, cls.DISPLAY, cls.GPS_LABEL, cls.ROADS, cls.PIN_COLORS, cls.ROW_TINT, cls.LABEL_SIDE)
    for key in list(_CUSTOM_MAP_KEYS):
        for table in tables:
            table.pop(key, None)
    _CUSTOM_MAP_KEYS.clear()
    try:
        from backend.models import CustomPlace
        rows = CustomPlace.query.order_by(CustomPlace.id).all()
    except Exception as exc:
        print(f"Warning: could not load custom places for the route map: {exc}")
        return
    hub = cls.STOPS["srinagar"]
    for i, row in enumerate(rows):
        key = _place_key(row.name)
        if not key or key in cls.STOPS:          # a built-in place is never redefined
            continue
        dark, bright, tint = _CUSTOM_PALETTE[i % len(_CUSTOM_PALETTE)]
        cls.DISPLAY[key] = row.name
        cls.PIN_COLORS[key] = (colors.HexColor(dark), colors.HexColor(bright))
        cls.ROW_TINT[key] = colors.HexColor(tint)
        cls.LABEL_SIDE[key] = "right"
        _CUSTOM_MAP_KEYS.add(key)
        if row.lat is None or row.lon is None:
            continue                              # listed in the day table; no pin without coordinates
        dest = (row.lat, row.lon)
        cls.STOPS[key] = dest
        cls.GPS_LABEL[key] = (f"{abs(row.lat):.2f}°{'N' if row.lat >= 0 else 'S'}  "
                              f"{abs(row.lon):.2f}°{'E' if row.lon >= 0 else 'W'}")
        cls.ROADS[key] = [(hub[0] + (dest[0] - hub[0]) * t, hub[1] + (dest[1] - hub[1]) * t)
                          for t in (0.0, 0.25, 0.5, 0.75, 1.0)]


# ─── Page 1 decision blocks ──────────────────────────────────────────────────
SVK_WA_NUMBER = "919419766510"
# Same figures as the website (index.html). Edit here when the website numbers change.
# (headline figure, small caption) - shown as five columns in the trust band.
TRUST_STATS = [("4.9/5", "GOOGLE  \u00b7  200+ REVIEWS"), ("5,000+", "GUESTS SERVED"),
               ("15+", "YEARS IN KASHMIR"), ("J&K", "TOURISM REGISTERED"),
               ("24/7", "SUPPORT ON YOUR TRIP")]
TRUST_QUOTE = ("Transfers were punctual, hotels were exactly as described, and our guide in "
               "Gulmarg was exceptional.")
TRUST_QUOTE_BY = "Arjun K., Grand Kashmir Circuit"
WA_GREEN = colors.HexColor("#1faa59")
WA_GREEN_DK = colors.HexColor("#168a47")
SAFFRON  = colors.HexColor("#f5b82e")
INK_SOFT = colors.HexColor("#64748b")
HAIR     = colors.HexColor("#e6eaf0")


def _fit_font(c, text, font, size, max_w):
    while size > 5 and c.stringWidth(text, font, size) > max_w:
        size -= 0.2
    return size


def _fit_text(c, text, font, size, max_w, min_size=7.0):
    """Shrink to min_size, then cut with an ellipsis: long names never get tiny or overflow."""
    text = str(text)
    while size > min_size and c.stringWidth(text, font, size) > max_w:
        size -= 0.2
    if c.stringWidth(text, font, size) > max_w:
        while len(text) > 1 and c.stringWidth(text + "\u2026", font, size) > max_w:
            text = text[:-1]
        text = text.rstrip() + "\u2026"
    return text, size


def _spaced(c, x, y, text, font, size, space=0.6, align="l"):
    """Letter-spaced text (small-caps eyebrows). Returns the drawn width."""
    w = c.stringWidth(text, font, size) + space * max(len(text) - 1, 0)
    if align == "c":
        x -= w / 2
    elif align == "r":
        x -= w
    t = c.beginText(x, y)
    t.setFont(font, size); t.setCharSpace(space); t.textOut(text); t.setCharSpace(0)
    c.drawText(t)
    return w


def _soft_shadow(c, x, y, w, h, r, layers=5, alpha=0.028, step=0.28 * mm):
    """Layered, very low-alpha rounded rects: a soft ambient shadow, no image needed."""
    c.saveState()
    c.setFillColor(colors.Color(0.06, 0.09, 0.16, alpha))
    for i in range(layers, 0, -1):
        g = i * step
        c.roundRect(x - g * 0.6, y - g * 1.25, w + g * 1.2, h + g * 0.9, r + g * 0.6, fill=1, stroke=0)
    c.restoreState()


def _grad_roundrect(c, x, y, w, h, r, c0, c1, angle="v"):
    """Rounded rectangle filled with a two-stop linear gradient (v = top to bottom, d = diagonal)."""
    c.saveState()
    p = c.beginPath(); p.roundRect(x, y, w, h, r)
    c.clipPath(p, stroke=0, fill=0)
    if angle == "d":
        c.linearGradient(x, y + h, x + w, y, (c0, c1), extend=True)
    elif angle == "h":
        c.linearGradient(x, y, x + w, y, (c0, c1), extend=True)
    else:
        c.linearGradient(x, y + h, x, y, (c0, c1), extend=True)
    c.restoreState()


def _check_badge(c, cx, cy, r, fill, tick=WHITE):
    c.saveState()
    c.setFillColor(fill); c.circle(cx, cy, r, fill=1, stroke=0)
    c.setStrokeColor(tick); c.setLineWidth(r * 0.42); c.setLineCap(1); c.setLineJoin(1)
    p = c.beginPath()
    p.moveTo(cx - r * 0.42, cy - r * 0.02); p.lineTo(cx - r * 0.1, cy - r * 0.36); p.lineTo(cx + r * 0.46, cy + r * 0.34)
    c.drawPath(p, fill=0, stroke=1)
    c.restoreState()


def _star(c, cx, cy, r, fill):
    import math
    p = c.beginPath()
    for i in range(10):
        ang = math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.42
        px, py = cx + rr * math.cos(ang), cy + rr * math.sin(ang)
        (p.moveTo if i == 0 else p.lineTo)(px, py)
    p.close(); c.setFillColor(fill); c.drawPath(p, fill=1, stroke=0)


def _clock_icon(c, cx, cy, r, col):
    c.setStrokeColor(col); c.setLineWidth(0.7); c.setLineCap(1)
    c.circle(cx, cy, r, fill=0, stroke=1)
    c.line(cx, cy, cx, cy + r * 0.62); c.line(cx, cy, cx + r * 0.5, cy - r * 0.1)


def _line_icon(c, kind, cx, cy, s, col):
    """Small stroked icons drawn from paths (no font or image dependency). s = half size."""
    c.saveState()
    c.setStrokeColor(col); c.setFillColor(col); c.setLineWidth(0.85); c.setLineCap(1); c.setLineJoin(1)
    if kind == "car":
        p = c.beginPath()
        p.moveTo(cx - s, cy - s * 0.35); p.lineTo(cx - s, cy + s * 0.05)
        p.lineTo(cx - s * 0.62, cy + s * 0.12); p.lineTo(cx - s * 0.36, cy + s * 0.58)
        p.lineTo(cx + s * 0.38, cy + s * 0.58); p.lineTo(cx + s * 0.66, cy + s * 0.12)
        p.lineTo(cx + s, cy + s * 0.05); p.lineTo(cx + s, cy - s * 0.35); p.close()
        c.drawPath(p, fill=0, stroke=1)
        c.line(cx - s * 0.62, cy + s * 0.12, cx + s * 0.66, cy + s * 0.12)
        c.setFillColor(WHITE)
        for dx in (-0.55, 0.55):
            c.circle(cx + s * dx, cy - s * 0.38, s * 0.24, fill=1, stroke=1)
    elif kind == "bed":
        c.line(cx - s, cy - s * 0.5, cx - s, cy + s * 0.55)
        c.line(cx - s, cy - s * 0.18, cx + s, cy - s * 0.18); c.line(cx + s, cy - s * 0.5, cx + s, cy - s * 0.18)
        c.roundRect(cx - s * 0.82, cy - s * 0.02, s * 0.6, s * 0.32, s * 0.12, fill=0, stroke=1)
        p = c.beginPath(); p.moveTo(cx - s * 0.05, cy - s * 0.18); p.lineTo(cx - s * 0.05, cy + s * 0.2)
        p.lineTo(cx + s * 0.78, cy + s * 0.2); p.lineTo(cx + s, cy - s * 0.18)
        c.drawPath(p, fill=0, stroke=1)
    elif kind == "meal":
        c.circle(cx, cy, s * 0.62, fill=0, stroke=1); c.circle(cx, cy, s * 0.3, fill=0, stroke=1)
        c.line(cx - s * 1.0, cy - s * 0.7, cx - s * 1.0, cy + s * 0.7)
        c.line(cx + s * 1.0, cy - s * 0.7, cx + s * 1.0, cy + s * 0.7)
    elif kind == "boat":
        p = c.beginPath(); p.moveTo(cx - s, cy - s * 0.12)
        p.curveTo(cx - s * 0.7, cy - s * 0.62, cx + s * 0.7, cy - s * 0.62, cx + s, cy - s * 0.12)
        p.lineTo(cx - s, cy - s * 0.12); c.drawPath(p, fill=0, stroke=1)
        q = c.beginPath(); q.moveTo(cx - s * 0.6, cy - s * 0.12); q.curveTo(cx - s * 0.55, cy + s * 0.62, cx + s * 0.55, cy + s * 0.62, cx + s * 0.6, cy - s * 0.12)
        c.drawPath(q, fill=0, stroke=1)
        c.line(cx - s * 0.2, cy + s * 0.08, cx - s * 0.2, cy - s * 0.12); c.line(cx + s * 0.2, cy + s * 0.08, cx + s * 0.2, cy - s * 0.12)
        c.line(cx - s * 0.9, cy - s * 0.8, cx + s * 0.9, cy - s * 0.8)
    elif kind == "tax":
        p = c.beginPath(); p.moveTo(cx - s * 0.62, cy + s * 0.9); p.lineTo(cx + s * 0.62, cy + s * 0.9)
        p.lineTo(cx + s * 0.62, cy - s * 0.9)
        for i, dx in enumerate((0.62 - 0.41, 0.62 - 0.83, 0.62 - 1.24)):
            p.lineTo(cx + s * dx, cy - s * (0.62 if i % 2 == 0 else 0.9))
        p.close(); c.drawPath(p, fill=0, stroke=1)
        for dy in (0.42, 0.04):
            c.line(cx - s * 0.3, cy + s * dy, cx + s * 0.3, cy + s * dy)
    c.restoreState()


def _wa_glyph(c, cx, cy, r):
    """White chat-bubble mark for the WhatsApp button."""
    c.setFillColor(WHITE); c.circle(cx, cy, r, fill=1, stroke=0)
    p = c.beginPath(); p.moveTo(cx - r * 0.95, cy - r * 1.0); p.lineTo(cx - r * 0.2, cy - r * 0.85); p.lineTo(cx - r * 0.85, cy - r * 0.2); p.close()
    c.drawPath(p, fill=1, stroke=0)
    c.setStrokeColor(WA_GREEN); c.setLineWidth(r * 0.3); c.setLineCap(1)
    ph = c.beginPath(); ph.moveTo(cx - r * 0.42, cy + r * 0.3)
    ph.curveTo(cx - r * 0.5, cy - r * 0.2, cx + r * 0.1, cy - r * 0.55, cx + r * 0.42, cy - r * 0.38)
    c.drawPath(ph, fill=0, stroke=1)


class PriceBand(Flowable):
    """Price per person, validity, 25% start amount and a one-tap WhatsApp confirm button."""
    def __init__(self, width, total, adults, kids, valid_until, first_amt, ref, show_per_person=False):
        super().__init__()
        self.show_per_person = bool(show_per_person)
        self.width, self.height = width, 33 * mm
        self.total, self.adults, self.kids = total, adults, kids
        self.valid_until, self.first_amt, self.ref = valid_until, first_amt, ref

    def draw(self):
        import urllib.parse as _up
        c, w, h = self.canv, self.width, self.height
        lw = w * 0.585
        R = 3 * mm
        _soft_shadow(c, 0, 0, w, h, R)
        c.setFillColor(colors.HexColor("#fffdf8")); c.setStrokeColor(colors.HexColor("#ecdfc2")); c.setLineWidth(0.6)
        c.roundRect(0, 0, w, h, R, fill=1, stroke=1)
        # gold edge: gradient clipped to the card's rounded corner and a 1.5 mm strip
        c.saveState()
        p = c.beginPath(); p.roundRect(0, 0, w, h, R); c.clipPath(p, stroke=0, fill=0)
        p2 = c.beginPath(); p2.rect(0, 0, 1.5 * mm, h); c.clipPath(p2, stroke=0, fill=0)
        c.linearGradient(0, h, 0, 0, (SAFFRON, GOLD_MID), extend=True)
        c.restoreState()

        x = 7 * mm
        try:
            n_adults = int(self.adults)
        except (TypeError, ValueError):
            n_adults = 0
        has_total = bool(self.total)
        n_kids = int(self.kids or 0)
        # per-person price is OPT-IN (itinerary builder switch); otherwise the headline is the package total
        per = round(self.total / n_adults) if (self.show_per_person and has_total and n_adults and not n_kids) else 0
        guests_txt = f"for {n_adults} adult" + ("s" if n_adults != 1 else "") + (f", {n_kids} child" + ("ren" if n_kids != 1 else "") if n_kids else "")
        # ── left: label + hold pill on one row, price, inclusions, 25/25/50 steps (same 33 mm height) ──
        left_r = lw - 4 * mm
        row_y = h - 5.7 * mm                       # vertical centre of the label / pill row
        c.setFillColor(GOLD)
        _spaced(c, x, row_y - 0.8 * mm, "PRICE PER PERSON" if per else "TOTAL PACKAGE PRICE", "Lato-Bold", 6.4, 1.0)
        if self.valid_until:
            txt = f"Price held until {self.valid_until}"
            c.setFont("Lato-Bold", 6.6)
            tw = c.stringWidth(txt, "Lato-Bold", 6.6) + 8.2 * mm
            px0, ph0 = left_r - tw, 4.6 * mm
            c.setFillColor(GOLD_LITE); c.setStrokeColor(colors.HexColor("#f6dfa0")); c.setLineWidth(0.5)
            c.roundRect(px0, row_y - ph0 / 2, tw, ph0, ph0 / 2, fill=1, stroke=1)
            _clock_icon(c, px0 + 3.0 * mm, row_y, 1.1 * mm, GOLD)
            c.setFillColor(GOLD); c.setFont("Lato-Bold", 6.6)
            c.drawString(px0 + 5.4 * mm, row_y - 2.2, txt)
        base = h - 15.4 * mm
        amount = per if per else (self.total if has_total else 0)
        if amount:
            c.setFillColor(INK_SOFT); c.setFont("Lato-Bold", 10.5)
            c.drawString(x, base, "INR")
            iw = c.stringWidth("INR", "Lato-Bold", 10.5) + 1.6 * mm
            c.setFillColor(NAVY_DEEP); c.setFont("Lato-Bold", 27)
            c.drawString(x + iw, base, f"{amount:,}")
            nw = c.stringWidth(f"{amount:,}", "Lato-Bold", 27)
            c.setFillColor(INK_SOFT); c.setFont("Lato", 8.4)
            c.drawString(x + iw + nw + 2.4 * mm, base, f"for {n_adults} adults" if per else guests_txt)
        else:
            c.setFillColor(NAVY_DEEP); c.setFont("Lato-Bold", 20)
            c.drawString(x, base, "Price on request")
        if has_total:
            avail = left_r - x
            if per:
                a, b, d = "Trip total ", f"INR {self.total:,}", "  \u00b7  stay, car, driver, meals and taxes included"
            else:
                a, b, d = "All-inclusive: ", "stay, car, driver, meals and taxes", ""
            sz = 7.4
            while sz > 5 and (c.stringWidth(a, "Lato", sz) + c.stringWidth(b, "Lato-Bold", sz) + c.stringWidth(d, "Lato", sz)) > avail:
                sz -= 0.2
            yy = h - 20.2 * mm; cx_ = x
            c.setFillColor(SLATE); c.setFont("Lato", sz); c.drawString(cx_, yy, a); cx_ += c.stringWidth(a, "Lato", sz)
            c.setFillColor(NAVY_DEEP); c.setFont("Lato-Bold", sz); c.drawString(cx_, yy, b); cx_ += c.stringWidth(b, "Lato-Bold", sz)
            c.setFillColor(SLATE); c.setFont("Lato", sz); c.drawString(cx_, yy, d)
            # payment steps: 25% now / 25% before arrival / 50% on arrival
            c.setStrokeColor(colors.HexColor("#efe6d0")); c.setLineWidth(0.5)
            c.line(x, h - 22.6 * mm, left_r, h - 22.6 * mm)
            i1 = int(self.first_amt or round(self.total * 0.25))
            i3 = int(self.total) - 2 * i1
            steps = [
                (SKY,                       f"25%  INR {i1:,}", "on confirmation"),
                (colors.HexColor("#7c3aed"), f"25%  INR {i1:,}", "7 days before arrival"),
                (EMERALD,                   f"50%  INR {i3:,}", "on arrival"),
            ]
            colw = (left_r - x) / 3.0
            r_c = 2.1 * mm; cy_ = 5.6 * mm
            for k, (col, l1, l2) in enumerate(steps):
                sx0 = x + k * colw
                c.setFillColor(col); c.circle(sx0 + r_c, cy_, r_c, fill=1, stroke=0)
                c.setFillColor(WHITE); c.setFont("Lato-Bold", 7.2)
                c.drawCentredString(sx0 + r_c, cy_ - 2.5, str(k + 1))
                tx0 = sx0 + 2 * r_c + 1.6 * mm
                maxw = colw - 2 * r_c - 2.6 * mm
                f1 = 6.9
                while f1 > 5.2 and c.stringWidth(l1, "Lato-Bold", f1) > maxw:
                    f1 -= 0.2
                f2 = 6.0
                while f2 > 4.8 and c.stringWidth(l2, "Lato", f2) > maxw:
                    f2 -= 0.2
                c.setFillColor(NAVY_DEEP); c.setFont("Lato-Bold", f1); c.drawString(tx0, cy_ + 0.5 * mm, l1)
                c.setFillColor(INK_SOFT); c.setFont("Lato", f2); c.drawString(tx0, cy_ - 2.5 * mm, l2)

        # right: deep navy action panel
        px, py, pw, ph = lw, 2.2 * mm, w - lw - 2.2 * mm, h - 4.4 * mm
        _grad_roundrect(c, px, py, pw, ph, 2.3 * mm, colors.HexColor("#14213d"), NAVY_DEEP, "d")
        c.setStrokeColor(colors.Color(1, 1, 1, alpha=0.08)); c.setLineWidth(0.5)
        c.roundRect(px, py, pw, ph, 2.3 * mm, fill=0, stroke=1)
        bx, bw_, bh = px + 5 * mm, pw - 10 * mm, 10.6 * mm
        has_first = bool(self.first_amt)
        by = py + ph - 5 * mm - bh if has_first else py + (ph - bh) / 2 + 2.5 * mm
        c.setFillColor(colors.Color(0, 0, 0, alpha=0.28)); c.roundRect(bx, by - 0.8, bw_, bh, 2.4 * mm, fill=1, stroke=0)
        _grad_roundrect(c, bx, by, bw_, bh, 2.4 * mm, colors.HexColor("#2ac46d"), WA_GREEN_DK, "v")
        c.setStrokeColor(colors.Color(1, 1, 1, alpha=0.28)); c.setLineWidth(0.4)
        c.roundRect(bx, by, bw_, bh, 2.4 * mm, fill=0, stroke=1)
        label = "Confirm on WhatsApp"
        c.setFont("Lato-Bold", 9.4)
        gw = 4.6 * mm; tw_ = c.stringWidth(label, "Lato-Bold", 9.4)
        sx = bx + (bw_ - (gw + 2.2 * mm + tw_)) / 2
        _wa_glyph(c, sx + gw / 2, by + bh / 2 + 0.2, gw / 2)
        c.setFillColor(WHITE); c.setFont("Lato-Bold", 9.4)
        c.drawString(sx + gw + 2.2 * mm, by + bh / 2 - 3.2, label)
        msg = _up.quote(f"Hi, I would like to confirm my Kashmir trip, quote {self.ref}")
        c.linkURL(f"https://wa.me/{SVK_WA_NUMBER}?text={msg}", (bx, by, bx + bw_, by + bh), relative=1, thickness=0)
        c.setFillColor(colors.HexColor("#9fb0c8")); c.setFont("Lato", 6.4)
        c.drawCentredString(px + pw / 2, by - 3.6 * mm, "Opens a chat with your quote number typed in")
        if has_first:
            ly = by - 6.6 * mm
            c.setStrokeColor(colors.Color(1, 1, 1, alpha=0.14)); c.setLineWidth(0.4)
            c.line(px + 6 * mm, ly, px + pw - 6 * mm, ly)
            a, b = "Start with just 25%  \u00b7  ", f"INR {self.first_amt:,}"
            tw2 = c.stringWidth(a, "Lato-Bold", 7.4) + c.stringWidth(b, "Lato-Bold", 7.4)
            tx = px + (pw - tw2) / 2
            c.setFillColor(WHITE); c.setFont("Lato-Bold", 7.4); c.drawString(tx, ly - 4 * mm, a)
            c.setFillColor(SAFFRON); c.drawString(tx + c.stringWidth(a, "Lato-Bold", 7.4), ly - 4 * mm, b)


DAY_MIN_START = 82 * mm   # room a day needs before it may start on the current page (banner + photo + ~2 steps)
_P1_SLACK = 3 * mm      # safety margin so page 1 never spills onto page 2


_EXTRA_LABELS = {
    "union_cab":  "Union cabs (Pahalgam ABC & snow-chain vehicle)",
    "gondola_p1": "Gondola Phase 1",
    "gondola_p2": "Gondola Phase 2",
}


def _extras_list(itinerary_data):
    ex = itinerary_data.get("included_extras") or []
    return [k for k in ("union_cab", "gondola_p1", "gondola_p2") if k in ex]


class BackdropGroup(Flowable):
    """Soft 'Kashmir morning' backdrop behind a stack of cards: pale sky-to-cream gradient, layered
    mountain ridges along the bottom, a faint sun glow and snow dots. Children are drawn on top."""
    PAD = 3.2 * mm

    def __init__(self, width, children, gap=3 * mm):
        super().__init__()
        self.width, self.children, self.gap = width, children, gap
        self._recalc()

    def _recalc(self):
        iw = self.width - 2 * self.PAD
        self._hs = [ch.wrap(iw, 10000)[1] for ch in self.children]
        self.height = sum(self._hs) + self.gap * (len(self.children) - 1) + 2 * self.PAD

    def wrap(self, aw, ah):
        self._recalc()
        return self.width, self.height

    def draw(self):
        import math, random
        c, w, h = self.canv, self.width, self.height
        R = 4 * mm
        _soft_shadow(c, 0, 0, w, h, R, layers=4, alpha=0.02)
        c.saveState()
        pth = c.beginPath(); pth.roundRect(0, 0, w, h, R); c.clipPath(pth, stroke=0, fill=0)
        c.linearGradient(0, h, w, 0, (colors.HexColor("#eaf4fb"), colors.HexColor("#fff7ea")), extend=True)
        # sun glow (top right)
        for k in range(7, 0, -1):
            c.setFillColor(colors.Color(1.0, 0.82, 0.45, alpha=0.035))
            c.circle(w * 0.90, h * 0.92, 5 * mm + k * 4.2 * mm, fill=1, stroke=0)
        # far + near mountain ridges
        for (base, amp, col, al, ph) in ((0.20, 0.17, "#9cc3e0", 0.20, 0.0), (0.10, 0.12, "#6fa3cc", 0.17, 1.7)):
            ridge = c.beginPath(); ridge.moveTo(0, 0); ridge.lineTo(0, h * base)
            steps = 46
            for i in range(1, steps + 1):
                x = w * i / steps
                y = h * base + h * amp * (0.55 * abs(math.sin(i * 0.42 + ph)) + 0.45 * abs(math.sin(i * 0.17 + ph * 0.6)))
                ridge.lineTo(x, y)
            ridge.lineTo(w, 0); ridge.close()
            c.setFillColor(colors.HexColor(col)); c.setFillAlpha(al)
            c.drawPath(ridge, fill=1, stroke=0)
        c.setFillAlpha(1)
        # snow dots
        rnd = random.Random(7)
        for _ in range(46):
            c.setFillColor(colors.Color(1, 1, 1, alpha=rnd.uniform(0.35, 0.8)))
            c.circle(rnd.uniform(0, w), rnd.uniform(h * 0.15, h), rnd.uniform(0.25, 0.7) * mm, fill=1, stroke=0)
        c.restoreState()
        c.setStrokeColor(colors.HexColor("#d6e6f1")); c.setLineWidth(0.7)
        c.roundRect(0, 0, w, h, R, fill=0, stroke=1)
        # children, top to bottom
        iw = w - 2 * self.PAD
        y = h - self.PAD
        for ch, hh in zip(self.children, self._hs):
            y -= hh
            ch.drawOn(c, self.PAD, y)
            y -= self.gap


class IncludedCards(Flowable):
    """'What's included' as roomy cards: coloured icon disc with a green 'included' tick, bold title,
    tinted caption. One row for up to 4 items, otherwise two balanced rows (last row centred)."""
    CARD_H = 11.6 * mm
    GAP = 2.4 * mm

    def __init__(self, width, items):
        super().__init__()
        self.width, self.items = width, items
        self.compact = False
        self._recalc()

    def _layout(self):
        n = len(self.items)
        rows = 1 if n <= 4 else 2
        cols = -(-n // rows)
        return rows, cols

    def _recalc(self):
        rows, _ = self._layout()
        ch = self.CARD_H - (1.4 * mm if self.compact else 0)
        self.card_h = ch
        self.height = rows * ch + (rows - 1) * (self.GAP - (0.6 * mm if self.compact else 0)) + 1.2 * mm

    def draw(self):
        c, w = self.canv, self.width
        rows, cols = self._layout()
        gap = self.GAP - (0.6 * mm if self.compact else 0)
        ch = self.card_h
        cw = (w - gap * (cols - 1)) / cols
        R = 3 * mm
        n = len(self.items)
        for i, item in enumerate(self.items):
            head, sub = item[0], item[1]
            kind = item[2] if len(item) > 2 else IncludedStrip._KINDS[i % 5]
            pal = IncludedStrip._KIND_PAL.get(kind) or IncludedStrip._PAL[i % 5]
            top_c, bot_c, tint, cap = (colors.HexColor(x) for x in pal)
            r, col = divmod(i, cols)
            in_row = cols if r < rows - 1 else n - cols * (rows - 1)
            x0 = col * (cw + gap) + (cols - in_row) * (cw + gap) / 2
            y0 = (rows - 1 - r) * (ch + gap) + 1.2 * mm
            _soft_shadow(c, x0, y0, cw, ch, R, layers=3, alpha=0.022)
            c.setFillColor(WHITE); c.setStrokeColor(colors.HexColor("#e3ebf2")); c.setLineWidth(0.6)
            c.roundRect(x0, y0, cw, ch, R, fill=1, stroke=1)
            c.saveState()
            pth = c.beginPath(); pth.roundRect(x0, y0, cw, ch, R); c.clipPath(pth, stroke=0, fill=0)
            c.setFillColor(tint); c.circle(x0 + 6.4 * mm, y0 + ch / 2, ch * 1.05, fill=1, stroke=0)
            c.setFillColor(WHITE); c.circle(x0 + 6.4 * mm, y0 + ch / 2, ch * 0.62, fill=1, stroke=0)
            c.setFillColor(tint); c.circle(x0 + 6.4 * mm, y0 + ch / 2, ch * 0.5, fill=1, stroke=0)
            c.restoreState()
            d = min(8.2 * mm, ch - 2.4 * mm)
            dx, dy = x0 + 2.4 * mm, y0 + (ch - d) / 2
            c.saveState()
            for k in range(3, 0, -1):
                c.setFillColor(colors.Color(bot_c.red, bot_c.green, bot_c.blue, alpha=0.07))
                c.circle(dx + d / 2, dy + d / 2 - 0.3 * mm, d / 2 + k * 0.5 * mm, fill=1, stroke=0)
            c.restoreState()
            _grad_roundrect(c, dx, dy, d, d, d / 2, top_c, bot_c, "d")
            c.saveState()
            c.setStrokeColor(colors.Color(1, 1, 1, alpha=0.55)); c.setLineWidth(0.5)
            c.circle(dx + d / 2, dy + d / 2, d / 2 - 0.4 * mm, fill=0, stroke=1)
            c.restoreState()
            IncludedStrip._glyph(c, kind, dx + d / 2, dy + d / 2, d * 0.235, bot_c)
            # little green 'included' tick on the disc
            _check_badge(c, dx + d - 0.5 * mm, dy + 0.6 * mm, 1.35 * mm, colors.HexColor("#16a34a"))
            tx = dx + d + 2.6 * mm
            avail = x0 + cw - 2.2 * mm - tx
            c.setFillColor(NAVY_DEEP)
            head, hfs = _fit_text(c, head, "Lato-Bold", 8.4, avail, 6.4)
            c.setFont("Lato-Bold", hfs)
            c.drawString(tx, y0 + ch / 2 + 0.9 * mm, head)
            c.setFillColor(cap)
            c.setFont("Lato", _fit_font(c, sub, "Lato", 6.6, avail))
            c.drawString(tx, y0 + ch / 2 - 3.1 * mm, sub)


class IncludedStrip(Flowable):
    """Five 'what you get' cells. Each has its own colour: a glossy gradient tile with a soft glow,
    a white pictogram, a bold title and a tinted caption, on a faint tinted cell background."""
    # (gradient top, gradient bottom, glow/tint, caption colour)
    _PAL = (
        ("#4f9dff", "#1d5fd6", "#e8f1ff", "#1e55b8"),   # car     - blue
        ("#9b7bff", "#6a3fd8", "#f0eaff", "#5b34b8"),   # bed     - violet
        ("#ffb347", "#e5780b", "#fff3e0", "#b45f08"),   # meals   - amber
        ("#2fd0c0", "#0a8f86", "#e4f8f5", "#0b756d"),   # shikara - teal
        ("#ff7a9c", "#d42a5b", "#ffe9ef", "#b0224c"),   # taxes   - rose
    )
    _KINDS = ("car", "bed", "meal", "boat", "tax")
    _KIND_PAL = {
        "cab":     ("#5fb0ff", "#1a6fc9", "#e6f2ff", "#175aa3"),   # union cab - sky blue
        "gondola": ("#7ddc6e", "#2b9a3f", "#eaf9e6", "#237a33"),   # gondola   - green
    }

    def __init__(self, width, items):
        super().__init__()
        self.width, self.height, self.items = width, 21 * mm, items
        self.compact = False

    # ---- white pictograms, drawn on a tile whose colour is `hole` ----------
    @staticmethod
    def _glyph(c, kind, cx, cy, u, hole):
        W = colors.white
        c.saveState()
        c.setFillColor(W); c.setStrokeColor(W); c.setLineCap(1); c.setLineJoin(1)
        if kind == "car":
            p = c.beginPath()                                   # cabin
            p.moveTo(cx - 0.62*u, cy + 0.02*u); p.lineTo(cx - 0.38*u, cy + 0.50*u)
            p.lineTo(cx + 0.38*u, cy + 0.50*u); p.lineTo(cx + 0.62*u, cy + 0.02*u); p.close()
            c.drawPath(p, fill=1, stroke=0)
            c.roundRect(cx - 0.95*u, cy - 0.46*u, 1.9*u, 0.56*u, 0.2*u, fill=1, stroke=0)   # body
            c.setFillColor(hole)                                # windows
            for dx in (-0.2, 0.2):
                q = c.beginPath()
                q.moveTo(cx + (dx-0.17)*u, cy + 0.06*u); q.lineTo(cx + (dx-0.10)*u, cy + 0.40*u)
                q.lineTo(cx + (dx+0.10)*u, cy + 0.40*u); q.lineTo(cx + (dx+0.17)*u, cy + 0.06*u); q.close()
                c.drawPath(q, fill=1, stroke=0)
            for dx in (-0.55, 0.55):                            # wheels
                c.setFillColor(hole); c.circle(cx + dx*u, cy - 0.46*u, 0.30*u, fill=1, stroke=0)
                c.setFillColor(W);    c.circle(cx + dx*u, cy - 0.46*u, 0.20*u, fill=1, stroke=0)
        elif kind == "bed":
            c.roundRect(cx - 0.98*u, cy - 0.50*u, 0.16*u, 1.0*u, 0.07*u, fill=1, stroke=0)   # headboard
            c.roundRect(cx - 0.98*u, cy - 0.30*u, 1.96*u, 0.24*u, 0.08*u, fill=1, stroke=0)  # frame
            c.roundRect(cx - 0.80*u, cy - 0.06*u, 1.74*u, 0.30*u, 0.10*u, fill=1, stroke=0)  # mattress
            c.setFillColor(hole); c.roundRect(cx - 0.66*u, cy + 0.10*u, 0.52*u, 0.26*u, 0.12*u, fill=1, stroke=0)
            c.setFillColor(W);    c.roundRect(cx - 0.62*u, cy + 0.12*u, 0.44*u, 0.20*u, 0.10*u, fill=1, stroke=0)  # pillow
            c.roundRect(cx + 0.78*u, cy - 0.50*u, 0.16*u, 0.30*u, 0.05*u, fill=1, stroke=0)  # leg
        elif kind == "meal":
            c.circle(cx, cy, 0.52*u, fill=1, stroke=0)                       # plate
            c.setFillColor(hole); c.circle(cx, cy, 0.36*u, fill=1, stroke=0)
            c.setFillColor(W);    c.circle(cx, cy, 0.24*u, fill=1, stroke=0)
            c.setLineWidth(0.20*u)                                           # fork
            c.line(cx - 0.88*u, cy - 0.55*u, cx - 0.88*u, cy + 0.55*u)
            c.setLineWidth(0.11*u)
            for dx in (-0.12, 0.0, 0.12):
                c.line(cx + (-0.88+dx)*u, cy + 0.10*u, cx + (-0.88+dx)*u, cy + 0.60*u)
            c.setLineWidth(0.18*u)                                           # knife
            c.line(cx + 0.88*u, cy - 0.55*u, cx + 0.88*u, cy + 0.20*u)
            k = c.beginPath(); k.moveTo(cx + 0.80*u, cy + 0.20*u); k.curveTo(cx + 0.78*u, cy + 0.62*u, cx + 0.96*u, cy + 0.66*u, cx + 1.0*u, cy + 0.62*u)
            k.lineTo(cx + 1.0*u, cy + 0.20*u); k.close(); c.drawPath(k, fill=1, stroke=0)
        elif kind == "boat":
            c.setLineWidth(0.11*u)                                           # canopy poles + roof
            c.line(cx - 0.50*u, cy - 0.12*u, cx - 0.50*u, cy + 0.20*u)
            c.line(cx + 0.50*u, cy - 0.12*u, cx + 0.50*u, cy + 0.20*u)
            r = c.beginPath(); r.moveTo(cx - 0.72*u, cy + 0.20*u)
            r.curveTo(cx - 0.40*u, cy + 0.72*u, cx + 0.40*u, cy + 0.72*u, cx + 0.72*u, cy + 0.20*u); r.close()
            c.drawPath(r, fill=1, stroke=0)
            h = c.beginPath(); h.moveTo(cx - 1.05*u, cy - 0.10*u)                 # curved hull
            h.curveTo(cx - 0.70*u, cy - 0.48*u, cx + 0.70*u, cy - 0.48*u, cx + 1.05*u, cy - 0.10*u)
            h.lineTo(cx - 1.05*u, cy - 0.10*u); h.close(); c.drawPath(h, fill=1, stroke=0)
            c.setLineWidth(0.10*u)                                           # water
            for yy in (-0.66, ):
                w = c.beginPath(); w.moveTo(cx - 0.95*u, cy + yy*u)
                w.curveTo(cx - 0.65*u, cy + (yy+0.16)*u, cx - 0.40*u, cy + (yy-0.12)*u, cx - 0.10*u, cy + yy*u)
                w.curveTo(cx + 0.20*u, cy + (yy+0.16)*u, cx + 0.45*u, cy + (yy-0.12)*u, cx + 0.95*u, cy + yy*u)
                c.drawPath(w, fill=0, stroke=1)
        elif kind == "cab":     # taxi: car with roof sign
            p = c.beginPath()
            p.moveTo(cx - 0.62*u, cy + 0.02*u); p.lineTo(cx - 0.38*u, cy + 0.46*u)
            p.lineTo(cx + 0.38*u, cy + 0.46*u); p.lineTo(cx + 0.62*u, cy + 0.02*u); p.close()
            c.drawPath(p, fill=1, stroke=0)
            c.roundRect(cx - 0.95*u, cy - 0.46*u, 1.9*u, 0.56*u, 0.2*u, fill=1, stroke=0)
            c.roundRect(cx - 0.24*u, cy + 0.50*u, 0.48*u, 0.20*u, 0.05*u, fill=1, stroke=0)   # roof sign
            c.setFillColor(hole)
            for dx in (-0.2, 0.2):
                q = c.beginPath()
                q.moveTo(cx + (dx-0.17)*u, cy + 0.06*u); q.lineTo(cx + (dx-0.10)*u, cy + 0.36*u)
                q.lineTo(cx + (dx+0.10)*u, cy + 0.36*u); q.lineTo(cx + (dx+0.17)*u, cy + 0.06*u); q.close()
                c.drawPath(q, fill=1, stroke=0)
            for dx in (-0.55, 0.55):
                c.setFillColor(hole); c.circle(cx + dx*u, cy - 0.46*u, 0.30*u, fill=1, stroke=0)
                c.setFillColor(W);    c.circle(cx + dx*u, cy - 0.46*u, 0.20*u, fill=1, stroke=0)
        elif kind == "gondola":  # cable car: sloped cable, hanger and cabin
            c.setLineWidth(0.10*u)
            c.line(cx - 1.05*u, cy + 0.78*u, cx + 1.05*u, cy + 0.50*u)                        # cable
            c.setLineWidth(0.12*u); c.line(cx, cy + 0.64*u, cx, cy + 0.32*u)                  # hanger
            c.roundRect(cx - 0.62*u, cy - 0.58*u, 1.24*u, 0.92*u, 0.16*u, fill=1, stroke=0)   # cabin
            c.setFillColor(hole)
            for dx in (-0.40, 0.08):
                c.roundRect(cx + dx*u, cy - 0.10*u, 0.32*u, 0.30*u, 0.05*u, fill=1, stroke=0)  # windows
            c.rect(cx - 0.62*u, cy - 0.30*u, 1.24*u, 0.06*u, fill=1, stroke=0)
        else:  # tax: receipt with zig-zag edge and ticked lines
            x0, x1, yt, yb = cx - 0.62*u, cx + 0.62*u, cy + 0.82*u, cy - 0.78*u
            r = c.beginPath(); r.moveTo(x0, yt); r.lineTo(x1, yt); r.lineTo(x1, yb)
            n = 5; step = (x1 - x0) / n
            for i in range(n):
                r.lineTo(x1 - step*(i + 0.5), yb + 0.20*u); r.lineTo(x1 - step*(i + 1), yb)
            r.lineTo(x0, yt); r.close(); c.drawPath(r, fill=1, stroke=0)
            c.setStrokeColor(hole); c.setLineWidth(0.11*u)
            for k, yy in enumerate((0.48, 0.14, -0.20)):
                c.line(cx - 0.34*u, cy + yy*u, cx + 0.34*u - (0.0 if k != 2 else 0.30*u), cy + yy*u)
        c.restoreState()

    def draw(self):
        c, w, h = self.canv, self.width, self.height
        R = 3.2 * mm
        _soft_shadow(c, 0, 0, w, h, R, layers=5, alpha=0.026)
        c.setFillColor(WHITE); c.setStrokeColor(GRAY_200); c.setLineWidth(0.6)
        c.roundRect(0, 0, w, h, R, fill=1, stroke=1)
        n = len(self.items); cw = w / n
        for i, item in enumerate(self.items):
            head, sub = item[0], item[1]
            kind = item[2] if len(item) > 2 else self._KINDS[i % 5]
            pal = self._KIND_PAL.get(kind) or self._PAL[i % 5]
            top_c, bot_c, tint, cap = (colors.HexColor(x) for x in pal)
            x0 = cw * i; cx = x0 + cw / 2
            # faint tinted wash behind the cell, fading downwards, clipped to the card
            c.saveState()
            pth = c.beginPath(); pth.roundRect(0, 0, w, h, R); c.clipPath(pth, stroke=0, fill=0)
            p2 = c.beginPath(); p2.rect(x0, 0, cw, h); c.clipPath(p2, stroke=0, fill=0)
            c.linearGradient(0, h, 0, 0, (tint, WHITE), extend=True)
            c.restoreState()
            if i:
                c.setStrokeColor(HAIR); c.setLineWidth(0.5); c.line(x0, 3 * mm, x0, h - 3 * mm)
            # coloured accent line along the top of the cell
            c.saveState()
            pth = c.beginPath(); pth.roundRect(0, 0, w, h, R); c.clipPath(pth, stroke=0, fill=0)
            c.setFillColor(bot_c); c.rect(x0, h - 0.9 * mm, cw, 0.9 * mm, fill=1, stroke=0)
            c.restoreState()
            # glossy tile with glow
            t = (8.4 if self.compact else 9.6) * mm; ty = h - (2.8 if self.compact else 3.3) * mm - t; tx = cx - t / 2
            c.saveState()
            for k in range(4, 0, -1):
                c.setFillColor(colors.Color(bot_c.red, bot_c.green, bot_c.blue, alpha=0.05))
                c.roundRect(tx - k*0.45*mm, ty - k*0.45*mm - 0.6*mm, t + k*0.9*mm, t + k*0.9*mm, 3.2*mm + k*0.4*mm, fill=1, stroke=0)
            c.restoreState()
            _grad_roundrect(c, tx, ty, t, t, 3 * mm, top_c, bot_c, "d")
            c.saveState()
            c.setStrokeColor(colors.Color(1, 1, 1, alpha=0.55)); c.setLineWidth(0.5)
            c.roundRect(tx + 0.3*mm, ty + 0.3*mm, t - 0.6*mm, t - 0.6*mm, 2.7*mm, fill=0, stroke=1)
            c.restoreState()
            self._glyph(c, kind, cx, ty + t / 2, (2.3 if self.compact else 2.6) * mm, bot_c)
            # text
            c.setFillColor(NAVY_DEEP)
            head, hfs = _fit_text(c, head, "Lato-Bold", 8.0 if n <= 6 else 7.2, cw - 3 * mm, 6.6 if n <= 6 else 5.4)
            c.setFont("Lato-Bold", hfs)
            c.drawCentredString(cx, ty - (4.0 if self.compact else 4.6) * mm, head)
            c.setFillColor(cap)
            c.setFont("Lato", _fit_font(c, sub, "Lato", 6.6, cw - 4 * mm))
            c.drawCentredString(cx, ty - (7.2 if self.compact else 8.0) * mm, sub)


class PromiseBox(Flowable):
    """Our promise: up to four commitments as columns. Each has a coloured gradient icon tile,
    a bold title and a short line of text. Items are (title, text) pairs; plain strings still work."""
    _PAL = (("#5aa9ff", "#1f63d8"),    # weather / road change - blue
            ("#2fd0c0", "#0a8f86"),    # driver details        - teal
            ("#a98bff", "#6a3fd8"),    # support               - violet
            ("#ffb347", "#e5780b"))    # no hidden charges     - amber
    _KINDS = ("cloud", "badge", "headset", "shield")
    HEAD_H = 8.2 * mm

    def __init__(self, width, lines):
        super().__init__()
        self.width = width
        self.items = []
        for t in list(lines)[:4]:
            if isinstance(t, (tuple, list)) and len(t) >= 2:
                self.items.append((str(t[0]), str(t[1])))
            else:
                self.items.append(("", str(t)))
        self.height = 28 * mm

    @staticmethod
    def _glyph(c, kind, cx, cy, u, hole):
        W = colors.white
        c.saveState()
        c.setFillColor(W); c.setStrokeColor(W); c.setLineCap(1); c.setLineJoin(1)
        if kind == "cloud":                                   # cloud with a little sun peeking out
            c.setLineWidth(0.12 * u)
            for ang in (150, 180, 210):
                import math
                dx, dy = math.cos(math.radians(ang)), math.sin(math.radians(ang))
                c.line(cx - 0.42*u + dx*0.62*u, cy + 0.36*u + dy*0.62*u + 0.2*u, cx - 0.42*u + dx*0.86*u, cy + 0.36*u + dy*0.86*u + 0.2*u)
            c.circle(cx - 0.42*u, cy + 0.50*u, 0.36*u, fill=1, stroke=0)
            c.setFillColor(hole); c.circle(cx + 0.10*u, cy - 0.04*u, 0.58*u, fill=1, stroke=0)   # cut-out ring
            c.setFillColor(W)
            c.circle(cx - 0.34*u, cy - 0.14*u, 0.34*u, fill=1, stroke=0)
            c.circle(cx + 0.10*u, cy + 0.02*u, 0.46*u, fill=1, stroke=0)
            c.circle(cx + 0.52*u, cy - 0.16*u, 0.32*u, fill=1, stroke=0)
            c.roundRect(cx - 0.68*u, cy - 0.48*u, 1.52*u, 0.36*u, 0.18*u, fill=1, stroke=0)
        elif kind == "badge":                                 # driver ID card
            c.roundRect(cx - 0.90*u, cy - 0.62*u, 1.80*u, 1.24*u, 0.20*u, fill=1, stroke=0)
            c.setFillColor(hole)
            c.circle(cx - 0.44*u, cy + 0.14*u, 0.22*u, fill=1, stroke=0)
            sh = c.beginPath(); sh.moveTo(cx - 0.84*u, cy - 0.46*u)
            sh.curveTo(cx - 0.84*u, cy - 0.14*u, cx - 0.04*u, cy - 0.14*u, cx - 0.04*u, cy - 0.46*u); sh.close()
            c.drawPath(sh, fill=1, stroke=0)
            c.setStrokeColor(hole); c.setLineWidth(0.14 * u)
            c.line(cx + 0.16*u, cy + 0.26*u, cx + 0.70*u, cy + 0.26*u)
            c.line(cx + 0.16*u, cy - 0.02*u, cx + 0.70*u, cy - 0.02*u)
            c.line(cx + 0.16*u, cy - 0.30*u, cx + 0.50*u, cy - 0.30*u)
        elif kind == "headset":
            c.setLineWidth(0.18 * u)
            arc = c.beginPath(); arc.arc(cx - 0.72*u, cy - 0.34*u, cx + 0.72*u, cy + 1.02*u, 0, 180)
            c.drawPath(arc, fill=0, stroke=1)
            c.roundRect(cx - 0.90*u, cy - 0.38*u, 0.34*u, 0.72*u, 0.14*u, fill=1, stroke=0)
            c.roundRect(cx + 0.56*u, cy - 0.38*u, 0.34*u, 0.72*u, 0.14*u, fill=1, stroke=0)
            mic = c.beginPath(); mic.moveTo(cx + 0.74*u, cy - 0.38*u)
            mic.curveTo(cx + 0.74*u, cy - 0.78*u, cx + 0.30*u, cy - 0.74*u, cx + 0.08*u, cy - 0.74*u)
            c.drawPath(mic, fill=0, stroke=1)
            c.circle(cx + 0.02*u, cy - 0.74*u, 0.14*u, fill=1, stroke=0)
        else:                                                 # shield with tick
            sh = c.beginPath(); sh.moveTo(cx, cy + 0.84*u)
            sh.lineTo(cx + 0.74*u, cy + 0.56*u); sh.lineTo(cx + 0.74*u, cy - 0.04*u)
            sh.curveTo(cx + 0.74*u, cy - 0.48*u, cx + 0.30*u, cy - 0.72*u, cx, cy - 0.86*u)
            sh.curveTo(cx - 0.30*u, cy - 0.72*u, cx - 0.74*u, cy - 0.48*u, cx - 0.74*u, cy - 0.04*u)
            sh.lineTo(cx - 0.74*u, cy + 0.56*u); sh.close()
            c.drawPath(sh, fill=1, stroke=0)
            c.setStrokeColor(hole); c.setLineWidth(0.20 * u)
            c.line(cx - 0.32*u, cy - 0.02*u, cx - 0.06*u, cy - 0.30*u)
            c.line(cx - 0.06*u, cy - 0.30*u, cx + 0.38*u, cy + 0.24*u)
        c.restoreState()

    def draw(self):
        from reportlab.lib.utils import simpleSplit
        c, w, h = self.canv, self.width, self.height
        # section label with a hairline, then four separate cards
        c.setFillColor(TEAL)
        _check_badge(c, 1.9 * mm, h - 2.6 * mm, 1.7 * mm, TEAL)
        tw = _spaced(c, 5.6 * mm, h - 3.6 * mm, "OUR PROMISE TO YOU", "Lato-Bold", 6.8, 1.1)
        c.setStrokeColor(colors.HexColor("#cfe5e0")); c.setLineWidth(0.5)
        c.line(5.6 * mm + tw + 3 * mm, h - 2.8 * mm, w, h - 2.8 * mm)

        n = max(len(self.items), 1)
        gap = 2.6 * mm
        cw = (w - gap * (n - 1)) / n
        ch = h - 6.2 * mm
        R = 2.8 * mm
        tile = 7.6 * mm
        for i, (title, text) in enumerate(self.items):
            x = i * (cw + gap)
            top_c, bot_c = (colors.HexColor(v) for v in self._PAL[i % 4])
            _soft_shadow(c, x, 0, cw, ch, R, layers=4, alpha=0.024)
            c.setFillColor(WHITE); c.setStrokeColor(colors.HexColor("#e3ebf2")); c.setLineWidth(0.6)
            c.roundRect(x, 0, cw, ch, R, fill=1, stroke=1)
            # soft tint washing in from the icon corner + coloured left edge
            c.saveState()
            pth = c.beginPath(); pth.roundRect(x, 0, cw, ch, R); c.clipPath(pth, stroke=0, fill=0)
            tint = colors.Color(bot_c.red, bot_c.green, bot_c.blue, alpha=0.07)
            c.setFillColor(tint); c.circle(x + 5 * mm, ch - 4 * mm, 17 * mm, fill=1, stroke=0)
            c.setFillColor(bot_c); c.rect(x, 0, 1.1 * mm, ch, fill=1, stroke=0)
            c.restoreState()
            tx = x + 4.2 * mm
            ty = ch - 2.6 * mm - tile
            c.saveState()
            for k in range(3, 0, -1):
                c.setFillColor(colors.Color(bot_c.red, bot_c.green, bot_c.blue, alpha=0.06))
                c.roundRect(tx - k*0.4*mm, ty - k*0.4*mm - 0.5*mm, tile + k*0.8*mm, tile + k*0.8*mm, 2.6*mm + k*0.3*mm, fill=1, stroke=0)
            c.restoreState()
            _grad_roundrect(c, tx, ty, tile, tile, 2.4 * mm, top_c, bot_c, "d")
            c.saveState()
            c.setStrokeColor(colors.Color(1, 1, 1, alpha=0.5)); c.setLineWidth(0.5)
            c.roundRect(tx + 0.3*mm, ty + 0.3*mm, tile - 0.6*mm, tile - 0.6*mm, 2.1*mm, fill=0, stroke=1)
            c.restoreState()
            self._glyph(c, self._KINDS[i % 4], tx + tile / 2, ty + tile / 2, 2.0 * mm, bot_c)
            # title sits beside the icon, the text gets the full card width underneath
            txx = tx + tile + 2.4 * mm
            tw_ = x + cw - 2.6 * mm - txx
            if title:
                tsz = _fit_font(c, title, "Lato-Bold", 8.2, tw_)
                c.setFillColor(NAVY_DEEP); c.setFont("Lato-Bold", tsz)
                c.drawString(txx, ty + tile / 2 - tsz * 0.17, title)
            bw = x + cw - 2.6 * mm - tx
            sz = 6.6
            lines = simpleSplit(text, "Lato", sz, bw)
            while len(lines) > 3 and sz > 5.6:
                sz -= 0.2; lines = simpleSplit(text, "Lato", sz, bw)
            c.setFillColor(SLATE); c.setFont("Lato", sz)
            y = ty - 3.3 * mm
            for ln in lines[:3]:
                c.drawString(tx, y, ln)
                y -= sz * 1.3 / 72 * 25.4 * mm


def _ts_icon(c, kind, cx, cy, s, col):
    """Tiny stroked glyphs for the Trip Summary badges (s = half size)."""
    c.saveState()
    c.setStrokeColor(col); c.setFillColor(col); c.setLineWidth(0.9); c.setLineCap(1); c.setLineJoin(1)
    if kind == "user":
        c.circle(cx, cy + s * 0.38, s * 0.34, fill=0, stroke=1)
        p = c.beginPath(); p.moveTo(cx - s * 0.7, cy - s * 0.75)
        p.curveTo(cx - s * 0.7, cy - s * 0.1, cx + s * 0.7, cy - s * 0.1, cx + s * 0.7, cy - s * 0.75)
        c.drawPath(p, fill=0, stroke=1)
    elif kind == "users":
        c.circle(cx - s * 0.32, cy + s * 0.38, s * 0.27, fill=0, stroke=1)
        c.circle(cx + s * 0.45, cy + s * 0.3, s * 0.22, fill=0, stroke=1)
        p = c.beginPath(); p.moveTo(cx - s * 0.95, cy - s * 0.7)
        p.curveTo(cx - s * 0.95, cy - s * 0.05, cx + s * 0.3, cy - s * 0.05, cx + s * 0.3, cy - s * 0.7)
        c.drawPath(p, fill=0, stroke=1)
    elif kind == "clock":
        c.circle(cx, cy, s * 0.82, fill=0, stroke=1)
        c.line(cx, cy, cx, cy + s * 0.5); c.line(cx, cy, cx + s * 0.38, cy - s * 0.1)
    elif kind == "pin":
        p = c.beginPath(); p.moveTo(cx, cy - s * 0.95)
        p.curveTo(cx - s * 1.0, cy + s * 0.1, cx - s * 0.7, cy + s * 0.9, cx, cy + s * 0.9)
        p.curveTo(cx + s * 0.7, cy + s * 0.9, cx + s * 1.0, cy + s * 0.1, cx, cy - s * 0.95)
        c.drawPath(p, fill=0, stroke=1); c.circle(cx, cy + s * 0.2, s * 0.26, fill=1, stroke=0)
    elif kind == "flag":
        c.line(cx - s * 0.6, cy - s * 0.9, cx - s * 0.6, cy + s * 0.9)
        p = c.beginPath(); p.moveTo(cx - s * 0.6, cy + s * 0.85); p.lineTo(cx + s * 0.8, cy + s * 0.85)
        p.lineTo(cx + s * 0.4, cy + s * 0.4); p.lineTo(cx + s * 0.8, cy - s * 0.05); p.lineTo(cx - s * 0.6, cy - s * 0.05)
        c.drawPath(p, fill=0, stroke=1)
    elif kind == "tag":
        p = c.beginPath(); p.moveTo(cx - s * 0.85, cy + s * 0.1); p.lineTo(cx + s * 0.1, cy + s * 0.95)
        p.lineTo(cx + s * 0.9, cy + s * 0.95); p.lineTo(cx + s * 0.9, cy + s * 0.15); p.lineTo(cx + s * 0.05, cy - s * 0.85); p.close()
        c.drawPath(p, fill=0, stroke=1); c.circle(cx + s * 0.5, cy + s * 0.55, s * 0.14, fill=1, stroke=0)
    elif kind == "calendar":
        c.roundRect(cx - s * 0.85, cy - s * 0.8, s * 1.7, s * 1.55, s * 0.18, fill=0, stroke=1)
        c.line(cx - s * 0.85, cy + s * 0.25, cx + s * 0.85, cy + s * 0.25)
        c.line(cx - s * 0.4, cy + s * 0.6, cx - s * 0.4, cy + s * 1.0); c.line(cx + s * 0.4, cy + s * 0.6, cx + s * 0.4, cy + s * 1.0)
    elif kind == "mail":
        c.roundRect(cx - s * 0.9, cy - s * 0.6, s * 1.8, s * 1.2, s * 0.15, fill=0, stroke=1)
        c.line(cx - s * 0.9, cy + s * 0.55, cx, cy - s * 0.1); c.line(cx + s * 0.9, cy + s * 0.55, cx, cy - s * 0.1)
    elif kind == "car":
        c.restoreState(); _line_icon(c, "car", cx, cy, s, col); return
    elif kind == "coin":
        c.circle(cx, cy, s * 0.85, fill=0, stroke=1)
        c.line(cx - s * 0.35, cy + s * 0.38, cx + s * 0.35, cy + s * 0.38); c.line(cx - s * 0.35, cy + s * 0.08, cx + s * 0.35, cy + s * 0.08)
        c.line(cx - s * 0.35, cy + s * 0.38, cx + s * 0.1, cy - s * 0.45)
    c.restoreState()


_TS_ICONS = {"CLIENT NAME": "user", "TOUR DURATION": "clock", "GUESTS": "users", "START POINT": "pin",
             "BUDGET TIER": "tag", "QUOTE VALID UNTIL": "calendar", "EMAIL": "mail", "TRAVEL DATE": "calendar",
             "VEHICLE": "car", "END POINT": "flag", "ESTIMATED COST": "coin"}


class TripSummary(Flowable):
    """Trip facts card. Navy header (budget tier + quote no.), a 'prepared for' row with the
    validity pill, a journey line (start -> end), four fact columns with tinted icon discs,
    and the estimated cost as a full-width emerald total bar."""
    HEAD_H = 9 * mm
    # (row A client, row B journey, row C facts, total bar), normal and compact
    _DIM = ((13.0 * mm, 12.0 * mm, 13.0 * mm, 11.0 * mm), (11.2 * mm, 10.4 * mm, 11.4 * mm, 10.0 * mm))

    def __init__(self, width, left, right, ref="", valid="", email=""):
        super().__init__()
        self.width, self.ref, self.valid, self.email = width, ref, valid, email
        self.tier, self.cost = "", None
        self.info = {}
        for label, value, hot in list(left) + list(right):
            if label == "BUDGET TIER":
                self.tier = str(value)
            elif hot:
                self.cost = str(value)
            else:
                self.info[label] = value
        self.compact = False
        self._recalc()

    def _recalc(self):
        a, j, f, bar = self._DIM[1 if self.compact else 0]
        self.height = self.HEAD_H + a + j + f + (bar if self.cost else 0)

    def draw(self):
        c, w, h = self.canv, self.width, self.height
        R = 3.5 * mm
        rowA, rowJ, rowF, BAR = self._DIM[1 if self.compact else 0]
        if not self.cost:
            BAR = 0
        y_a = h - self.HEAD_H                 # top of row A
        y_j = y_a - rowA                      # top of journey row
        y_f = y_j - rowJ                      # top of facts row
        y_b = y_f - rowF                      # top of total bar (= BAR)

        _soft_shadow(c, 0, 0, w, h, R, layers=5, alpha=0.03)
        c.setFillColor(WHITE); c.setStrokeColor(GRAY_200); c.setLineWidth(0.6)
        c.roundRect(0, 0, w, h, R, fill=1, stroke=1)

        # ---- header band ----
        c.saveState()
        p = c.beginPath(); p.roundRect(0, 0, w, h, R); c.clipPath(p, stroke=0, fill=0)
        p2 = c.beginPath(); p2.rect(0, y_a, w, self.HEAD_H); c.clipPath(p2, stroke=0, fill=0)
        c.linearGradient(0, 0, w, 0, (NAVY_DEEP, NAVY_MID), extend=True)
        c.restoreState()
        c.setFillColor(GOLD_MID); c.rect(0, y_a - 0.5 * mm, w, 0.9 * mm, fill=1, stroke=0)
        _diamond(c, 7 * mm, h - self.HEAD_H / 2, 1.5 * mm, colors.HexColor("#f5b82e"))
        c.setFillColor(WHITE)
        _spaced(c, 11.5 * mm, h - self.HEAD_H / 2 - 1.1 * mm, "TRIP SUMMARY", "Lato-Bold", 9, 1.6)
        rx = w - 6 * mm
        if self.ref:
            c.setFillColor(colors.HexColor("#93c5fd"))
            ref_txt = "QUOTE  " + _raw(self.ref)
            _spaced(c, rx, h - self.HEAD_H / 2 - 1.0 * mm, ref_txt, "Lato-Bold", 7.4, 0.8, "r")
            rx -= c.stringWidth(ref_txt, "Lato-Bold", 7.4) + len(ref_txt) * 0.8 + 4 * mm
        if self.tier:
            t = _raw(self.tier).upper()
            c.setFont("Lato-Bold", 7)
            tw = c.stringWidth(t, "Lato-Bold", 7) + len(t) * 0.5 + 5 * mm
            c.setFillColor(colors.HexColor("#f5b82e"))
            c.roundRect(rx - tw, h - self.HEAD_H / 2 - 2.6 * mm, tw, 5.2 * mm, 2.6 * mm, fill=1, stroke=0)
            c.setFillColor(NAVY_DEEP)
            _spaced(c, rx - tw / 2, h - self.HEAD_H / 2 - 0.9 * mm, t, "Lato-Bold", 7, 0.5, "c")

        # ---- row A: prepared for + validity pill ----
        c.saveState()
        p = c.beginPath(); p.roundRect(0, 0, w, h, R); c.clipPath(p, stroke=0, fill=0)
        p2 = c.beginPath(); p2.rect(0, y_j, w, rowA - 0.5 * mm); c.clipPath(p2, stroke=0, fill=0)
        c.linearGradient(0, 0, w, 0, (colors.HexColor("#f6f9fd"), WHITE), extend=True)
        c.restoreState()
        name = _raw(self.info.get("CLIENT NAME", "")) or "Guest"
        ymid = y_j + (rowA - 0.5 * mm) / 2
        ar = min(4.1 * mm, (rowA - 3 * mm) / 2)
        _grad_roundrect(c, 6 * mm, ymid - ar, 2 * ar, 2 * ar, ar, SKY_MID, NAVY_MID, "d")
        c.setFillColor(WHITE); c.setFont("Lato-Bold", 10.5)
        c.drawCentredString(6 * mm + ar, ymid - 3.6, (name.strip()[:1] or "G").upper())
        nx = 6 * mm + 2 * ar + 3 * mm
        c.setFillColor(INK_SOFT)
        lw_ = _spaced(c, nx, ymid + 2.9 * mm, "PREPARED FOR", "Lato-Bold", 5.8, 1.0)
        if self.email:
            c.setFont("Lato", 6.2); c.setFillColor(colors.HexColor("#94a3b8"))
            c.drawString(nx + lw_ + 3 * mm, ymid + 2.9 * mm, _raw(self.email))
        pill_w = 41 * mm
        nm, nfs = _fit_text(c, name, "Lato-Bold", 13, w - nx - pill_w - 12 * mm, 9)
        c.setFillColor(NAVY_DEEP); c.setFont("Lato-Bold", nfs)
        c.drawString(nx, ymid - 4.2 * mm, nm)
        if self.valid:
            ph = min(9.2 * mm, rowA - 3 * mm)
            px, py = w - 6 * mm - pill_w, ymid - ph / 2
            c.setFillColor(colors.HexColor("#fff8e6")); c.setStrokeColor(colors.HexColor("#f6dfa0")); c.setLineWidth(0.6)
            c.roundRect(px, py, pill_w, ph, ph / 2, fill=1, stroke=1)
            _ts_icon(c, "calendar", px + 5.2 * mm, ymid, 1.9 * mm, GOLD_MID)
            c.setFillColor(GOLD)
            _spaced(c, px + 9.4 * mm, ymid + 0.9 * mm, "QUOTE VALID UNTIL", "Lato-Bold", 5.2, 0.7)
            c.setFillColor(NAVY_DEEP); c.setFont("Lato-Bold", 8.8)
            c.drawString(px + 9.4 * mm, ymid - 3.0 * mm, _raw(self.valid))

        # ---- row B: journey line ----
        c.setStrokeColor(colors.HexColor("#e8eef5")); c.setLineWidth(0.5)
        c.line(5 * mm, y_j, w - 5 * mm, y_j)
        jm = y_j - rowJ / 2
        sp = _raw(self.info.get("START POINT", "")) or "-"
        ep = _raw(self.info.get("END POINT", "")) or "-"
        side_max = w * 0.30
        sp, sfs = _fit_text(c, sp, "Lato-Bold", 9.6, side_max, 7.4)
        ep, efs = _fit_text(c, ep, "Lato-Bold", 9.6, side_max, 7.4)
        # start: hollow ring; end: filled flag disc
        c.setStrokeColor(SKY); c.setFillColor(WHITE); c.setLineWidth(1.3)
        c.circle(7.4 * mm, jm, 1.6 * mm, fill=1, stroke=1)
        c.setFillColor(INK_SOFT)
        _spaced(c, 11.6 * mm, jm + 1.6 * mm, "START POINT", "Lato-Bold", 5.6, 0.9)
        c.setFillColor(NAVY_DEEP); c.setFont("Lato-Bold", sfs); c.drawString(11.6 * mm, jm - 3.0 * mm, sp)
        c.setFillColor(TEAL); c.circle(w - 7.4 * mm, jm, 1.9 * mm, fill=1, stroke=0)
        _ts_icon(c, "flag", w - 7.4 * mm, jm, 1.0 * mm, WHITE)
        c.setFillColor(INK_SOFT)
        _spaced(c, w - 11.6 * mm, jm + 1.6 * mm, "END POINT", "Lato-Bold", 5.6, 0.9, "r")
        c.setFillColor(NAVY_DEEP); c.setFont("Lato-Bold", efs); c.drawRightString(w - 11.6 * mm, jm - 3.0 * mm, ep)
        lx0 = 11.6 * mm + c.stringWidth(sp, "Lato-Bold", sfs) + 5 * mm
        lx1 = w - 11.6 * mm - c.stringWidth(ep, "Lato-Bold", efs) - 5 * mm
        if lx1 - lx0 > 22 * mm:
            c.setStrokeColor(colors.HexColor("#b9d4e8")); c.setLineWidth(0.9); c.setDash(1.2, 1.8); c.setLineCap(1)
            c.line(lx0, jm, lx1, jm); c.setDash()
            mx = (lx0 + lx1) / 2
            c.setFillColor(WHITE); c.setStrokeColor(colors.HexColor("#b9d4e8")); c.setLineWidth(0.8)
            c.circle(mx, jm, 3.3 * mm, fill=1, stroke=1)
            _ts_icon(c, "car", mx, jm, 1.9 * mm, SKY)

        # ---- row C: four facts ----
        c.setStrokeColor(colors.HexColor("#e8eef5")); c.setLineWidth(0.5)
        c.line(5 * mm, y_f, w - 5 * mm, y_f)
        facts = (("TOUR DURATION", "clock", "#0284c7"), ("GUESTS", "users", "#6a3fd8"),
                 ("VEHICLE", "car", "#e5780b"), ("TRAVEL DATE", "calendar", "#0a8f86"))
        cw = w / 4
        fm = y_f - rowF / 2
        for i, (label, icon, hexc) in enumerate(facts):
            col = colors.HexColor(hexc)
            x0 = cw * i
            if i:
                c.setStrokeColor(colors.HexColor("#e8eef5")); c.setLineWidth(0.5)
                c.line(x0, y_f - 2.2 * mm, x0, y_b + 2.2 * mm)
            dr = 3.4 * mm
            dx = x0 + 5 * mm + dr
            c.setFillColor(colors.Color(col.red, col.green, col.blue, alpha=0.12))
            c.circle(dx, fm, dr, fill=1, stroke=0)
            _ts_icon(c, icon, dx, fm, 1.9 * mm, col)
            tx = dx + dr + 2.4 * mm
            c.setFillColor(INK_SOFT)
            _spaced(c, tx, fm + 1.5 * mm, label, "Lato-Bold", 5.6, 0.8)
            v, fs = _fit_text(c, _raw(self.info.get(label, "")) or "-", "Lato-Bold", 10, x0 + cw - 3 * mm - tx, 7)
            c.setFillColor(NAVY_DEEP); c.setFont("Lato-Bold", fs)
            c.drawString(tx, fm - 3.3 * mm, v)

        # ---- total bar ----
        if self.cost:
            c.saveState()
            p = c.beginPath(); p.roundRect(0, 0, w, h, R); c.clipPath(p, stroke=0, fill=0)
            p2 = c.beginPath(); p2.rect(0, 0, w, BAR); c.clipPath(p2, stroke=0, fill=0)
            c.linearGradient(0, 0, w, 0, (colors.HexColor("#10b981"), colors.HexColor("#047857")), extend=True)
            c.setFillColor(colors.Color(1, 1, 1, alpha=0.10)); c.rect(0, BAR - 0.5 * mm, w, 0.5 * mm, fill=1, stroke=0)
            c.restoreState()
            my = BAR / 2
            _check_badge(c, 8.4 * mm, my, 2.1 * mm, colors.Color(1, 1, 1, alpha=0.22), tick=WHITE)
            c.setFillColor(colors.HexColor("#d1fae5"))
            _spaced(c, 13 * mm, my + 0.4 * mm, "ESTIMATED TOTAL COST", "Lato-Bold", 7.4, 1.2)
            c.setFillColor(colors.HexColor("#a7f3d0")); c.setFont("Lato", 5.8)
            c.drawString(13 * mm, my - 3.0 * mm, "Stay, car, driver, meals and taxes as listed")
            c.setFillColor(WHITE); c.setFont("Lato-Bold", 16.5)
            c.drawRightString(w - 8 * mm, my - 2.3 * mm, _raw(self.cost))


class TrustStrip(Flowable):
    """Dark proof band: five stat columns on the left, one guest quote on a glass panel on the right."""
    def __init__(self, width, stats, quote, by):
        super().__init__()
        self.width, self.height, self.stats, self.quote, self.by = width, 22 * mm, stats, quote, by

    @staticmethod
    def _cap_lines(cap):
        cap = cap.replace("\u00b7", " ").split()
        # up to two short lines, balanced
        if len(cap) <= 1:
            return [" ".join(cap)]
        best = min(range(1, len(cap)), key=lambda k: abs(len(" ".join(cap[:k])) - len(" ".join(cap[k:]))))
        return [" ".join(cap[:best]), " ".join(cap[best:])]

    def draw(self):
        from reportlab.lib.utils import simpleSplit
        c, w, h = self.canv, self.width, self.height
        R = 3.2 * mm
        _soft_shadow(c, 0, 0, w, h, R, layers=4, alpha=0.03)
        _grad_roundrect(c, 0, 0, w, h, R, colors.HexColor("#1a2740"), colors.HexColor("#0a1120"), "d")
        c.saveState()
        p = c.beginPath(); p.roundRect(0, 0, w, h, R); c.clipPath(p, stroke=0, fill=0)
        p2 = c.beginPath(); p2.rect(0, h - 0.8 * mm, w, 0.8 * mm); c.clipPath(p2, stroke=0, fill=0)
        c.linearGradient(0, 0, w, 0, (colors.HexColor("#1a2740"), SAFFRON, colors.HexColor("#1a2740")), (0, 0.5, 1), extend=False)
        c.restoreState()

        qw = w * 0.355                              # quote panel width
        sx0, sw = 3 * mm, w - qw - 7 * mm            # stats area
        n = len(self.stats); cw = sw / n
        for i, (val, cap) in enumerate(self.stats):
            cx = sx0 + cw * i + cw / 2
            if i:
                c.setStrokeColor(colors.Color(1, 1, 1, alpha=0.11)); c.setLineWidth(0.5)
                c.line(sx0 + cw * i, h * 0.28, sx0 + cw * i, h * 0.76)
            c.setFillColor(SAFFRON if i == 0 else WHITE)
            c.setFont("Lato-Bold", 12.6)
            c.drawCentredString(cx, h * 0.55, val)
            c.setFillColor(colors.HexColor("#9fb0c6"))
            lines = self._cap_lines(cap)
            fs = 5.0
            while max(c.stringWidth(l, "Lato-Bold", fs) + 0.4 * len(l) for l in lines) > cw - 2 * mm and fs > 4.0:
                fs -= 0.1
            for k, l in enumerate(lines):
                _spaced(c, cx, h * 0.55 - 3.7 * mm - k * (fs * 1.25 / 72 * 25.4 * mm), l, "Lato-Bold", fs, 0.4, "c")

        # quote panel (glass card)
        px, py, pw, ph = w - qw - 2.6 * mm, 2.6 * mm, qw, h - 5.4 * mm
        c.setFillColor(colors.Color(1, 1, 1, alpha=0.07)); c.setStrokeColor(colors.Color(1, 1, 1, alpha=0.14)); c.setLineWidth(0.5)
        c.roundRect(px, py, pw, ph, 2.4 * mm, fill=1, stroke=1)
        c.setFillColor(colors.Color(SAFFRON.red, SAFFRON.green, SAFFRON.blue, alpha=0.9))
        c.setFont("Lato-Bold", 22); c.drawString(px + 2.6 * mm, py + ph - 7.2 * mm, "\u201c")
        for k in range(5):
            _star(c, px + 11.2 * mm + k * 2.6 * mm, py + ph - 3.7 * mm, 1.15 * mm, SAFFRON)
        tw_ = pw - 5.2 * mm
        sz = 6.5
        q = self.quote
        lines = simpleSplit(q, "Lato-Italic", sz, tw_)
        while len(lines) > 3 and sz > 5.2:
            sz -= 0.2; lines = simpleSplit(q, "Lato-Italic", sz, tw_)
        c.setFillColor(colors.HexColor("#e2e8f0")); c.setFont("Lato-Italic", sz)
        y = py + ph - 8.0 * mm
        for ln in lines[:3]:
            c.drawString(px + 2.6 * mm, y, ln); y -= sz * 1.3 / 72 * 25.4 * mm
        c.setFillColor(SAFFRON); c.setFont("Lato-Bold", 5.8)
        c.drawString(px + 2.6 * mm, py + 1.9 * mm, "\u2014 " + self.by)


class NextSteps(Flowable):
    """What happens after the client says yes: a compact three-step line."""
    def __init__(self, width, steps):
        super().__init__()
        self.width, self.height, self.steps = width, 15 * mm, steps

    def draw(self):
        c, w, h = self.canv, self.width, self.height
        c.setFillColor(NAVY)
        tw = _spaced(c, 0, h - 3.2 * mm, "WHAT HAPPENS NEXT", "Lato-Bold", 6.6, 1.0)
        c.setStrokeColor(GRAY_200); c.setLineWidth(0.5)
        c.line(tw + 3 * mm, h - 2.4 * mm, w, h - 2.4 * mm)
        n = len(self.steps); cw = w / n; r = 2.7 * mm; cy = h - 9.6 * mm
        for i, (head, sub) in enumerate(self.steps):
            x = i * cw
            if i < n - 1:                                   # connector to the next step
                c.setStrokeColor(colors.HexColor("#bcd9ec")); c.setLineWidth(0.7); c.setDash(1, 1.6)
                c.line(x + cw - 6 * mm, cy, x + cw - 1 * mm, cy); c.setDash()
            _grad_roundrect(c, x, cy - r, 2 * r, 2 * r, r, SKY_MID, SKY, "v")
            c.setFillColor(WHITE); c.setFont("Lato-Bold", 8)
            c.drawCentredString(x + r, cy - 2.8, str(i + 1))
            c.setFillColor(NAVY_DEEP); c.setFont("Lato-Bold", 7.8)
            c.drawString(x + 2 * r + 2.4 * mm, cy + 0.9 * mm, head)
            c.setFillColor(INK_SOFT)
            c.setFont("Lato", _fit_font(c, sub, "Lato", 6.6, cw - 2 * r - 9 * mm))
            c.drawString(x + 2 * r + 2.4 * mm, cy - 2.7 * mm, sub)


def _trip_story(timeline):
    blob = " ".join(str(d.get("transit_route") or "") + " " + str(d.get("title") or "") for d in (timeline or [])).lower()
    n = sum(1 for k in ("sonamarg", "gulmarg", "pahalgam", "doodhpathri") if k in blob)
    if n >= 2:
        return f"{n} valleys, 1 shikara ride, and a driver who looks after everything"
    return "A Kashmir trip planned around you, with a driver who looks after everything"


class IncludedExcluded(Flowable):
    """Inclusions and exclusions as two cards in the same look as the hotel / travel cards:
    a medallion heading, a divider, then ticked (or crossed) lines."""
    PAD, HEAD_H, GAP = 5 * mm, 12 * mm, 4 * mm

    def __init__(self, width, inc, exc, compact=False):
        super().__init__()
        self.width, self.inc, self.exc = width, [_raw(i) for i in inc], [_raw(i) for i in exc]
        self.compact = compact
        self._recalc()

    def _recalc(self):
        self.fs = 7.2 if self.compact else 7.8
        self.lead = 3.2 * mm if self.compact else 3.5 * mm
        self.igap = 1.6 * mm if self.compact else 2.3 * mm
        self.cw = (self.width - self.GAP) / 2
        self.tw = self.cw - self.PAD - 7.5 * mm - 4 * mm
        def body(items):
            return sum(min(len(simpleSplit(t, "Lato", self.fs, self.tw)), 3) * self.lead + self.igap for t in items)
        self.card_h = self.HEAD_H + 2 * mm + max(body(self.inc), body(self.exc)) + 2 * mm
        self.height = self.card_h

    def wrap(self, aw, ah):
        return (self.width, self.height)

    def _card(self, c, x, items, title, sub, ring, tint, tick):
        h, cw = self.card_h, self.cw
        c.setFillColor(WHITE); c.setStrokeColor(GRAY_200); c.setLineWidth(0.5)
        c.roundRect(x, 0, cw, h, 2 * mm, fill=1, stroke=1)
        c.setFillColor(ring); c.roundRect(x, 0, 1.4 * mm, h, 0.7 * mm, fill=1, stroke=0)
        mx, my = x + self.PAD + 3.6 * mm, h - 6.4 * mm
        c.setFillColor(WHITE); c.setStrokeColor(ring); c.setLineWidth(1.5); c.circle(mx, my, 4.0 * mm, fill=1, stroke=1)
        c.setFillColor(tint); c.circle(mx, my, 3.1 * mm, fill=1, stroke=0)
        if tick:
            _check_tick(c, mx, my, 1.35 * mm, ring)
        else:
            c.setStrokeColor(ring); c.setLineWidth(1.0); c.setLineCap(1)
            d = 1.25 * mm
            c.line(mx - d, my - d, mx + d, my + d); c.line(mx - d, my + d, mx + d, my - d)
        c.setFillColor(NAVY); c.setFont("Lato-Bold", 9.4); c.drawString(x + self.PAD + 10 * mm, my + 0.7 * mm, title)
        c.setFillColor(GRAY_400); c.setFont("Lato", 6.6); c.drawString(x + self.PAD + 10 * mm, my - 2.9 * mm, sub)
        c.setStrokeColor(GRAY_200); c.setLineWidth(0.4)
        c.line(x + 4 * mm, h - self.HEAD_H, x + cw - 4 * mm, h - self.HEAD_H)
        y = h - self.HEAD_H - 4.6 * mm
        for t in items:
            lines = simpleSplit(t, "Lato", self.fs, self.tw)[:3]
            cx, cy = x + self.PAD + 2.2 * mm, y + 1.05 * mm
            c.setFillColor(tint); c.circle(cx, cy, 1.9 * mm, fill=1, stroke=0)
            if tick:
                _check_tick(c, cx, cy, 0.9 * mm, ring)
            else:
                c.setStrokeColor(ring); c.setLineWidth(0.9); c.setLineCap(1); d = 0.8 * mm
                c.line(cx - d, cy - d, cx + d, cy + d); c.line(cx - d, cy + d, cx + d, cy - d)
            c.setFillColor(GRAY_600); c.setFont("Lato", self.fs)
            for ln in lines:
                c.drawString(x + self.PAD + 7.5 * mm, y, ln); y -= self.lead
            y -= self.igap

    def draw(self):
        c = self.canv
        self._card(c, 0, self.inc, "What's included", f"{len(self.inc)} items in your price", EMERALD, EMERALD_LITE, True)
        self._card(c, self.cw + self.GAP, self.exc, "Not included", "Pay directly if you need these", ROSE, colors.HexColor("#ffe4e6"), False)


class PaymentPlan(Flowable):
    """Payment schedule as three instalment cards joined by a progress line, then a pay-by strip.
    rows: [(label, pct, amount_text, due, due_note, mode, status)]"""
    HEAD, GAP = 14 * mm, 3 * mm

    def __init__(self, width, rows, pay_label, pay_text, compact=False):
        super().__init__()
        self.width, self.rows = width, rows
        self.pay_label, self.pay_text = pay_label, _raw(pay_text)
        self.compact = compact
        self._recalc()

    def _recalc(self):
        self.cw = (self.width - 2 * self.GAP) / 3
        self.card_h = 33 * mm if self.compact else 38 * mm
        self.strip_tw = self.width - 6 * mm - 30 * mm
        self.pay_lines = simpleSplit(self.pay_text, "Lato", 7.4, self.strip_tw)[:2]
        self.strip_h = (7.5 + 3.2 * (len(self.pay_lines) - 1)) * mm + 1.2 * mm
        self.height = self.card_h + 3 * mm + self.strip_h

    def wrap(self, aw, ah):
        return (self.width, self.height)

    def draw(self):
        c, ch = self.canv, self.card_h
        y0 = self.strip_h + 3 * mm
        palette = [(SKY, SKY_LIGHT), (TEAL, TEAL_LITE), (NAVY, GRAY_100)]
        c.saveState(); c.translate(0, y0)
        for i, (label, pct, amt, due, note, mode, status) in enumerate(self.rows):
            x = i * (self.cw + self.GAP)
            ring, tint = palette[i % 3]
            c.setFillColor(WHITE); c.setStrokeColor(GRAY_200); c.setLineWidth(0.5)
            c.roundRect(x, 0, self.cw, ch, 2 * mm, fill=1, stroke=1)
            c.setFillColor(ring); c.roundRect(x, 0, self.cw, 1.4 * mm, 0.7 * mm, fill=1, stroke=0)
            # numbered medallion + title
            mx, my = x + 8 * mm, ch - 7.6 * mm
            c.setFillColor(WHITE); c.setStrokeColor(ring); c.setLineWidth(1.5); c.circle(mx, my, 4.0 * mm, fill=1, stroke=1)
            c.setFillColor(ring); c.circle(mx, my, 3.1 * mm, fill=1, stroke=0)
            c.setFillColor(WHITE); c.setFont("Lato-Bold", 9); c.drawCentredString(mx, my - 1.2 * mm, str(i + 1))
            c.setFillColor(NAVY); c.setFont("Lato-Bold", 9); c.drawString(x + 14 * mm, my + 0.5 * mm, label)
            c.setFillColor(GRAY_400); c.setFont("Lato", 6.6); c.drawString(x + 14 * mm, my - 3.1 * mm, mode)
            # share pill (top right)
            ptxt = f"{pct}%"
            pw = c.stringWidth(ptxt, "Lato-Bold", 7.4) + 5 * mm
            c.setFillColor(tint); c.roundRect(x + self.cw - pw - 3.5 * mm, ch - 8.6 * mm, pw, 4.6 * mm, 2.3 * mm, fill=1, stroke=0)
            c.setFillColor(ring); c.setFont("Lato-Bold", 7.4); c.drawCentredString(x + self.cw - pw / 2 - 3.5 * mm, ch - 7.1 * mm, ptxt)
            # amount
            c.setStrokeColor(GRAY_200); c.setLineWidth(0.4)
            c.line(x + 4 * mm, ch - 13.2 * mm, x + self.cw - 4 * mm, ch - 13.2 * mm)
            c.setFillColor(EMERALD); c.setFont("Lato-Bold", 14); c.drawString(x + 5 * mm, ch - 20.2 * mm, amt)
            # due
            c.setFillColor(BLACK); c.setFont("Lato-Bold", 7.6); c.drawString(x + 5 * mm, ch - 25.4 * mm, due)
            if note:
                c.setFillColor(GRAY_600); c.setFont("Lato", 6.8); c.drawString(x + 5 * mm, ch - 29 * mm, note)
            # status pill (bottom right)
            stw = c.stringWidth(status, "Lato-Bold", 6.8) + 5 * mm
            c.setFillColor(GOLD_LITE); c.roundRect(x + self.cw - stw - 3.5 * mm, 2.6 * mm, stw, 4.3 * mm, 2.1 * mm, fill=1, stroke=0)
            c.setFillColor(GOLD); c.setFont("Lato-Bold", 6.8); c.drawCentredString(x + self.cw - stw / 2 - 3.5 * mm, 4.0 * mm, status)
            if i < 2:                                                  # arrow chevron joining the cards
                ax = x + self.cw + self.GAP / 2
                c.setFillColor(WHITE); c.setStrokeColor(GRAY_200); c.setLineWidth(0.5)
                c.circle(ax, ch / 2, 2.0 * mm, fill=1, stroke=1)
                c.setStrokeColor(GRAY_400); c.setLineWidth(0.8); c.setLineCap(1)
                c.line(ax - 0.5 * mm, ch / 2 + 0.9 * mm, ax + 0.5 * mm, ch / 2); c.line(ax + 0.5 * mm, ch / 2, ax - 0.5 * mm, ch / 2 - 0.9 * mm)
        c.restoreState()
        # pay-by strip
        sh = self.strip_h
        c.setFillColor(GRAY_50); c.setStrokeColor(GRAY_200); c.setLineWidth(0.5)
        c.roundRect(0, 0, self.width, sh, 2 * mm, fill=1, stroke=1)
        c.setFillColor(SKY); c.roundRect(0, 0, 1.4 * mm, sh, 0.7 * mm, fill=1, stroke=0)
        lw = c.stringWidth(self.pay_label, "Lato-Bold", 7.2) + 6 * mm
        c.setFillColor(SKY_LIGHT); c.roundRect(5 * mm, sh / 2 - 2.5 * mm, lw, 5 * mm, 2.5 * mm, fill=1, stroke=0)
        c.setFillColor(SKY); c.setFont("Lato-Bold", 7.2); c.drawString(8 * mm, sh / 2 - 0.9 * mm, self.pay_label)
        c.setFillColor(GRAY_600); c.setFont("Lato", 7.4)
        ty = sh / 2 + (len(self.pay_lines) - 1) * 1.6 * mm - 1.0 * mm
        for ln in self.pay_lines:
            c.drawString(5 * mm + lw + 3 * mm, ty, ln); ty -= 3.2 * mm



def _fit_font(c, text, font, size, max_w, min_size=6.2):
    while size > min_size and c.stringWidth(text, font, size) > max_w:
        size -= 0.2
    return size


class CancellationLadder(Flowable):
    """Refund schedule as four step cards (green to red) plus a force-majeure strip.
    tiers: [(when, charge, refund_pct_int, refund_text, processing)]"""
    GAP = 3 * mm
    TONES = [(EMERALD, EMERALD_LITE), (colors.HexColor("#65a30d"), colors.HexColor("#ecfccb")),
             (GOLD_MID, GOLD_LITE), (ROSE, colors.HexColor("#ffe4e6"))]

    def __init__(self, width, tiers, note_title, note_text, compact=False):
        super().__init__()
        self.width, self.tiers = width, tiers
        self.note_title, self.note_text = _raw(note_title), _raw(note_text)
        self.compact = compact
        self._recalc()

    def _recalc(self):
        self.cw = (self.width - 3 * self.GAP) / 4
        self.card_h = 38 * mm if self.compact else 42 * mm
        self.strip_h = 10 * mm
        self.height = self.card_h + 3 * mm + self.strip_h

    def wrap(self, aw, ah):
        return (self.width, self.height)

    def draw(self):
        c, ch, cw = self.canv, self.card_h, self.cw
        y0 = self.strip_h + 3 * mm
        c.saveState(); c.translate(0, y0)
        for i, (when, charge, pct, rtxt, proc) in enumerate(self.tiers[:4]):
            x = i * (cw + self.GAP)
            ring, tint = self.TONES[i]
            c.setFillColor(WHITE); c.setStrokeColor(GRAY_200); c.setLineWidth(0.5)
            c.roundRect(x, 0, cw, ch, 2 * mm, fill=1, stroke=1)
            c.setFillColor(ring); c.roundRect(x, ch - 1.4 * mm, cw, 1.4 * mm, 0.7 * mm, fill=1, stroke=0)
            tw = cw - 8 * mm
            c.setFillColor(GRAY_400); c.setFont("Lato-Bold", 6.2); c.drawString(x + 4 * mm, ch - 6 * mm, "IF YOU CANCEL")
            c.setFillColor(NAVY); c.setFont("Lato-Bold", 8.2)
            y = ch - 10.2 * mm
            for ln in simpleSplit(_raw(when), "Lato-Bold", 8.2, tw)[:2]:
                c.drawString(x + 4 * mm, y, ln); y -= 3.5 * mm
            c.setStrokeColor(GRAY_200); c.setLineWidth(0.4)
            c.line(x + 4 * mm, ch - 17.2 * mm, x + cw - 4 * mm, ch - 17.2 * mm)
            c.setFillColor(ring); c.setFont("Lato-Bold", 17); c.drawString(x + 4 * mm, ch - 24.6 * mm, rtxt)
            rw = c.stringWidth(rtxt, "Lato-Bold", 17)
            c.setFillColor(GRAY_400); c.setFont("Lato-Bold", 6.2); c.drawString(x + 4 * mm + rw + 1.6 * mm, ch - 24.6 * mm, "REFUND")
            c.setFillColor(tint); c.roundRect(x + 4 * mm, ch - 28.6 * mm, tw, 1.8 * mm, 0.9 * mm, fill=1, stroke=0)
            if pct > 0:
                c.setFillColor(ring); c.roundRect(x + 4 * mm, ch - 28.6 * mm, max(tw * pct / 100.0, 1.8 * mm), 1.8 * mm, 0.9 * mm, fill=1, stroke=0)
            c.setFillColor(GRAY_600); c.setFont("Lato", 7)
            y = ch - 32.4 * mm
            for ln in simpleSplit(_raw(charge), "Lato", 7, tw)[:2]:
                c.drawString(x + 4 * mm, y, ln); y -= 3.1 * mm
            c.setFillColor(GRAY_400); c.setFont("Lato-Italic", 6.4)
            c.drawString(x + 4 * mm, 3 * mm, _raw(proc))
        c.restoreState()
        sh = self.strip_h
        c.setFillColor(GRAY_50); c.setStrokeColor(GRAY_200); c.setLineWidth(0.5)
        c.roundRect(0, 0, self.width, sh, 2 * mm, fill=1, stroke=1)
        c.setFillColor(SKY); c.roundRect(0, 0, 1.4 * mm, sh, 0.7 * mm, fill=1, stroke=0)
        mx, my = 8 * mm, sh / 2                                     # shield medallion
        c.setFillColor(WHITE); c.setStrokeColor(SKY); c.setLineWidth(1.2); c.circle(mx, my, 3.4 * mm, fill=1, stroke=1)
        c.setFillColor(SKY_LIGHT); c.circle(mx, my, 2.6 * mm, fill=1, stroke=0)
        c.setStrokeColor(SKY); c.setLineWidth(0.9); c.setLineJoin(1)
        pth = c.beginPath(); pth.moveTo(mx, my + 1.7 * mm); pth.lineTo(mx + 1.5 * mm, my + 1.0 * mm); pth.lineTo(mx + 1.3 * mm, my - 0.6 * mm)
        pth.lineTo(mx, my - 1.8 * mm); pth.lineTo(mx - 1.3 * mm, my - 0.6 * mm); pth.lineTo(mx - 1.5 * mm, my + 1.0 * mm); pth.close()
        c.drawPath(pth, fill=0, stroke=1)
        c.setFillColor(NAVY); c.setFont("Lato-Bold", 8); c.drawString(14 * mm, my + 0.6 * mm, self.note_title)
        c.setFillColor(GRAY_600); c.setFont("Lato", 7); c.drawString(14 * mm, my - 2.9 * mm, self.note_text)


def _note_icon(c, kind, cx, cy, col):
    c.setStrokeColor(col); c.setFillColor(col); c.setLineWidth(0.9); c.setLineCap(1); c.setLineJoin(1)
    if kind == "id":
        c.roundRect(cx - 2.3 * mm, cy - 1.6 * mm, 4.6 * mm, 3.2 * mm, 0.5 * mm, fill=0, stroke=1)
        c.circle(cx - 0.9 * mm, cy + 0.3 * mm, 0.55 * mm, fill=1, stroke=0)
        c.line(cx + 0.4 * mm, cy + 0.5 * mm, cx + 1.7 * mm, cy + 0.5 * mm); c.line(cx + 0.4 * mm, cy - 0.6 * mm, cx + 1.7 * mm, cy - 0.6 * mm)
    elif kind == "shield":
        pth = c.beginPath(); pth.moveTo(cx, cy + 2.2 * mm); pth.lineTo(cx + 2 * mm, cy + 1.3 * mm); pth.lineTo(cx + 1.7 * mm, cy - 0.8 * mm)
        pth.lineTo(cx, cy - 2.3 * mm); pth.lineTo(cx - 1.7 * mm, cy - 0.8 * mm); pth.lineTo(cx - 2 * mm, cy + 1.3 * mm); pth.close()
        c.drawPath(pth, fill=0, stroke=1); _check_tick(c, cx, cy, 0.9 * mm, col)
    elif kind == "health":
        c.line(cx, cy - 2 * mm, cx, cy + 2 * mm); c.line(cx - 2 * mm, cy, cx + 2 * mm, cy)
    elif kind == "weather":
        c.circle(cx - 1.0 * mm, cy - 0.4 * mm, 1.1 * mm, fill=0, stroke=1); c.circle(cx + 0.7 * mm, cy + 0.3 * mm, 1.4 * mm, fill=0, stroke=1)
        c.line(cx - 1.0 * mm, cy - 1.5 * mm, cx + 1.9 * mm, cy - 1.5 * mm)
    elif kind == "signal":
        for k, hh in enumerate((1.0, 2.0, 3.0)):
            c.line(cx - 1.8 * mm + k * 1.8 * mm, cy - 1.5 * mm, cx - 1.8 * mm + k * 1.8 * mm, cy - 1.5 * mm + hh * mm)
    else:                                                           # camera
        c.roundRect(cx - 2.3 * mm, cy - 1.5 * mm, 4.6 * mm, 3.0 * mm, 0.6 * mm, fill=0, stroke=1)
        c.circle(cx, cy, 0.9 * mm, fill=0, stroke=1)


class TravelNotesGrid(Flowable):
    """Important travel notes: six note cards in two columns, each with a medallion icon."""
    GAP = 3 * mm
    KINDS = ["id", "shield", "health", "weather", "signal", "camera"]
    RINGS = [(SKY, SKY_LIGHT), (TEAL, TEAL_LITE), (ROSE, colors.HexColor("#ffe4e6")),
             (GOLD_MID, GOLD_LITE), (SKY, SKY_LIGHT), (TEAL, TEAL_LITE)]

    def __init__(self, width, notes, compact=False):
        super().__init__()
        self.width = width
        self.notes = [(_raw(h), _raw(b)) for h, b in notes]
        self.compact = compact
        self._recalc()

    def _recalc(self):
        self.fs = 7.0 if self.compact else 7.5
        self.lead = 3.0 * mm if self.compact else 3.3 * mm
        self.cw = (self.width - self.GAP) / 2
        self.tw = self.cw - 13 * mm - 4 * mm
        n = len(self.notes)
        self.rows = (n + 1) // 2
        self.row_h = []
        for r in range(self.rows):
            hs = []
            for k in (2 * r, 2 * r + 1):
                if k < n:
                    lines = min(len(simpleSplit(self.notes[k][1], "Lato", self.fs, self.tw)), 6)
                    hs.append(5.6 * mm + lines * self.lead + 3.4 * mm)
            self.row_h.append(max(hs))
        self.height = sum(self.row_h) + (self.rows - 1) * self.GAP

    def wrap(self, aw, ah):
        return (self.width, self.height)

    def draw(self):
        c = self.canv
        y_top = self.height
        for r in range(self.rows):
            rh = self.row_h[r]
            for col in (0, 1):
                k = 2 * r + col
                if k >= len(self.notes):
                    continue
                head, body = self.notes[k]
                x = col * (self.cw + self.GAP)
                ring, tint = self.RINGS[k % 6]
                c.setFillColor(WHITE); c.setStrokeColor(GRAY_200); c.setLineWidth(0.5)
                c.roundRect(x, y_top - rh, self.cw, rh, 2 * mm, fill=1, stroke=1)
                c.setFillColor(ring); c.roundRect(x, y_top - rh, 1.4 * mm, rh, 0.7 * mm, fill=1, stroke=0)
                mx, my = x + 8.6 * mm, y_top - 6.6 * mm
                c.setFillColor(WHITE); c.setStrokeColor(ring); c.setLineWidth(1.4); c.circle(mx, my, 4.0 * mm, fill=1, stroke=1)
                c.setFillColor(tint); c.circle(mx, my, 3.1 * mm, fill=1, stroke=0)
                _note_icon(c, self.KINDS[k % 6], mx, my, ring)
                c.setFillColor(NAVY); c.setFont("Lato-Bold", 8.2)
                c.drawString(x + 14 * mm, y_top - 5.4 * mm, head)
                c.setFillColor(GRAY_600); c.setFont("Lato", self.fs)
                y = y_top - 9.4 * mm
                for ln in simpleSplit(body, "Lato", self.fs, self.tw)[:6]:
                    c.drawString(x + 14 * mm, y, ln); y -= self.lead
            y_top -= rh + self.GAP


class ContactCard(Flowable):
    """'Get in touch' as a dark brand card (same family as the hero and section bars) with six contact tiles."""
    def __init__(self, width, phones, email, website, hours, address, gst=""):
        super().__init__()
        self.width = width
        self.phones, self.email, self.website, self.hours = phones, email, website, hours
        self.address, self.gst = _raw(address), _raw(gst)
        self.height = 48 * mm

    def wrap(self, aw, ah):
        return (self.width, self.height)

    def _icon(self, c, kind, cx, cy):
        c.setStrokeColor(SKY_MID); c.setFillColor(SKY_MID); c.setLineWidth(0.9); c.setLineCap(1); c.setLineJoin(1)
        if kind == "phone":
            c.roundRect(cx - 1.3 * mm, cy - 2.1 * mm, 2.6 * mm, 4.2 * mm, 0.6 * mm, fill=0, stroke=1)
            c.circle(cx, cy - 1.3 * mm, 0.28 * mm, fill=1, stroke=0)
        elif kind == "mail":
            c.roundRect(cx - 2.2 * mm, cy - 1.5 * mm, 4.4 * mm, 3.0 * mm, 0.5 * mm, fill=0, stroke=1)
            c.line(cx - 2.2 * mm, cy + 1.5 * mm, cx, cy - 0.3 * mm); c.line(cx + 2.2 * mm, cy + 1.5 * mm, cx, cy - 0.3 * mm)
        elif kind == "globe":
            c.circle(cx, cy, 2.2 * mm, fill=0, stroke=1); c.ellipse(cx - 0.9 * mm, cy - 2.2 * mm, cx + 0.9 * mm, cy + 2.2 * mm, fill=0, stroke=1)
            c.line(cx - 2.2 * mm, cy, cx + 2.2 * mm, cy)
        elif kind == "clock":
            c.circle(cx, cy, 2.2 * mm, fill=0, stroke=1); c.line(cx, cy, cx, cy + 1.3 * mm); c.line(cx, cy, cx + 1.0 * mm, cy - 0.5 * mm)
        else:                                                       # pin
            c.circle(cx, cy + 0.5 * mm, 1.5 * mm, fill=0, stroke=1); c.line(cx, cy - 0.9 * mm, cx, cy - 2.2 * mm)

    def draw(self):
        c, w, h = self.canv, self.width, self.height
        c.setFillColor(NAVY_DEEP); c.roundRect(0, 0, w, h, 2.6 * mm, fill=1, stroke=0)
        c.setFillColor(SKY); c.roundRect(0, 0, 3 * mm, h, 1.4 * mm, fill=1, stroke=0)
        # brand block
        bx = 9 * mm
        c.setFillColor(WHITE); c.setFont("Lato-Bold", 14); c.drawString(bx, h - 13 * mm, "SERENE VIBES")
        c.setFillColor(SKY_MID); c.setFont("Lato-Bold", 14); c.drawString(bx, h - 19 * mm, "KASHMIR")
        c.setFillColor(GOLD_LITE); c.setFont("Lato-Italic", 8.2); c.drawString(bx, h - 25 * mm, "A Poem In Motion")
        c.setFillColor(GRAY_400); c.setFont("Lato", 6.6)
        c.drawString(bx, h - 31 * mm, "Your local team in Srinagar,")
        c.drawString(bx, h - 34.2 * mm, "with you from pickup to drop.")
        if self.gst:
            c.setFillColor(GRAY_400); c.setFont("Lato-Bold", 6.6); c.drawString(bx, 5 * mm, "GST  " + self.gst)
        divx = 56 * mm
        c.setStrokeColor(SLATE); c.setLineWidth(0.5); c.line(divx, 5 * mm, divx, h - 5 * mm)
        # tiles
        gx = divx + 5 * mm
        cw = (w - gx - 4 * mm) / 2
        tiles = [
            ("phone", "CALL / WHATSAPP", self.phones[0], "tel:" + re.sub(r"[^0-9+]", "", self.phones[0])),
            ("phone", "ALTERNATE LINE", self.phones[1] if len(self.phones) > 1 else self.phones[0],
             "tel:" + re.sub(r"[^0-9+]", "", self.phones[1] if len(self.phones) > 1 else self.phones[0])),
            ("mail", "EMAIL", self.email, "mailto:" + self.email),
            ("globe", "WEBSITE", self.website, "https://" + self.website),
            ("clock", "OPERATING HOURS", self.hours, None),
            ("pin", "OFFICE", self.address, None),
        ]
        rh = (h - 8 * mm) / 3
        for i, (kind, lab, val, url) in enumerate(tiles):
            col, row = i % 2, i // 2
            x = gx + col * cw
            ty = h - 4 * mm - row * rh
            mx, my = x + 3.6 * mm, ty - rh / 2
            c.setFillColor(SLATE); c.circle(mx, my, 3.6 * mm, fill=1, stroke=0)
            self._icon(c, kind, mx, my)
            tx, tw = x + 9 * mm, cw - 10 * mm
            c.setFillColor(GRAY_400); c.setFont("Lato-Bold", 5.8); c.drawString(tx, my + 1.6 * mm, lab)
            c.setFillColor(WHITE)
            if kind == "pin" and c.stringWidth(val, "Lato", 7.4) > tw:
                lines = simpleSplit(val, "Lato", 6.8, tw)[:2]
                c.setFont("Lato", 6.8)
                yy = my - 1.2 * mm
                for ln in lines:
                    c.drawString(tx, yy, ln); yy -= 2.9 * mm
            else:
                fs = _fit_font(c, val, "Lato-Bold", 7.6, tw)
                c.setFont("Lato-Bold", fs); c.drawString(tx, my - 2.0 * mm, val)
                if url:
                    c.linkURL(url, (tx, my - 3.2 * mm, tx + min(c.stringWidth(val, "Lato-Bold", fs), tw), my - 0.4 * mm), relative=1)



class TermsGrid(Flowable):
    """Terms & conditions as numbered cards in two balanced columns (same card family as the other pages)."""
    GAP = 3 * mm

    def __init__(self, width, items, compact=False):
        super().__init__()
        self.width = width
        self.items = [(_raw(h), _raw(b)) for h, b in items]
        self.compact = compact
        self._recalc()

    def _recalc(self):
        self.fs = 6.9 if self.compact else 7.3
        self.lead = 2.95 * mm if self.compact else 3.2 * mm
        self.cw = (self.width - self.GAP) / 2
        self.tw = self.cw - 14 * mm - 4 * mm
        self.hs, self.ls = [], []
        for h, b in self.items:
            lines = simpleSplit(b, "Lato", self.fs, self.tw)
            self.ls.append(lines)
            self.hs.append(5.6 * mm + len(lines) * self.lead + 3.2 * mm)
        best = None
        for k in range(1, len(self.items)):                       # split that makes the two columns most even
            lh = sum(self.hs[:k]) + (k - 1) * self.GAP
            rh = sum(self.hs[k:]) + (len(self.hs) - k - 1) * self.GAP
            if best is None or max(lh, rh) < best[0]:
                best = (max(lh, rh), k)
        self.split = best[1] if best else len(self.items)
        self.height = best[0] if best else 0

    def wrap(self, aw, ah):
        return (self.width, self.height)

    def draw(self):
        c = self.canv
        for col, (lo, hi) in enumerate(((0, self.split), (self.split, len(self.items)))):
            x = col * (self.cw + self.GAP)
            y_top = self.height
            for k in range(lo, hi):
                head, _ = self.items[k]
                h = self.hs[k]
                c.setFillColor(WHITE); c.setStrokeColor(GRAY_200); c.setLineWidth(0.5)
                c.roundRect(x, y_top - h, self.cw, h, 2 * mm, fill=1, stroke=1)
                c.setFillColor(SKY); c.roundRect(x, y_top - h, 1.4 * mm, h, 0.7 * mm, fill=1, stroke=0)
                mx, my = x + 8.2 * mm, y_top - 5.2 * mm
                c.setFillColor(NAVY_DEEP); c.circle(mx, my, 3.1 * mm, fill=1, stroke=0)
                c.setFillColor(WHITE); c.setFont("Lato-Bold", 7.6); c.drawCentredString(mx, my - 1.0 * mm, str(k + 1))
                c.setFillColor(NAVY); c.setFont("Lato-Bold", 8.3); c.drawString(x + 14 * mm, my - 0.9 * mm, head)
                c.setFillColor(GRAY_600); c.setFont("Lato", self.fs)
                y = y_top - 10 * mm
                for ln in self.ls[k]:
                    c.drawString(x + 14 * mm, y, ln); y -= self.lead
                y_top -= h + self.GAP


class GeneralTermsCard(Flowable):
    """General terms: one card, bullets in two columns."""
    def __init__(self, width, bullets, compact=False):
        super().__init__()
        self.width = width
        self.bullets = [_raw(b) for b in bullets]
        self.compact = compact
        self._recalc()

    def _recalc(self):
        self.fs = 6.9 if self.compact else 7.3
        self.lead = 2.95 * mm if self.compact else 3.2 * mm
        self.cw = (self.width - 12 * mm) / 2
        self.tw = self.cw - 5 * mm
        n = len(self.bullets)
        k = (n + 1) // 2
        self.cols = [self.bullets[:k], self.bullets[k:]]
        def hh(col):
            return sum(len(simpleSplit(b, "Lato", self.fs, self.tw)) * self.lead + 1.8 * mm for b in col)
        self.head_h = 11 * mm
        self.height = self.head_h + max(hh(self.cols[0]), hh(self.cols[1])) + 2.4 * mm

    def wrap(self, aw, ah):
        return (self.width, self.height)

    def draw(self):
        c, w, h = self.canv, self.width, self.height
        c.setFillColor(WHITE); c.setStrokeColor(GRAY_200); c.setLineWidth(0.5)
        c.roundRect(0, 0, w, h, 2 * mm, fill=1, stroke=1)
        c.setFillColor(TEAL); c.roundRect(0, 0, 1.4 * mm, h, 0.7 * mm, fill=1, stroke=0)
        mx, my = 9 * mm, h - 5.8 * mm
        c.setFillColor(WHITE); c.setStrokeColor(TEAL); c.setLineWidth(1.4); c.circle(mx, my, 3.6 * mm, fill=1, stroke=1)
        c.setFillColor(TEAL_LITE); c.circle(mx, my, 2.8 * mm, fill=1, stroke=0)
        _check_tick(c, mx, my, 1.1 * mm, TEAL)
        c.setFillColor(NAVY); c.setFont("Lato-Bold", 9); c.drawString(15 * mm, my + 0.2 * mm, "General terms")
        c.setFillColor(GRAY_400); c.setFont("Lato", 6.4); c.drawString(15 * mm, my - 3.0 * mm, "Good to know about your stay")
        c.setStrokeColor(GRAY_200); c.setLineWidth(0.4); c.line(5 * mm, h - self.head_h + 0.6 * mm, w - 4 * mm, h - self.head_h + 0.6 * mm)
        for ci, col in enumerate(self.cols):
            x = 6 * mm + ci * (self.cw + 2 * mm)
            y = h - self.head_h - 3.0 * mm
            for b in col:
                c.setFillColor(TEAL); c.circle(x + 1.0 * mm, y + 0.9 * mm, 0.7 * mm, fill=1, stroke=0)
                c.setFillColor(GRAY_600); c.setFont("Lato", self.fs)
                for ln in simpleSplit(b, "Lato", self.fs, self.tw):
                    c.drawString(x + 4 * mm, y, ln); y -= self.lead
                y -= 1.8 * mm



class AgreementCard(Flowable):
    """The acknowledgement text as a card: medallion heading, the wording, then quote reference and validity pills."""
    def __init__(self, width, text, ref, valid):
        super().__init__()
        self.width, self.text, self.ref, self.valid = width, _raw(text), ref, valid
        self.tw = width - 12 * mm
        self.lines = simpleSplit(self.text, "Lato", 7.8, self.tw)
        self.height = 14 * mm + len(self.lines) * 3.7 * mm + 12 * mm

    def wrap(self, aw, ah):
        return (self.width, self.height)

    def draw(self):
        c, w, h = self.canv, self.width, self.height
        c.setFillColor(WHITE); c.setStrokeColor(GRAY_200); c.setLineWidth(0.5)
        c.roundRect(0, 0, w, h, 2 * mm, fill=1, stroke=1)
        c.setFillColor(SKY); c.roundRect(0, 0, 1.4 * mm, h, 0.7 * mm, fill=1, stroke=0)
        mx, my = 9 * mm, h - 7 * mm
        c.setFillColor(WHITE); c.setStrokeColor(SKY); c.setLineWidth(1.5); c.circle(mx, my, 4.0 * mm, fill=1, stroke=1)
        c.setFillColor(SKY_LIGHT); c.circle(mx, my, 3.1 * mm, fill=1, stroke=0)
        c.setStrokeColor(SKY); c.setLineWidth(0.9); c.setLineCap(1)                       # little pen
        c.line(mx - 1.6 * mm, my - 1.6 * mm, mx + 1.4 * mm, my + 1.4 * mm); c.line(mx - 1.6 * mm, my - 1.6 * mm, mx - 1.6 * mm, my - 0.6 * mm)
        c.line(mx - 1.6 * mm, my - 1.6 * mm, mx - 0.6 * mm, my - 1.6 * mm)
        c.setFillColor(NAVY); c.setFont("Lato-Bold", 9.4); c.drawString(15 * mm, my + 0.6 * mm, "Your agreement")
        c.setFillColor(GRAY_400); c.setFont("Lato", 6.6); c.drawString(15 * mm, my - 3.0 * mm, "Please read, sign and return a copy")
        c.setStrokeColor(GRAY_200); c.setLineWidth(0.4); c.line(5 * mm, my - 5.6 * mm, w - 4 * mm, my - 5.6 * mm)
        y = my - 10 * mm
        c.setFillColor(GRAY_600); c.setFont("Lato", 7.8)
        for ln in self.lines:
            c.drawString(6 * mm, y, ln); y -= 3.7 * mm
        x = 6 * mm
        for lab, val, col, lite in (("QUOTE", self.ref, SKY, SKY_LIGHT), ("VALID UNTIL", self.valid, GOLD, GOLD_LITE)):
            t = f"{lab}   {val}"
            tw = c.stringWidth(t, "Lato-Bold", 7.2) + 6 * mm
            c.setFillColor(lite); c.roundRect(x, 2.8 * mm, tw, 5 * mm, 2.5 * mm, fill=1, stroke=0)
            c.setFillColor(col); c.setFont("Lato-Bold", 7.2); c.drawString(x + 3 * mm, 4.4 * mm, t)
            x += tw + 3 * mm
        c.setFillColor(GRAY_400); c.setFont("Lato-Italic", 6.6)
        c.drawRightString(w - 4 * mm, 4.4 * mm, "Rates may change after this date (hotel availability, season).")


class SignatureRow(Flowable):
    """Three signing cards: client, date, and Serene Vibes (with the company stamp when auth_stamp.png exists)."""
    GAP = 3 * mm

    def __init__(self, width, client_name, stamp_path=None):
        super().__init__()
        self.width, self.client_name, self.stamp_path = width, _raw(client_name), stamp_path
        self.height = 40 * mm
        self._stamp = None
        try:
            if stamp_path:
                self._stamp = ImageReader(stamp_path)
        except Exception:
            self._stamp = None

    def wrap(self, aw, ah):
        return (self.width, self.height)

    def draw(self):
        c, h = self.canv, self.height
        cw = (self.width - 2 * self.GAP) / 3
        specs = [("CLIENT", "Client name & signature", SKY), ("DATE", "Date of agreement", TEAL), ("FOR SERENE VIBES KASHMIR", "Authorised signatory", NAVY)]
        for i, (cap, lab, col) in enumerate(specs):
            x = i * (cw + self.GAP)
            c.setFillColor(WHITE); c.setStrokeColor(GRAY_200); c.setLineWidth(0.5)
            c.roundRect(x, 0, cw, h, 2 * mm, fill=1, stroke=1)
            c.setFillColor(col); c.roundRect(x, h - 1.4 * mm, cw, 1.4 * mm, 0.7 * mm, fill=1, stroke=0)
            c.setFillColor(GRAY_400); c.setFont("Lato-Bold", 6.2); c.drawString(x + 4 * mm, h - 6 * mm, cap)
            line_y = 12 * mm
            if i == 2:
                if self._stamp:
                    try:
                        iw, ih = self._stamp.getSize()
                        bw = min(cw - 12 * mm, 34 * mm); bh = bw * ih / iw
                        if bh > 17 * mm:
                            bh = 17 * mm; bw = bh * iw / ih
                        c.drawImage(self._stamp, x + (cw - bw) / 2, line_y + 2 * mm, bw, bh, mask="auto")
                    except Exception:
                        pass
                else:
                    c.setFillColor(colors.HexColor("#163078")); c.setFont("Lato-Bold", 8.6)
                    c.drawCentredString(x + cw / 2, line_y + 8 * mm, "SERENE VIBES KASHMIR")
            elif i == 1:
                c.setFillColor(GRAY_200); c.setFont("Lato", 9)
                c.drawCentredString(x + cw / 2, line_y + 2.6 * mm, "DD  /  MM  /  YYYY")
            else:
                c.setFillColor(GRAY_200); c.setFont("Lato-Italic", 7)
                c.drawString(x + 4 * mm, line_y + 14 * mm, "Sign here")
            c.setStrokeColor(NAVY); c.setLineWidth(0.6); c.line(x + 4 * mm, line_y, x + cw - 4 * mm, line_y)
            if i == 0:
                c.setFillColor(NAVY); c.setFont("Lato-Bold", 8.4)
                c.drawString(x + 4 * mm, line_y - 4.4 * mm, self.client_name[:34])
                c.setFillColor(GRAY_600); c.setFont("Lato", 6.8); c.drawString(x + 4 * mm, line_y - 8.2 * mm, lab)
            else:
                c.setFillColor(GRAY_600); c.setFont("Lato-Bold", 7.4); c.drawCentredString(x + cw / 2, line_y - 4.4 * mm, lab)


class NextStepCards(Flowable):
    """'What happens next': three numbered step cards joined by arrows."""
    GAP = 3 * mm

    def __init__(self, width, steps):
        super().__init__()
        self.width, self.steps = width, steps
        self.cw = (width - 2 * self.GAP) / 3
        self.tw = self.cw - 8 * mm
        self.ls = [simpleSplit(_raw(b), "Lato", 7.2, self.tw)[:3] for _, b in steps]
        self.height = 14 * mm + max(len(l) for l in self.ls) * 3.2 * mm + 3 * mm

    def wrap(self, aw, ah):
        return (self.width, self.height)

    def draw(self):
        c, h = self.canv, self.height
        palette = [SKY, TEAL, NAVY]
        for i, ((head, _), lines) in enumerate(zip(self.steps, self.ls)):
            x = i * (self.cw + self.GAP)
            ring = palette[i]
            c.setFillColor(WHITE); c.setStrokeColor(GRAY_200); c.setLineWidth(0.5)
            c.roundRect(x, 0, self.cw, h, 2 * mm, fill=1, stroke=1)
            c.setFillColor(ring); c.roundRect(x, h - 1.4 * mm, self.cw, 1.4 * mm, 0.7 * mm, fill=1, stroke=0)
            mx, my = x + 8 * mm, h - 8 * mm
            c.setFillColor(WHITE); c.setStrokeColor(ring); c.setLineWidth(1.5); c.circle(mx, my, 4.0 * mm, fill=1, stroke=1)
            c.setFillColor(ring); c.circle(mx, my, 3.1 * mm, fill=1, stroke=0)
            c.setFillColor(WHITE); c.setFont("Lato-Bold", 9); c.drawCentredString(mx, my - 1.2 * mm, str(i + 1))
            c.setFillColor(NAVY); c.setFont("Lato-Bold", 8.4); c.drawString(x + 14 * mm, my - 1.0 * mm, _raw(head))
            c.setFillColor(GRAY_600); c.setFont("Lato", 7.2)
            y = my - 7.4 * mm
            for ln in lines:
                c.drawString(x + 4 * mm, y, ln); y -= 3.2 * mm
            if i < 2:
                ax = x + self.cw + self.GAP / 2
                c.setFillColor(WHITE); c.setStrokeColor(GRAY_200); c.setLineWidth(0.5); c.circle(ax, h / 2, 2.0 * mm, fill=1, stroke=1)
                c.setStrokeColor(GRAY_400); c.setLineWidth(0.8); c.setLineCap(1)
                c.line(ax - 0.5 * mm, h / 2 + 0.9 * mm, ax + 0.5 * mm, h / 2); c.line(ax + 0.5 * mm, h / 2, ax - 0.5 * mm, h / 2 - 0.9 * mm)


class HelpStrip(Flowable):
    """Dark brand strip: 'Questions? Talk to us' with the call / WhatsApp / Instagram (/ Facebook) buttons."""
    def __init__(self, width, client_name="", ref=""):
        super().__init__()
        self.width, self.height = width, 19 * mm
        self.client_name, self.ref = client_name, ref

    def wrap(self, aw, ah):
        return (self.width, self.height)

    def draw(self):
        c, w, h = self.canv, self.width, self.height
        c.setFillColor(NAVY_DEEP); c.roundRect(0, 0, w, h, 2.6 * mm, fill=1, stroke=0)
        c.setFillColor(SKY); c.roundRect(0, 0, 3 * mm, h, 1.4 * mm, fill=1, stroke=0)
        c.setFillColor(WHITE); c.setFont("Lato-Bold", 10); c.drawString(8 * mm, h / 2 + 1.2 * mm, "Questions? Talk to us")
        c.setFillColor(GRAY_400); c.setFont("Lato", 7); c.drawString(8 * mm, h / 2 - 3.2 * mm, "Call or message us directly.")
        bh, gap = 8 * mm, 3 * mm
        btns = [
            (20 * mm, lambda x, y, bw: _draw_call_button(c, x, y, bw, bh)),
            (27 * mm, lambda x, y, bw: _draw_whatsapp_button(c, x, y, bw, bh, _whatsapp_url(self.client_name, self.ref), label="WhatsApp")),
            (27 * mm, lambda x, y, bw: _draw_instagram_button(c, x, y, bw, bh, label="Instagram")),
        ]
        if FACEBOOK_URL:
            btns.append((27 * mm, lambda x, y, bw: _draw_facebook_button(c, x, y, bw, bh, FACEBOOK_URL)))
        x = w - 5 * mm - sum(b[0] for b in btns) - gap * (len(btns) - 1)
        for bw, draw in btns:
            draw(x, (h - bh) / 2, bw)
            x += bw + gap



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
    client_email = str(itinerary_data.get("client_email") or "").strip()
    client_email = _real(client_email)   # blank / dummy email is never printed
    start_point  = str(itinerary_data.get("start_point") or "").strip() or DEFAULT_POINT
    end_point    = str(itinerary_data.get("end_point") or "").strip() or DEFAULT_POINT
    itinerary_data = dict(itinerary_data)
    _register_custom_map_places()
    itinerary_data["timeline"] = _apply_points(itinerary_data.get("timeline", []), start_point, end_point)
    # No cost entered (blank / 0) -> "TBD" everywhere in the PDF
    custom_cost  = _amount_int(itinerary_data.get("custom_cost")) or "TBD"

    # ── 1. Hero header ────────────────────────────────────────────────────────
    story.append(HeroHeader(
        usable_w, client_name, days, start_date, adults, kids,
        budget_tier, vehicle_type, custom_cost, bg_reader=_load_hero_photo(),
        ref=_quote_ref(client_name), route=_route_text(itinerary_data.get("timeline", []), start_point, end_point)
    ))
    story.append(Spacer(1, 3*mm))
    _tagline = Paragraph(clean(_trip_story(itinerary_data.get("timeline", []))),
                         ParagraphStyle("story", fontName="Lato-Italic", fontSize=10.5, leading=13,
                                        textColor=NAVY, alignment=TA_CENTER))
    _tagline_gap = Spacer(1, 3*mm)
    story.append(_tagline)
    story.append(_tagline_gap)

    # Decision block: price per person, WhatsApp confirm, what is included, our promise
    _total_now   = _amount_int(custom_cost)
    _valid_until = (datetime.datetime.now(IST) + datetime.timedelta(days=7)).strftime("%d %b %Y")
    _nights      = max(int(days) - 1, 1)
    _meal_name   = {"MAP": "Breakfast + dinner", "CP": "Breakfast daily", "EP": "No meals",
                    "AP": "All meals"}.get(str(itinerary_data.get("meal_plan") or "MAP").strip().upper(), "Meals as planned")
    story.append(PriceBand(usable_w, _total_now, adults, kids, _valid_until,
                           round(_total_now * 0.25) if _total_now else 0, _quote_ref(client_name),
                           show_per_person=bool(itinerary_data.get("show_per_person"))))
    story.append(Spacer(1, 3*mm))
    _extras = _extras_list(itinerary_data)
    _tiles = [
        ((f"Private {clean(str(vehicle_type))}", "pickup to drop") if len(clean(str(vehicle_type))) <= 8
         else (clean(str(vehicle_type)), "private, pickup to drop")),
        (f"{_nights} nights stay", "hotels as listed"),
        (_meal_name, "as per your meal plan"),
        ("Shikara ride", "1 hour, on us"),
        ("All taxes", "toll, fuel, parking"),
    ]
    if "union_cab" in _extras:
        _tiles.append(("Union cab", "Pahalgam & snow chain", "cab"))
    for _k, _ph in (("gondola_p1", "Phase 1"), ("gondola_p2", "Phase 2")):
        if _k in _extras:
            _tiles.append(("Gondola", _ph, "gondola"))
    _inner_w = usable_w - 2 * BackdropGroup.PAD
    story.append(BackdropGroup(usable_w, [
        IncludedCards(_inner_w, _tiles),
        PromiseBox(_inner_w, [
            ("Weather-proof plan", "Road or weather change? We rearrange sightseeing at no extra cost."),
            ("Your driver, named", "Driver name and number shared before you travel."),
            ("24/7 local support", "Our Srinagar team is on call throughout your trip."),
            ("No hidden charges", "Inclusions and exclusions are listed clearly."),
        ]),
    ]))
    story.append(Spacer(1, 4*mm))

    # ── 2. Quick-summary grid ─────────────────────────────────────────────────
    _cost_txt = f"INR {_amount_int(custom_cost):,}" if _is_amount(custom_cost) else "TBD"
    _valid_txt = (datetime.datetime.now(IST) + datetime.timedelta(days=7)).strftime("%d %b %Y")
    _guests_txt = f"{adults} Adults" + (f", {kids} Kids" if int(kids or 0) else "")
    summary_card = TripSummary(
        usable_w,
        [("CLIENT NAME", client_name, False),
         ("TOUR DURATION", f"{days} Days", False),
         ("GUESTS", _guests_txt, False),
         ("START POINT", start_point, False),
         ("BUDGET TIER", str(budget_tier), False)],
        [("TRAVEL DATE", str(start_date), False),
         ("VEHICLE", str(vehicle_type), False),
         ("END POINT", end_point, False),
         ("ESTIMATED COST", _cost_txt, _is_amount(custom_cost))],
        ref=_quote_ref(client_name), valid=_valid_txt, email=client_email or "")
    story.append(summary_card)
    story.append(Spacer(1, 4*mm))
    _trust = TrustStrip(usable_w, TRUST_STATS, TRUST_QUOTE, TRUST_QUOTE_BY)
    story.append(_trust)
    # ── Keep page 1 on ONE page: if it overflows, tighten gaps, then compact cards, then drop the strip
    def _p1_used():
        return sum(f.wrap(usable_w, 10000)[1] for f in story)
    _p1_room = (doc.height - 12) - _P1_SLACK
    if _p1_used() > _p1_room:
        for f in story:                                   # 1) tighten the gaps between blocks
            if isinstance(f, Spacer):
                f.height = min(f.height, 2 * mm)
    if _p1_used() > _p1_room:                             # 2) compact the two tall cards
        for f in story:
            if isinstance(f, BackdropGroup):
                for _ch in f.children:
                    if isinstance(_ch, IncludedCards):
                        _ch.compact = True; _ch._recalc()
                f.gap = 2 * mm; f._recalc()
            elif isinstance(f, TripSummary):
                f.compact = True; f._recalc()
    if _p1_used() > _p1_room:                             # 3) drop the italic tagline (the proof strip matters more)
        story.remove(_tagline); story.remove(_tagline_gap)
    if _p1_used() > _p1_room:                             # 4) slimmer proof strip + tighter gaps
        _trust.height = 18 * mm
        for f in story:
            if isinstance(f, Spacer):
                f.height = min(f.height, 1.5 * mm)
    if _p1_used() > _p1_room:                             # 5) truly last resort: drop the proof strip
        story.remove(_trust)
        while story and isinstance(story[-1], Spacer):
            story.pop()
    # NOTE: no trailing Spacer here. If page 1 is nearly full, a spacer that does not fit
    # spills onto page 2 and the PageBreak below then leaves page 2 blank.
    _used = sum(f.wrap(usable_w, 10000)[1] for f in story) + 4 * mm
    _steps = NextSteps(usable_w, [
        ("Review and sign", "Check itinerary, hotels and terms."),
        ("Pay the first 25%", "NEFT / UPI / Cheque confirms it."),
        ("Receive vouchers", "Hotel and transfer details before travel."),
    ])
    if (doc.height - 12) - _used > _steps.height + 6 * mm:      # only when it fits on page 1
        story.append(Spacer(1, 4*mm))
        story.append(_steps)
    story.append(PageBreak())

    # ── 2b. Tour Route Map - ALWAYS the lower part of page 1 ──────────────────
    # Measure what is already on page 1 (hero + summary), give the map block the
    # remaining height (legend rows shrink for long trips, the map takes the rest)
    # and push the block to the bottom of the page with a spacer.  A PageBreak
    # follows so the Day-by-Day section starts cleanly on page 2.
    timeline_for_map = itinerary_data.get("timeline", [])
    avail  = min((doc.height - 12) - 4 * mm, 138 * mm)     # map block opens page 2; Day 1 must fit under it
    map_title = SectionTitle(usable_w, "TOUR ROUTE MAP", icon="")
    gap_h  = 3 * mm
    route_map = KashmirRouteMap(usable_w, timeline_for_map,
                                max_height=avail - map_title.height - gap_h,
                                start_point=start_point, end_point=end_point,
                                start_info=itinerary_data.get("start_info"), end_info=itinerary_data.get("end_info"))
    story.append(KeepTogether([map_title, Spacer(1, gap_h), route_map]))
    story.append(Spacer(1, 4*mm))

    # ── 3. Day-by-day itinerary ───────────────────────────────────────────────
    _day_title = [SectionTitle(usable_w, "DAY-BY-DAY ITINERARY", icon=""), Spacer(1, 4*mm)]   # kept with Day 1

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

        _hsel = itinerary_data.get("selected_hotels") or itinerary_data.get("hotelSelections") or {}
        def _banner_hotel(_i=idx, _sel=_hsel):
            if not isinstance(_sel, dict):
                return ""
            hid = _sel.get(str(_i - 1))                    # 0-based day index, as the itinerary builder stores it
            if isinstance(hid, dict):
                hid = hid.get("id")
            info = HOTEL_LOOKUP.get(str(hid), {}) if hid else {}
            if not info.get("name"):
                return ""
            return f"{info['name']}, {info['place']}" if info.get("place") else info["name"]   # looked up at draw time: HOTEL_LOOKUP is defined below
        def _stay_label(_ov=overnight, _h=_banner_hotel):
            if not _ov or str(_ov).lower() in ("departure", ""):
                return ""
            return _h() or _ov
        _rows = getattr(route_map, "_rows", [])
        _travel = (_rows[idx - 1].get("travel") if idx - 1 < len(_rows) else None)
        _has_travel = bool(_travel and _travel.get("text"))

        # Only show a route line when the travel strip does not already carry it
        _route_show = route.split(":", 1)[0].strip() if ":" in str(route) else str(route).strip()   # "...: Overnight X" is in the Stay pill
        if _has_travel or not _route_show or _route_show.lower() == str(banner_title).strip().lower():
            _route_show = ""

        # Tidy the slots: drop empties and merge repeats (same heading twice -> one step, both descriptions).
        steps = []
        for slot in schedule:
            time_txt = str(slot.get("time_slot") or slot.get("time") or "").strip()
            if time_txt in ("***", "*", "\u2014", "\u2013", "-"):
                time_txt = ""
            head = str(slot.get("activity_title") or "").strip()
            desc = str(slot.get("description") or slot.get("activity") or "").strip()
            if not head and not desc:
                continue
            prev = steps[-1] if steps else None
            if prev and head and prev["head"].lower() == head.lower() and prev["time"] == time_txt:
                if desc and desc.lower() not in prev["desc"].lower():
                    prev["desc"] = (prev["desc"] + " " + desc).strip()
                continue
            steps.append({"time": time_txt, "head": head, "desc": desc})
        # A step with only a description (no heading) gets a short heading from its first words.
        for s_ in steps:
            if not s_["head"] and s_["desc"]:
                first = re.split(r"(?<=[.!?])\s", s_["desc"], 1)[0]
                words = first.split()
                s_["head"] = " ".join(words[:5]).rstrip(".,;:") + ("\u2026" if len(words) > 5 else "")

        day_bg = dest_bgs.get(_day_photo_key(day_info))
        _pk = _day_photo_key(day_info)
        spread = DayBookSpread(
            usable_w, idx, banner_title, _day_date(start_date, idx), _stay_label,
            travel=_travel, route=_route_show, photo=day_bg,
            photo_label=KashmirRouteMap.DISPLAY.get(_pk, str(_pk).title()) if day_bg is not None else KashmirRouteMap.DISPLAY.get(_pk, str(_pk).title()),
            steps=steps, client_name=client_name)
        block = [spread, Spacer(1, 3*mm)]
        if idx == 1:
            block = [KeepTogether(_day_title + [spread]), Spacer(1, 3*mm)]   # the heading never sits alone at the foot of a page
        # Each spread is one unbroken book; platypus moves a spread that does not fit to the next page.
        story.extend(block)

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
        "hlwi": {"name": "Hotel Lime Wood Inn",            "place": "Srinagar", "images": []},
        "tsr":  {"name": "The Shamas Residency",           "place": "Srinagar", "images": []},
        "wvr":  {"name": "West View Resorts",              "place": "Srinagar", "images": []},
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
        "asr":  {"name": "Asal Resorts",                   "place": "Pahalgam", "images": []},
        "hatr": {"name": "Hotel Apple Tree Resorts",       "place": "Gulmarg",  "images": []},
        "ggr":  {"name": "Gulmarg Gateway Resorts",              "place": "Gulmarg",  "images": []},
        "hghv": {"name": "Hotel Grand Hill View",          "place": "Gulmarg",  "images": []},
        "hmsp": {"name": "Hotel Marina By Stay Pattern",   "place": "Gulmarg",  "images": []},
		"nrs":  {"name": "Namrose Resorts",                 "place": "Sonamarg", "images": []},
    	"bdr":  {"name": "Badar Resorts",                   "place": "Sonamarg", "images": []},
   		"cibsp": {"name": "Country Inn-By Stay Pattern",    "place": "Sonamarg", "images": []},
    	"hmi": {"name": "Hotel Mughal India",               "place": "Sonamarg", "images": []},
    }

    # ── Add hotels created in the admin panel (Hotels tab) ────────────────
    try:
        from backend.services import custom_hotels as _custom_hotels
        for _hid, _info in _custom_hotels.get_all().items():
            HOTEL_LOOKUP.setdefault(_hid, _info)
    except Exception as _e:
        print(f"Warning: could not load admin-added hotels: {_e}")

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

    # Names sent by the itinerary builder itself (what the admin actually selected) -- most reliable.
    for _hid, _d in (itinerary_data.get("hotel_details") or {}).items():
        if isinstance(_d, dict) and _d.get("name") and str(_hid) not in HOTEL_LOOKUP:
            HOTEL_LOOKUP[str(_hid)] = {"name": str(_d["name"])[:150],
                                       "place": str(_d.get("place") or "-")[:40], "images": []}

    # ── Safety net: a hotel picked in the itinerary builder must never print as "To be confirmed".
    # If a selected hotel id is missing from HOTEL_LOOKUP (e.g. the earlier bulk read of
    # admin-added hotels failed or was stale), look that hotel up directly in the database.
    try:
        from backend.models import CustomHotel as _CH
        for _hsel in list(hotel_selections.values()):
            _hid = str(_hsel.get("id") if isinstance(_hsel, dict) else _hsel or "")
            if _hid and _hid not in HOTEL_LOOKUP:
                _row = _CH.query.filter_by(hotel_id=_hid).first()
                if _row:
                    HOTEL_LOOKUP[_hid] = {"name": _row.name, "place": _row.place, "images": []}
                else:
                    print(f"Warning: selected hotel id {_hid!r} not found in built-in or admin-added hotels")
    except Exception as _e:
        print(f"Warning: direct admin-hotel lookup failed: {_e}")

    # ── 3b. Where you'll stay ──────────────────────────────────────────────
    # Straight after the day-by-day plan: one card per stay (consecutive nights in the
    # same hotel and room setup share a card) with room type, rooms, meal plan and the
    # hotel's best photos together.
    _hd = itinerary_data.get("hotel_details") or {}

    def _count(day, hid, key, default):
        # rooms / extra beds typed on the day card (fallback: per-hotel values)
        v = day.get(key)
        if v in (None, ""):
            v = (_hd.get(str(hid)) or {}).get(key)
        try:
            return max(0, int(float(v))) if v not in (None, "") else default
        except (TypeError, ValueError):
            return default

    meal_plan_code = str(itinerary_data.get("meal_plan") or "MAP").strip().upper()
    _mp_code, _mp_desc = _MEAL_SHORT.get(meal_plan_code, _MEAL_SHORT["MAP"])
    _start_d = _start_dt(start_date)

    stays = []
    for idx, day_info in enumerate(timeline, start=1):
        hotel_id = hotel_selections.get(str(idx - 1))      # 0-based day index, as the itinerary builder stores it
        if isinstance(hotel_id, dict):
            hotel_id = hotel_id.get("id")
        overnight_raw = str(day_info.get("overnight_stay", "") or "").strip()
        dep_signal = f"{day_info.get('title', '')} {day_info.get('transit_route', '')}".lower()
        # A departure day has no hotel night
        if ("departure" in dep_signal or "airport drop" in dep_signal
                or not overnight_raw or overnight_raw.lower() == "departure"):
            continue
        known = bool(hotel_id) and str(hotel_id) in HOTEL_LOOKUP
        hid = str(hotel_id) if known else ""
        rooms = _count(day_info, hid, "rooms", 1) or 1
        eb = _count(day_info, hid, "eb", 0)
        room_type = str(day_info.get("room_type") or (_hd.get(hid) or {}).get("room_type") or "").strip()
        if not room_type and stays and hid and stays[-1]["hid"] == hid and stays[-1]["last"] == idx - 1:
            room_type = stays[-1]["room_type"]            # same hotel, next night: same room type
        key = (hid or "tbc:" + overnight_raw.lower(), rooms, eb, room_type)
        if stays and stays[-1]["key"] == key and stays[-1]["last"] == idx - 1:
            stays[-1]["last"] = idx
            continue
        info = HOTEL_LOOKUP[hid] if known else {}
        stays.append({
            "key": key, "hid": hid, "known": known, "first": idx, "last": idx,
            "name": info.get("name") or "Hotel to be confirmed",
            "place": info.get("place") or clean(overnight_raw.split(":")[0].strip().title()) or "-",
            "rooms": rooms, "eb": eb, "room_type": room_type,
        })

    for st in stays:
        n = st["last"] - st["first"] + 1
        st["nights"] = n
        stay_txt = f"{n} night" + ("s" if n != 1 else "")
        if _start_d:
            d_in = _start_d + datetime.timedelta(days=st["first"] - 1)
            d_out = _start_d + datetime.timedelta(days=st["last"])
            stay_txt += f"  ·  {d_in.strftime('%d %b')} – {d_out.strftime('%d %b')}"
        st["stay_txt"] = stay_txt
        st["room_type"] = st["room_type"] or "On confirmation"
        st["rooms_txt"] = f"{st['rooms']} room" + ("s" if st["rooms"] != 1 else "") \
            + (f" + {st['eb']} extra bed" + ("s" if st["eb"] != 1 else "") if st["eb"] else "")
        st["meal_txt"] = f"{_mp_code}  ·  {_mp_desc}"

    _photo_cache = {}
    def _stay_photos(st):
        if not st["known"]:
            return []
        if st["hid"] not in _photo_cache:
            _photo_cache[st["hid"]] = _pick_best_photos(HOTEL_LOOKUP[st["hid"]].get("images", []), 2)
        return _photo_cache[st["hid"]]

    _segs = []
    if stays:
        _title = [SectionTitle(usable_w, "WHERE YOU'LL STAY", icon=""), Spacer(1, 4*mm)]
        _cards = [HotelStayCard(usable_w, st, _stay_photos(st)) for st in stays]
        story.append(KeepTogether(_title + [_cards[0], Spacer(1, 3.5*mm)]))
        for _card in _cards[1:]:
            story.append(KeepTogether([_card, Spacer(1, 3.5*mm)]))

        _segs = _stay_segments(timeline, hotel_selections, HOTEL_LOOKUP)
        if _segs:
            story.append(KeepTogether([StayRouteStrip(usable_w, start_point, end_point, _segs), Spacer(1, 5*mm)]))
            # Only for compact itineraries, so the page never overflows.
            _exp = SignatureExperiences(usable_w, _segs, extras=_extras, photos=dest_bgs)
            if _exp.items and len(timeline) <= 6 and len(_segs) <= 4:
                story.append(KeepTogether([_exp, Spacer(1, 4*mm)]))
    page_block_1 = []

    # ── 5. Inclusions / Exclusions ────────────────────────────────────────────
    inc_items = [
        f"01 {clean(str(vehicle_type)).upper()} for all tours and transfers including pick up and drop",
        "Sightseeing tours as per the itinerary by individual car",
        "Stay at the hotels mentioned in the itinerary or similar",
        _MEAL_INCLUSION.get(str(itinerary_data.get("meal_plan") or "MAP").strip().upper(), _MEAL_INCLUSION["MAP"]),
        "Celebration Cake",
        _sharing_text(adults),
        "01 Hour complimentary Shikara ride",
        "Toll taxes, fuel charges, parking fees and driver's allowance",
    ]
    _extras = _extras_list(itinerary_data)
    for _k in _extras:
        inc_items.append(_EXTRA_LABELS[_k])
    _gondola_inc = [k for k in _extras if k.startswith("gondola")]
    _act = "Activities: River Rafting, Paragliding and Skiing"
    if len(_gondola_inc) == 2:
        pass                                           # both phases included: not an exclusion
    elif _gondola_inc == ["gondola_p1"]:
        _act += ", Gondola Phase II (INR 1000 per person)"
    elif _gondola_inc == ["gondola_p2"]:
        _act += ", Gondola Phase I (INR 800 per person)"
    else:
        _act += ", Gondola (Phase I INR 800 & Phase II INR 1000 per person)"
    exc_items = [
        "Any Airfare or Train fare",
        "Entrances, Snacks" + ("" if str(itinerary_data.get("meal_plan") or "MAP").strip().upper() == "AP" else ", Lunch") + " and any meals not covered by the meal plan",
        _act,
        "All personal expenses such as tips, laundry, telephone bills, beverages and camera fees",
    ]
    if "union_cab" not in _extras:
        exc_items.append("Union cabs for ABC Pahalgam and snow chain vehicle if required for Gulmarg")
    exc_items.append("Any claim due to road blocks, curfews, accidents etc.")

    # Calculate payment milestones dynamically (25% / 25% / 50% split per policy)
    total_amt   = _amount_int(custom_cost)
    inst1_amt   = round(total_amt * 0.25)
    inst2_amt   = round(total_amt * 0.25)
    inst3_amt   = total_amt - inst1_amt - inst2_amt

    _sd = _start_dt(start_date)
    _d1 = (datetime.datetime.now(IST) + datetime.timedelta(days=7)).strftime("%d %b %Y")
    _d2_dt = (_sd - datetime.timedelta(days=7)) if _sd else None
    _d2 = _d2_dt.strftime("%d %b %Y") if _d2_dt else ""
    _d2_passed = bool(_d2_dt and _d2_dt.date() <= datetime.datetime.now(IST).date())
    _d3 = _sd.strftime("%d %b %Y") if _sd else ""
    pay_rows = [
        ("1st Instalment", 25, f"INR {inst1_amt:,}" if total_amt else "TBD",
         "On confirmation", f"Hold quote by {_d1}", "NEFT / UPI / Cheque", "Pending"),
        ("2nd Instalment", 25, f"INR {inst2_amt:,}" if total_amt else "TBD",
         ("With the 1st instalment" if _d2_passed else "7 days before arrival"),
         ("" if _d2_passed or not _d2 else f"By {_d2}"), "NEFT / UPI / Cheque", "Pending"),
        ("3rd Instalment", 50, f"INR {inst3_amt:,}" if total_amt else "TBD",
         "On arrival", (_d3 or ""), "NEFT / UPI / Cheque", "Pending"),
    ]
    _bank = ["Account Name: Serene Vibes Kashmir", "Bank: J&amp;K Bank"]
    if BANK_ACCOUNT_NO:
        _bank.append(f"Account No: {BANK_ACCOUNT_NO}")
    if BANK_IFSC:
        _bank.append(f"IFSC: {BANK_IFSC}")
    _bank.append("UPI: serenevibeskashmir@upi")
    _has_bank = bool(BANK_ACCOUNT_NO and BANK_IFSC)
    _pay_label = "BANK TRANSFER" if _has_bank else "PAY BY UPI"
    _pay_text = "  |  ".join(_bank) if _has_bank else "serenevibeskashmir@upi"

    # ── Final page: Inclusions, Payment and Handy numbers ALWAYS share one page ──
    _inc_cards = IncludedExcluded(usable_w, inc_items, exc_items)
    _pay_plan = PaymentPlan(usable_w, pay_rows, _pay_label, _pay_text)
    _handy = HandyEssentials(usable_w, _segs, show_bar=False)
    _final_parts = lambda: [
        SectionTitle(usable_w, "INCLUSIONS & EXCLUSIONS", icon=""), Spacer(1, 3*mm), _inc_cards, Spacer(1, 5*mm),
        SectionTitle(usable_w, "PAYMENT SCHEDULE", icon=""), Spacer(1, 3*mm), _pay_plan, Spacer(1, 5*mm),
        SectionTitle(usable_w, "HANDY NUMBERS & LOCAL WORDS", icon=""), Spacer(1, 3*mm), _handy,
    ]
    _room = doc.height - 12 - 2 * mm
    def _final_h():
        return sum(f.wrap(usable_w, 10000)[1] for f in _final_parts())
    if _final_h() > _room:                      # long lists: tighten text, then cards, so it still fits one page
        _inc_cards.compact = True; _inc_cards._recalc()
        _pay_plan.compact = True; _pay_plan._recalc()
    story.append(KeepTogether(_final_parts()))
    story.append(CondPageBreak(doc.height - 14))   # the cancellation page starts fresh, never beside these three

    # ── 7–9. Cancellation Policy + Travel Notes + Contact Card ────────────────
    # Rule 2: these three sections ALWAYS share one page, in the same card look as the pages before.
    canc_data = [
        ("30 days or more before departure",  "Nil (Token forfeited)",          "70%",  "7–10 working days"),
        ("15–29 days before departure",       "25% of total tour cost",          "45%",  "7–10 working days"),
        ("7–14 days before departure",        "50% of total tour cost",          "20%",  "10–14 working days"),
        ("Less than 7 days / No Show",        "100% of total tour cost",         "Nil",  "Not applicable"),
        ("Natural Calamity / Force Majeure",  "Credit note for future travel",   "—",    "As per T&C"),
    ]
    # the cards are built from canc_data, so editing that list above changes the PDF (and the AI assistant)
    canc_tiers = []
    for _when, _chg, _ref, _proc in canc_data[:4]:
        _pct = int(re.sub(r"[^0-9]", "", _ref) or 0)
        canc_tiers.append((_when, "Charge: " + _chg, _pct, _ref,
                           ("Refund in " + _proc) if _pct else "No refund applicable"))
    _fm = canc_data[4]
    _canc = CancellationLadder(usable_w, canc_tiers, _fm[0], _fm[1] + ", " + _fm[3].lower() + ".")
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

    _notes = TravelNotesGrid(usable_w, travel_notes)
    _contact = ContactCard(usable_w, ["+91-9419766510", "+91-9858355260"], "serenevibeskashmir@gmail.com",
                           "www.serenevibeskashmir.com", "Mon–Sat, 9:00 AM – 7:00 PM IST",
                           "NH-44, Lethpora, Jammu & Kashmir – 192122", BUSINESS_GST_NO or "")
    _p2_parts = lambda: [
        SectionTitle(usable_w, "CANCELLATION POLICY", icon=""), Spacer(1, 3*mm), _canc, Spacer(1, 5*mm),
        SectionTitle(usable_w, "IMPORTANT TRAVEL NOTES", icon=""), Spacer(1, 3*mm), _notes, Spacer(1, 5*mm),
        SectionTitle(usable_w, "GET IN TOUCH WITH US", icon=""), Spacer(1, 3*mm), _contact,
    ]
    if sum(f.wrap(usable_w, 10000)[1] for f in _p2_parts()) > _room:     # tighten so all three still fit one page
        _canc.compact = True; _canc._recalc()
        _notes.compact = True; _notes._recalc()
    story.append(KeepTogether(_p2_parts()))

    # ── 10. Terms & Conditions — always on its own page (Rule 3) ──────────────
    story.append(CondPageBreak(doc.height - 14))   # Terms always start on a fresh page
    # T&C data: (heading, body_text)   (plain text only: the AI assistant reads this list)
    tc_sections = [
        ("Bookings & Payments",
         "Your booking is confirmed once the 1st instalment (25%) is received. The 2nd instalment (25%) is due "
         "7 days before arrival and the balance (50%) on arrival, as shown in the Payment Schedule. If we cannot "
         "confirm your booking on the requested dates, the amount paid is refunded in full."),

        ("Travel Plan / Itinerary",
         "This itinerary is planned for you. External factors such as weather, road conditions, natural hazards "
         "and physical ability of participants may require changes before or during the trip, and we will always "
         "rearrange sightseeing for you. Serene Vibes is not responsible for delays or expenses incurred due to "
         "natural calamities, delays or cancellations of your own flights or trains, accidents, transport "
         "breakdown, sickness, political closures or any untoward incidents."),

        ("Child Policy",
         "Children up to age 5 are not charged. Children aged 6-10 are not charged in the package "
         "but meal charges apply. Children aged 11 and above are considered adults and charged accordingly."),

        ("Hotel Policy",
         "Hotels are as mentioned in the itinerary, or similar if not available. Extra bed requests (adult/child) "
         "may be fulfilled with a rollaway bed or mattress subject to availability. Adjacent/adjoining room "
         "requests are also subject to availability. Twin or double bed allocation is at the hotel's discretion."),

        ("Check-In & Check-Out",
         "Standard check-in/out time is 12:00 Noon. Early check-in or late check-out requests can "
         "be made directly with hotel management and settled on-site."),

        ("Documents Required",
         "A government-issued photo ID (Aadhaar / Passport) is mandatory for every guest. Age proof is "
         "required for every child."),

        ("Billing",
         "In case of billing errors the agency reserves the right to re-invoice. Dishonoured cheques "
         "attract a penalty of INR 500 per instance; the agency reserves the right to take legal action."),

        ("Cancellations & Refunds",
         "Cancellation charges and refunds follow the Cancellation Policy in this document. Any alteration or "
         "cancellation after the tour begins may incur penalties, and refunds are not applicable for unused "
         "services. Send refund requests to serenevibeskashmir@gmail.com before the trip starts. Amounts held by "
         "hotels are refunded only upon recovery from the respective vendor."),

        ("Pandemic Limitation",
         "If the tour cannot be availed due to a pandemic, the agency will provide either a refund or "
         "a credit note for future travel, subject to third-party vendor (hotel / transport) conditions."),

        ("Extra Costs",
         "If the Government of India revises taxes or fuel costs after tour finalisation, the incremental "
         "amount will be added to the tour cost after due intimation to the guests."),

        ("Law & Jurisdiction",
         "All disputes, claims, and legal suits relating to any services offered by Serene Vibes are "
         "under the exclusive jurisdiction of Srinagar & Delhi Courts."),

        ("Complaints",
         "For any complaints, contact our nearest operations team member or write to "
         "serenevibeskashmir@gmail.com. We will resolve your concern at the earliest."),
    ]

    # General terms (plain text only: the AI assistant reads this list). Airfare is never sold by us
    # (see Exclusions), so no airline lines here.
    general_bullets = [
        "Carry a confirmed hotel voucher at the time of check-in.",
        "Number of meals corresponds to number of nights booked; breakfast not provided on day of arrival.",
        "The hotel has the right to claim damages incurred by guests.",
        "Mini-bar (if available) is on a chargeable basis.",
        "Cost of additional services outside the package must be settled directly at the hotel.",
    ]

    _tc_grid = TermsGrid(usable_w, tc_sections)
    _tc_gen = GeneralTermsCard(usable_w, general_bullets)
    _tc_parts = lambda: [SectionTitle(usable_w, "TERMS & CONDITIONS", icon=""), Spacer(1, 4*mm), _tc_grid,
                         Spacer(1, 4*mm), _tc_gen]
    if sum(f.wrap(usable_w, 10000)[1] for f in _tc_parts()) > _room:
        _tc_grid.compact = True; _tc_grid._recalc()
        _tc_gen.compact = True; _tc_gen._recalc()
    story.append(KeepTogether(_tc_parts()))
    story.append(Spacer(1, 2*mm))

    # ── Client Acknowledgement / Signature Block (last page, one page, same card look) ──
    story.append(PageBreak())
    ts_gen = datetime.datetime.now(IST)
    ts_valid = (ts_gen + datetime.timedelta(days=7)).strftime("%d %b %Y")
    _stamp_path = next((pp for pp in (
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "auth_stamp.png"),
        os.path.join(os.getcwd(), "backend", "services", "auth_stamp.png"),
        os.path.join(os.getcwd(), "auth_stamp.png"),
    ) if os.path.exists(pp)), None)
    _ack_text = ("I / We, the undersigned, confirm that I / We have read, understood, and agree to all the "
                 "terms and conditions, cancellation policy, and payment schedule outlined in this itinerary "
                 "document issued by Serene Vibes Kashmir. I / We understand that this constitutes a binding "
                 "booking agreement upon payment of the 1st instalment (25%).")
    # What happens next (uses only terms already stated in this document)
    _steps3 = [
        ("Review & sign", "Check the itinerary, hotels and terms, then sign and date this page."),
        ("Pay the 1st instalment", "Confirm the booking with the 1st instalment (25%) by NEFT / UPI / Cheque."),
        ("Receive your vouchers", "We share confirmed hotel and transfer details ahead of your travel date."),
    ]
    ts = ts_gen.strftime("%d %b %Y, %I:%M %p") + " IST"
    _last_parts = [
        SectionTitle(usable_w, "CLIENT ACKNOWLEDGEMENT", icon=""), Spacer(1, 3*mm),
        AgreementCard(usable_w, _ack_text, _quote_ref(client_name), ts_valid), Spacer(1, 3*mm),
        SignatureRow(usable_w, client_name, _stamp_path), Spacer(1, 5*mm),
        SectionTitle(usable_w, "WHAT HAPPENS NEXT", icon=""), Spacer(1, 3*mm),
        NextStepCards(usable_w, _steps3), Spacer(1, 3*mm),
        HelpStrip(usable_w, client_name, _quote_ref(client_name)), Spacer(1, 5*mm),
        SectionTitle(usable_w, "BEFORE YOU TRAVEL", icon=""), Spacer(1, 3*mm),
        TravelEssentials(usable_w, show_bar=False), Spacer(1, 4*mm),
        Paragraph(f"Document generated on {ts}  |  Serene Vibes Kashmir  |  serenevibeskashmir@gmail.com",
                  styles["footer_note"]),
    ]
    story.extend(_last_parts)

    # ── Build PDF ─────────────────────────────────────────────────────────────
    doc._svk_running = (_raw(f"Kashmir Tour Itinerary  |  Prepared for {client_name}"),
                        "Quote No. " + _quote_ref(client_name))
    doc.build(story, onFirstPage=_page_frame, onLaterPages=_page_frame,
              canvasmaker=NumberedCanvas)
    return f"output/{filename}"
