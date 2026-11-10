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
import threading

import requests

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))


def send_row(name, quote_no, cost, travel_date, extra=None, timeout=8):
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
    for k, v in (extra or {}).items():             # extra columns: email, days, adults, kids, ...
        row[k] = ", ".join(map(str, v)) if isinstance(v, (list, tuple)) else ("" if v is None else str(v))
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


def log_quote(name, quote_no, cost, travel_date, extra=None):
    """Send one quote to the sheet. Never raises and never waits more than ~4.5s, so a slow Google
    can't push the PDF request past the host's 10s limit."""
    if not os.getenv("GOOGLE_SHEET_WEBHOOK_URL", "").strip():
        return False
    result = {}

    def work():
        result["r"] = send_row(name, quote_no, cost, travel_date, extra, timeout=4)

    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(4.5)
    if "r" not in result:
        print("Google Sheet log failed: no answer from Apps Script within 4.5s")
        return False
    ok, detail = result["r"]
    if not ok:
        print(f"Google Sheet log failed: {detail}")
    return ok


def call_script(action, payload=None, timeout=8):
    """Ask the Apps Script to do something other than log a quote ("list" or "pay").
    Returns (data, error): data is the script's JSON reply when it says ok, otherwise None and error says why. Never raises."""
    url = os.getenv("GOOGLE_SHEET_WEBHOOK_URL", "").strip().strip('"').strip("'")
    if not url or not url.endswith("/exec"):
        return None, "GOOGLE_SHEET_WEBHOOK_URL is not set to the Apps Script Web app URL (ending in /exec)."
    body = {"secret": os.getenv("GOOGLE_SHEET_SECRET", "").strip(), "action": action, **(payload or {})}
    try:
        r = requests.post(url, data=json.dumps(body), headers={"Content-Type": "text/plain;charset=utf-8"},
                          timeout=(4, timeout), allow_redirects=True)
    except requests.exceptions.Timeout:
        return None, f"Google Sheet did not answer within {timeout}s. Try again."
    except Exception as exc:
        return None, f"Network error: {exc}"
    try:
        reply = r.json()
    except ValueError:
        return None, ("Google returned a web page instead of data. In Apps Script, deploy a NEW version of the "
                      "Web app (Who has access: Anyone) with the latest script.")
    if not isinstance(reply, dict) or reply.get("ok") is not True:
        err = reply.get("error") if isinstance(reply, dict) else None
        return None, f"Google Sheet refused it: {err or reply}"
    return reply, None
