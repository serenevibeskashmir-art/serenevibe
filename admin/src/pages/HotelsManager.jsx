import React, { useCallback, useEffect, useState } from 'react';
import { apiFetch } from '../api';

const PLACES = ['Srinagar', 'Pahalgam', 'Gulmarg', 'Sonamarg'];

/**
 * Hotels tab: add / rename / delete hotels. Hotels added here are used by the
 * itinerary builder, cost calculator, PDF quotation, website slideshow and the AI assistant.
 * Photos are added from the "Hotel Photo Manager" at the bottom of the Itinerary Builder.
 */
export default function HotelsManager({ onChanged, onUnauthorized }) {
  const [hotels, setHotels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState('');
  const [place, setPlace] = useState(PLACES[0]);
  const [editId, setEditId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);

  const load = useCallback(async () => {
    try {
      const res = await apiFetch('/api/admin/hotels');
      if (res.status === 401) return onUnauthorized?.();
      const data = await res.json();
      setHotels(data.hotels || []);
    } catch {
      setMsg({ type: 'error', text: 'Could not load hotels.' });
    } finally {
      setLoading(false);
    }
  }, [onUnauthorized]);

  useEffect(() => { load(); }, [load]);

  const reset = () => { setName(''); setPlace(PLACES[0]); setEditId(null); };

  const submit = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    setMsg(null);
    try {
      const res = await apiFetch(editId ? `/api/admin/hotels/${editId}` : '/api/admin/hotels', {
        method: editId ? 'PUT' : 'POST',
        body: JSON.stringify({ name, place }),
      });
      if (res.status === 401) return onUnauthorized?.();
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Save failed.');
      setMsg({ type: 'ok', text: editId ? 'Hotel updated.' : `"${data.hotel.name}" added to ${data.hotel.place}.` });
      reset();
      await load();
      await onChanged?.();
    } catch (err) {
      setMsg({ type: 'error', text: err.message });
    } finally {
      setBusy(false);
    }
  };

  const remove = async (h) => {
    if (!window.confirm(`Delete "${h.name}"? Its saved photos are deleted too.`)) return;
    try {
      const res = await apiFetch(`/api/admin/hotels/${h.id}`, { method: 'DELETE' });
      if (res.status === 401) return onUnauthorized?.();
      if (!res.ok) throw new Error('Delete failed.');
      if (editId === h.id) reset();
      await load();
      await onChanged?.();
    } catch (err) {
      setMsg({ type: 'error', text: err.message });
    }
  };

  const startEdit = (h) => { setEditId(h.id); setName(h.name); setPlace(h.place); setMsg(null); };

  return (
    <section style={S.panel}>
      <h2 style={S.title}>Hotels</h2>
      <p style={S.text}>
        Add hotels here and they appear everywhere: itinerary builder, cost calculator, PDF quotation, the website
        &ldquo;Where You&rsquo;ll Stay&rdquo; slideshow and the AI assistant. After adding a hotel, upload its photos
        in the <strong>Hotel Photo Manager</strong> at the bottom of the Itinerary Builder (a hotel with no photos
        is not shown in the website slideshow).
      </p>

      <form onSubmit={submit} style={S.form}>
        <input
          style={{ ...S.input, flex: '2 1 220px' }}
          placeholder="Hotel name, e.g. Hotel Royal Palace"
          value={name}
          maxLength={150}
          onChange={(e) => setName(e.target.value)}
        />
        <select style={{ ...S.input, flex: '1 1 140px' }} value={place} onChange={(e) => setPlace(e.target.value)}>
          {PLACES.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <button type="submit" disabled={busy || !name.trim()} style={S.primary}>
          {editId ? 'Save changes' : '+ Add hotel'}
        </button>
        {editId && <button type="button" onClick={reset} style={S.secondary}>Cancel</button>}
      </form>

      {msg && <p style={{ ...S.msg, color: msg.type === 'ok' ? '#047857' : '#b91c1c' }}>{msg.text}</p>}

      <h3 style={S.sub}>Hotels you added</h3>
      {loading ? (
        <p style={S.text}>Loading…</p>
      ) : hotels.length === 0 ? (
        <p style={S.text}>None yet. The built-in hotels are always available.</p>
      ) : (
        <ul style={S.list}>
          {hotels.map((h) => (
            <li key={h.id} style={S.row}>
              <div>
                <strong>{h.name}</strong>
                <span style={S.place}> · {h.place}</span>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button type="button" style={S.secondary} onClick={() => startEdit(h)}>Edit</button>
                <button type="button" style={S.danger} onClick={() => remove(h)}>Delete</button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

const S = {
  panel: { background: '#fff', border: '1px solid #e2e8f0', borderRadius: 14, padding: 'clamp(14px,4vw,24px)', fontFamily: 'Inter, system-ui, sans-serif', color: '#0f172a' },
  title: { margin: '0 0 6px', fontSize: '1.25rem' },
  sub: { margin: '24px 0 10px', fontSize: '1rem' },
  text: { margin: '0 0 16px', fontSize: '0.88rem', color: '#64748b', lineHeight: 1.5 },
  form: { display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' },
  input: { padding: '8px 12px', border: '1px solid #cbd5e1', borderRadius: 8, fontSize: '0.9rem', minHeight: 40, boxSizing: 'border-box', background: '#f8fafc', color: '#0f172a' },
  primary: { padding: '8px 18px', background: '#0284c7', color: '#fff', border: 'none', borderRadius: 8, fontWeight: 700, cursor: 'pointer', minHeight: 40 },
  secondary: { padding: '6px 14px', background: '#f1f5f9', color: '#334155', border: '1px solid #cbd5e1', borderRadius: 8, fontWeight: 600, cursor: 'pointer', minHeight: 36 },
  danger: { padding: '6px 14px', background: '#fef2f2', color: '#b91c1c', border: '1px solid #fecaca', borderRadius: 8, fontWeight: 600, cursor: 'pointer', minHeight: 36 },
  msg: { margin: '12px 0 0', fontSize: '0.85rem', fontWeight: 600 },
  list: { listStyle: 'none', margin: 0, padding: 0, border: '1px solid #e2e8f0', borderRadius: 10 },
  row: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, flexWrap: 'wrap', padding: '10px 14px', borderBottom: '1px solid #f1f5f9' },
  place: { color: '#64748b', fontSize: '0.85rem' },
};
