from dotenv import load_dotenv

load_dotenv()

import os


class Config:
    # Neon (and some platforms) give 'postgres://' — SQLAlchemy needs 'postgresql://'
    _db_url = os.getenv("DATABASE_URL", "sqlite:///travel.db")
    SQLALCHEMY_DATABASE_URI = _db_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Neon serverless: recycle connections to avoid 'SSL connection closed' errors
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,   # test connection before using from pool
        "pool_recycle": 300,     # recycle connections every 5 minutes
    }
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

    # --- AI Kashmir Travel Assistant (optional; the chat button stays hidden without a key) ---
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    ASSISTANT_MODEL = os.getenv("ASSISTANT_MODEL", "openai/gpt-oss-120b")
    ASSISTANT_TIMEOUT = float(os.getenv("ASSISTANT_TIMEOUT", "9"))          # seconds to wait for the model
    ASSISTANT_HOURLY_LIMIT = int(os.getenv("ASSISTANT_HOURLY_LIMIT", "25"))  # messages per visitor per hour
    ASSISTANT_DAILY_LIMIT = int(os.getenv("ASSISTANT_DAILY_LIMIT", "80"))    # messages per visitor per day
    ASSISTANT_SITE_DAILY_CAP = int(os.getenv("ASSISTANT_SITE_DAILY_CAP", "1500"))  # all visitors, per day (cost guard)
