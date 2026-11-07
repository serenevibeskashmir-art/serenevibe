import { useState } from "react";
import { apiFetch } from "../api.js";
import { VEHICLE_OPTIONS, MEAL_PLANS } from "../pages/QuotePreview.jsx";

export default function LeadForm({ onGenerated, trip = { vehicle: "", meal: "MAP" }, onTripChange = () => {} }) {
  const [destination, setDestination] = useState("Kashmir");
  const [days, setDays] = useState(5);
  const [clientName, setClientName] = useState("");
  const [startDate, setStartDate] = useState("");
  const [adults, setAdults] = useState(2);
  const [clientEmail, setClientEmail] = useState("");
  const [kids, setKids] = useState(0);
  const [tripPace, setTripPace] = useState("Moderate");
  const [budgetTier, setBudgetTier] = useState("Mid-Range");
  const [customVehicle, setCustomVehicle] = useState(false);   // "Other…" chosen in the vehicle list
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    let endDate = startDate;
    if (startDate) {
      let dateObj = new Date(startDate);
      dateObj.setDate(dateObj.getDate() + parseInt(days));
      endDate = dateObj.toISOString().split("T")[0];
    }

    const payload = {
      destination,
      days: parseInt(days) || 5,
      client_name: clientName || "Valued Client",
      client_email: clientEmail.trim(),   // optional; the PDF shows xxx@gmail.com when blank
      start_date: startDate || "TBD",
      adults: parseInt(adults) || 2,
      trip_pace: tripPace,
      kids: parseInt(kids) || 0,
      budget_tier: budgetTier,
      meal_plan: trip.meal || "MAP",
      ...(trip.vehicle.trim() ? { vehicle_type: trip.vehicle.trim() } : {}),   // blank = auto by group size
    };

    try {
      const response = await apiFetch("/api/itinerary/generate", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.error || "Failed to generate itinerary.");
      }

      onGenerated(result);

      setTimeout(() => {
        const target = document.getElementById("qp-top");
        if (target) {
          target.scrollIntoView({ behavior: "smooth", block: "start" });
        } else {
          window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
        }
      }, 150);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fieldStyle = { display: "flex", flexDirection: "column", gap: "3px", minWidth: 0 };
  const labelStyle = { fontSize: "0.76rem", fontWeight: "600", color: "#3d5a62", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" };
  const inputStyle = { width: "100%", padding: "6px 10px", borderRadius: "8px", border: "1px solid #c6d4d3", fontSize: "0.92rem", color: "#10272e", backgroundColor: "#fff", boxSizing: "border-box", minHeight: "38px" };
  const vehicleValue = customVehicle || (trip.vehicle && !VEHICLE_OPTIONS.includes(trip.vehicle)) ? "__custom" : trip.vehicle;

  return (
    <>
      <style>{`
        .lf-form { max-width: 820px; margin: 14px auto; padding: clamp(14px, 3vw, 20px); background: #fff; border-radius: 16px; border: 1px solid #d5e0df; border-top: 4px solid #c98a14; box-shadow: 0 18px 36px -26px rgba(16,39,46,.55); font-family: Inter, system-ui, -apple-system, "Segoe UI", sans-serif; box-sizing: border-box; }
        .lf-form input, .lf-form select { transition: border-color .15s, box-shadow .15s; }
        .lf-form input:hover, .lf-form select:hover { border-color: #8fb3ba !important; }
        .lf-form input:focus-visible, .lf-form select:focus-visible { outline: none; border-color: #1b5666 !important; box-shadow: 0 0 0 3px rgba(27,86,102,.18); }
        .lf-submit { transition: transform .12s, box-shadow .15s, background-color .2s; box-shadow: 0 10px 20px -12px rgba(16,39,46,.8); border-bottom: 3px solid #c98a14 !important; }
        .lf-submit:hover:not(:disabled) { background-color: #17414d !important; }
        .lf-submit:active:not(:disabled) { transform: translateY(1px); }
        .lf-submit:focus-visible { outline: 3px solid #c98a14; outline-offset: 2px; }
        @media (prefers-reduced-motion: reduce) { .lf-form * { transition: none !important; } }
        .lf-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px 12px; }
        .lf-span2 { grid-column: span 2; }
        .lf-full { grid-column: 1 / -1; }
        @media (max-width: 600px) {
          .lf-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 10px; }
          .lf-form { margin: 8px auto; border-radius: 12px; }
        }
      `}</style>

      <form onSubmit={handleSubmit} className="lf-form">
        <div className="lf-grid">
          <div style={fieldStyle}>
            <label style={labelStyle}>Destination</label>
            <input type="text" value={destination} onChange={(e) => setDestination(e.target.value)} style={inputStyle} required />
          </div>
          <div style={fieldStyle}>
            <label style={labelStyle}>Days</label>
            <input type="number" value={days} onChange={(e) => setDays(e.target.value)} style={inputStyle} required />
          </div>
          <div style={fieldStyle}>
            <label style={labelStyle}>Adults</label>
            <input type="number" value={adults} onChange={(e) => setAdults(e.target.value)} style={inputStyle} required />
          </div>
          <div style={fieldStyle}>
            <label style={labelStyle}>Kids under 12</label>
            <input type="number" min="0" value={kids} onChange={(e) => setKids(e.target.value)} style={inputStyle} />
          </div>

          <div style={fieldStyle} className="lf-span2 lf-name">
            <label style={labelStyle}>Client name</label>
            <input type="text" placeholder="e.g. John Doe" value={clientName} onChange={(e) => setClientName(e.target.value)} style={inputStyle} required />
          </div>
          <div style={fieldStyle} className="lf-span2 lf-name">
            <label style={labelStyle}>Email <span style={{ textTransform: "none", fontWeight: 500, color: "#94a3b8" }}>(optional)</span></label>
            <input type="email" placeholder="Leave blank if not given" value={clientEmail} onChange={(e) => setClientEmail(e.target.value)} style={inputStyle} />
          </div>

          <div style={fieldStyle}>
            <label style={labelStyle}>Start date</label>
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} style={inputStyle} required />
          </div>
          <div style={fieldStyle}>
            <label style={labelStyle}>Budget</label>
            <select value={budgetTier} onChange={(e) => setBudgetTier(e.target.value)} style={{ ...inputStyle, cursor: "pointer" }}>
              <option value="Budget">Budget</option>
              <option value="Mid-Range">Mid-Range</option>
              <option value="Luxury">Luxury</option>
            </select>
          </div>
          <div style={fieldStyle}>
            <label style={labelStyle}>Vehicle</label>
            <select value={vehicleValue} style={{ ...inputStyle, cursor: "pointer" }}
              onChange={(e) => {
                if (e.target.value === "__custom") { setCustomVehicle(true); onTripChange({ ...trip, vehicle: "" }); }
                else { setCustomVehicle(false); onTripChange({ ...trip, vehicle: e.target.value }); }
              }}>
              <option value="">Auto (by group)</option>
              {VEHICLE_OPTIONS.map((v) => <option key={v} value={v}>{v}</option>)}
              <option value="__custom">Other…</option>
            </select>
          </div>
          <div style={fieldStyle}>
            <label style={labelStyle} title={MEAL_PLANS.find((m) => m.code === trip.meal)?.desc}>Meal plan</label>
            <select value={trip.meal || "MAP"} style={{ ...inputStyle, cursor: "pointer" }}
              title={MEAL_PLANS.find((m) => m.code === trip.meal)?.desc}
              onChange={(e) => onTripChange({ ...trip, meal: e.target.value })}>
              {MEAL_PLANS.map((m) => <option key={m.code} value={m.code}>{m.code}</option>)}
            </select>
          </div>
          {vehicleValue === "__custom" && (
            <div style={fieldStyle} className="lf-full">
              <input type="text" placeholder="Vehicle name, e.g. Toyota Innova Hycross" value={trip.vehicle}
                onChange={(e) => onTripChange({ ...trip, vehicle: e.target.value })} style={inputStyle} />
            </div>
          )}
        </div>

        {/* Error banner */}
        {error && (
          <div style={{ marginTop: "10px", padding: "8px 12px", backgroundColor: "#fef2f2", border: "1px solid #fee2e2", borderRadius: "8px", color: "#dc2626", fontSize: "0.85rem", fontWeight: "500" }}>
            ⚠️ {error}
          </div>
        )}

        {/* Submit */}
        <button
          type="submit"
          className="lf-submit"
          disabled={loading}
          style={{
            width: "100%",
            marginTop: "12px",
            padding: "10px 24px",
            backgroundColor: loading ? "#5b7479" : "#10272e",
            color: "#ffffff",
            fontWeight: "700",
            fontSize: "1rem",
            letterSpacing: "0.01em",
            borderRadius: "10px",
            border: "none",
            cursor: loading ? "not-allowed" : "pointer",
            transition: "background-color 0.2s ease",
            minHeight: "42px",
          }}
        >
          {loading ? "Building the itinerary…" : "Generate Custom Itinerary"}
        </button>
      </form>
    </>
  );
}
