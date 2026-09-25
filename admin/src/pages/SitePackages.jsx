import React, { useCallback, useEffect, useRef, useState } from 'react';
import { apiFetch, getAdminToken } from '../api';

const ENDPOINT = '/api/admin/site-packages';
const MAX_INPUT_BYTES = 30 * 1024 * 1024;
const MAX_PHOTO_DIM = 1400;

/* --- image prep (same approach as the Website Photos tab) --- */
async function decodeImage(file) {
  if (window.createImageBitmap) {
    try {
      return await createImageBitmap(file, { imageOrientation: 'from-image' });
    } catch {
      /* fall through to <img> */
    }
  }
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const img = new Image();
    img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error('This file could not be read as a photo.')); };
    img.src = url;
  });
}

async function prepareImage(file, maxDim, maxBytes) {
  if (!file.type.startsWith('image/')) throw new Error('Please choose an image file (JPG, PNG or WEBP).');
  if (file.size > MAX_INPUT_BYTES) throw new Error('That file is over 30 MB. Please choose a smaller photo.');

  const source = await decodeImage(file);
  const w = source.width || source.naturalWidth;
  const h = source.height || source.naturalHeight;
  const scale = Math.min(1, maxDim / Math.max(w, h));
  const canvas = document.createElement('canvas');
  canvas.width = Math.round(w * scale);
  canvas.height = Math.round(h * scale);
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(source, 0, 0, canvas.width, canvas.height);
  if (source.close) source.close();

  const toBlob = (q) => new Promise((res) => canvas.toBlob(res, 'image/jpeg', q));
  let blob = null;
  for (const quality of [0.85, 0.75, 0.65, 0.55]) {
    blob = await toBlob(quality);
    if (blob && blob.size <= maxBytes) return blob;
  }
  if (!blob || blob.size > maxBytes) throw new Error('Photo is still too large after shrinking. Try a smaller image.');
  return blob;
}

function emptyDraft(pkg) {
  return {
    badge: pkg.badge || '',
    duration: pkg.duration || '',
    name: pkg.name || '',
    description: pkg.description || '',
    features: (pkg.features || []).join('\n'),
    price_label: pkg.price_label || '',
    price_note: pkg.price_note || '/ person',
    featured: !!pkg.featured,
    placeholder: pkg.placeholder || 'lake',
  };
}

function draftsEqual(a, b) {
  return a.badge === b.badge && a.duration === b.duration && a.name === b.name &&
    a.description === b.description && a.features === b.features &&
    a.price_label === b.price_label && a.price_note === b.price_note &&
    a.featured === b.featured && a.placeholder === b.placeholder;
}

function PackageCard({ pkg, index, total, maxBytes, onChange, onMove, onDelete, onUnauthorized, notify }) {
  const [draft, setDraft] = useState(() => emptyDraft(pkg));
  const [saved, setSaved] = useState(() => emptyDraft(pkg));
  const [busy, setBusy] = useState('');
  const [msg, setMsg] = useState(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => {
    setDraft(emptyDraft(pkg));
    setSaved(emptyDraft(pkg));
  }, [pkg.id, pkg.updated_at]);

  const dirty = !draftsEqual(draft, saved);

  const handleFailure = (res, fallback) => {
    if (res && res.status === 401) { onUnauthorized(); return; }
    return res ? res.json().then((j) => j.error || fallback).catch(() => fallback) : Promise.resolve(fallback);
  };

  const save = async () => {
    setMsg(null);
    setBusy('Saving…');
    try {
      const body = {
        ...draft,
        features: draft.features.split('\n').map((f) => f.trim()).filter(Boolean),
      };
      const res = await apiFetch(`${ENDPOINT}/${pkg.id}`, { method: 'PUT', body: JSON.stringify(body) });
      if (!res.ok) {
        const text = await handleFailure(res, 'Could not save the package.');
        if (text) throw new Error(text);
        return;
      }
      const updated = await res.json();
      onChange(updated);
      setSaved(emptyDraft(updated));
      notify(`${updated.name || 'Package'} saved. It is now live on the website.`);
    } catch (err) {
      setMsg({ type: 'err', text: err.message });
    } finally {
      setBusy('');
    }
  };

  const upload = async (file) => {
    if (!file) return;
    setMsg(null);
    setBusy('Preparing photo…');
    try {
      const blob = await prepareImage(file, MAX_PHOTO_DIM, maxBytes - 64 * 1024);
      setBusy('Uploading…');
      const res = await fetch(`${ENDPOINT}/${pkg.id}/photo?alt=${encodeURIComponent(draft.name.trim())}`, {
        method: 'PUT',
        headers: { Authorization: `Bearer ${getAdminToken()}`, 'Content-Type': 'image/jpeg' },
        body: blob,
      });
      if (!res.ok) {
        const text = await handleFailure(res, 'Upload failed. Please try again.');
        if (text) throw new Error(text);
        return;
      }
      onChange(await res.json());
      notify('Photo saved. It is now live on the website.');
    } catch (err) {
      setMsg({ type: 'err', text: err.message || 'Upload failed.' });
    } finally {
      setBusy('');
    }
  };

  const removePhoto = async () => {
    if (!window.confirm('Remove this package\u2019s photo from the website?')) return;
    setBusy('Removing photo…');
    setMsg(null);
    try {
      const res = await apiFetch(`${ENDPOINT}/${pkg.id}/photo`, { method: 'DELETE' });
      if (!res.ok) {
        const text = await handleFailure(res, 'Could not remove the photo.');
        if (text) throw new Error(text);
        return;
      }
      onChange(await res.json());
      notify('Photo removed.');
    } catch (err) {
      setMsg({ type: 'err', text: err.message });
    } finally {
      setBusy('');
    }
  };

  const remove = async () => {
    if (!window.confirm(`Delete "${pkg.name || 'this package'}" from the website? This cannot be undone.`)) return;
    setBusy('Deleting…');
    try {
      const res = await apiFetch(`${ENDPOINT}/${pkg.id}`, { method: 'DELETE' });
      if (!res.ok) {
        const text = await handleFailure(res, 'Could not delete the package.');
        if (text) throw new Error(text);
        return;
      }
      onDelete(pkg.id);
    } catch (err) {
      setMsg({ type: 'err', text: err.message });
      setBusy('');
    }
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    upload(e.dataTransfer.files && e.dataTransfer.files[0]);
  };

  const set = (field) => (e) => setDraft((d) => ({ ...d, [field]: e.target.value }));

  return (
    <div className="wp-card sp-card">
      <div
        className={`wp-preview sp-preview${dragging ? ' is-drag' : ''}`}
        style={{ aspectRatio: '16 / 10' }}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        {pkg.photo && pkg.photo.url ? (
          <>
            <img src={pkg.photo.url} alt={pkg.photo.alt || pkg.name} />
            <span className="wp-badge">Live</span>
          </>
        ) : (
          <div className="wp-empty">
            <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <rect x="3" y="4" width="18" height="16" rx="2" /><circle cx="9" cy="10" r="1.6" /><path d="M21 16l-5-5-8 8" />
            </svg>
            No photo yet.<br />Drop one here or use Upload.
          </div>
        )}
        {busy && <div className="wp-busy">{busy}</div>}
      </div>

      <div className="wp-body sp-body">
        <div className="sp-row sp-row-top">
          <span className="sp-index">Card {index + 1} of {total}</span>
          <div className="sp-move">
            <button type="button" className="wp-btn wp-btn-soft" disabled={index === 0 || !!busy} onClick={() => onMove(index, -1)} title="Move left">←</button>
            <button type="button" className="wp-btn wp-btn-soft" disabled={index === total - 1 || !!busy} onClick={() => onMove(index, 1)} title="Move right">→</button>
          </div>
        </div>

        <div className="sp-buttons">
          <button type="button" className="wp-btn wp-btn-primary" disabled={!!busy} onClick={() => inputRef.current && inputRef.current.click()}>
            {pkg.photo ? 'Replace photo' : 'Upload photo'}
          </button>
          {pkg.photo && (
            <button type="button" className="wp-btn wp-btn-ghost" disabled={!!busy} onClick={removePhoto}>Remove photo</button>
          )}
        </div>
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          style={{ display: 'none' }}
          onChange={(e) => { upload(e.target.files && e.target.files[0]); e.target.value = ''; }}
        />

        <label className="sp-field">
          <span>Name</span>
          <input className="wp-alt" type="text" value={draft.name} onChange={set('name')} maxLength={150} />
        </label>

        <div className="sp-fieldrow">
          <label className="sp-field">
            <span>Duration</span>
            <input className="wp-alt" type="text" value={draft.duration} onChange={set('duration')} placeholder="5 Nights / 6 Days" maxLength={60} />
          </label>
          <label className="sp-field">
            <span>Badge</span>
            <input className="wp-alt" type="text" value={draft.badge} onChange={set('badge')} placeholder="Essential" maxLength={60} />
          </label>
        </div>

        <label className="sp-field">
          <span>Description</span>
          <textarea className="wp-alt sp-textarea" rows={2} value={draft.description} onChange={set('description')} />
        </label>

        <label className="sp-field">
          <span>Features (one per line, shown with a checkmark)</span>
          <textarea className="wp-alt sp-textarea" rows={4} value={draft.features} onChange={set('features')} />
        </label>

        <div className="sp-fieldrow">
          <label className="sp-field">
            <span>Price (numbers only, e.g. 24,999)</span>
            <input className="wp-alt" type="text" value={draft.price_label} onChange={set('price_label')} placeholder="24,999" maxLength={40} />
          </label>
          <label className="sp-field">
            <span>Price note</span>
            <input className="wp-alt" type="text" value={draft.price_note} onChange={set('price_note')} placeholder="/ person" maxLength={40} />
          </label>
        </div>

        <div className="sp-fieldrow">
          <label className="sp-field">
            <span>Placeholder colour (shown before a photo loads)</span>
            <select className="wp-alt" value={draft.placeholder} onChange={set('placeholder')}>
              <option value="lake">Lake (teal)</option>
              <option value="pine">Pine (green)</option>
              <option value="slate">Slate (blue-grey)</option>
            </select>
          </label>
          <label className="sp-field sp-checkbox">
            <input type="checkbox" checked={draft.featured} onChange={(e) => setDraft((d) => ({ ...d, featured: e.target.checked }))} />
            <span>Highlight as "Recommended" (featured card)</span>
          </label>
        </div>

        <p className={`wp-msg ${msg ? msg.type : ''}`} role="status">{msg ? msg.text : ''}</p>

        <div className="sp-footer">
          <button type="button" className="wp-btn wp-btn-primary" disabled={!dirty || !!busy} onClick={save}>
            {dirty ? 'Save changes' : 'Saved'}
          </button>
          <button type="button" className="wp-btn wp-btn-ghost" disabled={!!busy} onClick={remove}>Delete card</button>
        </div>
      </div>
    </div>
  );
}

/**
 * SitePackages — admin panel for the "Structured Itineraries" section of the
 * homepage: card text (name, duration, badge, description, features, price)
 * plus each card's photo.
 */
export default function SitePackages({ authenticated, onUnauthorized }) {
  const [packages, setPackages] = useState(null);
  const [maxBytes, setMaxBytes] = useState(4 * 1024 * 1024);
  const [loadError, setLoadError] = useState('');
  const [creating, setCreating] = useState(false);
  const [toast, setToast] = useState(null);
  const toastTimer = useRef(null);

  const notify = useCallback((text, type = 'ok') => {
    setToast({ text, type });
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 3500);
  }, []);

  const load = useCallback(() => {
    setLoadError('');
    return apiFetch('/api/admin/site-packages')
      .then((res) => {
        if (res.status === 401) { onUnauthorized(); return null; }
        if (!res.ok) throw new Error('Could not load the packages.');
        return res.json();
      })
      .then((data) => {
        if (!data) return;
        setPackages(data.packages);
        if (data.max_upload_bytes) setMaxBytes(data.max_upload_bytes);
      })
      .catch((err) => setLoadError(err.message));
  }, [onUnauthorized]);

  useEffect(() => {
    if (!authenticated) return;
    setPackages(null);
    load();
  }, [authenticated, load]);

  const replace = (updated) => setPackages((prev) => prev.map((p) => (p.id === updated.id ? updated : p)));

  const remove = (id) => {
    setPackages((prev) => prev.filter((p) => p.id !== id));
    notify('Package deleted.');
  };

  const addPackage = async () => {
    setCreating(true);
    try {
      const res = await apiFetch(ENDPOINT, {
        method: 'POST',
        body: JSON.stringify({ name: 'New Package', duration: '', badge: 'New', description: '', features: [], price_label: '', price_note: '/ person' }),
      });
      if (res.status === 401) { onUnauthorized(); return; }
      if (!res.ok) throw new Error('Could not create a new package.');
      const created = await res.json();
      setPackages((prev) => [...(prev || []), created]);
      notify('New card added — fill it in below and upload a photo.');
    } catch (err) {
      notify(err.message, 'err');
    } finally {
      setCreating(false);
    }
  };

  const move = async (index, dir) => {
    setPackages((prev) => {
      const next = [...prev];
      const target = index + dir;
      if (target < 0 || target >= next.length) return prev;
      [next[index], next[target]] = [next[target], next[index]];
      apiFetch(`${ENDPOINT}/reorder`, {
        method: 'PUT',
        body: JSON.stringify({ order: next.map((p) => p.id) }),
      }).then((res) => (res.status === 401 ? onUnauthorized() : null)).catch(() => {});
      return next;
    });
  };

  return (
    <div className="wp-shell">
      <main className="wp-main">
        <div className="wp-intro">
          <div>
            <h2>Structured Itineraries</h2>
            <p>
              This is the "Structured Itineraries" section on the homepage. Edit each card's text, price and photo below —
              changes go live as soon as you save. Use the arrows to reorder cards, or add a brand-new one.
            </p>
          </div>
          <button type="button" className="wp-btn wp-btn-primary sp-add" disabled={creating || !packages} onClick={addPackage}>
            + Add package
          </button>
        </div>

        {loadError && <p className="wp-msg err">{loadError}</p>}
        {!packages && !loadError && <div className="wp-loading">Loading packages…</div>}

        {packages && packages.length === 0 && (
          <p className="wp-msg">No packages yet. Click "Add package" to create the first card.</p>
        )}

        <div className="wp-grid sp-grid">
          {(packages || []).map((pkg, index) => (
            <PackageCard
              key={pkg.id}
              pkg={pkg}
              index={index}
              total={packages.length}
              maxBytes={maxBytes}
              onChange={replace}
              onMove={move}
              onDelete={remove}
              onUnauthorized={onUnauthorized}
              notify={notify}
            />
          ))}
        </div>
      </main>

      {toast && <div className={`wp-toast${toast.type === 'err' ? ' err' : ''}`} role="status">{toast.text}</div>}
    </div>
  );
}
