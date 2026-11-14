import io
import os

from flask import Blueprint, jsonify, request, send_file

from backend.auth import admin_required
from backend.services.pdf_service import (generate_pdf, _quote_ref, normalize_extras, _extras_list, _amount_int,
                                          UNION_CAB_PLACES, COUPLE_EXTRAS, _GONDOLA_LABELS, clean_text_list)
from backend.services.pdf_archive import archive_pdf, get_archived_pdf, list_archive
from backend.services.sheet_log import log_quote, send_row

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


def _point_info(raw):
    """Optional looked-up details for a start/end point: {lat, lon, km, hours}. Bad values are dropped."""
    if not isinstance(raw, dict):
        return None
    def num(v, lo, hi):
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None
        return f if lo <= f <= hi else None
    out = {
        "lat": num(raw.get("lat"), -90, 90),
        "lon": num(raw.get("lon"), -180, 180),
        "km": num(raw.get("km"), 0, 5000),
        "hours": num(raw.get("hours"), 0, 100),
    }
    if out["lat"] is None or out["lon"] is None:
        out["lat"] = out["lon"] = None
    return out if any(v is not None for v in out.values()) else None


MEAL_PLANS = {
    "EP": "Room only. No meals included.",
    "CP": "Room + Breakfast",
    "MAP": "Room + Breakfast + One major meal (Lunch or Dinner)",
    "AP": "Room + Breakfast + Lunch + Dinner (All meals)",
}


def _included_extras(value):
    """Which normally-excluded extras are part of this package (admin switches)."""
    return normalize_extras(value)


def _meal_plan(value):
    value = str(value or "").strip().upper()
    return value if value in MEAL_PLANS else "MAP"


def _cost_value(value):
    """Cost as a whole number of rupees, or None when blank, zero or not a number
    (the cost box can send text such as "0.0" or "45000.5")."""
    try:
        n = int(round(float(str(value).replace(",", "").strip())))
    except (TypeError, ValueError, OverflowError):
        return None
    return n if n > 0 else None


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


def _inclusion_labels(payload):
    """Readable names of the optional extras ticked for this quote (cabs, gondola, couple items)."""
    names = {k: f"Union cab - {n}" for k, n in UNION_CAB_PLACES}
    names.update(_GONDOLA_LABELS)
    names.update(dict(COUPLE_EXTRAS))
    out = []
    for k in _extras_list(payload):
        if k == "union_cab_other" and payload.get("cab_other_places"):
            out.append("Union cab - " + ", ".join(payload["cab_other_places"]))
        else:
            out.append(names.get(k, k))
    return out + clean_text_list(payload.get("custom_inclusions"))


@itinerary_bp.route("/sheet-test", methods=["GET", "POST"])
@admin_required
def sheet_test():
    """Sends a TEST row to the Google Sheet and reports exactly what happened (open while logged in as admin)."""
    ok, detail = send_row("TEST - delete me", "SVK-TEST", 1, "Test")
    return jsonify({"ok": ok, "detail": detail}), (200 if ok else 502)


@itinerary_bp.route("/generate", methods=["POST"])
@admin_required
def generate_custom_itinerary():
    data = request.get_json() or {}

    output_dir = os.environ.get("OUTPUT_DIR", "/tmp/output")
    os.makedirs(output_dir, exist_ok=True)

    client_name = data.get("client_name", "Valued Client")
    client_email = str(data.get("client_email") or "").strip()
    days = int(data.get("days", 5))
    budget_tier = data.get("budget_tier", "Mid-Range")
    trip_pace = data.get("trip_pace", "Moderate")
    adults = int(data.get("adults", 2))
    custom_cost = _cost_value(data.get("custom_cost"))
    selected_hotels = data.get("hotelSelections") or data.get("selected_hotels", [])

    start_point = (data.get("start_point") or "").strip() or "Srinagar Airport"
    end_point = (data.get("end_point") or "").strip() or "Srinagar Airport"

    calculated_cost = custom_cost if custom_cost else days * (4000 if budget_tier == "Budget" else 6500)
    vehicle = data.get("vehicle_type") or _vehicle_type(adults)
    meal_plan = _meal_plan(data.get("meal_plan"))

    response_payload = {
        "client_name": client_name,
        "client_email": client_email,
        "days": days,
        "adults": adults,
        "kids": data.get("kids", 0),
        "start_date": data.get("start_date", "Flexible"),
        "budget_tier": budget_tier,
        "vehicle_type": vehicle,
        "meal_plan": meal_plan,
        "trip_pace": trip_pace,
        "start_point": start_point,
        "end_point": end_point,
        "start_info": _point_info(data.get("start_info")),
        "end_info": _point_info(data.get("end_info")),
        "selected_hotels": selected_hotels,
        "hotel_details": data.get("hotel_details") if isinstance(data.get("hotel_details"), dict) else {},
        "custom_cost": custom_cost,
        "show_per_person": bool(data.get("show_per_person", False)),
        "included_extras": _included_extras(data.get("included_extras")),
        "cab_other_places": clean_text_list(data.get("cab_other_places"), 6, 40),
        "custom_inclusions": clean_text_list(data.get("custom_inclusions")),
        "couple": bool(data.get("couple")) and adults == 2,
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
            "meal_plan": meal_plan,
            "start_point": start_point,
            "end_point": end_point,
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

    # Keep a permanent copy of this PDF in the 2nd database (no-op unless DATABASE_URL_2 is set; never blocks the PDF).
    archive_pdf(os.path.join(output_dir, f"Kashmir_Tour_{str(client_name).replace(' ', '_')}.pdf"),
                client_name, _quote_ref(client_name), days, calculated_cost)

    # Record the quote in the Google Sheet (no-op unless GOOGLE_SHEET_WEBHOOK_URL is set; never blocks the PDF).
    _hotel_names = []
    for _h in (response_payload.get("hotel_details") or {}).values():
        _n = (_h or {}).get("name") if isinstance(_h, dict) else None
        if _n and _n not in _hotel_names:
            _hotel_names.append(_n)
    log_quote(client_name, _quote_ref(client_name), calculated_cost, data.get("start_date", "Flexible"), {
        "email": client_email, "days": days, "adults": adults, "kids": data.get("kids", 0),
        "budget_tier": budget_tier, "vehicle": vehicle, "meal_plan": meal_plan,
        "pickup": start_point, "drop": end_point, "hotels": _hotel_names,
        "inclusions": _inclusion_labels(response_payload),
    })

    # On serverless hosting a second request may land on a different instance that
    # doesn't have the file, so the admin asks for the PDF in this same response.
    if data.get("return_pdf"):
        safe_name = str(client_name).replace(" ", "_")
        pdf_path = os.path.join(output_dir, f"Kashmir_Tour_{safe_name}.pdf")
        if os.path.exists(pdf_path):
            return send_file(pdf_path, mimetype="application/pdf", as_attachment=True,
                             download_name=f"Kashmir_Tour_{safe_name}.pdf")
        return jsonify({"error": "PDF was generated but could not be found on the server."}), 500

    return jsonify(response_payload), 200


@itinerary_bp.get("/archive")
@admin_required
def archive_list():
    """List PDFs saved in the 2nd database, newest first (?limit=&offset=)."""
    limit = min(max(request.args.get("limit", 100, type=int), 1), 500)
    offset = max(request.args.get("offset", 0, type=int), 0)
    try:
        rows = list_archive(limit, offset)
    except Exception as exc:
        return jsonify({"error": f"Could not read the PDF archive: {exc}"}), 500
    if rows is None:
        return jsonify({"error": "DATABASE_URL_2 is not set, so there is no PDF archive."}), 404
    return jsonify(rows)


@itinerary_bp.get("/archive/<int:pdf_id>")
@admin_required
def archive_download(pdf_id):
    """Download one archived PDF."""
    try:
        item = get_archived_pdf(pdf_id)
    except Exception as exc:
        return jsonify({"error": f"Could not read the PDF archive: {exc}"}), 500
    if item is None:
        return jsonify({"error": "PDF not found in the archive."}), 404
    filename, data = item
    return send_file(io.BytesIO(data), mimetype="application/pdf", as_attachment=True, download_name=filename)
