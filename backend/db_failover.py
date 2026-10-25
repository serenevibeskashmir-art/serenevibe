"""Two-Neon-database failover.

DATABASE_URL    -> primary Neon database (always tried first)
DATABASE_URL_2  -> secondary Neon database (used only when the primary can't be reached)

The pool's `creator` hook is called every time SQLAlchemy needs a *new* connection.
It tries the primary with a short timeout and falls back to the secondary. Because
the pool recycles connections every 5 minutes (see Config), the app drifts back to
the primary on its own once it is healthy again.

Note: this switches *connections*, it does not copy data between the databases.
"""
import os

import psycopg2

CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", "5"))  # seconds to wait for each database


def normalize(url: str) -> str:
    """Neon/Heroku style URL -> plain libpq URI that psycopg2.connect() accepts."""
    if not url:
        return ""
    url = url.strip()
    for prefix in ("postgresql+psycopg2://", "postgresql+psycopg://", "postgres://"):
        if url.startswith(prefix):
            return "postgresql://" + url[len(prefix):]
    return url


def sqlalchemy_url(url: str) -> str:
    """Same URL, pinned to the psycopg2 driver for SQLAlchemy."""
    return normalize(url).replace("postgresql://", "postgresql+psycopg2://", 1)


def make_creator(primary: str, secondary: str):
    primary, secondary = normalize(primary), normalize(secondary)

    def creator():
        try:
            return psycopg2.connect(primary, connect_timeout=CONNECT_TIMEOUT)
        except psycopg2.OperationalError as exc:
            print(f"Primary database unreachable ({str(exc).strip().splitlines()[0][:150]}); using DATABASE_URL_2")
            return psycopg2.connect(secondary, connect_timeout=CONNECT_TIMEOUT)

    return creator
