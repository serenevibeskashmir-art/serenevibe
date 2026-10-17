import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { apiFetch } from '../api';

/* Leads that arrive on your WhatsApp Business number. The server fills this
   list automatically; here you follow them up, fix details and download Excel. */

const STATUSES = ['new', 'quoted', 'follow-up', 'booked', 'lost'];
const STATUS_COLOR = { new: '#b8956b', quoted: '#2c6e9b', 'follow-up': '#c26a1b', booked: '#1f7a4d', lost: '#8a94a3' };
const FIELDS = [
  ['name', 'Name'], ['destination', 'Destination'], ['travel_dates', 'Travel dates'],
  ['people', 'People'], ['budget', 'Budget'],
];

const when = (iso) =>
  iso ? new Date(iso).toLocaleString('en-IN', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '';

export default function WhatsAppLeads({ onUnauthorized }) {
  const [leads, setLeads] = useState(null);
  const [connected, setConnected] = useState(true);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState('all');
  const [q, setQ] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await apiFetch('/api/admin/whatsapp-leads');
      if (res.status === 401) { onUnauthorized && onUnauthorized(); return; }
      if (!res.ok) throw new Error('Could not load leads.');
      const data = await res.json();
      setLeads(data.leads);
      setConnected(data.connected);
      setError('');
    } catch (e) {
      setError(e.message);
    }
  }, [onUnauthorized]);

  useEffect(() => {
    load();
    const t = setInterval(load, 30000);          // new WhatsApp leads appear on their own
    return () => clearInterval(t);
  }, [load]);

  const save = async (id, patch) => {
    setLeads((prev) => prev.map((l) => (l.id === id ? { ...l, ...patch } : l)));
    const res = await apiFetch(`/api/admin/whatsapp-leads/${id}`, { method: 'PUT', body: JSON.stringify(patch) });
    if (!res.ok) { setError('Could not save that change.'); load(); }
  };

  const download = async () => {
    setBusy(true);
    try {
      const res = await apiFetch('/api/admin/whatsapp-leads/export.xlsx');
      if (!res.ok) throw new Error('Download failed.');
      const url = URL.createObjectURL(await res.blob());
      const a = document.createElement('a');
      a.href = url; a.download = 'whatsapp-leads.xlsx'; a.click();
      URL.revokeObjectURL(url);
    } catch (e) { setError(e.message); }
    setBusy(false);
  };

  const shown = useMemo(() => {
    const s = q.trim().toLowerCase();
    return (leads || []).filter((l) =>
      (filter === 'all' || l.status === filter) &&
      (!s || [l.name, l.phone, l.destination, l.last_message].some((v) => (v || '').toLowerCase().includes(s))));
  }, [leads, filter, q]);

  const count = (st) => (leads || []).filter((l) => l.status === st).length;

  return (
    <section style={S.page}>
      <div style={S.wrap}>
        <div style={S.head}>
          <div>
            <h2 style={S.title}>WhatsApp Leads</h2>
            <p style={S.text}>Every new enquiry on your WhatsApp Business number is added here automatically. Details are picked out of the chat; fix anything that is wrong.</p>
          </div>
          <button type="button" style={S.primary} onClick={download} disabled={busy || !leads?.length}>
            {busy ? 'Preparing…' : 'Download Excel'}
          </button>
        </div>

        {!connected && (
          <div style={S.warn}>
            WhatsApp is not connected yet, so no leads can arrive. Finish the setup steps for the webhook
            (WHATSAPP_VERIFY_TOKEN and WHATSAPP_APP_SECRET on the server), then new messages will appear here.
          </div>
        )}
        {error && <div style={S.err}>{error}</div>}

        <div style={S.chips}>
          {['all', ...STATUSES].map((st) => (
            <button key={st} type="button" onClick={() => setFilter(st)}
              style={{ ...S.chip, ...(filter === st ? S.chipOn : {}) }}>
              {st === 'all' ? `All ${leads ? leads.length : ''}` : `${st} ${count(st)}`}
            </button>
          ))}
        </div>
        <input style={S.search} placeholder="Search name, phone, destination or message" value={q}
          onChange={(e) => setQ(e.target.value)} aria-label="Search leads" />

        {!leads && !error && <p style={S.text}>Loading…</p>}
        {leads && !shown.length && (
          <p style={S.text}>{leads.length ? 'No leads match.' : 'No leads yet. The first WhatsApp message you receive will show up here.'}</p>
        )}

        <div style={S.grid}>
          {shown.map((l) => (
            <article key={l.id} style={S.card}>
              <div style={S.cardTop}>
                <div style={{ minWidth: 0 }}>
                  <b style={S.name}>{l.name || 'Unknown name'}</b>
                  <a href={`https://wa.me/${l.phone}`} target="_blank" rel="noreferrer" style={S.phone}>+{l.phone}</a>
                </div>
                <select value={l.status} onChange={(e) => save(l.id, { status: e.target.value })}
                  style={{ ...S.status, borderColor: STATUS_COLOR[l.status], color: STATUS_COLOR[l.status] }}
                  aria-label={`Status for ${l.name || l.phone}`}>
                  {STATUSES.map((st) => <option key={st} value={st}>{st}</option>)}
                </select>
              </div>

              <p style={S.last}>“{l.last_message}”<small style={S.when}> {when(l.last_at)} · {l.msg_count} message{l.msg_count === 1 ? '' : 's'}</small></p>

              <div style={S.fields}>
                {FIELDS.map(([k, label]) => (
                  <label key={k} style={S.field}>
                    <span style={S.label}>{label}</span>
                    <input style={S.input} defaultValue={l[k]} key={l[k]} placeholder="not mentioned"
                      onBlur={(e) => e.target.value !== l[k] && save(l.id, { [k]: e.target.value })} />
                  </label>
                ))}
              </div>
              <label style={S.field}>
                <span style={S.label}>Notes</span>
                <textarea style={{ ...S.input, minHeight: 60 }} defaultValue={l.notes} key={'n' + l.notes}
                  onBlur={(e) => e.target.value !== l.notes && save(l.id, { notes: e.target.value })} />
              </label>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

const INK = '#1e3a4f', MUTED = '#5a6578', LINE = '#dde3ea', GOLD = '#b8956b';
const S = {
  page: { padding: 'clamp(16px,4vw,32px)', boxSizing: 'border-box' },
  wrap: { maxWidth: 1200, margin: '0 auto' },
  head: { display: 'flex', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap', alignItems: 'flex-start' },
  title: { margin: '0 0 8px', fontSize: 'clamp(1.1rem,3vw,1.35rem)', color: INK, fontFamily: 'Georgia, serif' },
  text: { margin: '0 0 12px', color: MUTED, maxWidth: 680, lineHeight: 1.6 },
  primary: { font: 'inherit', fontWeight: 600, borderRadius: 10, padding: '10px 18px', minHeight: 44, cursor: 'pointer', background: GOLD, border: `1px solid ${GOLD}`, color: '#fff' },
  warn: { background: '#fbf3e4', border: '1px solid #ecd9b3', color: '#6b4e12', borderRadius: 8, padding: '10px 14px', margin: '4px 0 12px', lineHeight: 1.5 },
  err: { background: '#fdecea', border: '1px solid #f3c2bd', color: '#8a1f17', borderRadius: 8, padding: '10px 14px', margin: '4px 0 12px' },
  chips: { display: 'flex', gap: 8, flexWrap: 'wrap', margin: '8px 0 12px' },
  chip: { font: 'inherit', fontSize: 14, padding: '8px 14px', minHeight: 40, borderRadius: 99, border: `1px solid ${LINE}`, background: '#fff', color: INK, cursor: 'pointer', textTransform: 'capitalize' },
  chipOn: { background: INK, color: '#fff', borderColor: INK },
  search: { width: '100%', boxSizing: 'border-box', font: 'inherit', fontSize: 16, padding: '10px 12px', minHeight: 44, border: `1px solid ${LINE}`, borderRadius: 8, marginBottom: 16, color: INK },
  grid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(min(100%, 340px), 1fr))', gap: 14 },
  card: { background: '#fff', border: `1px solid ${LINE}`, borderRadius: 12, padding: 16, minWidth: 0, color: INK },
  cardTop: { display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'flex-start' },
  name: { display: 'block', fontSize: '1.05rem', overflowWrap: 'anywhere' },
  phone: { color: MUTED, fontSize: 14 },
  status: { font: 'inherit', fontWeight: 600, fontSize: 14, padding: '6px 8px', minHeight: 40, borderRadius: 8, border: '2px solid', background: '#fff', textTransform: 'capitalize' },
  last: { margin: '10px 0 12px', color: MUTED, fontSize: 14, lineHeight: 1.5, overflowWrap: 'anywhere' },
  when: { display: 'block', marginTop: 2, fontSize: 12 },
  fields: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 },
  field: { display: 'block', minWidth: 0, marginTop: 6 },
  label: { display: 'block', fontSize: 12, fontWeight: 600, color: MUTED, marginBottom: 3 },
  input: { width: '100%', boxSizing: 'border-box', font: 'inherit', fontSize: 15, padding: '8px 10px', minHeight: 40, border: `1px solid ${LINE}`, borderRadius: 6, color: INK, background: '#fff' },
};
