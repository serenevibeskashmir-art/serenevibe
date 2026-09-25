from datetime import datetime, timezone

from sqlalchemy.orm import deferred

from backend.extensions import db


class Lead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20))
    budget_min = db.Column(db.Integer)
    budget_max = db.Column(db.Integer)
    preferred_destinations = db.Column(db.Text)
    travel_start = db.Column(db.String(20))
    travel_end = db.Column(db.String(20))
    adults = db.Column(db.Integer, default=2)
    kids = db.Column(db.Integer, default=0)


class Package(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    duration = db.Column(db.String(20))
    route = db.Column(db.Text)
    total_cost = db.Column(db.Integer)
    cab_type = db.Column(db.String(50))
    hotel_category = db.Column(db.String(50))
    inclusions = db.Column(db.Text)
    exclusions = db.Column(db.Text)
    day_plan = db.Column(db.Text)


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("lead.id"), nullable=False)
    package_id = db.Column(db.Integer, db.ForeignKey("package.id"), nullable=False)
    status = db.Column(db.String(50), default="draft")
    pdf_path = db.Column(db.Text)
    email_status = db.Column(db.String(50), default="not_sent")


class HotelImages(db.Model):
    """
    Stores reference photos for each hotel, keyed by hotel ID (e.g. 'htk', 'sghb').
    images_json holds a JSON array of image sources — either https:// URLs or
    base64 data URLs (data:image/jpeg;base64,...) from device uploads.
    Stored in the database so photos survive Render restarts and redeploys.
    """
    __tablename__ = "hotel_images"
    id        = db.Column(db.Integer, primary_key=True)
    hotel_id  = db.Column(db.String(20), unique=True, nullable=False, index=True)
    images_json = db.Column(db.Text, nullable=False, default="[]")


def _utc_now():
    """Naive UTC timestamp (works identically on SQLite and PostgreSQL)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class SitePhoto(db.Model):
    """
    One row per photo slot on the PUBLIC website (hero, destinations, packages,
    about, gallery). The slot list itself lives in routes/site_photos.py.

    The image bytes are stored in the database so photos survive redeploys and
    serverless cold starts. `data` is deferred, so listing photos never loads
    the image bytes. This table is separate from HotelImages, which belongs to
    the itinerary/PDF tool.
    """
    __tablename__ = "site_photos"
    id         = db.Column(db.Integer, primary_key=True)
    slot       = db.Column(db.String(40), unique=True, nullable=False, index=True)
    data       = deferred(db.Column(db.LargeBinary, nullable=False))
    mime       = db.Column(db.String(40), nullable=False)
    size       = db.Column(db.Integer, nullable=False, default=0)
    alt        = db.Column(db.String(200), nullable=False, default="")
    updated_at = db.Column(db.DateTime, nullable=False, default=_utc_now, onupdate=_utc_now)


class SiteLink(db.Model):
    """
    An optional link attached to a website photo slot (currently the Highlights
    video card: the thumbnail is a SitePhoto, the video URL lives here).

    Kept in its own table, rather than a new column on `site_photos`, so that
    `db.create_all()` creates it automatically on an existing database.
    No manual migration is needed.
    """
    __tablename__ = "site_links"
    id         = db.Column(db.Integer, primary_key=True)
    slot       = db.Column(db.String(40), unique=True, nullable=False, index=True)
    url        = db.Column(db.String(500), nullable=False, default="")
    updated_at = db.Column(db.DateTime, nullable=False, default=_utc_now, onupdate=_utc_now)


class SiteSetting(db.Model):
    """Small key/value store for admin-editable site settings (e.g. the AI assistant's
    on/off switch and the owner's rate notes). Created automatically by db.create_all()."""
    __tablename__ = "site_settings"
    key        = db.Column(db.String(60), primary_key=True)
    value      = db.Column(db.Text, nullable=False, default="")
    updated_at = db.Column(db.DateTime, nullable=False, default=_utc_now, onupdate=_utc_now)


class AssistantUsage(db.Model):
    """One row per AI-assistant message, used for rate limiting. Only a salted hash of the
    visitor's IP is stored, never the IP itself and never the message text."""
    __tablename__ = "assistant_usage"
    id         = db.Column(db.Integer, primary_key=True)
    ip_hash    = db.Column(db.String(64), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utc_now, index=True)


class SitePackage(db.Model):
    """
    One row per "Structured Itinerary" card shown on the public homepage
    (Packages section). Fully editable from the admin panel (/admin, tab
    "Packages"): text fields plus a photo, stored the same way as SitePhoto
    so it survives redeploys.
    """
    __tablename__ = "site_packages"
    id           = db.Column(db.Integer, primary_key=True)
    position     = db.Column(db.Integer, nullable=False, default=0, index=True)
    badge        = db.Column(db.String(60), nullable=False, default="")
    duration     = db.Column(db.String(60), nullable=False, default="")
    name         = db.Column(db.String(150), nullable=False, default="")
    description  = db.Column(db.Text, nullable=False, default="")
    features     = db.Column(db.Text, nullable=False, default="[]")  # JSON array of strings
    price_label  = db.Column(db.String(40), nullable=False, default="")
    price_note   = db.Column(db.String(40), nullable=False, default="/ person")
    featured     = db.Column(db.Boolean, nullable=False, default=False)
    placeholder  = db.Column(db.String(20), nullable=False, default="lake")  # lake | pine | slate
    # --- photo (same pattern as SitePhoto) ---
    photo_data   = deferred(db.Column(db.LargeBinary, nullable=True))
    photo_mime   = db.Column(db.String(40), nullable=True)
    photo_size   = db.Column(db.Integer, nullable=False, default=0)
    photo_alt    = db.Column(db.String(200), nullable=False, default="")
    updated_at   = db.Column(db.DateTime, nullable=False, default=_utc_now, onupdate=_utc_now)
