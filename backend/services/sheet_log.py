"""Logs every generated quote PDF as a row in a Google Sheet.

How it works: a tiny Google Apps Script (scripts/google_sheet_logger.gs) is deployed from the sheet as a
Web app. We POST one JSON row to its URL. No Google libraries or service-account keys are needed.

Env vars (both optional - when the URL is empty nothing is sent and PDF generation is unaffected):
    GOOGLE_SHEET_WEBHOOK_URL   the Web app URL from Apps Script (ends in /exec)
    GOOGLE_SHEET_SECRET        any secret word; must match SECRET in the Apps Script
"""
import datetime
import json
import os

import requests

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))


def send_row(name, quote_no, cost, travel_date, timeout=8):
    """POST one row. Returns (ok, detail) where detail says exactly what went wrong. Never raises."""
    url = os.getenv("GOOGLE_SHEET_WEBHOOK_URL", "").strip().strip('"').strip("'")
    if not url:
        return False, "GOOGLE_SHEET_WEBHOOK_URL is not set on the server (add it, then redeploy)."
    if not url.endswith("/exec"):
        return False, "GOOGLE_SHEET_WEBHOOK_URL must be the Web app URL ending in /exec (not /dev or the editor link)."
    row = {
        "secret": os.getenv("GOOGLE_SHEET_SECRET", "").strip(),
        "name": str(name or ""),
        "quote_no": str(quote_no or ""),
        "cost": cost if isinstance(cost, (int, float)) else str(cost or ""),
        "travel_date": str(travel_date or ""),
        "generated_at": datetime.datetime.now(IST).strftime("%d %b %Y %H:%M"),
    }
    try:
        # Apps Script answers a POST with a 302 to its result page; requests follows it.
        r = requests.post(url, data=json.dumps(row), headers={"Content-Type": "text/plain;charset=utf-8"},
                          timeout=(4, timeout), allow_redirects=True)
    except requests.exceptions.Timeout:
        return False, f"Apps Script did not answer within {timeout}s."
    except Exception as exc:                       # DNS, TLS, connection reset, ...
        return False, f"Network error: {exc}"
    body = r.text or ""
    try:
        reply = r.json()
    except ValueError:
        reply = None
    if isinstance(reply, dict) and reply.get("ok") is True:
        return True, "updated existing row" if reply.get("updated") else "row added"
    if isinstance(reply, dict):
        return False, f"Apps Script refused it: {reply.get('error') or reply}"
    if "accounts.google.com" in r.url or "<html" in body[:300].lower():
        return False, ("Google returned a web page instead of JSON - the Web app is not deployed with "
                       "'Who has access: Anyone', or the URL is for an old/other deployment. "
                       f"(HTTP {r.status_code})")
    return False, f"Unexpected reply HTTP {r.status_code}: {body[:200]}"


def log_quote(name, quote_no, cost, travel_date):
    """Send one quote to the sheet. Never raises: a Sheets problem must not block the PDF."""
    if not os.getenv("GOOGLE_SHEET_WEBHOOK_URL", "").strip():
        return False
    ok, detail = send_row(name, quote_no, cost, travel_date)
    if not ok:
        print(f"Google Sheet log failed: {detail}")
    return ok
