import { useEffect, useState } from "react";

// Bright saffron scroll button: visible on light and dark backgrounds.
// Usage: <ScrollDownButton /> once, inside App.jsx (or any page).
export default function ScrollDownButton() {
  const [atBottom, setAtBottom] = useState(false);

  useEffect(() => {
    const check = () =>
      setAtBottom(window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 80);
    check();
    window.addEventListener("scroll", check, { passive: true });
    window.addEventListener("resize", check);
    return () => {
      window.removeEventListener("scroll", check);
      window.removeEventListener("resize", check);
    };
  }, []);

  const go = () =>
    atBottom
      ? window.scrollTo({ top: 0, behavior: "smooth" })
      : window.scrollBy({ top: window.innerHeight * 0.8, behavior: "smooth" });

  return (
    <button
      type="button"
      onClick={go}
      aria-label={atBottom ? "Scroll to top" : "Scroll down"}
      style={{
        position: "fixed",
        right: "max(16px, env(safe-area-inset-right))",
        bottom: "max(20px, env(safe-area-inset-bottom))",
        zIndex: 9999,
        width: 56,
        height: 56,
        borderRadius: "50%",
        border: "3px solid #fff",
        background: "#f5b82e",   // change to #e11d48 (red) or #fff for the other options
        color: "#10272e",
        boxShadow: "0 6px 16px rgba(0,0,0,.35), 0 0 0 2px #10272e",
        display: "grid",
        placeItems: "center",
        cursor: "pointer",
      }}
    >
      <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor"
           strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round"
           style={{ transform: atBottom ? "rotate(180deg)" : "none", transition: "transform .2s" }}>
        <path d="M12 5v14M5 12l7 7 7-7" />
      </svg>
    </button>
  );
}
