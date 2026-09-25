import { useState } from "react";
import { apiFetch } from "../api.js";

export default function LeadForm({ onGenerated }) {
  const [destination, setDestination] = useState("Kashmir");
  const [days, setDays] = useState(5);
  const [clientName, setClientName] = useState("");
  const [startDate, setStartDate] = useState("");
  const [adults, setAdults] = useState(2);
  const [clientEmail, setClientEmail] = useState("");
  const [kids, setKids] = useState(0);
  const [tripPace, setTripPace] = useState("Moderate");
  const [budgetTier, setBudgetTier] = useState("Mid-Range");
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
      client_email: clientEmail || "N/A",
      start_date: startDate || "TBD",
      adults: parseInt(adults) || 2,
      trip_pace: tripPace,
      kids: parseInt(kids) || 0,
      budget_tier: budgetTier,
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

  const fieldStyle = {
    display: "flex",
    flexDirection: "column",
    gap: "6px",
  };

  const labelStyle = {
    fontSize: "0.75rem",
    fontWeight: "700",
    color: "#64748b",
    textTransform: "uppercase",
    letterSpacing: "0.5px",
  };

  const inputStyle = {
    width: "100%",
    padding: "10px 14px",
    borderRadius: "8px",
    border: "1px solid #cbd5e1",
    fontSize: "0.95rem",
    color: "#0f172a",
    backgroundColor: "#f8fafc",
    boxSizing: "border-box",
    minHeight: "44px",
  };

  return (
    <>
      {/* Inject responsive grid styles */}
      <style>{`
        .lf-form {
          max-width: 680px;
          margin: 24px auto;
          padding: clamp(16px, 5vw, 32px);
          background: #ffffff;
          border-radius: 16px;
          box-shadow: 0 10px 25px -5px rgba(0,0,0,0.05);
          border: 1px solid #e2e8f0;
          display: flex;
          flex-direction: column;
          gap: 16px;
          font-family: system-ui, sans-serif;
          box-sizing: border-box;
        }
        .lf-grid-2 {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 16px;
        }
        @media (max-width: 520px) {
          .lf-grid-2 { grid-template-columns: 1fr; gap: 16px; }
          .lf-form { margin: 16px auto; border-radius: 12px; }
        }
      `}</style>

      <form onSubmit={handleSubmit} className="lf-form">

        {/* Row 1: Destination + Days */}
        <div className="lf-grid-2">
          <div style={fieldStyle}>
            <label style={labelStyle}>📍 Destination</label>
            <input type="text" value={destination} onChange={(e) => setDestination(e.target.value)} style={inputStyle} required />
          </div>
          <div style={fieldStyle}>
            <label style={labelStyle}>📅 Number of Days</label>
            <input type="number" value={days} onChange={(e) => setDays(e.target.value)} style={inputStyle} required />
          </div>
        </div>

        {/* Row 2: Client Name + Email */}
        <div className="lf-grid-2">
          <div style={fieldStyle}>
            <label style={labelStyle}>👤 Client Name</label>
            <input type="text" placeholder="e.g. John Doe" value={clientName} onChange={(e) => setClientName(e.target.value)} style={inputStyle} required />
          </div>
          <div style={fieldStyle}>
            <label style={labelStyle}>✉️ Client Email</label>
            <input type="email" placeholder="client@example.com" value={clientEmail} onChange={(e) => setClientEmail(e.target.value)} style={inputStyle} required />
          </div>
        </div>

        {/* Row 3: Start Date + Budget */}
        <div className="lf-grid-2">
          <div style={fieldStyle}>
            <label style={labelStyle}>🗓️ Travel Start Date</label>
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} style={inputStyle} required />
          </div>
          <div style={fieldStyle}>
            <label style={labelStyle}>💎 Budget Tier</label>
            <select value={budgetTier} onChange={(e) => setBudgetTier(e.target.value)} style={{ ...inputStyle, cursor: "pointer" }}>
              <option value="Budget">Budget</option>
              <option value="Mid-Range">Mid-Range</option>
              <option value="Luxury">Luxury</option>
            </select>
          </div>
        </div>

        {/* Row 4: Adults + Kids */}
        <div className="lf-grid-2">
          <div style={fieldStyle}>
            <label style={labelStyle}>👥 Number of Adults</label>
            <input type="number" value={adults} onChange={(e) => setAdults(e.target.value)} style={inputStyle} required />
          </div>
          <div style={fieldStyle}>
            <label style={labelStyle}>👶 Kids (Under 12)</label>
            <input type="number" min="0" value={kids} onChange={(e) => setKids(e.target.value)} style={inputStyle} />
          </div>
        </div>

        {/* Error banner */}
        {error && (
          <div style={{ padding: "10px 14px", backgroundColor: "#fef2f2", border: "1px solid #fee2e2", borderRadius: "8px", color: "#dc2626", fontSize: "0.85rem", fontWeight: "500" }}>
            ⚠️ {error}
          </div>
        )}

        {/* Submit */}
        <button
          type="submit"
          disabled={loading}
          style={{
            width: "100%",
            padding: "13px 24px",
            backgroundColor: loading ? "#64748b" : "#1e293b",
            color: "#ffffff",
            fontWeight: "700",
            fontSize: "1rem",
            borderRadius: "8px",
            border: "none",
            cursor: loading ? "not-allowed" : "pointer",
            transition: "background-color 0.2s ease",
            minHeight: "48px",
          }}
        >
          {loading ? "Generating Luxury Plan..." : "✨ Generate Custom Itinerary"}
        </button>
      </form>
    </>
  );
}
