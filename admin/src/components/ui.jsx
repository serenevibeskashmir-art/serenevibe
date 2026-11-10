import { useEffect } from "react";

/* Small shared pieces for the mobile admin: icons, bottom sheet, +/- stepper. */

const PATHS = {
  back: "M15 18l-6-6 6-6",
  chev: "M9 6l6 6-6 6",
  undo: "M9 14L4 9l5-5M4 9h10a6 6 0 010 12h-3",
  redo: "M15 14l5-5-5-5M20 9H10a6 6 0 000 12h3",
  more: "M12 5.5h.01M12 12h.01M12 18.5h.01",
  plus: "M12 5v14M5 12h14",
  x: "M6 6l12 12M18 6L6 18",
  check: "M5 12l5 5 9-10",
  spark: "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z",
  trash: "M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3",
  up: "M6 15l6-6 6 6",
  down: "M6 9l6 6 6-6",
  copy: "M9 9h11v11H9zM5 15V6a2 2 0 012-2h9",
  route: "M6 19a2 2 0 100-4 2 2 0 000 4zM18 9a2 2 0 100-4 2 2 0 000 4zM8 17h8a3 3 0 000-6H8a3 3 0 010-6h8",
  chat: "M21 12a8 8 0 01-11.6 7.1L4 20l1-4.6A8 8 0 1121 12z",
  box: "M3 8l9-5 9 5v8l-9 5-9-5zM3 8l9 5 9-5M12 13v8",
  image: "M3 6a2 2 0 012-2h14a2 2 0 012 2v12a2 2 0 01-2 2H5a2 2 0 01-2-2zM9 10a1.5 1.5 0 100-3 1.5 1.5 0 000 3zM21 16l-5-5-8 9",
  bot: "M6 8h12a2 2 0 012 2v8a2 2 0 01-2 2H6a2 2 0 01-2-2v-8a2 2 0 012-2zM12 8V4M9 14h.01M15 14h.01",
  pdf: "M14 3H7a2 2 0 00-2 2v14a2 2 0 002 2h10a2 2 0 002-2V8zM14 3v5h5M9 14h6M9 17h4",
  logout: "M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9",
  wallet: "M3 7a2 2 0 012-2h12v4M3 7v11a2 2 0 002 2h15V9H5a2 2 0 01-2-2zM16.5 14.5h.01",
  pin: "M12 21s7-6.2 7-11a7 7 0 10-14 0c0 4.8 7 11 7 11zM12 12a2 2 0 100-4 2 2 0 000 4z",
};

export function Icon({ name, size = 20 }) {
  return (
    <svg className="sv-ic" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={PATHS[name] || ""} />
    </svg>
  );
}

/** Bottom sheet on phones, centred dialog on desktop. */
export function Sheet({ title, onClose, children }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { window.removeEventListener("keydown", onKey); document.body.style.overflow = prev; };
  }, [onClose]);
  return (
    <div className="sv-sheet-wrap" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="sv-sheet" role="dialog" aria-modal="true" aria-label={title}>
        <div className="sv-grab" />
        <div className="sv-sheet-h">
          <h3>{title}</h3>
          <button type="button" className="sv-ib sv-ib-soft" onClick={onClose} aria-label="Close"><Icon name="x" /></button>
        </div>
        <div className="sv-sheet-b">{children}</div>
      </div>
    </div>
  );
}

/** Big − / + counter. */
export function Stepper({ label, value, min = 0, max = 99, onChange }) {
  return (
    <div className="sv-stp">
      <span>{label}</span>
      <div className="sv-stp-c">
        <button type="button" aria-label={`Fewer ${label}`} disabled={value <= min} onClick={() => onChange(value - 1)}>−</button>
        <b>{value}</b>
        <button type="button" aria-label={`More ${label}`} disabled={value >= max} onClick={() => onChange(value + 1)}>+</button>
      </div>
    </div>
  );
}

/** Row that opens a sheet: label, value, chevron. */
export function PickRow({ label, value, hint, warn, onClick, disabled }) {
  return (
    <button type="button" className={"sv-row" + (warn ? " warn" : "")} onClick={onClick} disabled={disabled}>
      <span className="k">{label}</span>
      <span className="v">{value}{hint ? <small>{hint}</small> : null}</span>
      <Icon name="chev" size={18} />
    </button>
  );
}
