from flask import Blueprint, jsonify, request

from backend.extensions import db
from backend.models import Package

packages_bp = Blueprint("packages", __name__)


@packages_bp.post("/")
def create_package():
    data = request.json or {}
    pkg = Package(
        name=data["name"],
        duration=data.get("duration", ""),
        route=data.get("route", ""),
        total_cost=data.get("total_cost", 0),
        cab_type=data.get("cab_type", "Sedan"),
        hotel_category=data.get("hotel_category", "Deluxe"),
        inclusions=data.get("inclusions", "[]"),
        exclusions=data.get("exclusions", "[]"),
        day_plan=data.get("day_plan", "[]"),
    )
    db.session.add(pkg)
    db.session.commit()
    return jsonify({"id": pkg.id, "message": "package created"})
