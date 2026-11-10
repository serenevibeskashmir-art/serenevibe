import React, { useState } from 'react';
import Payments from './Payments.jsx';
import Ledger from './Ledger.jsx';

/* One tab for money: what clients have paid you (Payments) and what you spend / earn (Expenses & profit).
   Both live in the same Google Sheet. Each view stays mounted once opened, so switching is instant. */

const VIEWS = [
  { id: 'payments', label: 'Client payments' },
  { id: 'ledger',   label: 'Expenses & profit' },
];

export default function Accounts({ onUnauthorized }) {
  const [view, setView]       = useState('payments');
  const [opened, setOpened]   = useState({ payments: true, ledger: false });

  const pick = (id) => { setView(id); setOpened((o) => ({ ...o, [id]: true })); };

  return (
    <div>
      <div style={S.bar}>
        <div style={S.seg} role="tablist" aria-label="Accounts">
          {VIEWS.map((v) => (
            <button key={v.id} type="button" role="tab" aria-selected={view === v.id}
              style={{ ...S.btn, ...(view === v.id ? S.on : {}) }} onClick={() => pick(v.id)}>{v.label}</button>
          ))}
        </div>
      </div>
      <div hidden={view !== 'payments'}>{opened.payments && <Payments onUnauthorized={onUnauthorized} />}</div>
      <div hidden={view !== 'ledger'}>{opened.ledger && <Ledger onUnauthorized={onUnauthorized} />}</div>
    </div>
  );
}

const S = {
  bar: { padding: 'clamp(16px,4vw,32px) clamp(16px,4vw,32px) 0', boxSizing: 'border-box' },
  seg: { maxWidth: 640, margin: '0 auto', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, background: '#eef2f6', padding: 4, borderRadius: 12 },
  btn: { font: 'inherit', fontWeight: 700, fontSize: 14, border: 0, borderRadius: 9, padding: '10px 6px', minHeight: 46, cursor: 'pointer', background: 'transparent', color: '#1e3a4f' },
  on: { background: '#152a3a', color: '#fff' },
};
