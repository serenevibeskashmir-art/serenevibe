"""Expenses & profit: entries live in the "Expenses" tab of the same Google Sheet as the quotes.

    GET    /api/admin/ledger        -> {"rows": [...]}  (newest date first)
    POST   /api/admin/ledger        -> body {type, amount, date, category, description, quote_no, client}; adds one row
    DELETE /api/admin/ledger/<id>   -> removes that row

Like payments, the sheet is the single source of truth: nothing is stored in the database.
"""
import datetime

from flask import Blueprint, jsonify, request

from backend.auth import admin_required
from backend.services.sheet_log import call_script

ledger_bp = Blueprint("ledger", __name__)

TYPES = {"profit": "Profit", "expense": "Expense"}
MAX_AMOUNT = 100_000_000


@ledger_bp.get("/admin/ledger")
@admin_required
def list_ledger():
    data, error = call_script("ledger_list")
    if error:
        return jsonify({"error": error}), 502
    return jsonify({"rows": data.get("rows", [])})


@ledger_bp.post("/admin/ledger")
@admin_required
def add_ledger():
    body = request.get_json(silent=True) or {}

    kind = TYPES.get(str(body.get("type") or "").strip().lower())
    if not kind:
        return jsonify({"error": "Choose Profit or Expense."}), 400

    try:
        amount = round(float(str(body.get("amount")).replace(",", "").strip()), 2)
    except (TypeError, ValueError, OverflowError):
        return jsonify({"error": "Enter the amount as a number."}), 400
    if not (0 < amount <= MAX_AMOUNT):
        return jsonify({"error": "Amount must be more than 0 and under ₹10 crore."}), 400

    date_text = str(body.get("date") or "").strip()
    try:
        datetime.date.fromisoformat(date_text)
    except ValueError:
        return jsonify({"error": "Pick a valid date."}), 400

    payload = {
        "type": kind,
        "amount": amount,
        "date": date_text,
        "category": str(body.get("category") or "").strip()[:60],
        "description": str(body.get("description") or "").strip()[:300],
        "quote_no": str(body.get("quote_no") or "").strip()[:40],
        "client": str(body.get("client") or "").strip()[:80],
    }
    data, error = call_script("ledger_add", payload)
    if error:
        return jsonify({"error": error}), 502
    return jsonify({"ok": True, "row": data.get("row")})


@ledger_bp.delete("/admin/ledger/<entry_id>")
@admin_required
def delete_ledger(entry_id):
    entry_id = (entry_id or "").strip()
    if not entry_id or len(entry_id) > 64:
        return jsonify({"error": "Entry not specified."}), 400
    data, error = call_script("ledger_delete", {"id": entry_id})
    if error:
        return jsonify({"error": error}), 502
    return jsonify({"ok": True})
