import { useCallback, useEffect, useRef, useState } from 'react';
import AdminLogin from './components/AdminLogin.jsx';
import LeadForm from './components/LeadForm.jsx';
import QuotePreview from './pages/QuotePreview.jsx';
import AssistantSettings from './pages/AssistantSettings.jsx';
import SitePackages from './pages/SitePackages.jsx';
import WebsitePhotos from './pages/WebsitePhotos.jsx';
import { clearAdminToken, verifyAdminSession } from './api';

const TABS = [
  { id: 'itinerary', label: 'Itinerary Builder'    },
  { id: 'packages',  label: 'Packages'             },
  { id: 'photos',    label: 'Website Photos'       },
  { id: 'assistant', label: 'AI Assistant'         },
];

export default function App() {
  const [authenticated, setAuthenticated] = useState(false);
  const [checking, setChecking]           = useState(true);
  const [activeTab, setActiveTab]         = useState('itinerary');
  const [quote, setQuote]                 = useState(null);

  useEffect(() => {
    verifyAdminSession()
      .then((ok) => setAuthenticated(ok))
      .finally(() => setChecking(false));
  }, []);

  const handleLogout = useCallback(() => {
    clearAdminToken();
    setAuthenticated(false);
    setQuote(null);
  }, []);

  if (checking) {
    return <div style={styles.loading}>Verifying admin session…</div>;
  }

  if (!authenticated) {
    return (
      <AdminLogin
        subtitle="Sign in to manage itineraries, packages, and website photos."
        onSuccess={() => setAuthenticated(true)}
      />
    );
  }

  return (
    <div style={styles.shell}>
      {/* ── Header ── */}
      <header style={styles.header}>
        <div style={styles.headerLeft}>
          <p style={styles.brand}>Serene Vibes Kashmir</p>
          <h1 style={styles.title}>Admin Dashboard</h1>
          <p style={styles.tagline}>A Poem In Motion</p>
        </div>
        <div style={styles.headerActions}>
          <a href="/" style={styles.link}>View Website</a>
          <button type="button" onClick={handleLogout} style={styles.logout}>
            Sign Out
          </button>
        </div>
      </header>

      {/* ── Tab Bar ── */}
      <nav style={styles.tabBar} aria-label="Admin sections">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            style={{
              ...styles.tab,
              ...(activeTab === tab.id ? styles.tabActive : {}),
            }}
            onClick={() => setActiveTab(tab.id)}
            aria-current={activeTab === tab.id ? 'page' : undefined}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {/* ── Panels ── */}
      {activeTab === 'itinerary' && (
        <section style={styles.panel}>
          <div style={styles.sectionIntro}>
            <h2 style={styles.sectionTitle}>Create Client Itinerary</h2>
            <p style={styles.sectionText}>
              Enter trip details below to generate a day-wise plan, assign hotels,
              calculate costs, and export a PDF quotation.
            </p>
          </div>
          <LeadForm onGenerated={setQuote} />
          {quote && <QuotePreview quote={quote} />}
        </section>
      )}

      {activeTab === 'packages' && (
        <SitePackages
          authenticated={authenticated}
          onUnauthorized={handleLogout}
        />
      )}

      {activeTab === 'photos' && (
        <WebsitePhotos
          authenticated={authenticated}
          onUnauthorized={handleLogout}
        />
      )}

      {activeTab === 'assistant' && (
        <AssistantSettings
          authenticated={authenticated}
          onUnauthorized={handleLogout}
        />
      )}
    </div>
  );
}

const styles = {
  loading: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: 'Inter, system-ui, sans-serif',
    color: '#5a6578',
  },
  shell: {
    minHeight: '100vh',
    background: '#f7f8fa',
    fontFamily: 'Inter, system-ui, sans-serif',
    overflowX: 'hidden',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: '16px',
    padding: 'clamp(16px,4vw,24px) clamp(16px,5vw,32px)',
    background: '#1e3a4f',
    color: '#fff',
    flexWrap: 'wrap',
  },
  headerLeft: { minWidth: 0, flex: '1 1 200px' },
  brand: {
    margin: 0,
    fontSize: '0.72rem',
    letterSpacing: '0.12em',
    textTransform: 'uppercase',
    color: '#b8956b',
    fontWeight: 700,
  },
  title: {
    margin: '4px 0',
    fontSize: 'clamp(1.25rem,5vw,1.75rem)',
    fontFamily: 'Georgia, serif',
    fontWeight: 600,
  },
  tagline: { margin: 0, fontSize: '0.875rem', opacity: 0.8 },
  headerActions: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    flexShrink: 0,
    marginTop: '4px',
  },
  link: {
    color: '#fff',
    textDecoration: 'none',
    fontSize: '0.875rem',
    opacity: 0.9,
    whiteSpace: 'nowrap',
  },
  logout: {
    padding: '8px 14px',
    borderRadius: '6px',
    border: '1px solid rgba(255,255,255,0.25)',
    background: 'transparent',
    color: '#fff',
    cursor: 'pointer',
    fontSize: '0.875rem',
    whiteSpace: 'nowrap',
    minHeight: '44px',
  },
  /* Tab bar */
  tabBar: {
    display: 'flex',
    gap: 0,
    background: '#152a3a',
    borderBottom: '1px solid #0e1f2d',
    padding: '0 clamp(16px,5vw,32px)',
    overflowX: 'auto',
  },
  tab: {
    padding: '12px 20px',
    background: 'transparent',
    border: 'none',
    borderBottom: '3px solid transparent',
    color: 'rgba(255,255,255,0.65)',
    cursor: 'pointer',
    fontSize: '0.9rem',
    fontWeight: 500,
    whiteSpace: 'nowrap',
    transition: 'color 0.15s, border-color 0.15s',
    fontFamily: 'Inter, system-ui, sans-serif',
    minHeight: '44px',
  },
  tabActive: {
    color: '#fff',
    borderBottomColor: '#b8956b',
  },
  /* Itinerary panel */
  panel: {
    padding: 'clamp(16px,4vw,32px)',
    maxWidth: '1200px',
    margin: '0 auto',
    boxSizing: 'border-box',
  },
  sectionIntro: { marginBottom: '20px' },
  sectionTitle: {
    margin: '0 0 8px',
    fontSize: 'clamp(1.1rem,3vw,1.35rem)',
    color: '#1e3a4f',
    fontFamily: 'Georgia, serif',
  },
  sectionText: {
    margin: 0,
    color: '#5a6578',
    maxWidth: '720px',
    lineHeight: 1.6,
    fontSize: 'clamp(0.85rem,2vw,1rem)',
  },
};
