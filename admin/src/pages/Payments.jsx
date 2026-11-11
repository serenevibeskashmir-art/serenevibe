import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { apiFetch } from '../api';

/* Payments: the quotes logged in your Google Sheet, with the amount each client has paid.
   Enter an amount here and it is written straight into the sheet (Booking Amount + Payment Status). */

const FILTERS = ['All', 'Pending', 'Token paid', 'Paid in full'];
const TINT = { 'Pending': ['#fdecc8', '#8a5a00'], 'Token paid': ['#dbeafe', '#1d4ed8'], 'Paid in full': ['#d6f5e3', '#14703b'] };
const inr = (n) => '₹' + Math.round(n || 0).toLocaleString('en-IN');
const key = (r) => `${r.name}||${r.quote_no}`;

export default function Payments({ onUnauthorized }) {
  const [rows, setRows]     = useState(null);
  const [error, setError]   = useState('');
  const [filter, setFilter] = useState('All');
  const [q, setQ]           = useState('');
  const [open, setOpen]     = useState(null);     // key of the row being edited
  const [amount, setAmount] = useState('');
  const [busy, setBusy]     = useState(false);
  const [saved, setSaved]   = useState('');       // key of the row just saved

  const load = useCallback(async () => {
    setError('');
    try {
      const res = await apiFetch('/api/admin/payments');
      if (res.status === 401) { onUnauthorized && onUnauthorized(); return; }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || 'Could not read the sheet.');
      setRows(data.rows);
    } catch (e) { setError(e.message); setRows((r) => r || []); }
  }, [onUnauthorized]);

  useEffect(() => { load(); }, [load]);

  const totals = useMemo(() => {
    const all = rows || [];
    return {
      quoted: all.reduce((s, r) => s + r.cost, 0),
      received: all.reduce((s, r) => s + r.booking_amount, 0),
      pending: all.filter((r) => r.status === 'Pending').length,
    };
  }, [rows]);

  const shown = useMemo(() => {
    const s = q.trim().toLowerCase();
    return (rows || []).filter((r) =>
      (filter === 'All' || r.status === filter) &&
      (!s || [r.name, r.quote_no, r.email].some((v) => (v || '').toLowerCase().includes(s))));
  }, [rows, filter, q]);

  const start = (r) => {
    setOpen(key(r)); setSaved(''); setError('');
    setAmount(String(r.booking_amount > 0 ? r.booking_amount : Math.round(r.cost * 0.25)));   // 25% token by default
  };

  const save = async (r) => {
    setBusy(true); setError('');
    try {
      const res = await apiFetch('/api/admin/payments', {
        method: 'POST', body: JSON.stringify({ name: r.name, quote_no: r.quote_no, amount }),
      });
      if (res.status === 401) { onUnauthorized && onUnauthorized(); return; }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || 'Could not save.');
      setRows((prev) => prev.map((x) => (key(x) === key(r) ? { ...x, ...data.row } : x)));
      setOpen(null); setSaved(key(r));
    } catch (e) { setError(e.message); }
    setBusy(false);
  };

  const n = Number(amount);
  const bad = amount === '' || !(n >= 0);

  return (
    <section style={S.page}>
      <div style={S.wrap}>
        <p style={S.text}>Every quote you generate is logged in your Google Sheet. Enter what a client has paid and the sheet is updated for you.</p>

        {rows && (
          <div style={S.stats}>
            <Stat label="Quoted" value={inr(totals.quoted)} />
            <Stat label="Received" value={inr(totals.received)} />
            <Stat label="Unpaid quotes" value={totals.pending} />
          </div>
        )}

        <div style={S.chips} role="tablist" aria-label="Payment status">
          {FILTERS.map((f) => (
            <button key={f} type="button" role="tab" aria-selected={filter === f}
              style={{ ...S.chip, ...(filter === f ? S.chipOn : {}) }} onClick={() => setFilter(f)}>{f}</button>
          ))}
        </div>
        <div style={S.tools}>
          <input style={S.input} type="search" placeholder="Search name or quote no" value={q} onChange={(e) => setQ(e.target.value)} />
          <button type="button" style={S.ghost} onClick={load}>Refresh</button>
        </div>

        {error && <div style={S.err} role="alert">{error}</div>}
        {rows === null && <div style={S.empty}>Reading the sheet…</div>}
        {rows && !rows.length && !error && <div style={S.empty}>No quotes in the sheet yet. They appear here after you generate a PDF.</div>}
        {rows && rows.length > 0 && !shown.length && <div style={S.empty}>No quotes match.</div>}

        {shown.map((r) => {
          const k = key(r), editing = open === k, [bg, fg] = TINT[r.status] || TINT.Pending;
          return (
            <div key={k} style={S.card}>
              <div style={S.top}>
                <div style={{ minWidth: 0 }}>
                  <b style={S.name}>{r.name}</b>
                  <small style={S.small}>{r.quote_no}{r.travel_date ? ` · travel ${r.travel_date}` : ''}</small>
                </div>
                <span style={{ ...S.badge, background: bg, color: fg }}>{r.status}</span>
              </div>
              <div style={S.nums}>
                <Num label="Cost" value={inr(r.cost)} />
                <Num label="Paid" value={r.booking_amount > 0 ? inr(r.booking_amount) : '—'} />
                <Num label="Balance" value={inr(r.balance)} tone={r.balance > 0 ? '#b42318' : '#14703b'} />
              </div>

              {!editing && (
                <button type="button" style={{ ...S.primary, minHeight: 38, padding: '4px 14px', fontSize: 14 }} onClick={() => start(r)}>
                  {r.booking_amount > 0 ? 'Change amount' : 'Add booking amount'}
                </button>
              )}
              {saved === k && !editing && <div style={S.ok}>Saved to the sheet.</div>}

              {editing && (
                <div style={S.edit}>
                  <label style={S.label} htmlFor={`amt-${k}`}>Total amount received so far (₹)</label>
                  <input id={`amt-${k}`} style={S.input} type="number" inputMode="numeric" min="0" autoFocus
                    value={amount} onChange={(e) => setAmount(e.target.value)} />
                  <div style={S.quick}>
                    <button type="button" style={S.chip} onClick={() => setAmount(String(Math.round(r.cost * 0.25)))}>25% · {inr(r.cost * 0.25)}</button>
                    <button type="button" style={S.chip} onClick={() => setAmount(String(Math.round(r.cost * 0.5)))}>50%</button>
                    <button type="button" style={S.chip} onClick={() => setAmount(String(r.cost))}>Full · {inr(r.cost)}</button>
                  </div>
                  {!bad && <small style={S.small}>Balance after this: {inr(r.cost - n)}</small>}
                  <div style={S.nav}>
                    <button type="button" style={S.ghost} onClick={() => setOpen(null)} disabled={busy}>Cancel</button>
                    <button type="button" style={S.primary} onClick={() => save(r)} disabled={busy || bad}>
                      {busy ? 'Saving…' : 'Save to sheet'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

const Stat = ({ label, value }) => (
  <div style={S.stat}><small style={S.small}>{label}</small><b style={S.statNum}>{value}</b></div>
);
const Num = ({ label, value, tone }) => (
  <div><small style={S.small}>{label}</small><b style={{ display: 'block', color: tone || INK, fontVariantNumeric: 'tabular-nums' }}>{value}</b></div>
);

const INK = '#1e3a4f', MUTED = '#5a6578', LINE = '#dde3ea', GOLD = '#b8956b';
const S = {
  page: { padding: 'clamp(8px,3vw,32px) clamp(10px,3vw,32px) clamp(12px,3vw,32px)', boxSizing: 'border-box' },
  wrap: { maxWidth: 640, margin: '0 auto' },
  text: { margin: '0 0 8px', color: MUTED, fontSize: 12.5, lineHeight: 1.4 },
  stats: { display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 6, marginBottom: 8 },
  stat: { background: '#152a3a', color: '#fff', borderRadius: 10, padding: '7px 9px', minWidth: 0 },
  statNum: { display: 'block', fontFamily: 'Georgia, serif', fontSize: '.98rem', color: '#e3c49b', fontVariantNumeric: 'tabular-nums' },
  chips: { display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 },
  chip: { font: 'inherit', fontSize: 13, fontWeight: 600, border: `1px solid ${LINE}`, background: '#fff', color: INK, borderRadius: 99, padding: '4px 12px', minHeight: 34, cursor: 'pointer' },
  chipOn: { background: GOLD, borderColor: GOLD, color: '#fff' },
  tools: { display: 'flex', gap: 6, marginBottom: 8 },
  input: { flex: 1, width: '100%', boxSizing: 'border-box', font: 'inherit', fontSize: 16, color: INK, background: '#fff', border: `1px solid ${LINE}`, borderRadius: 8, padding: '6px 10px', minHeight: 42 },
  card: { background: '#fff', border: `1px solid ${LINE}`, borderRadius: 12, padding: 12, marginBottom: 8, color: INK },
  top: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 10 },
  name: { display: 'block', fontFamily: 'Georgia, serif', fontSize: '1rem', overflowWrap: 'anywhere' },
  small: { display: 'block', color: MUTED, fontSize: 11.5, marginTop: 1 },
  badge: { fontSize: 11, fontWeight: 700, borderRadius: 99, padding: '3px 10px', whiteSpace: 'nowrap' },
  nums: { display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 8, margin: '8px 0' },
  primary: { flex: 1, width: '100%', font: 'inherit', fontWeight: 600, borderRadius: 9, padding: '6px 14px', minHeight: 42, cursor: 'pointer', background: GOLD, border: `1px solid ${GOLD}`, color: '#fff' },
  ghost: { flex: '0 0 auto', font: 'inherit', fontWeight: 600, borderRadius: 9, padding: '6px 14px', minHeight: 42, cursor: 'pointer', background: '#fff', border: `1px solid ${LINE}`, color: INK },
  edit: { borderTop: `1px solid ${LINE}`, paddingTop: 8 },
  label: { display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6 },
  quick: { display: 'flex', gap: 6, flexWrap: 'wrap', margin: '8px 0 4px' },
  nav: { display: 'flex', gap: 8, marginTop: 8 },
  err: { background: '#fee4e2', color: '#b42318', borderRadius: 8, padding: '10px 12px', marginBottom: 12 },
  ok: { color: '#14703b', fontSize: 13, fontWeight: 600, marginTop: 8 },
  empty: { textAlign: 'center', color: MUTED, padding: '18px 0' },
};
