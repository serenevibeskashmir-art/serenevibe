import React, { useMemo, useState } from 'react';
import { HOTEL_KB } from './QuotePreview.jsx';

/* Step-by-step trip cost calculator.
   Step 0: number of nights. Steps 1..N: one night each (location, hotel,
   rooms, cost per night, extra beds, EB cost). Last step: vehicle + total.
   Works entirely in the browser; nothing is saved or sent to the server. */

const LOCS = [
  { key: 'srinagar', label: 'Srinagar' },
  { key: 'pahalgam', label: 'Pahalgam' },
  { key: 'gulmarg',  label: 'Gulmarg'  },
  { key: 'sonamarg', label: 'Sonamarg' },
];
const MAX_NIGHTS = 30;

const inr = (n) => '₹' + Math.round(n).toLocaleString('en-IN');
const num = (v) => Math.max(0, parseFloat(v) || 0);
const hotelsOf = (loc) => (HOTEL_KB[loc] || []).map((h) => h.name);
const blankNight = (prev) =>
  prev
    ? { ...prev }
    : { loc: 'srinagar', hotel: hotelsOf('srinagar')[0] || '', rooms: 1, rate: '', eb: 0, ebc: '' };
const dayCost = (r) => ({ rooms: num(r.rooms) * num(r.rate), eb: num(r.eb) * num(r.ebc) });

export default function CostCalculator() {
  const [nights, setNights] = useState(1);
  const [rows, setRows]     = useState([blankNight()]);
  const [vehicle, setVehicle] = useState('');
  const [step, setStep]     = useState(0);
  const [copied, setCopied] = useState(false);

  const totals = useMemo(() => {
    let rooms = 0, eb = 0;
    rows.forEach((r) => { const c = dayCost(r); rooms += c.rooms; eb += c.eb; });
    const veh = num(vehicle);
    return { rooms, eb, hotel: rooms + eb, veh, total: rooms + eb + veh };
  }, [rows, vehicle]);

  const setNightCount = (value) => {
    const n = Math.min(MAX_NIGHTS, Math.max(1, parseInt(value, 10) || 1));
    setNights(n);
    setRows((prev) => {
      const next = prev.slice(0, n);
      while (next.length < n) next.push(blankNight(next[next.length - 1]));
      return next;
    });
  };

  const update = (i, patch) =>
    setRows((prev) => prev.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));

  const changeLoc = (i, loc) => update(i, { loc, hotel: hotelsOf(loc)[0] || '' });

  const go = (s) => { setStep(s); window.scrollTo(0, 0); };

  const copySummary = async () => {
    const label = (r) => (LOCS.find((l) => l.key === r.loc) || {}).label;
    const lines = rows.map((r, i) => {
      const c = dayCost(r);
      return `Day ${i + 1}: ${label(r)}, ${r.hotel}, ${num(r.rooms)} room(s) x ${inr(num(r.rate))}` +
        (num(r.eb) ? ` + ${num(r.eb)} EB x ${inr(num(r.ebc))}` : '') +
        ` = ${inr(c.rooms + c.eb)}`;
    });
    lines.push(`Hotels: ${inr(totals.hotel)}`, `Vehicle: ${inr(totals.veh)}`, `Total: ${inr(totals.total)}`);
    try {
      await navigator.clipboard.writeText(lines.join('\n'));
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch { /* clipboard blocked: nothing to do */ }
  };

  const lastStep = nights + 1;
  const row = rows[step - 1];

  return (
    <section style={S.page}>
      <div style={S.wrap}>
        <h2 style={S.title}>Trip Cost Calculator</h2>

        <div style={S.progress} aria-hidden="true">
          {Array.from({ length: nights + 2 }, (_, i) => (
            <i key={i} style={{ ...S.seg, ...(i <= step ? S.segOn : {}) }} />
          ))}
        </div>

        {step === 0 && (
          <>
            <div style={S.card}>
              <h3 style={S.h3}>How many nights?</h3>
              <p style={S.sub}>The trip is priced one night at a time. Each night gets its own step.</p>
              <div style={S.stepper}>
                <button type="button" style={S.round} aria-label="One night less"
                  onClick={() => setNightCount(nights - 1)}>−</button>
                <input type="number" min="1" max={MAX_NIGHTS} inputMode="numeric"
                  style={S.bigInput} value={nights} aria-label="Number of nights"
                  onChange={(e) => e.target.value !== '' && setNightCount(e.target.value)} />
                <button type="button" style={S.round} aria-label="One night more"
                  onClick={() => setNightCount(nights + 1)}>+</button>
              </div>
              <div style={S.center}>{nights} night{nights > 1 ? 's' : ''}, {nights + 1} days</div>
            </div>
            <div style={S.nav}>
              <button type="button" style={S.primary} onClick={() => go(1)}>Next</button>
            </div>
          </>
        )}

        {step >= 1 && step <= nights && row && (
          <>
            <div style={S.card}>
              <h3 style={S.h3}>Night {step} of {nights}</h3>
              <p style={S.sub}>
                Day {step}{step > 1 ? ` · starts as a copy of Day ${step - 1}, change what differs` : ''}
              </p>

              <label style={S.field}>
                <span style={S.label}>Location</span>
                <select style={S.input} value={row.loc} onChange={(e) => changeLoc(step - 1, e.target.value)}>
                  {LOCS.map((l) => <option key={l.key} value={l.key}>{l.label}</option>)}
                </select>
              </label>

              <label style={S.field}>
                <span style={S.label}>Hotel</span>
                <select style={S.input} value={row.hotel} onChange={(e) => update(step - 1, { hotel: e.target.value })}>
                  {hotelsOf(row.loc).map((h) => <option key={h} value={h}>{h}</option>)}
                </select>
              </label>

              <div style={S.two}>
                <label style={S.field}>
                  <span style={S.label}>Number of rooms</span>
                  <input type="number" min="0" inputMode="numeric" style={S.input}
                    value={row.rooms} onChange={(e) => update(step - 1, { rooms: e.target.value })} />
                </label>
                <label style={S.field}>
                  <span style={S.label}>Cost per night (₹)</span>
                  <input type="number" min="0" step="100" inputMode="numeric" style={S.input}
                    value={row.rate} onChange={(e) => update(step - 1, { rate: e.target.value })} />
                </label>
              </div>

              <div style={S.two}>
                <label style={S.field}>
                  <span style={S.label}>No. of EB</span>
                  <input type="number" min="0" inputMode="numeric" style={S.input}
                    value={row.eb} onChange={(e) => update(step - 1, { eb: e.target.value })} />
                </label>
                <label style={S.field}>
                  <span style={S.label}>Cost of EB (₹)</span>
                  <input type="number" min="0" step="100" inputMode="numeric" style={S.input}
                    value={row.ebc} onChange={(e) => update(step - 1, { ebc: e.target.value })} />
                </label>
              </div>

              <div style={S.dayTotal}>
                <div>
                  Day {step} total
                  <small style={S.small}>
                    {num(row.rooms)} × {inr(num(row.rate))} + {num(row.eb)} EB × {inr(num(row.ebc))}
                  </small>
                </div>
                <b style={S.dayTotalNum}>{inr(dayCost(row).rooms + dayCost(row).eb)}</b>
              </div>
            </div>
            <div style={S.nav}>
              <button type="button" style={S.ghost} onClick={() => go(step - 1)}>Back</button>
              <button type="button" style={S.primary} onClick={() => go(step + 1)}>
                {step === nights ? 'Next: vehicle' : `Next: night ${step + 1}`}
              </button>
            </div>
          </>
        )}

        {step === lastStep && (
          <>
            <div style={S.card}>
              <h3 style={S.h3}>Vehicle and total</h3>
              <label style={S.field}>
                <span style={S.label}>Vehicle cost, whole trip (₹)</span>
                <input type="number" min="0" step="100" inputMode="numeric" style={S.input}
                  value={vehicle} onChange={(e) => setVehicle(e.target.value)} />
                <small style={S.small}>Added once at the end.</small>
              </label>
            </div>

            <div style={{ ...S.card, marginTop: 12 }}>
              <h3 style={S.h3}>Night by night</h3>
              <ul style={S.list}>
                {rows.map((r, i) => {
                  const c = dayCost(r);
                  const loc = (LOCS.find((l) => l.key === r.loc) || {}).label;
                  return (
                    <li key={i} style={S.li}>
                      <div style={{ minWidth: 0 }}>
                        <b>Day {i + 1} · {loc}</b>
                        <small style={S.small}>{r.hotel}</small>
                        <small style={S.small}>
                          {num(r.rooms)} room × {inr(num(r.rate))}
                          {num(r.eb) ? ` + ${num(r.eb)} EB × ${inr(num(r.ebc))}` : ''}
                        </small>
                        <button type="button" style={S.link} onClick={() => go(i + 1)}>Edit</button>
                      </div>
                      <b style={S.nowrap}>{inr(c.rooms + c.eb)}</b>
                    </li>
                  );
                })}
              </ul>
            </div>

            <div style={S.sum}>
              <SumRow label={`Rooms (${nights} nights)`} value={inr(totals.rooms)} />
              <SumRow label={`Extra beds (${nights} nights)`} value={inr(totals.eb)} />
              <SumRow label="Hotels subtotal" value={inr(totals.hotel)} />
              <SumRow label="Vehicle" value={inr(totals.veh)} />
              <div style={{ ...S.sumRow, ...S.sumTotal }}>
                <span style={{ color: '#fff', fontWeight: 600 }}>Grand total</span>
                <b style={S.grand}>{inr(totals.total)}</b>
              </div>
            </div>

            <div style={S.nav}>
              <button type="button" style={S.ghost} onClick={() => go(nights)}>Back</button>
              <button type="button" style={S.primary} onClick={copySummary}>
                {copied ? 'Copied' : 'Copy quote summary'}
              </button>
            </div>
          </>
        )}
      </div>

      {/* Running total, always visible */}
      <div style={S.bar} aria-live="polite">
        <div style={S.barInner}>
          <span style={S.barLbl}>{step === lastStep ? 'Grand total' : `Running total · ${nights} night${nights > 1 ? 's' : ''}`}</span>
          <b style={S.barNum}>{inr(totals.total)}</b>
        </div>
      </div>
    </section>
  );
}

function SumRow({ label, value }) {
  return (
    <div style={S.sumRow}>
      <span>{label}</span>
      <b style={{ color: '#fff', fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>{value}</b>
    </div>
  );
}

const INK = '#1e3a4f', MUTED = '#5a6578', LINE = '#dde3ea', GOLD = '#b8956b', NAVY = '#152a3a';

const S = {
  page: { padding: 'clamp(16px,4vw,32px)', paddingBottom: 96, boxSizing: 'border-box' },
  wrap: { maxWidth: 560, margin: '0 auto' },
  title: { margin: '0 0 8px', fontSize: 'clamp(1.1rem,3vw,1.35rem)', color: INK, fontFamily: 'Georgia, serif' },
  h3: { margin: '0 0 4px', fontSize: '1.2rem', color: INK, fontFamily: 'Georgia, serif' },
  sub: { margin: '0 0 16px', color: MUTED },
  progress: { display: 'flex', gap: 4, margin: '12px 0 16px' },
  seg: { flex: 1, height: 5, borderRadius: 3, background: LINE, display: 'block' },
  segOn: { background: GOLD },
  card: { background: '#fff', border: `1px solid ${LINE}`, borderRadius: 12, padding: 18, color: INK },
  field: { display: 'block', marginTop: 14, minWidth: 0 },
  label: { display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 5, color: INK },
  input: {
    width: '100%', boxSizing: 'border-box', font: 'inherit', fontSize: 16, color: INK, background: '#fff',
    border: `1px solid ${LINE}`, borderRadius: 8, padding: '10px 12px', minHeight: 48,
  },
  two: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 },
  stepper: { display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 18, margin: '18px 0 6px' },
  round: {
    width: 56, height: 56, borderRadius: '50%', border: `1px solid ${LINE}`, background: '#fff',
    color: INK, fontSize: 26, cursor: 'pointer',
  },
  bigInput: {
    width: 110, textAlign: 'center', fontFamily: 'Georgia, serif', fontSize: '2.6rem', fontWeight: 600,
    padding: 4, minHeight: 64, border: 0, borderBottom: `2px solid ${GOLD}`, borderRadius: 0,
    background: 'transparent', color: INK, boxSizing: 'border-box',
  },
  center: { textAlign: 'center', color: MUTED },
  dayTotal: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 12,
    background: '#f7f1e9', borderRadius: 8, padding: '12px 14px', marginTop: 18,
  },
  dayTotalNum: { fontFamily: 'Georgia, serif', fontSize: '1.4rem', whiteSpace: 'nowrap' },
  small: { display: 'block', color: MUTED, fontSize: 12, marginTop: 2 },
  nav: { display: 'flex', gap: 10, marginTop: 16 },
  primary: {
    flex: 1, font: 'inherit', fontWeight: 600, borderRadius: 10, padding: '12px 18px', minHeight: 50,
    cursor: 'pointer', background: GOLD, border: `1px solid ${GOLD}`, color: '#fff',
  },
  ghost: {
    flex: '0 0 auto', font: 'inherit', fontWeight: 600, borderRadius: 10, padding: '12px 18px', minHeight: 50,
    cursor: 'pointer', background: '#fff', border: `1px solid ${LINE}`, color: INK,
  },
  list: { margin: 0, padding: 0, listStyle: 'none' },
  li: { display: 'flex', justifyContent: 'space-between', gap: 12, padding: '10px 0', borderBottom: `1px solid ${LINE}` },
  link: { background: 'none', border: 0, padding: 0, marginTop: 4, color: GOLD, fontWeight: 600, fontSize: 13, cursor: 'pointer' },
  nowrap: { whiteSpace: 'nowrap' },
  sum: { background: NAVY, color: '#fff', borderRadius: 12, padding: '16px 18px', marginTop: 16 },
  sumRow: { display: 'flex', justifyContent: 'space-between', gap: 12, padding: '5px 0', color: 'rgba(255,255,255,.82)' },
  sumTotal: { borderTop: '1px solid rgba(255,255,255,.25)', marginTop: 8, paddingTop: 12, alignItems: 'baseline' },
  grand: { fontFamily: 'Georgia, serif', fontSize: '1.7rem', color: '#e3c49b', fontVariantNumeric: 'tabular-nums' },
  bar: {
    position: 'fixed', left: 0, right: 0, bottom: 0, background: NAVY, color: '#fff', zIndex: 5,
    padding: '10px 16px calc(10px + env(safe-area-inset-bottom, 0px))',
  },
  barInner: { maxWidth: 560, margin: '0 auto', display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 12 },
  barLbl: { fontSize: 13, color: 'rgba(255,255,255,.8)' },
  barNum: { fontFamily: 'Georgia, serif', fontSize: '1.3rem', color: '#e3c49b', fontVariantNumeric: 'tabular-nums' },
};
