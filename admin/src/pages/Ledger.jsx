import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { apiFetch } from '../api';

/* Expenses & profit: every entry is written to the "Expenses" tab of your Google Sheet.
   Add an entry here and it appears in the sheet; delete it here and it leaves the sheet. */

const TYPES = ['Profit', 'Expense'];
const FILTERS = ['All', ...TYPES];
const SUGGEST = {
  Profit: ['Package booking', 'Commission', 'Referral', 'Other'],
  Expense: ['Hotel', 'Cab / Transport', 'Food', 'Activities & Tickets', 'Marketing', 'Salary', 'Office', 'Other'],
};
const TINT = { Profit: ['#d6f5e3', '#14703b'], Expense: ['#fee4e2', '#b42318'] };
const inr = (n) => '₹' + Math.round(n || 0).toLocaleString('en-IN');

const todayISO = () => {                      // local date (not UTC) so the default is right after midnight in India
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};
const prettyDate = (iso) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || '');
  if (!m) return iso || '';
  return new Date(+m[1], +m[2] - 1, +m[3]).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
};
const prettyMonth = (ym) => {
  const [y, m] = ym.split('-');
  return new Date(+y, +m - 1, 1).toLocaleDateString('en-IN', { month: 'long', year: 'numeric' });
};

const blank = () => ({ type: 'Expense', amount: '', date: todayISO(), category: '', description: '', quote_no: '', client: '' });

export default function Ledger({ onUnauthorized }) {
  const [rows, setRows]       = useState(null);
  const [error, setError]     = useState('');
  const [filter, setFilter]   = useState('All');
  const [month, setMonth]     = useState('all');
  const [form, setForm]       = useState(blank);
  const [adding, setAdding]   = useState(false);   // is the add form open
  const [busy, setBusy]       = useState(false);
  const [removing, setRemoving] = useState('');    // id being deleted
  const [note, setNote]       = useState('');
  const [quotes, setQuotes]   = useState(null);    // quotes from the Quotes sheet, for "Link to quote"
  const [quotesErr, setQuotesErr] = useState('');
  const [qSearch, setQSearch]   = useState('');
  const [qOpen, setQOpen]       = useState(false);   // quote list is only shown while the search box is in use
  const qBox = useRef(null);

  const load = useCallback(async () => {
    setError('');
    try {
      const res = await apiFetch('/api/admin/ledger');
      if (res.status === 401) { onUnauthorized && onUnauthorized(); return; }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || 'Could not read the sheet.');
      setRows(data.rows);
    } catch (e) { setError(e.message); setRows((r) => r || []); }
  }, [onUnauthorized]);

  useEffect(() => { load(); }, [load]);

  const loadQuotes = useCallback(async () => {
    setQuotesErr('');
    try {
      const res = await apiFetch('/api/admin/payments');       // same quote list the Client payments view reads
      if (res.status === 401) { onUnauthorized && onUnauthorized(); return; }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || 'Could not read the quotes.');
      setQuotes(data.rows || []);
    } catch (e) { setQuotesErr(e.message); setQuotes((q) => q || []); }
  }, [onUnauthorized]);

  useEffect(() => {                                  // tap anywhere outside the picker to close the list
    if (!qOpen) return undefined;
    const close = (e) => { if (qBox.current && !qBox.current.contains(e.target)) setQOpen(false); };
    document.addEventListener('pointerdown', close);
    return () => document.removeEventListener('pointerdown', close);
  }, [qOpen]);

  const quoteMatches = useMemo(() => {
    const s = qSearch.trim().toLowerCase();
    return (quotes || [])
      .filter((r) => !s || [r.name, r.quote_no].some((v) => (v || '').toLowerCase().includes(s)))
      .slice(0, 30);
  }, [quotes, qSearch]);

  const months = useMemo(
    () => [...new Set((rows || []).map((r) => (r.date || '').slice(0, 7)).filter(Boolean))].sort().reverse(),
    [rows]);

  const inMonth = useMemo(
    () => (rows || []).filter((r) => month === 'all' || (r.date || '').startsWith(month)),
    [rows, month]);

  const totals = useMemo(() => {
    const sum = (t) => inMonth.filter((r) => r.type === t).reduce((s, r) => s + r.amount, 0);
    const profit = sum('Profit'), expense = sum('Expense');
    return { profit, expense, net: profit - expense };
  }, [inMonth]);

  const shown = useMemo(() => inMonth.filter((r) => filter === 'All' || r.type === filter), [inMonth, filter]);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const amountNum = Number(form.amount);
  const bad = !(amountNum > 0) || !form.date;

  const openForm = (type) => {
    setForm({ ...blank(), type }); setAdding(true); setNote(''); setError(''); setQSearch(''); setQOpen(false);
    loadQuotes();                                              // always fresh: picks up quotes made a minute ago
  };

  const add = async () => {
    setBusy(true); setError(''); setNote('');
    try {
      const res = await apiFetch('/api/admin/ledger', { method: 'POST', body: JSON.stringify(form) });
      if (res.status === 401) { onUnauthorized && onUnauthorized(); return; }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || 'Could not save.');
      setRows((prev) => {
        const next = [data.row, ...(prev || [])];
        return next.sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0));   // stable: newest date first
      });
      setAdding(false);
      setNote(`${data.row.type} of ${inr(data.row.amount)} saved to the sheet.`);
    } catch (e) { setError(e.message); }
    setBusy(false);
  };

  const remove = async (r) => {
    if (!window.confirm(`Delete this ${r.type.toLowerCase()} of ${inr(r.amount)}${r.category ? ` (${r.category})` : ''}? It will also be removed from the sheet.`)) return;
    setRemoving(r.id); setError(''); setNote('');
    try {
      const res = await apiFetch(`/api/admin/ledger/${encodeURIComponent(r.id)}`, { method: 'DELETE' });
      if (res.status === 401) { onUnauthorized && onUnauthorized(); return; }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || 'Could not delete.');
      setRows((prev) => prev.filter((x) => x.id !== r.id));
      setNote('Deleted from the sheet.');
    } catch (e) { setError(e.message); }
    setRemoving('');
  };

  return (
    <section style={S.page}>
      <div style={S.wrap}>
        <p style={S.text}>Add what you spend and what you earn. Everything is saved straight into the <b>Expenses</b> tab of your Google Sheet.</p>

        {rows && (
          <>
            <div style={S.stats}>
              <Stat label="Profit" value={inr(totals.profit)} />
              <Stat label="Expenses" value={inr(totals.expense)} />
              <Stat label="Net" value={(totals.net < 0 ? '−' : '') + inr(Math.abs(totals.net))} tone={totals.net < 0 ? '#ffb4ab' : '#9be3b8'} />
            </div>
            {months.length > 0 && (
              <div style={S.tools}>
                <select style={S.input} value={month} onChange={(e) => setMonth(e.target.value)} aria-label="Month">
                  <option value="all">All time</option>
                  {months.map((m) => <option key={m} value={m}>{prettyMonth(m)}</option>)}
                </select>
              </div>
            )}
          </>
        )}

        {!adding && (
          <div style={S.nav}>
            <button type="button" style={{ ...S.primary, background: '#14703b', borderColor: '#14703b' }} onClick={() => openForm('Profit')}>+ Add profit</button>
            <button type="button" style={{ ...S.primary, background: '#b42318', borderColor: '#b42318' }} onClick={() => openForm('Expense')}>+ Add expense</button>
          </div>
        )}

        {adding && (
          <div style={{ ...S.card, borderColor: TINT[form.type][1] }}>
            <div style={S.seg} role="tablist" aria-label="Entry type">
              {TYPES.map((t) => (
                <button key={t} type="button" role="tab" aria-selected={form.type === t}
                  style={{ ...S.segBtn, ...(form.type === t ? { background: TINT[t][1], color: '#fff' } : {}) }}
                  onClick={() => setForm((f) => ({ ...f, type: t }))}>{t}</button>
              ))}
            </div>

            <label style={S.label} htmlFor="lg-amt">Amount (₹)</label>
            <input id="lg-amt" style={S.input} type="number" inputMode="decimal" min="0" autoFocus
              value={form.amount} onChange={set('amount')} placeholder="e.g. 4500" />

            <label style={S.label} htmlFor="lg-date">Date</label>
            <input id="lg-date" style={S.input} type="date" value={form.date} onChange={set('date')} max="2100-12-31" />

            <label style={S.label} htmlFor="lg-cat">Category</label>
            <input id="lg-cat" style={S.input} list="lg-cats" value={form.category} onChange={set('category')} maxLength={60} placeholder="Pick or type" />
            <datalist id="lg-cats">{SUGGEST[form.type].map((c) => <option key={c} value={c} />)}</datalist>

            <label style={S.label} htmlFor="lg-desc">Note (optional)</label>
            <input id="lg-desc" style={S.input} value={form.description} onChange={set('description')} maxLength={300} placeholder="e.g. Houseboat advance, Sharma family" />

            <label style={S.label} htmlFor="lg-q">Link to quote (optional)</label>
            {form.quote_no ? (
              <div style={S.picked}>
                <div style={{ minWidth: 0 }}>
                  <b style={S.cat}>{form.client || 'Quote'}</b>
                  <small style={S.small}>{form.quote_no}</small>
                </div>
                <button type="button" style={S.del} onClick={() => setForm((f) => ({ ...f, quote_no: '', client: '' }))}>Remove</button>
              </div>
            ) : (
              <div ref={qBox}>
                <input id="lg-q" style={S.input} type="search" value={qSearch}
                  onChange={(e) => { setQSearch(e.target.value); setQOpen(true); }}
                  onFocus={() => setQOpen(true)} onClick={() => setQOpen(true)}
                  placeholder={quotes === null ? 'Loading quotes…' : 'Tap to choose a quote'} autoComplete="off" />
                {qOpen && (
                  <div style={S.list} role="listbox" aria-label="Quotes">
                    {quotesErr && <small style={{ ...S.small, color: '#b42318', padding: '10px 12px' }}>{quotesErr} <button type="button" style={S.del} onClick={loadQuotes}>Try again</button></small>}
                    {quotes === null && !quotesErr && <small style={{ ...S.small, padding: '10px 12px' }}>Loading quotes…</small>}
                    {quotes && !quotes.length && !quotesErr && <small style={{ ...S.small, padding: '10px 12px' }}>No quotes in the sheet yet.</small>}
                    {quotes && quotes.length > 0 && !quoteMatches.length && <small style={{ ...S.small, padding: '10px 12px' }}>No quote matches.</small>}
                    {quoteMatches.map((r) => (
                      <button key={`${r.name}||${r.quote_no}`} type="button" role="option" style={S.pick}
                        onClick={() => { setForm((f) => ({ ...f, quote_no: r.quote_no, client: r.name })); setQSearch(''); setQOpen(false); }}>
                        <b>{r.name}</b><small style={S.small}>{r.quote_no}{r.travel_date ? ` · travel ${r.travel_date}` : ''}</small>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            <div style={S.nav}>
              <button type="button" style={S.ghost} onClick={() => setAdding(false)} disabled={busy}>Cancel</button>
              <button type="button" style={S.primary} onClick={add} disabled={busy || bad}>{busy ? 'Saving…' : 'Save to sheet'}</button>
            </div>
          </div>
        )}

        {note && <div style={S.ok} role="status">{note}</div>}
        {error && <div style={S.err} role="alert">{error}</div>}

        <div style={{ ...S.chips, marginTop: 14 }} role="tablist" aria-label="Show">
          {FILTERS.map((f) => (
            <button key={f} type="button" role="tab" aria-selected={filter === f}
              style={{ ...S.chip, ...(filter === f ? S.chipOn : {}) }} onClick={() => setFilter(f)}>{f === 'All' ? 'All' : f === 'Expense' ? 'Expenses' : 'Profit'}</button>
          ))}
          <button type="button" style={S.chip} onClick={load}>Refresh</button>
        </div>

        {rows === null && <div style={S.empty}>Reading the sheet…</div>}
        {rows && !rows.length && !error && <div style={S.empty}>Nothing added yet. Use the buttons above to add your first entry.</div>}
        {rows && rows.length > 0 && !shown.length && <div style={S.empty}>No entries match.</div>}

        {shown.map((r) => {
          const [bg, fg] = TINT[r.type] || TINT.Expense;
          return (
            <div key={r.id} style={S.row}>
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={S.rowTop}>
                  <span style={{ ...S.badge, background: bg, color: fg }}>{r.type}</span>
                  <b style={S.cat}>{r.category || 'Uncategorised'}</b>
                </div>
                <small style={S.small}>{prettyDate(r.date)}{r.client ? ` · ${r.client}` : ''}{r.quote_no ? ` · ${r.quote_no}` : ''}</small>
                {r.description && <small style={{ ...S.small, color: INK }}>{r.description}</small>}
              </div>
              <div style={S.right}>
                <b style={{ color: fg, fontVariantNumeric: 'tabular-nums' }}>{r.type === 'Expense' ? '−' : '+'}{inr(r.amount)}</b>
                <button type="button" style={S.del} onClick={() => remove(r)} disabled={removing === r.id} aria-label={`Delete ${r.type} ${inr(r.amount)}`}>
                  {removing === r.id ? '…' : 'Delete'}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

const Stat = ({ label, value, tone }) => (
  <div style={S.stat}><small style={{ ...S.small, color: '#b9c6d2' }}>{label}</small><b style={{ ...S.statNum, ...(tone ? { color: tone } : {}) }}>{value}</b></div>
);

const INK = '#1e3a4f', MUTED = '#5a6578', LINE = '#dde3ea', GOLD = '#b8956b';
const S = {
  page: { padding: 'clamp(16px,4vw,32px)', boxSizing: 'border-box' },
  wrap: { maxWidth: 640, margin: '0 auto' },
  text: { margin: '0 0 14px', color: MUTED },
  stats: { display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 10, marginBottom: 12 },
  stat: { background: '#152a3a', color: '#fff', borderRadius: 12, padding: '10px 12px', minWidth: 0 },
  statNum: { display: 'block', fontFamily: 'Georgia, serif', fontSize: '1.05rem', color: '#e3c49b', fontVariantNumeric: 'tabular-nums', overflowWrap: 'anywhere' },
  chips: { display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 10 },
  chip: { font: 'inherit', fontSize: 13, fontWeight: 600, border: `1px solid ${LINE}`, background: '#fff', color: INK, borderRadius: 99, padding: '7px 14px', minHeight: 40, cursor: 'pointer' },
  chipOn: { background: GOLD, borderColor: GOLD, color: '#fff' },
  tools: { display: 'flex', gap: 8, marginBottom: 12 },
  input: { flex: 1, width: '100%', boxSizing: 'border-box', font: 'inherit', fontSize: 16, color: INK, background: '#fff', border: `1px solid ${LINE}`, borderRadius: 8, padding: '10px 12px', minHeight: 48 },
  card: { background: '#fff', border: `2px solid ${LINE}`, borderRadius: 12, padding: 16, marginBottom: 12, color: INK },
  seg: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, marginBottom: 12, background: '#eef2f6', padding: 4, borderRadius: 10 },
  segBtn: { font: 'inherit', fontWeight: 700, border: 0, borderRadius: 8, padding: '10px 0', minHeight: 44, cursor: 'pointer', background: 'transparent', color: INK },
  label: { display: 'block', fontSize: 13, fontWeight: 600, margin: '12px 0 6px' },
  primary: { flex: 1, width: '100%', font: 'inherit', fontWeight: 600, borderRadius: 10, padding: '12px 18px', minHeight: 48, cursor: 'pointer', background: GOLD, border: `1px solid ${GOLD}`, color: '#fff' },
  ghost: { flex: '0 0 auto', font: 'inherit', fontWeight: 600, borderRadius: 10, padding: '12px 18px', minHeight: 48, cursor: 'pointer', background: '#fff', border: `1px solid ${LINE}`, color: INK },
  nav: { display: 'flex', gap: 10, marginTop: 12, marginBottom: 4 },
  row: { display: 'flex', gap: 12, alignItems: 'flex-start', justifyContent: 'space-between', background: '#fff', border: `1px solid ${LINE}`, borderRadius: 12, padding: '12px 14px', marginBottom: 10, color: INK },
  rowTop: { display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' },
  cat: { fontFamily: 'Georgia, serif', fontSize: '1rem', overflowWrap: 'anywhere' },
  small: { display: 'block', color: MUTED, fontSize: 12, marginTop: 3, overflowWrap: 'anywhere' },
  badge: { fontSize: 11, fontWeight: 700, borderRadius: 99, padding: '3px 10px', whiteSpace: 'nowrap' },
  right: { display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6, flex: '0 0 auto' },
  del: { font: 'inherit', fontSize: 12, fontWeight: 600, color: '#b42318', background: 'transparent', border: 0, padding: '8px 4px', minHeight: 36, cursor: 'pointer', textDecoration: 'underline' },
  err: { background: '#fee4e2', color: '#b42318', borderRadius: 8, padding: '10px 12px', marginTop: 12 },
  ok: { color: '#14703b', fontSize: 13, fontWeight: 600, margin: '10px 0 0' },
  picked: { display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, background: '#f4f8fb', border: `1px solid ${LINE}`, borderRadius: 8, padding: '8px 12px', minHeight: 48 },
  list: { marginTop: 6, maxHeight: 220, overflowY: 'auto', overscrollBehavior: 'contain', border: `1px solid ${LINE}`, borderRadius: 8, background: '#fff' },
  pick: { display: 'block', width: '100%', textAlign: 'left', font: 'inherit', color: INK, background: '#fff', border: 0, borderBottom: `1px solid ${LINE}`, padding: '10px 12px', minHeight: 48, cursor: 'pointer' },
  empty: { textAlign: 'center', color: MUTED, padding: '28px 0' },
};
