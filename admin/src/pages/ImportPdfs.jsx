import React, { useRef, useState } from 'react';
import { getAdminToken } from '../api';

/* Import old itinerary PDFs into the Google Sheet.
   1. Pick one or more PDFs made by this site. Each is read on the server (nothing is saved yet).
   2. Check / fix what was read.  3. "Add to sheet" writes each quote as a row (same name + quote no = updates its row). */

const inr = (n) => '₹' + Math.round(Number(n) || 0).toLocaleString('en-IN');
const MORE = [
  ['email', 'Email'], ['days', 'Days'], ['adults', 'Adults'], ['kids', 'Kids'], ['budget_tier', 'Budget tier'],
  ['vehicle', 'Vehicle'], ['meal_plan', 'Meal plan'], ['pickup', 'Pick-up'], ['drop', 'Drop'],
  ['hotels', 'Hotels'], ['inclusions', 'Extra inclusions'], ['generated_at', 'Quote date'],
];
let seq = 0;

export default function ImportPdfs({ existing, onUnauthorized, onImported }) {
  const [items, setItems] = useState([]);
  const [reading, setReading] = useState(false);
  const [busy, setBusy] = useState(false);
  const input = useRef(null);

  const patch = (id, p) => setItems((prev) => prev.map((x) => (x.id === id ? { ...x, ...p } : x)));
  const setField = (id, k, v) => setItems((prev) => prev.map((x) => (x.id === id ? { ...x, fields: { ...x.fields, [k]: v }, state: x.state === 'done' ? 'ready' : x.state } : x)));
  const inSheet = (f) => (existing || []).some((r) => r.name === f.name && r.quote_no === f.quote_no);

  const post = async (url, opts) => {
    const token = getAdminToken();
    const res = await fetch(url, { ...opts, headers: { ...(opts.headers || {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) } });
    if (res.status === 401) { onUnauthorized && onUnauthorized(); throw new Error('Please log in again.'); }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `Server error (${res.status}).`);
    return data;
  };

  const pick = async (e) => {
    const files = Array.from(e.target.files || []);
    e.target.value = '';
    if (!files.length) return;
    setReading(true);
    for (const file of files) {                       // one request per file: stays under the host's size and time limits
      const id = ++seq;
      setItems((prev) => [...prev, { id, file: file.name, state: 'reading', fields: {}, error: '' }]);
      try {
        const fd = new FormData(); fd.append('file', file);
        const data = await post('/api/admin/payments/import/parse', { method: 'POST', body: fd });
        patch(id, { state: 'ready', fields: data.fields, missing: data.missing });
      } catch (err) { patch(id, { state: 'failed', error: err.message }); }
    }
    setReading(false);
  };

  const valid = (f) => f.name && f.quote_no && Number(String(f.cost).replace(/,/g, '')) > 0;

  const importAll = async () => {
    setBusy(true);
    for (const it of items) {
      if (it.state !== 'ready' || !valid(it.fields)) continue;
      patch(it.id, { state: 'saving', error: '' });
      try {
        const data = await post('/api/admin/payments/import', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ...it.fields, cost: String(it.fields.cost).replace(/,/g, '') }),
        });
        patch(it.id, { state: 'done', note: data.detail });
      } catch (err) { patch(it.id, { state: 'ready', error: err.message }); }
    }
    setBusy(false);
    onImported && onImported();
  };

  const ready = items.filter((x) => x.state === 'ready' && valid(x.fields)).length;
  const clear = () => setItems((prev) => prev.filter((x) => x.state === 'reading' || x.state === 'saving'));

  return (
    <div style={S.box}>
      <b style={S.title}>Import old itinerary PDFs</b>
      <p style={S.text}>Choose PDFs you already sent to clients. The details are read from each one and added to your Google Sheet. Payments stay “Pending” until you enter them below.</p>
      <input ref={input} type="file" accept="application/pdf,.pdf" multiple hidden onChange={pick} />
      <div style={S.row}>
        <button type="button" style={S.primary} onClick={() => input.current && input.current.click()} disabled={reading || busy}>
          {reading ? 'Reading PDFs…' : items.length ? 'Add more PDFs' : 'Choose PDF files'}
        </button>
        {items.length > 0 && <button type="button" style={S.ghost} onClick={clear} disabled={busy || reading}>Clear</button>}
      </div>

      {items.map((it) => {
        const f = it.fields || {}, dup = it.state === 'ready' && inSheet(f);
        return (
          <div key={it.id} style={S.card}>
            <div style={S.top}>
              <small style={S.file}>{it.file}</small>
              {it.state === 'reading' && <span style={S.tag}>Reading…</span>}
              {it.state === 'saving' && <span style={S.tag}>Saving…</span>}
              {it.state === 'done' && <span style={{ ...S.tag, background: '#d6f5e3', color: '#14703b' }}>{it.note === 'updated existing row' ? 'Updated in sheet' : 'Added to sheet'}</span>}
              {dup && <span style={{ ...S.tag, background: '#dbeafe', color: '#1d4ed8' }}>Already in sheet · will update</span>}
              {it.state === 'failed' && <span style={{ ...S.tag, background: '#fee4e2', color: '#b42318' }}>Could not read</span>}
            </div>
            {it.error && <div style={S.err}>{it.error}</div>}

            {(it.state === 'ready' || it.state === 'saving' || it.state === 'done') && (
              <>
                <div style={S.grid}>
                  <Field label="Client name" value={f.name} onChange={(v) => setField(it.id, 'name', v)} bad={!f.name} />
                  <Field label="Quote no" value={f.quote_no} onChange={(v) => setField(it.id, 'quote_no', v)} bad={!f.quote_no} />
                  <Field label="Cost (₹)" value={f.cost} inputMode="numeric" onChange={(v) => setField(it.id, 'cost', v)} bad={!(Number(String(f.cost).replace(/,/g, '')) > 0)} />
                  <Field label="Travel date" value={f.travel_date} onChange={(v) => setField(it.id, 'travel_date', v)} />
                </div>
                <small style={S.small}>{f.days ? `${f.days} days` : ''}{f.adults ? ` · ${f.adults} adults` : ''}{Number(f.kids) ? `, ${f.kids} kids` : ''}{f.cost ? ` · ${inr(String(f.cost).replace(/,/g, ''))}` : ''}</small>
                <details style={S.more}>
                  <summary style={S.sum}>All details read from the PDF</summary>
                  <div style={S.grid}>
                    {MORE.map(([k, label]) => <Field key={k} label={label} value={f[k]} onChange={(v) => setField(it.id, k, v)} />)}
                  </div>
                </details>
              </>
            )}
          </div>
        );
      })}

      {items.some((x) => x.state === 'ready' || x.state === 'done') && (
        <button type="button" style={{ ...S.primary, marginTop: 6 }} onClick={importAll} disabled={busy || reading || !ready}>
          {busy ? 'Adding to sheet…' : ready ? `Add ${ready} quote${ready > 1 ? 's' : ''} to sheet` : 'Nothing left to add'}
        </button>
      )}
    </div>
  );
}

const Field = ({ label, value, onChange, bad, inputMode }) => (
  <label style={S.fld}>
    <span style={S.lab}>{label}</span>
    <input style={{ ...S.input, ...(bad ? { borderColor: '#b42318' } : {}) }} value={value ?? ''} inputMode={inputMode}
      onChange={(e) => onChange(e.target.value)} />
  </label>
);

const INK = '#1e3a4f', MUTED = '#5a6578', LINE = '#dde3ea', GOLD = '#b8956b';
const S = {
  box: { background: '#fff', border: `1px solid ${LINE}`, borderRadius: 12, padding: 12, marginBottom: 10, color: INK },
  title: { fontFamily: 'Georgia, serif', fontSize: '1rem' },
  text: { margin: '4px 0 8px', color: MUTED, fontSize: 12.5, lineHeight: 1.4 },
  row: { display: 'flex', gap: 8 },
  primary: { flex: 1, width: '100%', font: 'inherit', fontWeight: 600, borderRadius: 9, padding: '6px 14px', minHeight: 42, cursor: 'pointer', background: GOLD, border: `1px solid ${GOLD}`, color: '#fff' },
  ghost: { flex: '0 0 auto', font: 'inherit', fontWeight: 600, borderRadius: 9, padding: '6px 14px', minHeight: 42, cursor: 'pointer', background: '#fff', border: `1px solid ${LINE}`, color: INK },
  card: { border: `1px solid ${LINE}`, borderRadius: 10, padding: 10, marginTop: 8 },
  top: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, flexWrap: 'wrap' },
  file: { color: MUTED, fontSize: 11.5, overflowWrap: 'anywhere' },
  tag: { fontSize: 11, fontWeight: 700, borderRadius: 99, padding: '3px 10px', background: '#fdecc8', color: '#8a5a00', whiteSpace: 'nowrap' },
  err: { background: '#fee4e2', color: '#b42318', borderRadius: 8, padding: '8px 10px', margin: '6px 0', fontSize: 13 },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(140px,1fr))', gap: 6, marginTop: 6 },
  fld: { display: 'block', minWidth: 0 },
  lab: { display: 'block', fontSize: 11.5, color: MUTED, marginBottom: 2 },
  input: { width: '100%', boxSizing: 'border-box', font: 'inherit', fontSize: 16, color: INK, background: '#fff', border: `1px solid ${LINE}`, borderRadius: 8, padding: '4px 8px', minHeight: 38 },
  small: { display: 'block', color: MUTED, fontSize: 11.5, marginTop: 6 },
  more: { marginTop: 6 },
  sum: { cursor: 'pointer', fontSize: 13, fontWeight: 600, color: INK },
};
