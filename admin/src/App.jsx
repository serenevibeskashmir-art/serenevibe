import { useCallback, useEffect, useState } from 'react';
import AdminLogin from './components/AdminLogin.jsx';
import LeadForm from './components/LeadForm.jsx';
import QuotePreview, { loadCustomHotels } from './pages/QuotePreview.jsx';
import AssistantSettings from './pages/AssistantSettings.jsx';
import SitePackages from './pages/SitePackages.jsx';
import WebsitePhotos from './pages/WebsitePhotos.jsx';
import WhatsAppLeads from './pages/WhatsAppLeads.jsx';
import ScrollDownButton from './components/ScrollDownButton.jsx';
import { Icon } from './components/ui.jsx';
import { clearAdminToken, verifyAdminSession } from './api';

// Bottom navigation on phones, tab row on desktop (see admin-mobile.css).
const TABS = [
  { id: 'itinerary', label: 'Itinerary', title: 'Itinerary Builder', icon: 'route' },
  { id: 'whatsapp',  label: 'Leads',     title: 'WhatsApp Leads',    icon: 'chat'  },
  { id: 'packages',  label: 'Packages',  title: 'Packages',          icon: 'box'   },
  { id: 'photos',    label: 'Photos',    title: 'Website Photos',    icon: 'image' },
  { id: 'assistant', label: 'Assistant', title: 'AI Assistant',      icon: 'bot'   },
];

const STEPS = [
  { id: 'trip',   label: 'Trip'   },
  { id: 'days',   label: 'Days'   },
  { id: 'review', label: 'Review' },
];

export default function App() {
  const [authenticated, setAuthenticated] = useState(false);
  const [checking, setChecking]           = useState(true);
  const [activeTab, setActiveTab]         = useState('itinerary');
  const [step, setStep]                   = useState('trip');
  const [quote, setQuote]                 = useState(null);
  const [trip, setTrip]                   = useState({ vehicle: '', meal: 'MAP' });   // vehicle '' = auto by group size

  useEffect(() => {
    verifyAdminSession()
      .then(async (ok) => {
        if (ok) await loadCustomHotels();   // admin-added hotels must be ready before the builder renders
        setAuthenticated(ok);
      })
      .finally(() => setChecking(false));
  }, []);

  const handleLogout = useCallback(() => {
    clearAdminToken();
    setAuthenticated(false);
    setQuote(null);
    setStep('trip');
  }, []);

  const handleGenerated = useCallback((q) => {
    setQuote(q);
    setStep('days');
  }, []);

  if (checking) {
    return <div className="sv-loading">Verifying admin session…</div>;
  }

  if (!authenticated) {
    return (
      <AdminLogin
        subtitle="Sign in to manage itineraries, packages, and website photos."
        onSuccess={() => loadCustomHotels().finally(() => setAuthenticated(true))}
      />
    );
  }

  const tab = TABS.find((t) => t.id === activeTab) || TABS[0];
  const inItinerary = activeTab === 'itinerary';

  return (
    <div className={'sv-shell' + (inItinerary ? ' has-steps' : '')}>
      <header className="sv-top">
        <div className="sv-top-row">
          <div className="sv-brand">
            <div className="sv-eyebrow-top">Serene Vibes Kashmir</div>
            <h1>{tab.title}</h1>
          </div>
          <a href="/" className="sv-toplink">Website</a>
          <button type="button" className="sv-ib" onClick={handleLogout} aria-label="Sign out" title="Sign out">
            <Icon name="logout" />
          </button>
        </div>

        {inItinerary && (
          <div className="sv-steps" role="tablist" aria-label="Itinerary steps">
            {STEPS.map((s, i) => {
              const locked = s.id !== 'trip' && !quote;
              return (
                <button
                  key={s.id}
                  type="button"
                  role="tab"
                  aria-selected={step === s.id}
                  disabled={locked}
                  title={locked ? 'Build the itinerary first' : undefined}
                  className={step === s.id ? 'on' : ''}
                  onClick={() => { setStep(s.id); window.scrollTo({ top: 0 }); }}
                >
                  <span className="n">{i + 1}</span>{s.label}
                </button>
              );
            })}
          </div>
        )}
      </header>

      <main className="sv-main">
        {inItinerary && (
          <section className="sv-panel">
            {/* Both stay mounted so edits in Days are kept while you look at Trip. */}
            <div hidden={step !== 'trip'}>
              <LeadForm onGenerated={handleGenerated} trip={trip} onTripChange={setTrip} hasQuote={!!quote} />
            </div>
            {quote && (
              <div hidden={step === 'trip'}>
                <QuotePreview quote={quote} trip={trip} step={step === 'review' ? 'review' : 'days'} onStep={setStep} />
              </div>
            )}
          </section>
        )}

        {activeTab === 'whatsapp' && <WhatsAppLeads onUnauthorized={handleLogout} />}

        {activeTab === 'packages' && (
          <SitePackages authenticated={authenticated} onUnauthorized={handleLogout} />
        )}

        {activeTab === 'photos' && (
          <WebsitePhotos authenticated={authenticated} onUnauthorized={handleLogout} />
        )}

        {activeTab === 'assistant' && (
          <AssistantSettings authenticated={authenticated} onUnauthorized={handleLogout} />
        )}
      </main>

      {!inItinerary && <ScrollDownButton />}

      <nav className="sv-nav" aria-label="Admin sections">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={activeTab === t.id ? 'on' : ''}
            aria-current={activeTab === t.id ? 'page' : undefined}
            onClick={() => { setActiveTab(t.id); window.scrollTo({ top: 0 }); }}
          >
            <Icon name={t.icon} size={22} />
            <span>{t.label}</span>
          </button>
        ))}
      </nav>
    </div>
  );
}
