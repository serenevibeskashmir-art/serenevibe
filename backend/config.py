from dotenv import load_dotenv

load_dotenv()

import os


class Config:
    # Neon (and some platforms) give 'postgres://' — SQLAlchemy needs 'postgresql://'
    _db_url = os.getenv("DATABASE_URL", "sqlite:///travel.db")
    _db_url = _db_url.replace("postgres://", "postgresql://", 1)
    # Some providers hand out connection strings pinned to the psycopg v3 driver
    # ('postgresql+psycopg://'), but only psycopg2-binary is installed (see
    # requirements.txt). Force the driver we actually have so this never breaks
    # depending on which format the DB provider's dashboard gives you.
    if _db_url.startswith("postgresql+psycopg://"):
        _db_url = _db_url.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)
    elif _db_url.startswith("postgresql://"):
        _db_url = _db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Neon serverless: recycle connections to avoid 'SSL connection closed' errors
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,   # test connection before using from pool
        "pool_recycle": 300,     # recycle connections every 5 minutes
    }
    # Optional 2nd Neon database used as a failover when DATABASE_URL can't be reached.
    DATABASE_URL_2 = os.getenv("DATABASE_URL_2", "").strip()
    if DATABASE_URL_2 and SQLALCHEMY_DATABASE_URI.startswith("postgresql"):
        from backend.db_failover import make_creator
        SQLALCHEMY_ENGINE_OPTIONS["creator"] = make_creator(SQLALCHEMY_DATABASE_URI, DATABASE_URL_2)
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

    # --- Cloudinary image storage (optional; without these, images stay in the database) ---
    # Either set CLOUDINARY_URL=cloudinary://<api_key>:<api_secret>@<cloud_name>  (copy it from the
    # Cloudinary dashboard) or the three separate variables below.
    CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "").strip()
    CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "").strip()
    CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "").strip()
    _cld_url = os.getenv("CLOUDINARY_URL", "").strip()
    if _cld_url.startswith("cloudinary://") and not (CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET):
        from urllib.parse import urlparse as _urlparse
        _u = _urlparse(_cld_url)
        CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET, CLOUDINARY_CLOUD_NAME = _u.username or "", _u.password or "", _u.hostname or ""

    # Hotel photos: set CLOUDINARY_HOTEL_PHOTOS=false to keep them in the database (Neon) instead.
    CLOUDINARY_HOTEL_PHOTOS = os.getenv("CLOUDINARY_HOTEL_PHOTOS", "true").strip().lower() not in ("0", "false", "no", "off")

    # --- AI Kashmir Travel Assistant (optional; the chat button stays hidden without a key) ---
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    ASSISTANT_MODEL = os.getenv("ASSISTANT_MODEL", "openai/gpt-oss-120b")
    ASSISTANT_TIMEOUT = float(os.getenv("ASSISTANT_TIMEOUT", "9"))          # seconds to wait for the model
    ASSISTANT_HOURLY_LIMIT = int(os.getenv("ASSISTANT_HOURLY_LIMIT", "25"))  # messages per visitor per hour
    ASSISTANT_DAILY_LIMIT = int(os.getenv("ASSISTANT_DAILY_LIMIT", "80"))    # messages per visitor per day
    ASSISTANT_SITE_DAILY_CAP = int(os.getenv("ASSISTANT_SITE_DAILY_CAP", "1500"))  # all visitors, per day (cost guard)

    # --- WhatsApp lead capture (optional; webhook rejects everything until these are set) ---
    WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "")   # any secret word you choose; paste the same one in Meta
    WHATSAPP_APP_SECRET = os.getenv("WHATSAPP_APP_SECRET", "")       # Meta app secret, used to check messages really come from Meta
