import { useState } from "react";
import { apiFetch } from "../api.js";
import { VEHICLE_OPTIONS, MEAL_PLANS } from "../pages/QuotePreview.jsx";
import { Icon, Stepper } from "./ui.jsx";

/* Trip step: big inputs, +/- steppers, segmented controls. Sends the same payload as before. */
export default function LeadForm({ onGenerated, trip = { vehicle: "", meal: "MAP" }, onTripChange = () => {}, hasQuote = false }) {
  const [destination, setDestination] = useState("Kashmir");
  const [days, setDays] = useState(5);
  const [clientName, setClientName] = useState("");
  const [startDate, setStartDate] = useState("");
  const [adults, setAdults] = useState(2);
  const [clientEmail, setClientEmail] = useState("");
  const [kids, setKids] = useState(0);
  const [tripPace] = useState("Moderate");
  const [budgetTier, setBudgetTier] = useState("Mid-Range");
  const [customVehicle, setCustomVehicle] = useState(false);   // "Other…" chosen in the vehicle list
  const coupleItems = trip.coupleExtras || [];
  const toggleCoupleItem = (k) => onTripChange({ ...trip, coupleExtras: coupleItems.includes(k) ? coupleItems.filter((x) => x !== k) : [...coupleItems, k] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (hasQuote && !window.confirm("Rebuild the itinerary? Changes you made to the days will be replaced.")) return;
    setLoading(true);
    setError(null);

    const payload = {
      destination,
      days: parseInt(days) || 5,
      client_name: clientName.trim() || "Valued Client",
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
      const response = await apiFetch("/api/itinerary/generate", { method: "POST", body: JSON.stringify(payload) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || "Failed to generate itinerary.");
      onGenerated(result);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const vehicleValue = customVehicle || (trip.vehicle && !VEHICLE_OPTIONS.includes(trip.vehicle)) ? "__custom" : trip.vehicle;
  const pickVehicle = (v) => {
    if (v === "__custom") { setCustomVehicle(true); onTripChange({ ...trip, vehicle: "" }); }
    else { setCustomVehicle(false); onTripChange({ ...trip, vehicle: v }); }
  };
  const meal = MEAL_PLANS.find((m) => m.code === (trip.meal || "MAP"));
  const isCouple = Number(adults) === 2;   // couple options are offered only for exactly 2 adults

  return (
    <form onSubmit={handleSubmit} className="sv-stack sv-form">
      <section className="sv-card sv-stack">
        <label className="sv-field"><span className="sv-lbl">Client name</span>
          <input className="sv-inp" type="text" placeholder="e.g. John Doe" autoComplete="off" value={clientName} onChange={(e) => setClientName(e.target.value)} required /></label>
        <label className="sv-field"><span className="sv-lbl">Email (optional)</span>
          <input className="sv-inp" type="email" inputMode="email" placeholder="Leave blank if not given" value={clientEmail} onChange={(e) => setClientEmail(e.target.value)} /></label>
        <div className="sv-pair sv-pair-fields">
          <label className="sv-field"><span className="sv-lbl">Start date</span>
            <input className="sv-inp" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} required /></label>
          <label className="sv-field"><span className="sv-lbl">Destination</span>
            <input className="sv-inp" type="text" value={destination} onChange={(e) => setDestination(e.target.value)} required /></label>
        </div>
      </section>

      <section className="sv-card sv-stack">
        <Stepper label="Days" value={Number(days) || 1} min={1} max={30} onChange={setDays} />
        <div className="sv-pair">
          <Stepper label="Adults" value={Number(adults) || 1} min={1} max={30} onChange={setAdults} />
          <Stepper label="Kids <12" value={Number(kids) || 0} min={0} max={15} onChange={setKids} />
        </div>
        {isCouple && (
          <div className="sv-stack">
            <button type="button" className={"sv-sw" + (trip.couple ? " on" : "")} role="switch" aria-checked={!!trip.couple}
              onClick={() => onTripChange({ ...trip, couple: !trip.couple })}>
              <span>Couple</span><i className="box" /></button>
            {trip.couple && [["couple_cake", "Cake Cutting Celebration"], ["couple_bed", "Bed decoration"], ["couple_candle", "Candle light dinner"]].map(([k, lab]) => (
              <button key={k} type="button" className={"sv-sw" + (coupleItems.includes(k) ? " on" : "")} role="switch" aria-checked={coupleItems.includes(k)}
                onClick={() => toggleCoupleItem(k)}>
                <span>{lab}</span><i className="box" /></button>
            ))}
            {trip.couple && <div className="sv-sub">Ticked items are added to the PDF.</div>}
          </div>
        )}
      </section>

      <section className="sv-card sv-stack">
        <div><span className="sv-lbl">Budget</span>
          <div className="sv-seg">{["Budget", "Mid-Range", "Luxury"].map((b) => (
            <button key={b} type="button" className={budgetTier === b ? "on" : ""} onClick={() => setBudgetTier(b)}>{b}</button>))}</div></div>
        <div><span className="sv-lbl">Meal plan</span>
          <div className="sv-seg">{MEAL_PLANS.map((m) => (
            <button key={m.code} type="button" className={(trip.meal || "MAP") === m.code ? "on" : ""} onClick={() => onTripChange({ ...trip, meal: m.code })}>{m.code}</button>))}</div>
          <div className="sv-sub sv-mt">{meal?.name}: {meal?.desc}</div></div>
        <div><span className="sv-lbl">Vehicle</span>
          <div className="sv-pills">
            <button type="button" className={"sv-pillb" + (vehicleValue === "" ? " on" : "")} onClick={() => pickVehicle("")}>Auto (by group)</button>
            {VEHICLE_OPTIONS.map((v) => <button key={v} type="button" className={"sv-pillb" + (vehicleValue === v ? " on" : "")} onClick={() => pickVehicle(v)}>{v}</button>)}
            <button type="button" className={"sv-pillb" + (vehicleValue === "__custom" ? " on" : "")} onClick={() => pickVehicle("__custom")}>Other…</button>
          </div>
          {vehicleValue === "__custom" && (
            <input className="sv-inp sv-mt" type="text" placeholder="Vehicle name, e.g. Toyota Innova Hycross" value={trip.vehicle}
              onChange={(e) => onTripChange({ ...trip, vehicle: e.target.value })} />
          )}
        </div>
      </section>

      {error && <div className="sv-note bad" role="alert">{error}</div>}

      <button type="submit" className="sv-btn sv-primary sv-full" disabled={loading}>
        {loading ? <><span className="sv-spin" />Building the itinerary…</> : <>{hasQuote ? "Rebuild itinerary" : "Build itinerary"}<Icon name="chev" /></>}
      </button>
      {hasQuote && <div className="sv-sub sv-center">Rebuilding replaces the changes you made in Days.</div>}
    </form>
  );
}
