import os

from flask import Blueprint, jsonify, request

from backend.auth import admin_required
from backend.services.pdf_service import generate_pdf

itinerary_bp = Blueprint("itinerary", __name__)

DEFAULT_TIMELINE = [
    {
        "day": 1,
        "title": "Arrival in Srinagar & Leisure Exploration",
        "date": "Day 1 Plan",
        "overnight_stay": "Srinagar",
        "schedule": [
            {"time_slot": "Morning", "activity_title": "Airport Pickup", "description": "Meet driver at Srinagar Airport and check into your houseboat."},
            {"time_slot": "Evening", "activity_title": "Shikara Ride", "description": "Enjoy a 1-hour sunset Shikara ride on Dal Lake."},
        ],
    },
    {
        "day": 2,
        "title": "Excursion to the Alpine Meadows of Gulmarg",
        "date": "Day 2 Plan",
        "overnight_stay": "Srinagar",
        "schedule": [
            {"time_slot": "09:00 AM", "activity_title": "Gulmarg Excursion", "description": "Drive to Gulmarg for snow activities and explore Phase 1 Gondola cable car ride."},
        ],
    },
    {
        "day": 3,
        "title": "Srinagar to Pahalgam (Valley of Shepherds)",
        "date": "Day 3 Plan",
        "overnight_stay": "Pahalgam",
        "schedule": [
            {"time_slot": "08:30 AM", "activity_title": "Srinagar to Pahalgam", "description": "Travel to Pahalgam. Stop at beautiful saffron fields and Avantipur temple ruins along the highway stretch."},
        ],
    },
    {
        "day": 4,
        "title": "Exploring Local Valleys of Pahalgam",
        "date": "Day 4 Plan",
        "overnight_stay": "Srinagar",
        "schedule": [
            {"time_slot": "10:00 AM", "activity_title": "Pahalgam Local Sightseeing", "description": "Visit Aru Valley and Betaab Valley via local eco-union cabs."},
        ],
    },
    {
        "day": 5,
        "title": "Srinagar to Sonamarg (Meadow of Gold)",
        "date": "Day 5 Plan",
        "overnight_stay": "Srinagar",
        "schedule": [
            {"time_slot": "09:00 AM", "activity_title": "Sonamarg Excursion", "description": "Day excursion to Sonamarg along the Sindh River, visiting Thajiwas Glacier via pony or local union vehicle."},
            {"time_slot": "04:00 PM", "activity_title": "Return to Srinagar", "description": "Return drive back to Srinagar for overnight stay."},
        ],
    },
    {
        "day": 6,
        "title": "Extended Exploration & Adventure Activities",
        "date": "Day 6 Plan",
        "overnight_stay": "Srinagar",
        "schedule": [
            {"time_slot": "09:00 AM", "activity_title": "Adventure Activity", "description": "Choose from adventure sports like trekking, fishing, or visit to lesser-known destinations based on your preferences and season."},
            {"time_slot": "05:00 PM", "activity_title": "Evening Leisure", "description": "Return to hotel and relax. Optional: enjoy traditional Kashmiri tea and pastries."},
        ],
    },
    {
        "day": 7,
        "title": "Cultural Immersion & Local Markets",
        "date": "Day 7 Plan",
        "overnight_stay": "Srinagar",
        "schedule": [
            {"time_slot": "10:00 AM", "activity_title": "Local Market Tour", "description": "Visit traditional bazaars like Lal Chowk and explore Kashmiri handicrafts, carpets, and local artisan workshops."},
            {"time_slot": "02:00 PM", "activity_title": "Culinary Experience", "description": "Enjoy authentic Kashmiri cuisine at a local restaurant. Learn about traditional dishes and spices."},
            {"time_slot": "06:00 PM", "activity_title": "Evening Exploration", "description": "Explore the old city streets or visit a local craft workshop."},
        ],
    },
    {
        "day": 8,
        "title": "Wellness & Leisure Day",
        "date": "Day 8 Plan",
        "overnight_stay": "Srinagar",
        "schedule": [
            {"time_slot": "09:00 AM", "activity_title": "Wellness Activities", "description": "Enjoy spa treatments, yoga, or meditation sessions. Optional: Ayurvedic massage or wellness retreat."},
            {"time_slot": "01:00 PM", "activity_title": "Lunch Break", "description": "Relax at your hotel and enjoy a leisurely lunch with a view of Dal Lake."},
            {"time_slot": "04:00 PM", "activity_title": "Personal Exploration", "description": "Time for shopping, personal activities, or optional visits to any missed attractions."},
        ],
    },
    {
        "day": 9,
        "title": "Souvenir Shopping & Departure Transfer",
        "date": "Day 9 Plan",
        "overnight_stay": "Departure",
        "schedule": [
            {"time_slot": "11:00 AM", "activity_title": "Souvenir Shopping", "description": "Quick drop at local emporiums for authentic walnuts, saffron, and pashmina shawls before heading to airport terminal entry gates."},
        ],
    },
]


def _vehicle_type(adults):
    adults = int(adults or 2)
    if adults <= 3:
        return "Sedan"
    if adults <= 7:
        return "Ertiga/Innova"
    return "Tempo/Traveler"


def _build_default_timeline(days):
    """
    Build a default timeline of exactly `days` entries where the LAST day
    is always the departure day, no matter how short the trip is.

    DEFAULT_TIMELINE's final entry is the departure template. Everything
    before it is regular sightseeing content. For a trip of length `days`
    we take the first (days - 1) sightseeing days and then append the
    departure day, renumbered to be the actual last day.
    """
    days = max(days, 1)
    sightseeing_days = DEFAULT_TIMELINE[:-1]
    departure_template = DEFAULT_TIMELINE[-1]

    if days == 1:
        # Single-day trip: nothing but arrival/departure.
        timeline = []
    else:
        timeline = [dict(d) for d in sightseeing_days[: days - 1]]

    departure_day = dict(departure_template)
    departure_day["day"] = days
    departure_day["date"] = f"Day {days} Plan"
    timeline.append(departure_day)

    return timeline


@itinerary_bp.route("/generate", methods=["POST"])
@admin_required
def generate_custom_itinerary():
    data = request.get_json() or {}

    output_dir = os.environ.get("OUTPUT_DIR", "/tmp/output")
    os.makedirs(output_dir, exist_ok=True)

    client_name = data.get("client_name", "Valued Client")
    client_email = data.get("client_email", "N/A")
    days = int(data.get("days", 5))
    budget_tier = data.get("budget_tier", "Mid-Range")
    trip_pace = data.get("trip_pace", "Moderate")
    adults = int(data.get("adults", 2))
    custom_cost = data.get("custom_cost")
    selected_hotels = data.get("hotelSelections") or data.get("selected_hotels", [])

    calculated_cost = int(custom_cost) if custom_cost else days * (4000 if budget_tier == "Budget" else 6500)
    vehicle = data.get("vehicle_type") or _vehicle_type(adults)

    response_payload = {
        "client_name": client_name,
        "client_email": client_email,
        "days": days,
        "adults": adults,
        "kids": data.get("kids", 0),
        "start_date": data.get("start_date", "Flexible"),
        "budget_tier": budget_tier,
        "vehicle_type": vehicle,
        "trip_pace": trip_pace,
        "selected_hotels": selected_hotels,
        "custom_cost": custom_cost,
        "meta_summary": {
            "client_name": client_name,
            "client_email": client_email,
            "total_days": days,
            "budget_tier": budget_tier,
            "trip_pace": trip_pace,
            "kids": data.get("kids", 0),
            "adults": adults,
            "start_date": data.get("start_date", "Flexible"),
            "vehicle_type": vehicle,
        },
        "logistics": {"assigned_vehicle": vehicle},
        "financial_summary": {"total_payable_inr": calculated_cost},
        "timeline": data.get("timeline") or _build_default_timeline(days),
    }

    if not data.get("timeline"):
        response_payload["timeline"] = _build_default_timeline(days)

    response_payload["itinerary_timeline"] = response_payload["timeline"]

    try:
        generate_pdf(response_payload)
    except Exception as pdf_error:
        print(f"PDF Generation Failed: {pdf_error}")
        return jsonify({"error": f"Failed to build file structure: {pdf_error}"}), 500

    return jsonify(response_payload), 200
