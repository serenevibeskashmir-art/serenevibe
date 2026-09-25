import React, { useCallback, useEffect, useRef, useState } from 'react';
import { apiFetch } from '../api';

const ENDPOINT = '/api/admin/assistant';

const NOTES_PLACEHOLDER = `Examples (replace with your real rates):
Budget tier: Rs 14,000 - 16,000 per person for 5N/6D, 3-star hotels, shared Innova.
Standard tier: Rs 22,000 - 26,000 per person for 5N/6D, 3/4-star hotels, private cab.
Child (5-11 years) is charged 70% of the adult rate. Infants under 5 are free.
Peak season (May 15 - Jun 30) adds Rs 3,000 per person.
Gulmarg gondola Phase 2 tickets are extra (paid on the spot).
We do not arrange flights or trains to Srinagar.`;

function statusOf(info) {
  if (!info.configured) {
    return { tone: 'bad', title: 'Not connected', text: 'The AI key is missing, so the assistant is hidden on your website. Add GROQ_API_KEY in your Vercel environment variables, then redeploy (see DEPLOY_VERCEL.md).' };
  }
  if (!info.enabled) {
    return { tone: 'off', title: 'Switched off', text: 'The assistant is connected but hidden from visitors. Turn it on below.' };
  }
  return { tone: 'good', title: 'Live on your website', text: 'Visitors see the "Ask our Kashmir Travel Assistant" button in the bottom-left corner.' };
}

export default function AssistantSettings({ authenticated, onUnauthorized }) {
  const [info, setInfo] = useState(null);
  const [enabled, setEnabled] = useState(true);
  const [notes, setNotes] = useState('');
  const [loadError, setLoadError] = useState('');
  const [saving, setSaving] = useState(false);
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
    apiFetch(ENDPOINT)
      .then((res) => {
        if (res.status === 401) { onUnauthorized(); return null; }
        if (!res.ok) throw new Error('Could not load the assistant settings.');
        return res.json();
      })
      .then((data) => {
        if (!data) return;
        setInfo(data);
        setEnabled(data.enabled);
        setNotes(data.notes || '');
      })
      .catch((err) => setLoadError(err.message));
  }, [authenticated, onUnauthorized]);

  const limit = info ? info.notes_limit : 4000;
  const dirty = info && (enabled !== info.enabled || notes.trim() !== (info.notes || '').trim());

  const save = async () => {
    setSaving(true);
    try {
      const res = await apiFetch(ENDPOINT, { method: 'PUT', body: JSON.stringify({ enabled, notes }) });
      if (res.status === 401) { onUnauthorized(); return; }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || 'Could not save. Please try again.');
      setInfo(data);
      setEnabled(data.enabled);
      setNotes(data.notes || '');
      notify('Saved. The assistant uses these notes from its next message.');
    } catch (err) {
      notify(err.message, 'err');
    } finally {
      setSaving(false);
    }
  };

  const status = info ? statusOf({ ...info, enabled: info.enabled }) : null;

  return (
    <div className="wp-shell">
      <main className="wp-main">
        <div className="wp-intro">
          <div>
            <h2>AI Travel Assistant</h2>
            <p>
              Visitors describe their trip (budget, people, days) and get a suggested route with an estimate, then send the plan to your WhatsApp.
              It already knows your destinations, the seasons, and every package and price on the Packages tab. Use the notes below to teach it your real rates.
            </p>
          </div>
        </div>

        {loadError && <p className="wp-msg err">{loadError}</p>}
        {!info && !loadError && <div className="wp-loading">Loading…</div>}

        {info && (
          <div className="wp-as-layout">
            <section className={`wp-as-card wp-as-status wp-as-${status.tone}`}>
              <h3><span className="wp-as-dot" aria-hidden="true" /> {status.title}</h3>
              <p>{status.text}</p>
              <dl className="wp-as-stats">
                <div><dt>Messages in the last 24 hours</dt><dd>{info.messages_24h} <span>of {info.site_daily_cap} daily cap</span></dd></div>
                <div><dt>AI model</dt><dd>{info.model}</dd></div>
              </dl>
              <label className="wp-as-toggle">
                <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
                <span>Show the assistant on the website</span>
              </label>
            </section>

            <section className="wp-as-card">
              <h3>Your rates and policies</h3>
              <p className="wp-hint">
                The assistant only quotes prices from your Packages and from these notes. If it has no rate for something, it says the team will confirm.
                Add your budget tiers, child pricing, peak-season charges and anything it should never promise.
              </p>
              <textarea
                className="wp-alt sp-textarea wp-as-notes"
                rows={12}
                maxLength={limit}
                value={notes}
                placeholder={NOTES_PLACEHOLDER}
                onChange={(e) => setNotes(e.target.value)}
                aria-label="Rates and policy notes for the assistant"
              />
              <div className="wp-as-foot">
                <span className={`wp-size${notes.length > limit * 0.95 ? ' wp-as-warn' : ''}`}>{notes.length} / {limit} characters</span>
                <button type="button" className="wp-btn wp-btn-primary wp-as-save" onClick={save} disabled={saving || !dirty}>
                  {saving ? 'Saving…' : 'Save changes'}
                </button>
              </div>
            </section>
          </div>
        )}
      </main>

      {toast && <div className={`wp-toast${toast.type === 'err' ? ' err' : ''}`} role="status">{toast.text}</div>}
    </div>
  );
}
