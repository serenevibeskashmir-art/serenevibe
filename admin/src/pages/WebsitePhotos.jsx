import React, { useCallback, useEffect, useRef, useState } from 'react';
import { apiFetch, getAdminToken } from '../api';

const ENDPOINT = '/api/admin/site-photos';
const MAX_INPUT_BYTES = 30 * 1024 * 1024; // what we accept from the device, before shrinking

/* Load the picked file, honouring camera rotation (EXIF) where the browser supports it. */
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

/* Shrink to the slot's maximum size and re-encode as JPEG so uploads are fast and the site loads quickly. */
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
  ctx.fillStyle = '#ffffff'; // PNGs with transparency
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

function formatBytes(n) {
  if (!n) return '';
  return n > 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${Math.round(n / 1024)} KB`;
}

function PhotoCard({ slot, maxBytes, onChange, onUnauthorized, notify }) {
  const [busy, setBusy] = useState('');
  const [alt, setAlt] = useState(slot.alt || '');
  const [link, setLink] = useState(slot.link || '');
  const [msg, setMsg] = useState(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => { setAlt(slot.alt || ''); }, [slot.alt, slot.updated_at]);
  useEffect(() => { setLink(slot.link || ''); }, [slot.link]);

  const handleFailure = (res, fallback) => {
    if (res && res.status === 401) { onUnauthorized(); return; }
    return res ? res.json().then((j) => j.error || fallback).catch(() => fallback) : Promise.resolve(fallback);
  };

  const upload = async (file) => {
    if (!file) return;
    setMsg(null);
    setBusy('Preparing…');
    try {
      const blob = await prepareImage(file, slot.max_dim, maxBytes - 64 * 1024);
      setBusy('Uploading…');
      const res = await fetch(`${ENDPOINT}/${slot.slot}?alt=${encodeURIComponent(alt.trim())}`, {
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
      notify(`${slot.label} saved. It is now live on the website.`);
    } catch (err) {
      setMsg({ type: 'err', text: err.message || 'Upload failed.' });
    } finally {
      setBusy('');
    }
  };

  const remove = async () => {
    if (!window.confirm(`Remove the ${slot.label} photo from the website?`)) return;
    setBusy('Removing…');
    setMsg(null);
    try {
      const res = await apiFetch(`${ENDPOINT}/${slot.slot}`, { method: 'DELETE' });
      if (!res.ok) {
        const text = await handleFailure(res, 'Could not remove the photo.');
        if (text) throw new Error(text);
        return;
      }
      onChange(await res.json());
      notify(`${slot.label} removed.`);
    } catch (err) {
      setMsg({ type: 'err', text: err.message });
    } finally {
      setBusy('');
    }
  };

  const saveAlt = async () => {
    if (!slot.has_photo || alt.trim() === (slot.alt || '')) return;
    setMsg(null);
    try {
      const res = await apiFetch(`${ENDPOINT}/${slot.slot}`, { method: 'PATCH', body: JSON.stringify({ alt }) });
      if (!res.ok) {
        const text = await handleFailure(res, 'Could not save the description.');
        if (text) throw new Error(text);
        return;
      }
      onChange(await res.json());
      setMsg({ type: 'ok', text: 'Description saved.' });
    } catch (err) {
      setMsg({ type: 'err', text: err.message });
    }
  };

  const saveLink = async () => {
    if (!slot.has_link || link.trim() === (slot.link || '')) return;
    setMsg(null);
    try {
      const res = await apiFetch(`${ENDPOINT}/${slot.slot}`, { method: 'PATCH', body: JSON.stringify({ link }) });
      if (!res.ok) {
        const text = await handleFailure(res, 'Could not save the link.');
        if (text) throw new Error(text);
        return;
      }
      const updated = await res.json();
      onChange(updated);
      setLink(updated.link || '');
      notify(updated.link ? `${slot.label}: link saved. It is now live on the website.` : `${slot.label}: link removed.`);
    } catch (err) {
      setMsg({ type: 'err', text: err.message });
    }
  };

  const onDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    upload(e.dataTransfer.files && e.dataTransfer.files[0]);
  };

  return (
    <div
      className={`wp-card${dragging ? ' is-drag' : ''}`}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
    >
      <div className="wp-preview" style={{ aspectRatio: slot.ratio }}>
        {slot.has_photo ? (
          <>
            <img src={slot.url} alt={slot.alt || slot.label} />
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

      <div className="wp-body">
        <div>
          <p className="wp-label">{slot.label}</p>
          <p className="wp-hint">{slot.hint}</p>
        </div>
        <p className="wp-size">
          Best size {slot.size}
          {slot.has_photo && slot.size_bytes ? ` · saved ${formatBytes(slot.size_bytes)}` : ''}
        </p>

        <div>
          <label className="wp-alt-label" htmlFor={`alt-${slot.slot}`}>Description (for screen readers and search)</label>
          <input
            id={`alt-${slot.slot}`}
            className="wp-alt"
            type="text"
            maxLength={200}
            value={alt}
            placeholder="e.g. Shikara on Dal Lake at sunset"
            onChange={(e) => setAlt(e.target.value)}
            onBlur={saveAlt}
            onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur(); }}
          />
        </div>

        {slot.has_link && (
          <div>
            <label className="wp-alt-label" htmlFor={`link-${slot.slot}`}>{slot.link_label || 'Link'}</label>
            <input
              id={`link-${slot.slot}`}
              className="wp-alt"
              type="url"
              inputMode="url"
              maxLength={500}
              value={link}
              placeholder={slot.link_placeholder || 'https://…'}
              onChange={(e) => setLink(e.target.value)}
              onBlur={saveLink}
              onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur(); }}
            />
            <p className="wp-link-note">
              {slot.link
                ? <>Saved. <a href={slot.link} target="_blank" rel="noopener noreferrer">Open link ↗</a> · Clear the box to go back to the default video.</>
                : 'Not set yet, so the website shows its default video. The link saves when you click outside the box or press Enter.'}
            </p>
          </div>
        )}

        <p className={`wp-msg ${msg ? msg.type : ''}`} role="status">{msg ? msg.text : ''}</p>

        <div className="wp-buttons">
          <button type="button" className="wp-btn wp-btn-primary" disabled={!!busy} onClick={() => inputRef.current && inputRef.current.click()}>
            {slot.has_photo ? 'Replace photo' : 'Upload photo'}
          </button>
          {slot.has_photo && (
            <button type="button" className="wp-btn wp-btn-ghost" disabled={!!busy} onClick={remove}>Remove</button>
          )}
        </div>
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          style={{ display: 'none' }}
          onChange={(e) => { upload(e.target.files && e.target.files[0]); e.target.value = ''; }}
        />
      </div>
    </div>
  );
}

/**
 * WebsitePhotos — photo management panel.
 *
 * Props
 *   authenticated  boolean  – already verified by the parent (App)
 *   onUnauthorized function – called when the API returns 401 so the
 *                             parent can log the user out globally
 */
export default function WebsitePhotos({ authenticated, onUnauthorized }) {
  const [slots, setSlots] = useState(null);
  const [maxBytes, setMaxBytes] = useState(4 * 1024 * 1024);
  const [loadError, setLoadError] = useState('');
  const [toast, setToast] = useState(null);
  const toastTimer = useRef(null);

  const notify = useCallback((text, type = 'ok') => {
    setToast({ text, type });
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 3500);
  }, []);

  useEffect(() => {
    if (!authenticated) return;
    setLoadError('');
    setSlots(null);
    apiFetch(ENDPOINT)
      .then((res) => {
        if (res.status === 401) { onUnauthorized(); return null; }
        if (!res.ok) throw new Error('Could not load the photo list.');
        return res.json();
      })
      .then((data) => {
        if (!data) return;
        setSlots(data.slots);
        if (data.max_upload_bytes) setMaxBytes(data.max_upload_bytes);
      })
      .catch((err) => setLoadError(err.message));
  }, [authenticated, onUnauthorized]);

  const replaceSlot = (updated) => setSlots((prev) => prev.map((s) => (s.slot === updated.slot ? updated : s)));

  const groups = [];
  (slots || []).forEach((s) => {
    let g = groups.find((x) => x.name === s.group);
    if (!g) { g = { name: s.group, items: [] }; groups.push(g); }
    g.items.push(s);
  });
  const total = slots ? slots.length : 0;
  const done = slots ? slots.filter((s) => s.has_photo).length : 0;

  return (
    <div className="wp-shell">
      <main className="wp-main">
        <div className="wp-intro">
          <div>
            <h2>Upload once, live everywhere</h2>
            <p>
              Choose a photo for any spot below. It is shrunk automatically, saved to your database, and appears on the website straight away.
              You can also drag a photo onto a card. Spots without a photo show a tasteful placeholder.
            </p>
          </div>
          <div className="wp-progress">
            <div className="wp-progress-label">{done} of {total} photos uploaded</div>
            <div className="wp-progress-bar"><span style={{ width: total ? `${(done / total) * 100}%` : 0 }} /></div>
          </div>
        </div>

        {loadError && <p className="wp-msg err">{loadError}</p>}
        {!slots && !loadError && <div className="wp-loading">Loading photos…</div>}

        {groups.map((g) => (
          <section className="wp-group" key={g.name}>
            <h3 className="wp-group-title">
              {g.name}
              <span className="wp-group-count">{g.items.filter((i) => i.has_photo).length} of {g.items.length}</span>
            </h3>
            <div className="wp-grid">
              {g.items.map((s) => (
                <PhotoCard key={s.slot} slot={s} maxBytes={maxBytes} onChange={replaceSlot} onUnauthorized={onUnauthorized} notify={notify} />
              ))}
            </div>
          </section>
        ))}
      </main>

      {toast && <div className={`wp-toast${toast.type === 'err' ? ' err' : ''}`} role="status">{toast.text}</div>}
    </div>
  );
}
