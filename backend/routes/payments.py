"""Payments tab: read the quotes from the Google Sheet and save the amount a client has paid.

    GET  /api/admin/payments               -> {"rows": [...]}  (newest quote first)
    POST /api/admin/payments               -> body {name, quote_no, amount}; writes Booking Amount + Payment Status into the sheet
    POST /api/admin/payments/import/parse  -> JSON {pages: [text of each PDF page], created}  (the browser reads the PDF, so size does not matter)
                                              or multipart "file" (a small PDF); returns the fields read from it
    POST /api/admin/payments/import        -> body {name, quote_no, cost, travel_date, ...}; adds / updates that quote's row in the sheet

The sheet stays the single source of truth: nothing is stored in the database.
"""
from flask import Blueprint, jsonify, request

from backend.auth import admin_required
from backend.services.pdf_import import parse_pages, parse_quote_pdf
from backend.services.sheet_log import call_script, send_row

payments_bp = Blueprint("payments", __name__)

MAX_PDF_BYTES = 4 * 1024 * 1024          # the host rejects request bodies over ~4.5 MB


@payments_bp.get("/admin/payments")
@admin_required
def list_payments():
    data, error = call_script("list")
    if error:
        return jsonify({"error": error}), 502
    return jsonify({"rows": data.get("rows", [])})


@payments_bp.post("/admin/payments")
@admin_required
def save_payment():
    body = request.get_json(silent=True) or {}
    name = str(body.get("name") or "").strip()
    quote_no = str(body.get("quote_no") or "").strip()
    try:
        amount = int(round(float(str(body.get("amount")).replace(",", "").strip())))
    except (TypeError, ValueError, OverflowError):
        return jsonify({"error": "Enter the amount as a number."}), 400
    if not name or not quote_no:
        return jsonify({"error": "Quote not specified."}), 400
    if amount < 0 or amount > 100_000_000:
        return jsonify({"error": "Amount is out of range."}), 400
    data, error = call_script("pay", {"name": name, "quote_no": quote_no, "amount": amount})
    if error:
        return jsonify({"error": error}), 502
    return jsonify({"ok": True, "row": data.get("row")})


@payments_bp.post("/admin/payments/import/parse")
@admin_required
def import_parse():
    """Read ONE old quote PDF. Nothing is written to the sheet here."""
    body = request.get_json(silent=True)
    if isinstance(body, dict) and isinstance(body.get("pages"), list):
        try:
            return jsonify(parse_pages(body["pages"], body.get("created")))
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 422
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "Choose a PDF file."}), 400
    data = f.read(MAX_PDF_BYTES + 1)
    if len(data) > MAX_PDF_BYTES:
        return jsonify({"error": "This PDF is over 4 MB, too big to upload here."}), 413
    if not data.startswith(b"%PDF"):
        return jsonify({"error": "This is not a PDF file."}), 400
    try:
        result = parse_quote_pdf(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 422
    return jsonify(result)


@payments_bp.post("/admin/payments/import")
@admin_required
def import_row():
    """Write ONE reviewed quote into the Quotes tab. The same name + quote number updates its row instead of duplicating it."""
    b = request.get_json(silent=True) or {}
    name = str(b.get("name") or "").strip()
    quote_no = str(b.get("quote_no") or "").strip()
    if not name or not quote_no:
        return jsonify({"error": "Client name and quote number are required."}), 400
    try:
        cost = int(round(float(str(b.get("cost")).replace(",", "").strip())))
    except (TypeError, ValueError, OverflowError):
        return jsonify({"error": "Cost must be a number."}), 400
    if cost <= 0 or cost > 100_000_000:
        return jsonify({"error": "Cost is out of range."}), 400

    extra = {k: b.get(k) for k in ("email", "days", "adults", "kids", "budget_tier", "vehicle", "meal_plan",
                                   "pickup", "drop", "hotels", "inclusions")}
    if str(b.get("generated_at") or "").strip():
        extra["generated_at"] = str(b["generated_at"]).strip()[:40]     # keep the original date, not today
    ok, detail = send_row(name, quote_no, cost, str(b.get("travel_date") or "").strip(), extra)
    if not ok:
        return jsonify({"error": detail}), 502
    return jsonify({"ok": True, "detail": detail})
