import React, { useState, useEffect, useRef } from "react";
import { apiFetch } from "../api.js";

const UI_THEME = {
  colors: {
    primary: "#1e293b",
    accent: "#0284c7",
    background: "#f8fafc",
    cardBg: "#ffffff",
    border: "#e2e8f0",
    textDark: "#0f172a",
    textLight: "#64748b",
    success: "#10b981",
  },
  shadows: {
    sm: "0 1px 2px 0 rgb(0 0 0 / 0.05)",
    md: "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)",
  }
};

const TRANSIT_OPTIONS = [
  "Airport Pickup and Local Sightseeing: Overnight Srinagar",
  "Srinagar Local Sightseeing: Overnight Srinagar",
  "Srinagar to Gulmarg: Overnight Srinagar",
  "Srinagar to Gulmarg: Overnight Gulmarg",
  "Srinagar to Pahalgam: Overnight Pahalgam",
  "Pahalgam to Srinagar: Overnight Srinagar",
  "Srinagar to Sonamarg: Overnight Srinagar",
  "Srinagar to Sonamarg: Overnight Sonamarg",
  "Gulmarg to Pahalgam: Overnight Pahalgam",
  "Gulmarg to Srinagar: Overnight Srinagar",
  "Sonamarg to Gulmarg: Overnight Gulmarg",
  "Pahalgam: Local Sightseeing For 2nd Day",
  "Srinagar to Doodhpathri: Overnight Srinagar",
  "Airport Drop-Departure"
];

const ROUTE_SCHEDULE_TEMPLATES = {
  "Srinagar Local Sightseeing: Overnight Srinagar": [
    { time_slot: "***", description: "Srinagar, the summer capital of Jammu & Kashmir, is known for its Mughal-era gardens and the scenic Dal Lake." },
    { time_slot: "***", description: "Visit famous Mughal Gardens: Nishat Bagh and Shalimar Bagh." },
    { time_slot: "***", description: "Enjoy a relaxing 1-hour Shikara ride on Dal Lake." },
    { time_slot: "***", description: "Explore the historic Shankaracharya Temple for a panoramic city view." }
  ],
  "Srinagar to Gulmarg: Overnight Srinagar": [
    { time_slot: "***", description: "Gulmarg, the Meadow of Flowers, is a hill station famous for its alpine meadows and one of the world's highest cable car rides." },
    { time_slot: "***", description: "Drive from Srinagar to Gulmarg (Meadow of Flowers)." },
    { time_slot: "***", description: "Enjoy the famous Gondola Cable Car Ride (Phase 1 & Phase 2)." },
    { time_slot: "***", description: "Drive back to Srinagar for overnight stay." }
  ],
  "Srinagar to Gulmarg: Overnight Gulmarg": [
    { time_slot: "***", description: "Gulmarg, the Meadow of Flowers, is a hill station famous for its alpine meadows and one of the world's highest cable car rides." },
    { time_slot: "***", description: "Drive from Srinagar to Gulmarg (Meadow of Flowers)." },
    { time_slot: "***", description: "Enjoy the famous Gondola Cable Car Ride (Phase 1 & Phase 2)." },
    { time_slot: "***", description: "Check-in at your Gulmarg hotel and enjoy the night in the bed of flowers." }
  ],
  "Srinagar to Pahalgam: Overnight Pahalgam": [
    { time_slot: "***", description: "Pahalgam, the Valley of Shepherds, is reached via Pampore's saffron fields and the ancient Avantipur temple ruins." },
    { time_slot: "***", description: "Proceed towards Pahalgam past the saffron fields of Pampore, the marvelous ruins of Awantipur and the village of Bijbehara which remains famous as the breadbasket of Kashmir." },
    { time_slot: "***", description: "Check-in at Pahalgam hotel and head out for local sightseeing." },
    { time_slot: "***", description: "Visit Aru Valley, Betaab Valley, and Chandanwari via local cabs." }
  ],
  "Pahalgam: Local Sightseeing For 2nd Day": [
    { time_slot: "***", description: "After breakfast, enjoy the scenic beauty of Pahalgam and take a leisurely walk along the Lidder River." },
    { time_slot: "***", description: "Visit the picturesque Pahalgam market and explore local handicrafts, Kashmiri woollens, and traditional souvenirs." },
    { time_slot: "***", description: "Proceed towards the nearby scenic areas and enjoy breathtaking views of the surrounding pine forests, mountains, and valleys." },
    { time_slot: "***", description: "Later, check out from the hotel and proceed towards Srinagar for your onward journey." }
  ],
  "Pahalgam to Srinagar: Overnight Srinagar": [
    { time_slot: "***", description: "Returning to Srinagar retraces the same scenic saffron-field and riverside route from Pahalgam." },
    { time_slot: "***", description: "Proceed towards Srinagar past the saffron fields of Pampore, the marvelous ruins of Awantipur and the village of Bijbehara which remains famous as the breadbasket of Kashmir." },
    { time_slot: "***", description: "Check-in at Srinagar hotel and head out for local sightseeing." },
    { time_slot: "***", description: "Visit famous Mughal Gardens: Nishat Bagh and Shalimar Bagh." }
  ],
  "Srinagar to Sonamarg: Overnight Srinagar": [
    { time_slot: "***", description: "Sonamarg, the Meadow of Gold, sits along the Sindh River and is the gateway to the Thajiwas Glacier." },
    { time_slot: "***", description: "Day excursion to Sonamarg (Meadow of Gold) along the Sindh River." },
    { time_slot: "***", description: "Visit Thajiwas Glacier via pony or local union vehicle." },
    { time_slot: "***", description: "Return drive back to Srinagar for overnight stay." }
  ],
  "Gulmarg to Srinagar: Overnight Srinagar": [
    { time_slot: "***", description: "Another day to explore Srinagar's beautiful lakes, gardens, heritage sites, and famous attractions at your own pace." },
    { time_slot: "***", description: "Enjoy a peaceful Shikara Ride on the famous Dal Lake and admire the surrounding Himalayan scenery." },
    { time_slot: "***", description: "Explore Mughal Gardens including Nishat Bagh and Shalimar Bagh, followed by a leisurely visit to Pari Mahal." },
    { time_slot: "***", description: "Return to your Srinagar hotel for overnight stay." }
  ],
  "Gulmarg to Pahalgam: Overnight Pahalgam": [
    { time_slot: "***", description: "This route connects Kashmir's premier hill station to the Valley of Shepherds via scenic village roads." },
    { time_slot: "***", description: "Drive from Gulmarg down to Pahalgam via scenic village routes." },
    { time_slot: "***", description: "Explore the local Pahalgam market and riverside walk." }
  ],
  "Airport Pickup and Local Sightseeing: Overnight Srinagar": [
    { time_slot: "Arrival", description: "Your Kashmir journey begins in Srinagar, set on the banks of Dal Lake amid the Mughal gardens." },
    { time_slot: "***", description: "Welcome to Kashmir, Paradise on Earth! Our representative will meet you at the Srinagar International Airport and take you to your hotel." },
    { time_slot: "***", description: "On the beginning of Day-1, you will head out for local sightseeing that includes a visit to the famous Mughal gardens of Nishat and Shalimar, Chashma Shahi Garden and Pari Mahal. You can spend the evening exploring Dal Lake and then head back to your hotel or houseboat for the overnight stay." }
  ],
  "Srinagar to Doodhpathri: Overnight Srinagar": [
    { time_slot: "***", description: "Doodhpathri, the Valley of Milk, is a pristine offbeat meadow fed by the Shaliganga river stream." },
    { time_slot: "***", description: "Drive to Doodhpathri (Valley of Milk), a pristine offbeat meadow." },
    { time_slot: "***", description: "Enjoy walks along the roaring Shaliganga river stream." },
    { time_slot: "***", description: "Drive back to Srinagar." }
  ],
  "Sonamarg to Gulmarg: Overnight Gulmarg": [
    { time_slot: "***", description: "Gulmarg, the Meadow of Flowers, is renowned for its breathtaking Himalayan landscapes, lush meadows, and world-famous attractions." },
    { time_slot: "***", description: "Depart from Sonamarg and enjoy a scenic drive towards Gulmarg through the beautiful Kashmir Valley." },
    { time_slot: "***", description: "Explore Gulmarg's picturesque meadows and enjoy leisure time surrounded by stunning mountain views." },
    { time_slot: "***", description: "Check in to your Gulmarg hotel and relax for an overnight stay." }
  ],
  "Airport Drop-Departure": [
    { time_slot: "Departure", description: "Your Kashmir tour concludes with departure from Srinagar International Airport." },
    { time_slot: "***", description: "Breakfast at hotel and complete check-out formalities." },
    { time_slot: "***", description: "Transfer to Srinagar International Airport for departure flight." }
  ]
};

const HOTEL_KB = {
  srinagar: [
    {id: "ngm",  name: "Hotel New Green Meadows",       place: "Srinagar", images: []},
    {id: "nclr", name: "New Classic Luxury Resorts",    place: "Srinagar", images: []},
    {id: "hsp",  name: "Hotel Sideeq Palace",           place: "Srinagar", images: []},
    {id: "htv",  name: "Hotel The Victory",             place: "Srinagar", images: []},
    {id: "htk",  name: "Hotel The Karims",              place: "Srinagar", images: []},
    {id: "hgr",  name: "Hotel Gurcoo Residency",        place: "Srinagar", images: []},
    {id: "hdw",  name: "Hotel Deewan",                  place: "Srinagar", images: []},
    {id: "hsd",  name: "Hotel Sadaf",                   place: "Srinagar", images: []},
    {id: "sghb", name: "Srinagar Group of House-Boats", place: "Srinagar", images: []},
    {id: "hicl", name: "Hotel Iceland",                 place: "Srinagar", images: []},
  ],
  pahalgam: [
    {id: "hri",  name: "Hotel Riverside Inn",           place: "Pahalgam", images: []},
    {id: "hsr",  name: "Hotel Supreme Resorts",         place: "Pahalgam", images: []},
    {id: "hhr",  name: "Hotel Highland Resorts",        place: "Pahalgam", images: []},
    {id: "hfh",  name: "Hotel Falcon Heights",          place: "Pahalgam", images: []},
    {id: "hlr",  name: "Hotel Lavish Residency",        place: "Pahalgam", images: []},
    {id: "hil",  name: "Hotel Ice Land",                place: "Pahalgam", images: []},
    {id: "her",  name: "Hotel Eden Resorts and Spa",    place: "Pahalgam", images: []},
  ],
  gulmarg: [
    {id: "hatr", name: "Hotel Apple Tree Resorts",      place: "Gulmarg", images: []},
    {id: "ggr",  name: "Gulmarg Gateway Resorts",       place: "Gulmarg", images: []},
    {id: "hghv", name: "Hotel Grand Hill View",         place: "Gulmarg", images: []},
    {id: "hmsp", name: "Hotel Marina By Stay Pattern",  place: "Gulmarg", images: []},
  ],
  sonamarg: [
    {id: "nrs",  name: "Namrose Resorts",               place: "Sonamarg", images: []},
    {id: "bdr",  name: "Badar Resorts",                 place: "Sonamarg", images: []},
    {id: "cibsp",name: "Country Inn-By Stay Pattern",   place: "Sonamarg", images: []},
    {id: "hmi",  name: "Hotel Mughal India",            place: "Sonamarg", images: []},
  ],
};

function getHotelGroup(overnight_stay = "") {
  const s = overnight_stay.toLowerCase();
  if (s.includes("pahalgam")) return "pahalgam";
  if (s.includes("gulmarg"))  return "gulmarg";
  if (s.includes("sonamarg")) return "sonamarg";
  return "srinagar";
}

const ALL_HOTELS_FLAT = Object.values(HOTEL_KB).flat().reduce((acc, h) => {
  acc[h.id] = h;
  return acc;
}, {});

// ── Hotel Cost Dashboard ───────────────────────────────────────────────────
function calcRowTotal(row) {
  const n  = Number(row.stays)    || 0;
  const r  = Number(row.rooms)    || 0;
  const eb = Number(row.eb)       || 0;
  const rr = Number(row.roomRate) || 0;
  const er = Number(row.ebRate)   || 0;
  return (n * r * rr) + (n * eb * er);
}

function fmtINR(n) {
  return "₹" + Math.round(n).toLocaleString("en-IN");
}

function HotelCostDashboard({ hotelSelections = {}, timeline = [], onTotalChange }) {
  const buildRows = (prev = {}) => {
    const next = {};
    Object.values(hotelSelections).forEach((hotelId) => {
      if (!hotelId || !ALL_HOTELS_FLAT[hotelId]) return;
      next[hotelId] = prev[hotelId] || {
        hotelId, stays: 1, rooms: 1, eb: 0, cnb: 0, roomRate: 0, ebRate: 0,
      };
    });
    return next;
  };

  const [rows, setRows]       = React.useState(() => buildRows());
  const [cabCost, setCabCost] = React.useState(0);

  React.useEffect(() => { setRows((prev) => buildRows(prev)); }, [hotelSelections]);

  React.useEffect(() => {
    if (onTotalChange) {
      const hotelTotal = Object.values(rows).reduce((sum, r) => sum + calcRowTotal(r), 0);
      onTotalChange(hotelTotal + (Number(cabCost) || 0));
    }
  }, [rows, cabCost]);

  const handleChange = (hotelId, field, value) => {
    setRows((prev) => ({ ...prev, [hotelId]: { ...prev[hotelId], [field]: value } }));
  };

  const hotelDaysMap = {};
  Object.entries(hotelSelections).forEach(([dayIdx, hotelId]) => {
    if (!hotelId) return;
    if (!hotelDaysMap[hotelId]) hotelDaysMap[hotelId] = [];
    hotelDaysMap[hotelId].push(Number(dayIdx) + 1);
  });

  const rowList    = Object.values(rows);
  const hotelTotal = rowList.reduce((sum, r) => sum + calcRowTotal(r), 0);
  const grandTotal = hotelTotal + (Number(cabCost) || 0);

  const thStyle = {
    padding: "8px 10px", backgroundColor: "#f1f5f9", color: "#475569",
    fontWeight: "700", fontSize: "0.73rem", textTransform: "uppercase",
    letterSpacing: "0.4px", borderBottom: "1px solid #e2e8f0",
    whiteSpace: "nowrap", textAlign: "left",
  };
  const tdStyle = {
    padding: "8px 10px", borderBottom: "1px solid #f1f5f9",
    color: "#0f172a", verticalAlign: "middle",
  };
  const numInput = {
    width: "64px", padding: "5px 6px", border: "1px solid #cbd5e1",
    borderRadius: "6px", fontSize: "0.82rem", color: "#0f172a",
    backgroundColor: "#f8fafc", textAlign: "center", minHeight: "36px",
    boxSizing: "border-box",
  };

  return (
    <>
      <style>{`
        .hcd-totals {
          display: flex;
          justify-content: flex-end;
          align-items: center;
          gap: 20px;
          margin-top: 14px;
          padding-top: 12px;
          border-top: 2px solid #e2e8f0;
          flex-wrap: wrap;
        }
        .hcd-divider { width: 1px; height: 24px; background: #e2e8f0; }
        @media (max-width: 600px) {
          .hcd-totals { flex-direction: column; align-items: flex-start; gap: 12px; }
          .hcd-divider { display: none; }
          .hcd-cab-input { width: 100% !important; box-sizing: border-box; }
        }
      `}</style>
      <div style={{ marginTop: "32px", backgroundColor: "#ffffff", border: "1px solid #e2e8f0", borderRadius: "12px", padding: "clamp(14px, 4vw, 20px) clamp(14px, 4vw, 24px)", fontFamily: "system-ui, sans-serif" }}>
        <div style={{ marginBottom: "14px", paddingBottom: "12px", borderBottom: "1px solid #e2e8f0" }}>
          <p style={{ margin: 0, fontSize: "1rem", fontWeight: "700", color: "#0f172a" }}>🏨 Hotel Cost Breakdown</p>
          <p style={{ margin: "3px 0 0", fontSize: "0.78rem", color: "#64748b" }}>
            Hotels auto-fetched from assignments above · Formula: (Nights × Rooms × Room Rate) + (Nights × EB × EB Rate) + Trip Cab Cost
          </p>
        </div>

        {rowList.length === 0 ? (
          <p style={{ textAlign: "center", color: "#94a3b8", fontSize: "0.85rem", padding: "24px 0" }}>
            No hotels assigned yet. Use the hotel picker above for each day — they will appear here automatically.
          </p>
        ) : (
          <>
            <div style={{ overflowX: "auto", WebkitOverflowScrolling: "touch" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem", minWidth: "560px" }}>
                <thead>
                  <tr>
                    <th style={thStyle}>Hotel</th>
                    <th style={thStyle}>Assigned Days</th>
                    <th style={thStyle}>Nights</th>
                    <th style={thStyle}>Rooms</th>
                    <th style={thStyle}>EB</th>
                    <th style={thStyle}>CNB</th>
                    <th style={thStyle}>Room Rate/Night (₹)</th>
                    <th style={thStyle}>EB Rate/Night (₹)</th>
                    <th style={{ ...thStyle, textAlign: "right" }}>Total (₹)</th>
                  </tr>
                </thead>
                <tbody>
                  {rowList.map((row) => {
                    const hotel = ALL_HOTELS_FLAT[row.hotelId];
                    const days  = (hotelDaysMap[row.hotelId] || []).sort((a, b) => a - b);
                    return (
                      <tr key={row.hotelId}>
                        <td style={tdStyle}>
                          <div style={{ fontWeight: "600", color: "#1e293b" }}>{hotel.name}</div>
                          <div style={{ fontSize: "0.72rem", color: "#94a3b8", marginTop: "1px" }}>📍 {hotel.place}</div>
                        </td>
                        <td style={tdStyle}>
                          <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
                            {days.map((d) => (
                              <span key={d} style={{ padding: "2px 7px", borderRadius: "999px", backgroundColor: "#eff6ff", color: "#1d4ed8", fontSize: "0.72rem", fontWeight: "700" }}>Day {d}</span>
                            ))}
                          </div>
                        </td>
                        {["stays","rooms","eb","cnb","roomRate","ebRate"].map((field) => (
                          <td key={field} style={tdStyle}>
                            <input type="number" min="0" style={numInput} value={row[field]} onChange={(e) => handleChange(row.hotelId, field, e.target.value)} />
                          </td>
                        ))}
                        <td style={{ ...tdStyle, textAlign: "right", fontWeight: "700", color: "#0284c7" }}>
                          {fmtINR(calcRowTotal(row))}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="hcd-totals">
              <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                <span style={{ fontSize: "0.82rem", color: "#475569", fontWeight: "600" }}>🏨 Hotel Subtotal:</span>
                <span style={{ fontSize: "1rem", fontWeight: "700", color: "#0284c7" }}>{fmtINR(hotelTotal)}</span>
              </div>
              <div className="hcd-divider" />
              <div style={{ display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" }}>
                <label style={{ fontSize: "0.82rem", color: "#854d0e", fontWeight: "600", whiteSpace: "nowrap" }}>🚗 Cab Cost – Full Trip (₹):</label>
                <input type="number" min="0" value={cabCost} onChange={(e) => setCabCost(e.target.value)} className="hcd-cab-input" style={{ width: "110px", padding: "6px 8px", border: "1px solid #fde047", borderRadius: "6px", fontSize: "0.88rem", color: "#854d0e", backgroundColor: "#fef9c3", textAlign: "center", fontWeight: "600", minHeight: "36px" }} />
              </div>
              <div className="hcd-divider" />
              <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                <span style={{ fontSize: "0.9rem", color: "#0f172a", fontWeight: "700" }}>Grand Total:</span>
                <span style={{ fontSize: "1.25rem", fontWeight: "800", color: "#10b981" }}>{fmtINR(grandTotal)}</span>
              </div>
            </div>
          </>
        )}
      </div>
    </>
  );
}

// ── Hotel Image Manager ────────────────────────────────────────────────────
const ALL_HOTELS_LIST = Object.values(HOTEL_KB).flat();

function HotelImageManager() {
  const [hotelImages, setHotelImages]   = useState({});
  const [selectedId,  setSelectedId]    = useState(ALL_HOTELS_LIST[0]?.id || "");
  const [urlDraft,    setUrlDraft]       = useState("");
  const [uploadFile,  setUploadFile]    = useState(null);
  const [saving,      setSaving]        = useState(false);
  const [loadMsg,     setLoadMsg]       = useState("Loading…");
  const fileInputRef = useRef(null);

  useEffect(() => {
    apiFetch("/api/admin/hotel-images")
      .then((r) => r.json())
      .then((data) => { setHotelImages(data || {}); setLoadMsg(null); })
      .catch(() => setLoadMsg(null));
  }, []);

  const currentImages = hotelImages[selectedId] || [];
  const selectedHotel = ALL_HOTELS_FLAT[selectedId];

  const addUrl = () => {
    const url = urlDraft.trim();
    if (!url) return;
    const updated = { ...hotelImages, [selectedId]: [...currentImages, url] };
    setHotelImages(updated);
    setUrlDraft("");
  };

  const handleFileChange = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const dataUrl = ev.target.result;
      const updated = { ...hotelImages, [selectedId]: [...currentImages, dataUrl] };
      setHotelImages(updated);
    };
    reader.readAsDataURL(file);
    e.target.value = "";
  };

  const removeImage = (idx) => {
    const next = currentImages.filter((_, i) => i !== idx);
    setHotelImages({ ...hotelImages, [selectedId]: next });
  };

  const saveImages = async () => {
    setSaving(true);
    try {
      const res = await apiFetch("/api/admin/hotel-images", {
        method: "POST",
        body: JSON.stringify({ [selectedId]: currentImages }),
      });
      if (res.ok) {
        alert("✅ Images saved for " + selectedHotel?.name);
      } else {
        alert("Save failed — check server.");
      }
    } catch {
      alert("Network error while saving.");
    } finally {
      setSaving(false);
    }
  };

  const groupLabels = { srinagar: "Srinagar", pahalgam: "Pahalgam", gulmarg: "Gulmarg", sonamarg: "Sonamarg" };

  return (
    <div style={{ marginTop: "40px", backgroundColor: "#fff", border: "1px solid #e2e8f0", borderRadius: "14px", overflow: "hidden", fontFamily: "system-ui, sans-serif" }}>
      {/* Header */}
      <div style={{ padding: "18px clamp(14px, 4vw, 24px)", borderBottom: "1px solid #e2e8f0", background: "linear-gradient(135deg, #1e3a4f 0%, #0f2a3a 100%)", color: "#fff" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <span style={{ fontSize: "1.35rem" }}>🖼️</span>
          <div>
            <p style={{ margin: 0, fontSize: "1rem", fontWeight: "700" }}>Hotel Photo Manager</p>
            <p style={{ margin: "2px 0 0", fontSize: "0.78rem", opacity: 0.75 }}>
              Add reference photos for each hotel — these appear in the generated PDF quotation.
            </p>
          </div>
        </div>
      </div>

      <div className="hpm-grid">
        {/* Left: hotel list */}
        <div className="hpm-sidebar">
          {Object.entries(groupLabels).map(([groupKey, label]) => (
            <div key={groupKey}>
              <div style={{ padding: "8px 14px", fontSize: "0.7rem", fontWeight: "800", color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.6px", backgroundColor: "#f8fafc", borderBottom: "1px solid #f1f5f9" }}>
                📍 {label}
              </div>
              {(HOTEL_KB[groupKey] || []).map((hotel) => {
                const imgCount = (hotelImages[hotel.id] || []).length;
                const isActive = selectedId === hotel.id;
                return (
                  <div
                    key={hotel.id}
                    onClick={() => setSelectedId(hotel.id)}
                    style={{
                      padding: "10px 14px",
                      cursor: "pointer",
                      borderBottom: "1px solid #f1f5f9",
                      backgroundColor: isActive ? "#eff6ff" : "transparent",
                      borderLeft: isActive ? "3px solid #0284c7" : "3px solid transparent",
                      transition: "background 0.12s",
                    }}
                  >
                    <div style={{ fontSize: "0.83rem", fontWeight: isActive ? "700" : "500", color: isActive ? "#1d4ed8" : "#1e293b" }}>
                      {hotel.name}
                    </div>
                    <div style={{ marginTop: "3px", fontSize: "0.7rem", color: imgCount > 0 ? "#10b981" : "#94a3b8", fontWeight: "600" }}>
                      {imgCount > 0 ? `${imgCount} photo${imgCount > 1 ? "s" : ""}` : "No photos yet"}
                    </div>
                  </div>
                );
              })}
            </div>
          ))}
        </div>

        {/* Right: image editor */}
        <div style={{ padding: "clamp(14px, 4vw, 20px) clamp(14px, 4vw, 24px)" }}>
          {loadMsg ? (
            <p style={{ color: "#94a3b8", fontSize: "0.88rem" }}>{loadMsg}</p>
          ) : (
            <>
              <div style={{ marginBottom: "18px" }}>
                <h4 style={{ margin: "0 0 4px", fontSize: "1rem", color: "#0f172a", fontWeight: "700" }}>
                  {selectedHotel?.name}
                </h4>
                <p style={{ margin: 0, fontSize: "0.78rem", color: "#64748b" }}>
                  📍 {selectedHotel?.place} · {currentImages.length} photo{currentImages.length !== 1 ? "s" : ""} saved
                </p>
              </div>

              {/* Add via URL */}
              <div style={{ display: "flex", gap: "8px", marginBottom: "14px", flexWrap: "wrap" }}>
                <input
                  type="url"
                  placeholder="Paste image URL (https://…)"
                  value={urlDraft}
                  onChange={(e) => setUrlDraft(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && addUrl()}
                  style={{ flex: "1 1 180px", padding: "8px 12px", border: "1px solid #cbd5e1", borderRadius: "8px", fontSize: "0.85rem", color: "#0f172a", backgroundColor: "#f8fafc", minHeight: "40px", boxSizing: "border-box" }}
                />
                <button
                  onClick={addUrl}
                  style={{ padding: "8px 16px", backgroundColor: "#0284c7", color: "#fff", border: "none", borderRadius: "8px", fontWeight: "700", fontSize: "0.82rem", cursor: "pointer", whiteSpace: "nowrap", minHeight: "40px" }}
                >
                  + Add URL
                </button>
              </div>

              {/* Add via file upload */}
              <div style={{ marginBottom: "20px", display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" }}>
                <button
                  onClick={() => fileInputRef.current?.click()}
                  style={{ padding: "8px 16px", backgroundColor: "#f1f5f9", color: "#334155", border: "1px solid #cbd5e1", borderRadius: "8px", fontWeight: "600", fontSize: "0.82rem", cursor: "pointer", display: "inline-flex", alignItems: "center", gap: "6px", minHeight: "40px" }}
                >
                  📁 Upload from Device
                </button>
                <input ref={fileInputRef} type="file" accept="image/*" style={{ display: "none" }} onChange={handleFileChange} />
                <span style={{ fontSize: "0.72rem", color: "#94a3b8" }}>
                  JPG, PNG, WEBP — stored as base64
                </span>
              </div>

              {/* Image grid */}
              {currentImages.length === 0 ? (
                <div style={{ textAlign: "center", padding: "40px 20px", backgroundColor: "#f8fafc", borderRadius: "10px", border: "2px dashed #e2e8f0" }}>
                  <div style={{ fontSize: "2rem", marginBottom: "8px" }}>🏔️</div>
                  <p style={{ margin: 0, color: "#94a3b8", fontSize: "0.85rem" }}>No photos yet — add a URL or upload an image above.</p>
                </div>
              ) : (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))", gap: "12px", marginBottom: "20px" }}>
                  {currentImages.map((src, idx) => (
                    <div key={idx} style={{ position: "relative", borderRadius: "8px", overflow: "hidden", border: "1px solid #e2e8f0", boxShadow: "0 1px 3px rgba(0,0,0,0.07)" }}>
                      <img
                        src={src}
                        alt={`Hotel photo ${idx + 1}`}
                        style={{ width: "100%", height: "100px", objectFit: "cover", display: "block" }}
                        onError={(e) => { e.target.style.display = "none"; e.target.nextSibling.style.display = "flex"; }}
                      />
                      <div style={{ display: "none", height: "100px", alignItems: "center", justifyContent: "center", backgroundColor: "#f1f5f9", color: "#94a3b8", fontSize: "0.75rem", flexDirection: "column", gap: "4px" }}>
                        <span>⚠️</span><span>Invalid URL</span>
                      </div>
                      <button
                        onClick={() => removeImage(idx)}
                        title="Remove photo"
                        style={{ position: "absolute", top: "5px", right: "5px", width: "22px", height: "22px", borderRadius: "50%", border: "none", backgroundColor: "rgba(220,38,38,0.88)", color: "#fff", cursor: "pointer", fontSize: "0.7rem", fontWeight: "900", display: "flex", alignItems: "center", justifyContent: "center", lineHeight: 1 }}
                      >
                        ✕
                      </button>
                      <div style={{ padding: "4px 6px", fontSize: "0.65rem", color: "#94a3b8", backgroundColor: "#fff", textAlign: "center" }}>
                        Photo {idx + 1}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Save button */}
              <div style={{ display: "flex", justifyContent: "flex-end" }}>
                <button
                  onClick={saveImages}
                  disabled={saving}
                  style={{ padding: "10px 22px", backgroundColor: saving ? "#94a3b8" : "#10b981", color: "#fff", border: "none", borderRadius: "8px", fontWeight: "700", fontSize: "0.88rem", cursor: saving ? "not-allowed" : "pointer", minHeight: "44px" }}
                >
                  {saving ? "Saving…" : "💾 Save Photos for " + (selectedHotel?.name || "Hotel")}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Main QuotePreview export ───────────────────────────────────────────────
export default function QuotePreview({ quote }) {
  const [timeline,        setTimeline]        = useState(quote?.itinerary_timeline || []);
  const [activeDay,       setActiveDay]       = useState(0);
  const [editableCost,    setEditableCost]    = useState(quote?.financial_summary?.total_payable_inr || 38500);
  const [hotelSelections, setHotelSelections] = useState({});

  useEffect(() => {
    if (quote?.financial_summary?.total_payable_inr) setEditableCost(quote.financial_summary.total_payable_inr);
  }, [quote]);

  useEffect(() => {
    if (quote?.itinerary_timeline) { setTimeline(quote.itinerary_timeline); setActiveDay(0); }
  }, [quote]);

  const handleDescriptionChange = (dayIndex, activityIndex, newValue) => {
    const updatedTimeline = [...timeline];
    updatedTimeline[dayIndex].schedule[activityIndex].description = newValue;
    setTimeline(updatedTimeline);
  };

  return (
    <>
      <style>{`
        .qp-wrap {
          padding: clamp(14px, 4vw, 24px);
          background: ${UI_THEME.colors.background};
          min-height: 100vh;
          font-family: system-ui, sans-serif;
          box-sizing: border-box;
        }
        .qp-meta-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
          gap: 16px;
          background: ${UI_THEME.colors.cardBg};
          padding: 16px 20px;
          border-radius: 12px;
          box-shadow: ${UI_THEME.shadows.sm};
          border: 1px solid ${UI_THEME.colors.border};
          margin-bottom: 24px;
        }
        .qp-active-day {
          padding: clamp(14px, 4vw, 20px);
          background: #f8fafc;
          border-radius: 6px;
          border: 1px solid #e2e8f0;
        }
        .qp-route-select {
          width: 100%;
          max-width: 480px;
          padding: 8px 12px;
          border-radius: 6px;
          border: 1px solid #cbd5e1;
          background: #fff;
          font-size: 0.9rem;
          color: #1e293b;
          cursor: pointer;
          box-sizing: border-box;
        }
        .qp-hotel-select {
          width: 100%;
          max-width: 480px;
          padding: 8px 12px;
          border-radius: 6px;
          border: 1px solid #cbd5e1;
          background: #fff;
          font-size: 0.85rem;
          font-weight: 500;
          color: #1e293b;
          cursor: pointer;
          box-sizing: border-box;
        }
        .qp-city-btns {
          display: flex;
          gap: 8px;
          flex-wrap: wrap;
          margin-top: 8px;
        }
        .qp-activity-row {
          display: flex;
          align-items: center;
          gap: 10px;
          margin-bottom: 8px;
          flex-wrap: wrap;
        }
        .qp-time-input {
          padding: 4px 8px;
          width: 90px;
          border: 1px solid #cbd5e1;
          border-radius: 4px;
          min-height: 36px;
          box-sizing: border-box;
          flex-shrink: 0;
        }
        .qp-title-input {
          padding: 4px 8px;
          flex: 1;
          min-width: 120px;
          border: 1px solid #cbd5e1;
          border-radius: 4px;
          min-height: 36px;
          box-sizing: border-box;
        }
        .qp-footer-bar {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          gap: 16px;
          margin-top: 20px;
          border-top: 2px solid #e2e8f0;
          padding-top: 16px;
          flex-wrap: wrap;
        }
        .qp-footer-cost {
          display: flex;
          align-items: center;
          gap: 10px;
          flex-wrap: wrap;
        }
        .qp-cost-input {
          padding: 6px 12px;
          font-size: 1.1rem;
          width: 130px;
          border: 1px solid #cbd5e1;
          border-radius: 4px;
          min-height: 40px;
          box-sizing: border-box;
        }
        .qp-hotel-assignments {
          font-size: 0.78rem;
          color: #475569;
          line-height: 1.7;
          max-width: 260px;
          flex: 1 1 200px;
        }
        .qp-save-btn {
          padding: 12px 20px;
          background: #10b981;
          color: #fff;
          border: none;
          border-radius: 5px;
          cursor: pointer;
          font-weight: bold;
          min-height: 48px;
          white-space: nowrap;
          align-self: flex-end;
        }
        @media (max-width: 600px) {
          .qp-footer-bar {
            flex-direction: column;
            align-items: stretch;
          }
          .qp-footer-cost { flex-direction: column; align-items: flex-start; }
          .qp-cost-input { width: 100%; }
          .qp-hotel-assignments { max-width: 100%; }
          .qp-save-btn { width: 100%; text-align: center; }
          .qp-route-select, .qp-hotel-select { max-width: 100%; }
          .qp-time-input { width: 80px; }
        }
        @media (max-width: 420px) {
          .qp-activity-row { flex-direction: column; align-items: stretch; }
          .qp-time-input, .qp-title-input { width: 100%; }
        }
      `}</style>

      <div className="qp-wrap">
        {/* 1. Dashboard Header */}
        <div style={{ marginBottom: "24px", paddingBottom: "16px", borderBottom: "1px solid " + UI_THEME.colors.border }}>
          <h2 style={{ fontSize: "clamp(1.3rem, 4vw, 1.75rem)", fontWeight: "800", color: UI_THEME.colors.primary, margin: "0 0 6px 0" }}>
            ✨ Live Itinerary Preview & Customizer
          </h2>
          <p style={{ margin: 0, fontSize: "0.9rem", color: UI_THEME.colors.textLight }}>
            Review or edit the day-by-day plan details below before saving.
          </p>
        </div>

        {/* 2. Client Metadata */}
        <div className="qp-meta-grid">
          <div style={{ fontSize: "0.9rem", color: UI_THEME.colors.textDark }}><strong style={{ color: UI_THEME.colors.textLight }}>Client:</strong> {quote?.meta_summary?.client_name || "N/A"}</div>
          <div style={{ fontSize: "0.9rem", color: UI_THEME.colors.textDark }}><strong style={{ color: UI_THEME.colors.textLight }}>Budget Tier:</strong> {quote?.meta_summary?.budget_tier || "N/A"}</div>
          <div style={{ fontSize: "0.9rem", color: UI_THEME.colors.textDark }}><strong style={{ color: UI_THEME.colors.textLight }}>Vehicle:</strong> {quote?.meta_summary?.vehicle_type || "N/A"}</div>
        </div>

        {/* 3. Day tabs */}
        <div style={{ display: "flex", gap: "8px", overflowX: "auto", WebkitOverflowScrolling: "touch", paddingBottom: "10px", marginBottom: "15px", scrollbarWidth: "none" }}>
          {timeline.map((dayData, idx) => (
            <button key={idx} onClick={() => setActiveDay(idx)} style={{ padding: "8px 16px", border: "none", borderRadius: "20px", cursor: "pointer", fontWeight: "bold", backgroundColor: activeDay === idx ? "#1e293b" : "#f1f5f9", color: activeDay === idx ? "#fff" : "#334155", whiteSpace: "nowrap", flexShrink: 0, minHeight: "40px" }}>
              Day {dayData.day}
            </button>
          ))}
        </div>

        {/* 4. Active day editor */}
        {timeline[activeDay] && (
          <div className="qp-active-day">
            <h3 style={{ margin: "0 0 15px 0", color: "#0f172a", fontSize: "clamp(1rem, 3vw, 1.2rem)" }}>
              📍 Day {timeline[activeDay].day}: {timeline[activeDay].title || timeline[activeDay].date}
            </h3>

            {/* Route selector */}
            <div id="day-route-select" style={{ marginBottom: "15px" }}>
              <label style={{ fontWeight: "bold", color: "#334155", display: "block", marginBottom: "5px", fontSize: "0.9rem" }}>🚗 Select Day Route / Travel Option:</label>
              <select
                className="qp-route-select"
                value={timeline[activeDay]?.transit_route || ""}
                onChange={(e) => {
                  const updatedRoute = e.target.value;
                  const automaticSchedule = ROUTE_SCHEDULE_TEMPLATES[updatedRoute] || [];
                  const overnightMatch = updatedRoute.match(/Overnight\s+(\w+)/i);
                  const derivedCity = overnightMatch ? overnightMatch[1] : null;
                  if (derivedCity) {
                    const groupKey = derivedCity.toLowerCase();
                    const hotelGroup = HOTEL_KB[groupKey] || HOTEL_KB["srinagar"];
                    setHotelSelections(prev => ({ ...prev, [activeDay]: hotelGroup[0].id }));
                  } else {
                    setHotelSelections(prev => ({ ...prev, [activeDay]: null }));
                  }
                  setTimeline(prev => {
                    const next = [...prev];
                    if (next[activeDay]) {
                      next[activeDay] = { ...next[activeDay], transit_route: updatedRoute, title: updatedRoute, schedule: automaticSchedule, ...(derivedCity && { overnight_stay: derivedCity }) };
                    }
                    return next;
                  });
                }}
              >
                <option value="">-- Choose Route for Day {activeDay + 1} --</option>
                {TRANSIT_OPTIONS.map((route, i) => <option key={i} value={route}>{route}</option>)}
              </select>
            </div>

            {/* Hotel city picker */}
            <div style={{ marginBottom: "15px" }}>
              <label style={{ fontWeight: "bold", color: "#334155", display: "block", marginBottom: "6px", fontSize: "0.9rem" }}>🏠 Assign Hotel/Stay:</label>
              <div className="qp-city-btns">
                {["Srinagar", "Pahalgam", "Gulmarg", "Sonamarg"].map((city) => {
                  const isActive = (timeline[activeDay]?.overnight_stay || "Srinagar") === city;
                  return (
                    <button
                      key={city}
                      type="button"
                      onClick={() => {
                        const updated = [...timeline];
                        if (updated[activeDay]) { updated[activeDay].overnight_stay = city; setTimeline(updated); setHotelSelections(prev => ({ ...prev, [activeDay]: null })); }
                      }}
                      style={{ padding: "8px 16px", borderRadius: "20px", border: isActive ? "2px solid #2563eb" : "1px solid #cbd5e1", backgroundColor: isActive ? "#2563eb" : "#fff", fontSize: "0.85rem", fontWeight: "bold", color: isActive ? "#fff" : "#1e293b", cursor: "pointer", transition: "all 0.15s", minHeight: "40px" }}
                    >
                      {city}
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Hotel dropdown */}
            <div style={{ marginBottom: "15px" }}>
              <select
                className="qp-hotel-select"
                value={hotelSelections[activeDay] || ""}
                onChange={(e) => setHotelSelections(prev => ({ ...prev, [activeDay]: e.target.value }))}
              >
                <option value="">-- Choose Hotel --</option>
                {(HOTEL_KB[getHotelGroup(timeline[activeDay].overnight_stay)] || HOTEL_KB["srinagar"]).map((hotel) => (
                  <option key={hotel.id} value={hotel.id}>{hotel.name} — {hotel.place} · B&D Included</option>
                ))}
              </select>
            </div>

            {/* Activity list */}
            <div style={{ display: "flex", flexDirection: "column", gap: "15px", marginTop: "15px" }}>
              {timeline[activeDay].schedule.map((slot, actIdx) => (
                <div key={actIdx} style={{ backgroundColor: "#fff", padding: "clamp(10px, 3vw, 15px)", borderRadius: "6px", border: "1px solid #cbd5e1" }}>
                  <div className="qp-activity-row">
                    <input
                      type="text"
                      value={slot.time_slot}
                      onChange={(e) => { const t = [...timeline]; t[activeDay].schedule[actIdx].time_slot = e.target.value; setTimeline(t); }}
                      className="qp-time-input"
                    />
                    <input
                      type="text"
                      value={slot.activity_title}
                      onChange={(e) => { const t = [...timeline]; t[activeDay].schedule[actIdx].activity_title = e.target.value; setTimeline(t); }}
                      className="qp-title-input"
                    />
                  </div>
                  <textarea
                    value={slot.description}
                    onChange={(e) => handleDescriptionChange(activeDay, actIdx, e.target.value)}
                    style={{ width: "100%", padding: "8px", border: "1px solid #cbd5e1", borderRadius: "4px", boxSizing: "border-box", resize: "vertical" }}
                    rows={3}
                  />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 5. Hotel Cost Dashboard */}
        <HotelCostDashboard hotelSelections={hotelSelections} timeline={timeline} onTotalChange={(total) => setEditableCost(total)} />

        {/* 6. Hotel Photo Manager */}
        <HotelImageManager />

        {/* 7. Footer / PDF export */}
        <div className="qp-footer-bar">
          <div className="qp-footer-cost">
            <h3 style={{ margin: 0, fontSize: "1rem" }}>Total Est. Cost (₹):</h3>
            <input
              type="number"
              value={editableCost}
              onChange={(e) => setEditableCost(e.target.value)}
              className="qp-cost-input"
            />
          </div>

          <div className="qp-hotel-assignments">
            <strong style={{ color: "#0f172a", display: "block", marginBottom: "4px" }}>🏨 Hotel Assignments:</strong>
            {timeline.map((day, idx) => {
              const group  = getHotelGroup(day.overnight_stay);
              const selId  = hotelSelections[idx];
              const hotel  = HOTEL_KB[group]?.find(h => h.id === selId);
              return (
                <div key={idx} style={{ display: "flex", justifyContent: "space-between", gap: "8px" }}>
                  <span style={{ color: "#94a3b8" }}>Day {day.day}:</span>
                  <span style={{ fontWeight: "600", color: hotel ? "#4338ca" : "#94a3b8" }}>{hotel ? hotel.name : "Not assigned"}</span>
                </div>
              );
            })}
          </div>

          <button
            className="qp-save-btn"
            onClick={async () => {
              try {
                const currentClientName = quote?.meta_summary?.client_name || "Client";
                const printRes = await apiFetch("/api/itinerary/generate", {
                  method: "POST",
                  body: JSON.stringify({
                    client_name: currentClientName,
                    client_email: quote?.meta_summary?.client_email || "N/A",
                    days: quote?.meta_summary?.total_days || 5,
                    start_date: quote?.meta_summary?.start_date || quote?.start_date || "Flexible",
                    adults: quote?.meta_summary?.adults || quote?.adults || 2,
                    kids: quote?.meta_summary?.kids ?? quote?.kids ?? 0,
                    budget_tier: quote?.meta_summary?.budget_tier || "Mid-Range",
                    trip_pace: quote?.meta_summary?.trip_pace || "Moderate",
                    custom_cost: editableCost,
                    timeline,
                    hotelSelections,
                  }),
                });
                if (printRes.ok) {
                  alert("🎉 Custom modifications applied! Initiating file download...");
                  const safeName     = currentClientName.replace(/ /g, "_");
                  const fileName     = "Kashmir_Tour_" + safeName + ".pdf";
                  const fileResponse = await apiFetch("/output/" + fileName);
                  const fileBlob     = await fileResponse.blob();
                  const blobUrl      = window.URL.createObjectURL(fileBlob);
                  const link         = document.createElement("a");
                  link.href          = blobUrl;
                  link.setAttribute("download", fileName);
                  document.body.appendChild(link);
                  link.click();
                  document.body.removeChild(link);
                  window.URL.revokeObjectURL(blobUrl);
                } else {
                  alert("Compilation failed on Flask server.");
                }
              } catch (err) {
                console.error(err);
                alert("System Interface Error: Script logic execution crashed.");
              }
            }}
          >
            💾 Lock Changes & Generate PDF
          </button>
        </div>
      </div>
    </>
  );
}
