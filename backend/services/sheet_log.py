"""Logs every generated quote PDF as a row in a Google Sheet.

How it works: a tiny Google Apps Script (scripts/google_sheet_logger.gs) is deployed from the sheet as a
Web app. We POST one JSON row to its URL. No Google libraries or service-account keys are needed.

Env vars (both optional - when the URL is empty nothing is sent and PDF generation is unaffected):
    GOOGLE_SHEET_WEBHOOK_URL   the Web app URL from Apps Script (ends in /exec)
    GOOGLE_SHEET_SECRET        any secret word; must match SECRET in the Apps Script
"""
import datetime
import os

import requests

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))


def log_quote(name, quote_no, cost, travel_date):
    """Send one quote to the sheet. Never raises: a Sheets problem must not block the PDF."""
    url = os.getenv("GOOGLE_SHEET_WEBHOOK_URL", "").strip()
    if not url:
        return False
    row = {
        "secret": os.getenv("GOOGLE_SHEET_SECRET", "").strip(),
        "name": str(name or ""),
        "quote_no": str(quote_no or ""),
        "cost": cost if isinstance(cost, (int, float)) else str(cost or ""),
        "travel_date": str(travel_date or ""),
        "generated_at": datetime.datetime.now(IST).strftime("%d %b %Y %H:%M"),
    }
    try:
        r = requests.post(url, json=row, timeout=6)
        ok = r.status_code < 400 and '"ok":true' in r.text.replace(" ", "")
        if not ok:
            print(f"Google Sheet log failed: HTTP {r.status_code} {r.text[:200]}")
        return ok
    except Exception as exc:                       # network error, timeout, ...
        print(f"Google Sheet log failed: {exc}")
        return False
