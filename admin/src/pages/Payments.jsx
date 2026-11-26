import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { apiFetch } from '../api';
import ImportPdfs from './ImportPdfs';

/* Payments: the quotes logged in your Google Sheet, with the amount each client has paid.
   Enter an amount here and it is written straight into the sheet (Booking Amount + Payment Status). */

const FILTERS = ['All', 'Pending', 'Token paid', 'Paid in full', 'Completed', 'Follow-up due'];
const LEAD = ['hot', 'warm', 'cold', 'dead'];
const LEAD_COLOR = { hot: '#c62828', warm: '#c26a1b', cold: '#2c6e9b', dead: '#6b7686' };
const ymd = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const inDays = (n) => { const d = new Date(); d.setDate(d.getDate() + n); return ymd(d); };
const isDue = (r) => !!r.follow_up_date && r.follow_up_date <= ymd(new Date()) && !r.completed && r.lead_status !== 'dead';
const TINT = { 'Pending': ['#fdecc8', '#8a5a00'], 'Token paid': ['#dbeafe', '#1d4ed8'], 'Paid in full': ['#d6f5e3', '#14703b'] };
const inr = (n) => '₹' + Math.round(n || 0).toLocaleString('en-IN');
const key = (r) => `${r.name}||${r.quote_no}`;
const MON = { jan: 0, feb: 1, mar: 2, apr: 3, may: 4, jun: 5, jul: 6, aug: 7, sep: 8, oct: 9, nov: 10, dec: 11 };

/* "2027-01-25" or "25 Jan 2027" -> day number (null when the quote says "Flexible" or has no date) */
function travelDay(s) {
  const t = String(s || '').trim();
  let m = t.match(/^(\d{4})-(\d{1,2})-(\d{1,2})/);
  if (m) return Math.floor(Date.UTC(+m[1], +m[2] - 1, +m[3]) / 864e5);
  m = t.match(/(\d{1,2})\s+([A-Za-z]{3})[A-Za-z]*\.?,?\s+(\d{4})/);
  if (m && MON[m[2].toLowerCase()] !== undefined) return Math.floor(Date.UTC(+m[3], MON[m[2].toLowerCase()], +m[1]) / 864e5);
  return null;
}

/* Nearest upcoming trip first; then quotes with no date; then trips already past (most recent first). */
function byTravel(a, b) {
  const now = new Date(), today = Math.floor(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()) / 864e5);
  const rank = (d) => (d === null ? 1 : d >= today ? 0 : 2);
  const da = travelDay(a.travel_date), db = travelDay(b.travel_date);
  if (rank(da) !== rank(db)) return rank(da) - rank(db);
  if (da === null) return 0;
  return rank(da) === 0 ? da - db : db - da;
}

export default function Payments({ onUnauthorized }) {
  const [rows, setRows]     = useState(null);
  const [error, setError]   = useState('');
  const [filter, setFilter] = useState('All');
  const [q, setQ]           = useState('');
  const [open, setOpen]     = useState(null);     // key of the row being edited
  const [amount, setAmount] = useState('');
  const [busy, setBusy]     = useState(false);
  const [saved, setSaved]   = useState('');       // key of the row just saved
  const [confirming, setConfirming] = useState('');   // key of the row whose Confirm is being saved
  const [completing, setCompleting] = useState('');   // key of the row whose Mark complete is being saved
  const [importing, setImporting] = useState(false);   // the "import old PDFs" panel is open

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
      (filter === 'All' || (filter === 'Completed' ? r.completed : filter === 'Follow-up due' ? isDue(r) : r.status === filter)) &&
      (!s || [r.name, r.quote_no, r.email].some((v) => (v || '').toLowerCase().includes(s)))).sort(byTravel);
  }, [rows, filter, q]);

  const toggleConfirm = async (r) => {
    const k = key(r), next = !r.confirmed;
    setConfirming(k); setError('');
    try {
      const res = await apiFetch('/api/admin/payments/confirm', {
        method: 'POST', body: JSON.stringify({ name: r.name, quote_no: r.quote_no, confirmed: next }),
      });
      if (res.status === 401) { onUnauthorized && onUnauthorized(); return; }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || 'Could not update the sheet.');
      setRows((prev) => prev.map((x) => (key(x) === k ? { ...x, confirmed: next, ...(data.row || {}) } : x)));
    } catch (e) { setError(e.message); }
    setConfirming('');
  };

  /* Mark complete: the trip is over / the booking is closed. Writes the date into "Completed On" in the sheet. */
  const toggleComplete = async (r) => {
    const k = key(r), next = !r.completed;
    if (next && r.balance > 0 && !window.confirm(`Mark ${r.name} complete? The remaining ${inr(r.balance)} will be recorded as received (Paid in full, balance ₹0).`)) return;
    setCompleting(k); setError('');
    try {
      const res = await apiFetch('/api/admin/payments/complete', {
        method: 'POST', body: JSON.stringify({ name: r.name, quote_no: r.quote_no, completed: next }),
      });
      if (res.status === 401) { onUnauthorized && onUnauthorized(); return; }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || 'Could not update the sheet.');
      setRows((prev) => prev.map((x) => (key(x) === k ? { ...x, completed: next, completed_on: data.completed_on || '', ...(next ? { follow_up_date: '' } : {}), ...(data.row || {}) } : x)));
    } catch (e) { setError(e.message); }
    setCompleting('');
  };

  /* Hot / warm / cold / dead and the date to call this client back. Written to the sheet's Lead Status + Follow-up Date columns. */
  const saveLead = async (r, patch) => {
    const k = key(r), next = { lead_status: r.lead_status || '', follow_up_date: r.follow_up_date || '', ...patch };
    setRows((prev) => prev.map((x) => (key(x) === k ? { ...x, ...next } : x)));
    setError('');
    try {
      const res = await apiFetch('/api/admin/payments/lead', { method: 'POST', body: JSON.stringify({ name: r.name, quote_no: r.quote_no, ...next }) });
      if (res.status === 401) { onUnauthorized && onUnauthorized(); return; }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || 'Could not update the sheet.');
    } catch (e) { setError(e.message); load(); }
  };

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

        <button type="button" style={{ ...S.ghost, width: '100%', marginBottom: 8 }} onClick={() => setImporting((v) => !v)}>
          {importing ? 'Close PDF import' : 'Import old itinerary PDFs'}
        </button>
        {importing && <ImportPdfs existing={rows} onUnauthorized={onUnauthorized} onImported={load} />}

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
            <div key={k} style={{ ...S.card, ...(r.confirmed ? S.cardOn : {}), ...(r.completed ? S.cardDone : {}) }}>
              <div style={S.top}>
                <div style={{ minWidth: 0 }}>
                  <b style={S.name}>{r.name}</b>
                  <small style={S.small}>{r.quote_no}{r.travel_date ? ` · travel ${r.travel_date}` : ''}</small>
                </div>
                <div style={S.badges}>
                  <span style={{ ...S.badge, background: bg, color: fg }}>{r.status}</span>
                  {r.completed && <span style={{ ...S.badge, background: '#2f5d9e', color: '#fff' }}>Completed{r.completed_on ? ` · ${r.completed_on}` : ''}</span>}
                </div>
              </div>
              <div style={S.nums}>
                <Num label="Cost" value={inr(r.cost)} />
                <Num label="Paid" value={r.booking_amount > 0 ? inr(r.booking_amount) : '—'} />
                <Num label="Balance" value={inr(r.balance)} tone={r.balance > 0 ? '#b42318' : '#14703b'} />
              </div>

              {!editing && (
                <div style={S.btns}>
                  <button type="button" style={{ ...S.primary, minHeight: 38, padding: '4px 14px', fontSize: 14 }} onClick={() => start(r)}>
                    {r.booking_amount > 0 ? 'Change amount' : 'Add booking amount'}
                  </button>
                  <button type="button" disabled={confirming === k} onClick={() => toggleConfirm(r)}
                    style={{ ...S.confirm, ...(r.confirmed ? S.confirmOn : {}) }}
                    title={r.confirmed ? 'Row is green in the sheet. Tap to undo.' : 'Turn this row green and record the 25% booking amount'}>
                    {confirming === k ? 'Saving…' : r.confirmed ? '✓ Confirmed' : 'Confirm'}
                  </button>
                  <button type="button" disabled={completing === k} onClick={() => toggleComplete(r)}
                    style={{ ...S.complete, ...(r.completed ? S.completeOn : {}) }}
                    title={r.completed ? 'Marked complete in the sheet. Tap to undo.' : 'Booking finished: paid in full, balance 0, date saved in the sheet'}>
                    {completing === k ? 'Saving…' : r.completed ? '✓ Completed · tap to undo' : 'Mark complete'}
                  </button>
                </div>
              )}
              {saved === k && !editing && <div style={S.ok}>Saved to the sheet.</div>}

              {!editing && !r.completed && (
                <div style={{ ...S.lead, ...(isDue(r) ? S.leadDue : {}) }}>
                  <div style={S.leadRow}>
                    <div style={S.leadCol}>
                      <span style={S.label}>Lead</span>
                      <select value={r.lead_status || ''} onChange={(e) => saveLead(r, { lead_status: e.target.value })}
                        style={{ ...S.select, ...(r.lead_status ? { borderColor: LEAD_COLOR[r.lead_status], color: LEAD_COLOR[r.lead_status] } : {}) }}
                        aria-label={`Lead status for ${r.name}`}>
                        <option value="">Not set</option>
                        {LEAD.map((st) => <option key={st} value={st}>{st}</option>)}
                      </select>
                    </div>
                    <div style={S.leadCol}>
                      <span style={S.label}>Follow up on{isDue(r) ? (r.follow_up_date === ymd(new Date()) ? ' · TODAY' : ' · OVERDUE') : ''}</span>
                      <input type="date" style={S.dateIn} value={r.follow_up_date || ''}
                        onChange={(e) => saveLead(r, { follow_up_date: e.target.value })} aria-label={`Follow-up date for ${r.name}`} />
                    </div>
                  </div>
                  <div style={S.quick}>
                    {[['Today', 0], ['Tomorrow', 1], ['+3 days', 3], ['+7 days', 7]].map(([label, n]) => (
                      <button key={label} type="button" style={S.mini} onClick={() => saveLead(r, { follow_up_date: inDays(n) })}>{label}</button>
                    ))}
                    {r.follow_up_date && <button type="button" style={S.mini} onClick={() => saveLead(r, { follow_up_date: '' })}>Clear</button>}
                  </div>
                </div>
              )}

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
  cardOn: { background: '#eaf7f0', borderColor: '#7cc8a0' },
  btns: { display: 'flex', gap: 8, flexWrap: 'wrap' },
  confirm: { flex: '0 0 auto', font: 'inherit', fontSize: 14, fontWeight: 700, borderRadius: 9, padding: '4px 14px', minHeight: 38, cursor: 'pointer', background: '#fff', border: '1px solid #2e9e66', color: '#1b7a4b' },
  confirmOn: { background: '#2e9e66', color: '#fff' },
  complete: { flex: '1 1 100%', font: 'inherit', fontSize: 14, fontWeight: 700, borderRadius: 9, padding: '4px 14px', minHeight: 38, cursor: 'pointer', background: '#fff', border: '1px solid #334e68', color: '#334e68' },
  completeOn: { background: '#2f5d9e', borderColor: '#2f5d9e', color: '#fff' },
  cardDone: { background: '#e3edf9', borderColor: '#7c9cc4', borderLeft: '6px solid #2f5d9e', fontWeight: 700 },
  lead: { marginTop: 10, padding: '8px 10px', border: `1px solid ${LINE}`, borderRadius: 8, background: '#fafbfc' },
  leadDue: { borderColor: '#c62828', background: '#fdf0ef' },
  leadRow: { display: 'grid', gridTemplateColumns: '1fr 1.3fr', gap: 8 },
  leadCol: { minWidth: 0 },
  select: { width: '100%', boxSizing: 'border-box', font: 'inherit', fontSize: 15, fontWeight: 600, textTransform: 'capitalize', minHeight: 40, padding: '4px 8px', borderRadius: 8, border: `2px solid ${LINE}`, background: '#fff', color: INK },
  dateIn: { width: '100%', boxSizing: 'border-box', font: 'inherit', fontSize: 15, minHeight: 40, padding: '4px 8px', borderRadius: 8, border: `1px solid ${LINE}`, background: '#fff', color: INK },
  mini: { font: 'inherit', fontSize: 13, fontWeight: 600, padding: '4px 10px', minHeight: 32, borderRadius: 99, border: `1px solid ${LINE}`, background: '#fff', color: INK, cursor: 'pointer' },
  badges: { display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 },
  edit: { borderTop: `1px solid ${LINE}`, paddingTop: 8 },
  label: { display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6 },
  quick: { display: 'flex', gap: 6, flexWrap: 'wrap', margin: '8px 0 4px' },
  nav: { display: 'flex', gap: 8, marginTop: 8 },
  err: { background: '#fee4e2', color: '#b42318', borderRadius: 8, padding: '10px 12px', marginBottom: 12 },
  ok: { color: '#14703b', fontSize: 13, fontWeight: 600, marginTop: 8 },
  empty: { textAlign: 'center', color: MUTED, padding: '18px 0' },
};
