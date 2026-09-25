from flask import Blueprint, jsonify, request

from backend.auth import admin_required
from backend.services.email_service import send_email

email_bp = Blueprint("email", __name__)


@email_bp.post("/send")
@admin_required
def send():
    data = request.json or {}

    recipient = data.get("to_email") or data.get("email_to") or data.get("clientEmail")
    if not recipient:
        return jsonify({"error": "Missing recipient email (to_email)"}), 400

    subject = data.get("subject") or f"Your Travel Itinerary to {data.get('destination', 'Kashmir')}"

    html_body = data.get("html_body")
    if not html_body:
        client = data.get("client_name", "Valued Client")
        dest = data.get("destination", "Kashmir")
        days = data.get("days", "")
        itin_text = data.get("itinerary", "")
        html_body = f"""
        <h3>Hello {client},</h3>
        <p>Thank you for choosing Serene Vibes Kashmir. Here are your custom tour package details:</p>
        <hr/>
        <p><strong>Destination:</strong> {dest}</p>
        <p><strong>Duration:</strong> {days} Days</p>
        <p><strong>Itinerary Details:</strong></p>
        <p style="white-space: pre-line;">{itin_text}</p>
        <hr/>
        <p>Have a wonderful trip!</p>
        """

    result = send_email(recipient, subject, html_body, data.get("pdf_path"))
    return jsonify(result)
