"""Payments tab: read the quotes from the Google Sheet and save the amount a client has paid.

    GET  /api/admin/payments   -> {"rows": [...]}  (newest quote first)
    POST /api/admin/payments   -> body {name, quote_no, amount}; writes Booking Amount + Payment Status into the sheet

The sheet stays the single source of truth: nothing is stored in the database.
"""
from flask import Blueprint, jsonify, request

from backend.auth import admin_required
from backend.services.sheet_log import call_script

payments_bp = Blueprint("payments", __name__)


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
