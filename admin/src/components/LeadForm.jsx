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
        const target = document.getElementById("day-route-select");
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
  const labelStyle = { fontSize: "0.68rem", fontWeight: "700", color: "#64748b", textTransform: "uppercase", letterSpacing: "0.4px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" };
  const inputStyle = { width: "100%", padding: "6px 10px", borderRadius: "8px", border: "1px solid #cbd5e1", fontSize: "0.9rem", color: "#0f172a", backgroundColor: "#f8fafc", boxSizing: "border-box", minHeight: "38px" };
  const vehicleValue = customVehicle || (trip.vehicle && !VEHICLE_OPTIONS.includes(trip.vehicle)) ? "__custom" : trip.vehicle;

  return (
    <>
      <style>{`
        .lf-form { max-width: 820px; margin: 14px auto; padding: clamp(12px, 3vw, 18px); background: #fff; border-radius: 14px; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.05); border: 1px solid #e2e8f0; font-family: system-ui, sans-serif; box-sizing: border-box; }
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
            <label style={labelStyle}>📍 Destination</label>
            <input type="text" value={destination} onChange={(e) => setDestination(e.target.value)} style={inputStyle} required />
          </div>
          <div style={fieldStyle}>
            <label style={labelStyle}>📅 Days</label>
            <input type="number" value={days} onChange={(e) => setDays(e.target.value)} style={inputStyle} required />
          </div>
          <div style={fieldStyle}>
            <label style={labelStyle}>👥 Adults</label>
            <input type="number" value={adults} onChange={(e) => setAdults(e.target.value)} style={inputStyle} required />
          </div>
          <div style={fieldStyle}>
            <label style={labelStyle}>👶 Kids (&lt;12)</label>
            <input type="number" min="0" value={kids} onChange={(e) => setKids(e.target.value)} style={inputStyle} />
          </div>

          <div style={fieldStyle} className="lf-span2 lf-name">
            <label style={labelStyle}>👤 Client Name</label>
            <input type="text" placeholder="e.g. John Doe" value={clientName} onChange={(e) => setClientName(e.target.value)} style={inputStyle} required />
          </div>
          <div style={fieldStyle} className="lf-span2 lf-name">
            <label style={labelStyle}>✉️ Email <span style={{ textTransform: "none", fontWeight: 500, color: "#94a3b8" }}>(optional)</span></label>
            <input type="email" placeholder="Leave blank if not given" value={clientEmail} onChange={(e) => setClientEmail(e.target.value)} style={inputStyle} />
          </div>

          <div style={fieldStyle}>
            <label style={labelStyle}>🗓️ Start Date</label>
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} style={inputStyle} required />
          </div>
          <div style={fieldStyle}>
            <label style={labelStyle}>💎 Budget</label>
            <select value={budgetTier} onChange={(e) => setBudgetTier(e.target.value)} style={{ ...inputStyle, cursor: "pointer" }}>
              <option value="Budget">Budget</option>
              <option value="Mid-Range">Mid-Range</option>
              <option value="Luxury">Luxury</option>
            </select>
          </div>
          <div style={fieldStyle}>
            <label style={labelStyle}>🚗 Vehicle</label>
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
            <label style={labelStyle}>🍽️ Meal Plan</label>
            <select value={trip.meal || "MAP"} style={{ ...inputStyle, cursor: "pointer" }}
              title={MEAL_PLANS.find((m) => m.code === trip.meal)?.desc}
              onChange={(e) => onTripChange({ ...trip, meal: e.target.value })}>
              {MEAL_PLANS.map((m) => <option key={m.code} value={m.code}>{m.code} – {m.name}</option>)}
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
          disabled={loading}
          style={{
            width: "100%",
            marginTop: "12px",
            padding: "10px 24px",
            backgroundColor: loading ? "#64748b" : "#1e293b",
            color: "#ffffff",
            fontWeight: "700",
            fontSize: "1rem",
            borderRadius: "8px",
            border: "none",
            cursor: loading ? "not-allowed" : "pointer",
            transition: "background-color 0.2s ease",
            minHeight: "42px",
          }}
        >
          {loading ? "Generating Luxury Plan..." : "✨ Generate Custom Itinerary"}
        </button>
      </form>
    </>
  );
}
