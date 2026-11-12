"""Saves a copy of every generated PDF into the 2nd database (DATABASE_URL_2).

The PDFs are written ONLY to DATABASE_URL_2, using their own small engine, so the
primary database (and db.create_all()) is not touched. Archiving never blocks or
breaks PDF generation: any error is printed and swallowed.

Every generation is a new row (nothing is overwritten), even when the same client
name is used twice. Only the newest PDF_ARCHIVE_KEEP PDFs (default 30) are kept: saving a
new one automatically deletes the oldest ones beyond that.
"""
import datetime
import os

from sqlalchemy import (Column, DateTime, Integer, LargeBinary, MetaData, String, Table,
                        create_engine, delete, desc, insert, select)

from backend.db_failover import sqlalchemy_url

_metadata = MetaData()
generated_pdfs = Table(
    "generated_pdfs", _metadata,
    Column("id", Integer, primary_key=True),
    Column("created_at", DateTime, nullable=False, index=True),
    Column("client_name", String(150), nullable=False, index=True),
    Column("quote_ref", String(40), nullable=False, default=""),
    Column("filename", String(200), nullable=False),
    Column("days", Integer),
    Column("total_inr", Integer),
    Column("size_bytes", Integer, nullable=False, default=0),
    Column("pdf_data", LargeBinary, nullable=False),
)

KEEP_LAST = max(int(os.getenv("PDF_ARCHIVE_KEEP", "30") or 30), 1)   # how many newest PDFs to keep

_engine = None
_table_ready = False


def _get_engine():
    """Engine for DATABASE_URL_2, or None when it isn't configured."""
    global _engine
    url = os.getenv("DATABASE_URL_2", "").strip()
    if not url:
        return None
    if _engine is None:
        _engine = create_engine(sqlalchemy_url(url), pool_pre_ping=True, pool_recycle=300)
    return _engine


def _ready():
    """Engine with the table created (once per process), or None."""
    global _table_ready
    eng = _get_engine()
    if eng is None:
        return None
    if not _table_ready:
        _metadata.create_all(eng)
        _table_ready = True
    return eng


def archive_pdf(pdf_path, client_name, quote_ref="", days=None, total_inr=None):
    """Store the PDF file at pdf_path in DATABASE_URL_2. Returns the new row id, or None."""
    try:
        eng = _ready()
        if eng is None:
            return None
        with open(pdf_path, "rb") as fh:
            data = fh.read()
        now = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
        with eng.begin() as conn:
            res = conn.execute(insert(generated_pdfs).values(
                created_at=now, client_name=str(client_name)[:150], quote_ref=str(quote_ref or "")[:40],
                filename=os.path.basename(pdf_path)[:200], days=days, total_inr=total_inr,
                size_bytes=len(data), pdf_data=data))
            # Keep only the newest KEEP_LAST rows; delete everything older (same transaction as the insert).
            keep = [r[0] for r in conn.execute(select(generated_pdfs.c.id).order_by(desc(generated_pdfs.c.id)).limit(KEEP_LAST))]
            conn.execute(delete(generated_pdfs).where(generated_pdfs.c.id < min(keep)))
            return res.inserted_primary_key[0]
    except Exception as exc:  # never let archiving break PDF generation
        print(f"PDF archive to DATABASE_URL_2 failed: {exc}")
        return None


def list_archive(limit=100, offset=0):
    """Newest first, without the PDF bytes."""
    eng = _ready()
    if eng is None:
        return None
    cols = [c for c in generated_pdfs.c if c.name != "pdf_data"]
    with eng.connect() as conn:
        rows = conn.execute(select(*cols).order_by(desc(generated_pdfs.c.id)).limit(limit).offset(offset)).mappings().all()
    return [{**dict(r), "created_at": r["created_at"].isoformat() + "Z"} for r in rows]


def get_archived_pdf(pdf_id):
    """(filename, bytes) for one archived PDF, or None."""
    eng = _ready()
    if eng is None:
        return None
    with eng.connect() as conn:
        row = conn.execute(select(generated_pdfs.c.filename, generated_pdfs.c.pdf_data)
                           .where(generated_pdfs.c.id == pdf_id)).first()
    return (row[0], bytes(row[1])) if row else None
