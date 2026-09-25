from flask import Blueprint, jsonify, request

from backend.extensions import db
from backend.models import Lead

leads_bp = Blueprint("leads", __name__)


@leads_bp.post("/")
def create_lead():
    data = request.json or {}
    lead = Lead(
        name=data["name"],
        email=data["email"],
        phone=data.get("phone", ""),
        budget_min=data.get("budget_min"),
        budget_max=data.get("budget_max"),
        preferred_destinations=data.get("preferred_destinations", ""),
        travel_start=data.get("travel_start", ""),
        travel_end=data.get("travel_end", ""),
        adults=data.get("adults", 2),
        kids=data.get("kids", 0),
    )
    db.session.add(lead)
    db.session.commit()
    return jsonify({"id": lead.id, "message": "lead created"})
