document.addEventListener('DOMContentLoaded', () => {
  initHeader();
  initMobileNav();
  initPhotos();
  initTestimonialSlider();
  initReachChart();
  initSeasonCards();
  initWhatsAppLinks();
  initQuoteModal();
  initForms();
  initQuotePicks();
  initDestinationCards();
  initPackages();
  initPackageEnquire();
  initPolicyLinks();
  initScrollFx();
  initScrollSpy();
  initCountUp();
  initReveal();
  initPackageGlow();
  initMisc();
  initVideoModal();
  registerServiceWorker();
});

const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/* ------------------------------------------------------------------ */
/* WhatsApp                                                            */
/* Change the number here (country code + number, digits only).        */
/* Also update the three static wa.me links in index.html (data-wa).   */
/* ------------------------------------------------------------------ */
const WHATSAPP_NUMBER = '919419766510';

function whatsappUrl(text) {
  return `https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(text)}`;
}

function openWhatsApp(text) {
  const url = whatsappUrl(text);
  const win = window.open(url, '_blank');
  if (win) { win.opener = null; return; }
  window.location.href = url; // pop-up blocked: open in this tab instead
}

function initWhatsAppLinks() {
  document.querySelectorAll('a[data-wa]').forEach(link => {
    link.href = whatsappUrl("Hello Serene Vibes Kashmir! I'd like to know more about your Kashmir tour packages.");
  });
}

function formatTravelDate(value) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value || '');
  if (!m) return 'Flexible / not decided';
  return new Date(+m[1], +m[2] - 1, +m[3]).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' });
}

function registerServiceWorker() {
  if (!('serviceWorker' in navigator)) return;
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js', { scope: '/' }).catch(err => {
      console.warn('Service worker registration failed:', err);
    });
  });
}

/* ------------------------------------------------------------------ */
/* Header + mobile navigation                                          */
/* ------------------------------------------------------------------ */
function initHeader() {
  const header = document.getElementById('header');
  if (!header) return;
  const onScroll = () => header.classList.toggle('scrolled', window.scrollY > 40);
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
}

function initMobileNav() {
  const toggle = document.getElementById('navToggle');
  const links = document.getElementById('navLinks');
  if (!toggle || !links) return;

  const setOpen = (open) => {
    toggle.classList.toggle('open', open);
    links.classList.toggle('open', open);
    toggle.setAttribute('aria-expanded', String(open));
    toggle.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
    document.body.classList.toggle('nav-open', open);
  };

  toggle.addEventListener('click', () => setOpen(!links.classList.contains('open')));
  links.querySelectorAll('a').forEach(link => link.addEventListener('click', () => setOpen(false)));
  document.addEventListener('keydown', e => { if (e.key === 'Escape') setOpen(false); });
  window.matchMedia('(min-width: 901px)').addEventListener('change', e => { if (e.matches) setOpen(false); });
}

/* ------------------------------------------------------------------ */
/* Photos: every image on the page comes from the database             */
/* (uploaded in the admin panel at /admin/photos)                      */
/* ------------------------------------------------------------------ */
function initPhotos() {
  const embedded = window.__SITE_PHOTOS__;
  if (embedded && embedded.photos) {
    applyPhotos(embedded.photos, embedded.links);
    return;
  }
  // Fallback when the server could not embed the list (or the page came from a cache)
  fetch('/api/site-photos', { cache: 'no-cache' })
    .then(res => (res.ok ? res.json() : null))
    .then(data => applyPhotos((data && data.photos) || {}, (data && data.links) || {}))
    .catch(() => applyPhotos({}, {}));
}

let SITE_PHOTOS = {};
let SITE_LINKS = {};   // {slot: url}, e.g. the Highlights video link set in the admin panel

function applyPhotos(photos, links) {
  SITE_PHOTOS = photos || {};
  SITE_LINKS = links || {};
  document.dispatchEvent(new Event('sitephotos'));
  applyVideoLink();
  document.querySelectorAll('[data-photo]').forEach(box => {
    const slot = box.dataset.photo;
    const photo = photos[slot];
    const img = box.querySelector('img');
    if (!photo || !img) return;

    if (photo.alt) img.alt = photo.alt;
    box.dataset.src = photo.url;
    if (slot !== 'hero') img.loading = 'lazy';
    img.decoding = 'async';
    img.addEventListener('load', () => box.classList.add('has-photo'), { once: true });
    img.src = photo.url;
    if (img.complete && img.naturalWidth) box.classList.add('has-photo');
  });

  initGallery(photos);
  initSiteSlideshows(photos);
}

/* ------------------------------------------------------------------ */
/* Generic photo slideshows (Office photo, Guest Photos) — crossfades  */
/* through whichever of a card's slots have a photo uploaded in the    */
/* admin panel. Works with as few as one photo; falls back to the      */
/* placeholder icon (if any) when none are uploaded yet.               */
/* ------------------------------------------------------------------ */
function initSiteSlideshows(photos) {
  document.querySelectorAll('[data-site-slideshow]').forEach(box => {
    const slides = [...box.querySelectorAll('.site-slide')];
    const shown = slides.filter(s => Boolean(photos[s.dataset.photo]));
    box.classList.toggle('has-photos', shown.length > 0);
    if (!shown.length) return;

    shown.forEach((s, i) => s.classList.toggle('is-active', i === 0));

    const dotsBox = box.querySelector('[data-site-dots]');
    let dotEls = [];
    if (dotsBox) {
      dotsBox.innerHTML = '';
      if (shown.length > 1) {
        shown.forEach((_, i) => {
          const dot = document.createElement('button');
          dot.type = 'button';
          dot.className = 'site-dot' + (i === 0 ? ' is-active' : '');
          dot.setAttribute('aria-label', `Show photo ${i + 1}`);
          dot.addEventListener('click', () => goTo(i));
          dotsBox.appendChild(dot);
        });
        dotEls = [...dotsBox.children];
      }
    }

    let current = 0;
    let timer = null;
    function goTo(i) {
      current = (i + shown.length) % shown.length;
      shown.forEach((s, idx) => s.classList.toggle('is-active', idx === current));
      dotEls.forEach((d, idx) => d.classList.toggle('is-active', idx === current));
    }
    function start() {
      if (prefersReducedMotion || shown.length < 2 || timer) return;
      timer = setInterval(() => goTo(current + 1), 4500);
    }
    function stop() { clearInterval(timer); timer = null; }
    start();
    box.addEventListener('mouseenter', stop);
    box.addEventListener('mouseleave', start);
  });
}

/* ------------------------------------------------------------------ */
/* Gallery + lightbox (section stays hidden until photos exist)        */
/* ------------------------------------------------------------------ */
function initGallery(photos) {
  const section = document.querySelector('[data-gallery]');
  const grid = section && section.querySelector('.gallery-grid');
  if (!section || !grid) return;

  const tiles = [...grid.querySelectorAll('.gallery-tile')];
  const shown = [];
  tiles.forEach(tile => {
    const has = Boolean(photos[tile.dataset.photo]);
    tile.hidden = !has;
    if (has) shown.push(tile);
  });
  if (!shown.length) return;

  section.hidden = false;
  grid.dataset.layout = (shown.length === 3 || shown.length === 6) ? 'feature' : 'flat';

  const box = document.getElementById('lightbox');
  const img = document.getElementById('lbImg');
  const cap = document.getElementById('lbCap');
  if (!box || !img || typeof box.showModal !== 'function') return;

  let index = 0;
  const show = (i) => {
    index = (i + shown.length) % shown.length;
    const tile = shown[index];
    const alt = tile.querySelector('img').alt || '';
    img.src = tile.dataset.src;
    img.alt = alt;
    cap.textContent = alt === 'Kashmir travel photo' ? '' : alt;
  };

  shown.forEach((tile, i) => tile.addEventListener('click', () => { show(i); box.showModal(); }));
  document.getElementById('lbPrev').addEventListener('click', () => show(index - 1));
  document.getElementById('lbNext').addEventListener('click', () => show(index + 1));
  document.getElementById('lbClose').addEventListener('click', () => box.close());
  box.addEventListener('click', e => { if (e.target === box) box.close(); }); // click outside the photo
  box.addEventListener('keydown', e => {
    if (e.key === 'ArrowLeft') show(index - 1);
    if (e.key === 'ArrowRight') show(index + 1);
  });
}

/* ------------------------------------------------------------------ */
/* Testimonials                                                        */
/* ------------------------------------------------------------------ */
function initTestimonialSlider() {
  const track = document.getElementById('testimonialsTrack');
  const prevBtn = document.getElementById('prevBtn');
  const nextBtn = document.getElementById('nextBtn');
  const dotsContainer = document.getElementById('sliderDots');
  if (!track || !prevBtn || !nextBtn || !dotsContainer) return;

  const slides = [...track.querySelectorAll('.testimonial')];
  const slider = track.parentElement;
  let current = 0;
  let timer = null;
  let userPaused = false;

  slides.forEach((_, i) => {
    const dot = document.createElement('button');
    dot.type = 'button';
    dot.className = 'slider-dot' + (i === 0 ? ' active' : '');
    dot.setAttribute('aria-label', `Go to review ${i + 1}`);
    dot.addEventListener('click', () => goTo(i));
    dotsContainer.appendChild(dot);
  });
  const dots = [...dotsContainer.querySelectorAll('.slider-dot')];

  function goTo(index) {
    current = (index + slides.length) % slides.length;
    track.style.transform = `translateX(-${current * 100}%)`;
    dots.forEach((d, i) => d.classList.toggle('active', i === current));
    slides.forEach((s, i) => s.setAttribute('aria-hidden', String(i !== current)));
  }

  prevBtn.addEventListener('click', () => goTo(current - 1));
  nextBtn.addEventListener('click', () => goTo(current + 1));

  const start = () => { if (!prefersReducedMotion && !userPaused && !timer) timer = setInterval(() => goTo(current + 1), 7000); };
  const stop = () => { clearInterval(timer); timer = null; };
  slider.addEventListener('mouseenter', stop);
  slider.addEventListener('mouseleave', start);
  slider.addEventListener('focusin', stop);
  slider.addEventListener('focusout', start);
  document.addEventListener('visibilitychange', () => (document.hidden ? stop() : start()));

  // Pause control + arrow keys (auto-advancing content must be stoppable)
  const pauseBtn = document.getElementById('pauseBtn');
  if (pauseBtn) pauseBtn.addEventListener('click', () => {
    userPaused = !userPaused;
    pauseBtn.classList.toggle('paused', userPaused);
    pauseBtn.setAttribute('aria-label', userPaused ? 'Resume auto-advance' : 'Pause auto-advance');
    userPaused ? stop() : start();
  });
  slider.addEventListener('keydown', e => {
    if (e.key === 'ArrowLeft') goTo(current - 1);
    if (e.key === 'ArrowRight') goTo(current + 1);
  });

  // Swipe on touch screens
  let startX = null;
  slider.addEventListener('pointerdown', e => { startX = e.clientX; });
  slider.addEventListener('pointerup', e => {
    if (startX === null) return;
    const dx = e.clientX - startX;
    startX = null;
    if (Math.abs(dx) > 50) goTo(current + (dx < 0 ? 1 : -1));
  });
  slider.addEventListener('pointercancel', () => { startX = null; });

  goTo(0);
  start();
}

/* ------------------------------------------------------------------ */
/* Distance × elevation chart: selecting a destination fades its photo  */
/* in as the chart background                                           */
/* ------------------------------------------------------------------ */
const REACH_START_WITH = 'Srinagar'; // a destination name, or null to start with the plain white chart

function initReachChart() {
  const chart = document.getElementById('reach');
  if (!chart) return;

  // Stems grow once, when the chart scrolls into view
  if (!('IntersectionObserver' in window)) {
    chart.classList.add('in-view');
  } else {
    const observer = new IntersectionObserver(entries => {
      if (entries.some(e => e.isIntersecting)) { chart.classList.add('in-view'); observer.disconnect(); }
    }, { threshold: 0.3 });
    observer.observe(chart);
  }

  const stops = [...chart.querySelectorAll('.reach-stop')];
  const layers = [...chart.querySelectorAll('.reach-bg-layer')];
  const meta = document.getElementById('reachDetailMeta');
  const title = document.getElementById('reachDetailName');
  const desc = document.getElementById('reachDetailDesc');
  const cta = document.getElementById('reachDetailCta');
  if (!stops.length || layers.length < 2) return;
  let current = null;
  let layerIndex = 0;

  // Photo comes from the admin panel. If a destination has no chart photo of its own,
  // the photo of the matching destination card is used instead.
  function showPhoto(stop) {
    const photo = SITE_PHOTOS[stop.dataset.slot] || SITE_PHOTOS[stop.dataset.fallback];
    const next = layers[layerIndex = (layerIndex + 1) % layers.length];
    const prev = layers[(layerIndex + 1) % layers.length];
    const img = next.querySelector('img');
    next.classList.remove('has-photo');
    if (photo) {
      img.onload = () => next.classList.add('has-photo');
      img.src = photo.url;
      if (img.complete && img.naturalWidth) next.classList.add('has-photo');
    } else {
      img.removeAttribute('src');
    }
    next.classList.add('on');
    prev.classList.remove('on');
  }

  function select(stop, userAction) {
    if (stop === null || (stop === current && userAction)) {   // click the selected one again to go back to the plain chart
      current = null;
      chart.classList.remove('is-photo');
      stops.forEach(s => { s.classList.remove('is-active'); s.querySelector('.reach-name').setAttribute('aria-pressed', 'false'); });
      return;
    }
    current = stop;
    const { name, elev, km, desc: text } = stop.dataset;
    stops.forEach(s => {
      const on = s === stop;
      s.classList.toggle('is-active', on);
      s.querySelector('.reach-name').setAttribute('aria-pressed', String(on));
    });
    meta.textContent = `${elev} above sea level · ${km === '0 km' ? 'Base city' : km + ' from Srinagar'}`;
    title.textContent = name;
    desc.textContent = text;
    cta.textContent = `Enquire about ${name}`;
    cta.dataset.destination = name;
    showPhoto(stop);
    chart.classList.add('is-photo');
  }

  stops.forEach(stop => stop.addEventListener('click', () => select(stop, true)));

  cta.addEventListener('click', e => {
    e.preventDefault();
    scrollToContact();
    const interest = document.getElementById('tripInterest');
    if (interest) interest.value = 'custom';
    const message = document.getElementById('message');
    if (message && !message.value) {
      message.value = `I am interested in a trip to ${cta.dataset.destination}, Kashmir. Please share available packages and pricing.`;
    }
  });

  // Photos may arrive after the page has loaded (when the server could not embed them)
  document.addEventListener('sitephotos', () => { if (current) showPhoto(current); });

  const start = stops.find(s => s.dataset.name === REACH_START_WITH);
  if (start) select(start, false);
}

/* ------------------------------------------------------------------ */
/* Seasons: click-to-expand highlights, auto-flag the current season   */
/* ------------------------------------------------------------------ */
function initSeasonCards() {
  const grid = document.getElementById('seasonGrid');
  if (!grid) return;
  const cards = [...grid.querySelectorAll('.season-card')];
  if (!cards.length) return;

  const currentMonth = new Date().getMonth() + 1; // 1-12
  cards.forEach(card => {
    const start = Number(card.dataset.start);
    const end = Number(card.dataset.end);
    const inRange = start <= end
      ? currentMonth >= start && currentMonth <= end
      : currentMonth >= start || currentMonth <= end; // wraps year-end (winter)
    if (inRange) {
      const badge = card.querySelector('.season-badge');
      if (badge) badge.hidden = false;
    }
  });

  cards.forEach(card => {
    card.addEventListener('click', () => {
      const detail = document.getElementById(card.getAttribute('aria-controls'));
      const isOpen = card.getAttribute('aria-expanded') === 'true';

      cards.forEach(other => {
        if (other === card) return;
        other.setAttribute('aria-expanded', 'false');
        const otherDetail = document.getElementById(other.getAttribute('aria-controls'));
        if (otherDetail) otherDetail.classList.remove('is-open');
      });

      card.setAttribute('aria-expanded', String(!isOpen));
      if (detail) detail.classList.toggle('is-open', !isOpen);
    });
  });

  grid.addEventListener('click', e => {
    const cta = e.target.closest('.season-detail-cta');
    if (!cta) return;
    e.preventDefault();
    scrollToContact();
    const interest = document.getElementById('tripInterest');
    if (interest) interest.value = 'custom';
    const message = document.getElementById('message');
    if (message && !message.value) {
      message.value = `I'm planning a trip during ${cta.dataset.season}. Please share the best-fit package and pricing.`;
    }
  });
}

/* ------------------------------------------------------------------ */
/* Forms + enquiry prefills                                            */
/* ------------------------------------------------------------------ */
function showNote(elementId, message) {
  const note = document.getElementById(elementId);
  if (!note) return;
  note.textContent = message;
  note.className = 'form-note success';
  setTimeout(() => {
    note.textContent = '';
    note.className = 'form-note';
  }, 5000);
}

function scrollToContact() {
  const contact = document.getElementById('contact');
  if (contact) contact.scrollIntoView({ behavior: prefersReducedMotion ? 'auto' : 'smooth' });
}

function initQuoteModal() {
  const overlay  = document.getElementById('quoteModalOverlay');
  const openBtn  = document.getElementById('quoteOpenBtn');
  const closeBtn = document.getElementById('quoteModalClose');
  if (!overlay || !openBtn) return;
  let closing = null;

  function openModal() {
    clearTimeout(closing);
    overlay.hidden = false;
    document.body.style.overflow = 'hidden';
    // two frames so the browser paints the closed state first and the fade-in actually animates
    requestAnimationFrame(() => requestAnimationFrame(() => overlay.classList.add('is-open')));
    closeBtn && closeBtn.focus();
  }
  function closeModal() {
    overlay.classList.remove('is-open');
    document.body.style.overflow = '';
    closing = setTimeout(() => { overlay.hidden = true; }, prefersReducedMotion ? 0 : 240);
    openBtn.focus();
  }

  openBtn.addEventListener('click', openModal);
  closeBtn && closeBtn.addEventListener('click', closeModal);
  overlay.addEventListener('click', e => { if (e.target === overlay) closeModal(); });

  // Escape closes; Tab stays inside the dialog while it is open
  document.addEventListener('keydown', e => {
    if (overlay.hidden) return;
    if (e.key === 'Escape') { closeModal(); return; }
    if (e.key !== 'Tab') return;
    const items = [...overlay.querySelectorAll('button, select, input, a[href]')].filter(el => !el.disabled && el.offsetParent !== null);
    if (!items.length) return;
    const first = items[0], last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  });
}

function initQuotePicks() {
  const picks = document.querySelectorAll('.quote-pick');
  const destSelect = document.getElementById('destination');
  if (!picks.length || !destSelect) return;

  picks.forEach(pick => {
    pick.addEventListener('click', () => {
      picks.forEach(p => p.classList.remove('active'));
      pick.classList.add('active');
      destSelect.value = pick.dataset.dest || '';
    });
  });

  destSelect.addEventListener('change', () => {
    const matching = [...picks].find(p => p.dataset.dest === destSelect.value);
    picks.forEach(p => p.classList.toggle('active', p === matching));
  });
}

function initForms() {
  const searchForm = document.getElementById('searchForm');
  const contactForm = document.getElementById('contactForm');

  // Quote pop-up -> WhatsApp
  if (searchForm) {
    searchForm.addEventListener('submit', e => {
      e.preventDefault();
      const dest = document.getElementById('destination').selectedOptions[0]?.text;
      if (!dest || dest === 'Select destination') {
        showNote('searchNote', 'Please select a destination first.');
        return;
      }
      const travelers = document.getElementById('travelers').value;
      const date = formatTravelDate(document.getElementById('dates').value);
      openWhatsApp([
        '*Quote request: Serene Vibes Kashmir website*',
        `Destination: ${dest}`,
        `Travel date: ${date}`,
        `Guests: ${travelers}`
      ].join('\n'));
      showNote('searchNote', 'Opening WhatsApp… tap Send there to deliver your request to our team.');
      setTimeout(() => {
        const close = document.getElementById('quoteModalClose');
        const overlay = document.getElementById('quoteModalOverlay');
        if (close && overlay && !overlay.hidden) close.click();
      }, 2500);
    });
  }

  // Enquiry form -> WhatsApp
  if (contactForm) {
    contactForm.addEventListener('submit', e => {
      e.preventDefault();
      const val = id => (document.getElementById(id)?.value || '').trim();
      const interest = document.getElementById('tripInterest');
      const lines = ['*New enquiry: Serene Vibes Kashmir website*'];
      lines.push(`Name: ${val('firstName')} ${val('lastName')}`.trim());
      if (val('email')) lines.push(`Email: ${val('email')}`);
      if (val('phone')) lines.push(`Phone: ${val('phone')}`);
      if (interest && interest.value) lines.push(`Package: ${interest.selectedOptions[0].text}`);
      if (val('message')) lines.push(`Requirements: ${val('message')}`);
      openWhatsApp(lines.join('\n'));
      showNote('formNote', 'Opening WhatsApp… tap Send there to deliver your enquiry to our team.');
      contactForm.reset();
    });
  }
}

function initDestinationCards() {
  document.querySelectorAll('.destination-card').forEach(card => {
    card.addEventListener('click', e => {
      e.preventDefault();
      const name = card.dataset.destination || card.querySelector('h3')?.textContent;
      scrollToContact();
      const interest = document.getElementById('tripInterest');
      if (interest) interest.value = 'custom';

      const message = document.getElementById('message');
      if (!name || !message) return;

      let inquiry = `I am interested in a trip to ${name}, Kashmir. Please share available packages and pricing.`;
      const spots = card.querySelectorAll('.destination-spots li');
      if (spots.length) {
        const highlights = [...spots].map(li => li.textContent).join(', ');
        inquiry = `I am interested in a Srinagar itinerary covering ${highlights}. Please share available packages and pricing.`;
      }
      if (!message.value) message.value = inquiry;
    });
  });
}

function initPackageEnquire() {
  const packageMap = {
    'Valley Discovery': 'valley',
    'Grand Kashmir Circuit': 'circuit',
    'Heritage & Houseboat': 'heritage'
  };
  // Delegated on document (not the individual buttons) because package cards
  // are rendered dynamically from /api/site-packages after this runs.
  document.addEventListener('click', e => {
    const btn = e.target.closest('[data-package]');
    if (!btn) return;
    e.preventDefault();
    const pkg = btn.dataset.package;
    scrollToContact();
    const interest = document.getElementById('tripInterest');
    if (interest) interest.value = packageMap[pkg] || 'custom';
    const message = document.getElementById('message');
    if (message && !message.value) {
      message.value = `I would like to enquire about the ${pkg} package. Please share full itinerary details and quotation.`;
    }
  });
}

/* ------------------------------------------------------------------ */
/* Packages ("Structured Itineraries"): content comes from the database */
/* (edited in the admin panel, tab "Packages")                          */
/* ------------------------------------------------------------------ */
function initPackages() {
  const grid = document.querySelector('[data-packages-grid]');
  if (!grid) return;

  const embedded = window.__SITE_PACKAGES__;
  if (embedded && embedded.packages) {
    renderPackages(embedded.packages);
    return;
  }
  fetch('/api/site-packages', { cache: 'no-cache' })
    .then(res => (res.ok ? res.json() : null))
    .then(data => renderPackages((data && data.packages) || []))
    .catch(() => {});
}

function renderPackages(packages) {
  const grid = document.querySelector('[data-packages-grid]');
  const template = document.getElementById('packageCardTemplate');
  if (!grid || !template || !packages.length) return;

  grid.innerHTML = '';
  packages.forEach(pkg => {
    const node = template.content.firstElementChild.cloneNode(true);

    node.classList.toggle('package-card--featured', !!pkg.featured);

    const photoBox = node.querySelector('[data-package-photo]');
    if (pkg.placeholder === 'pine' || pkg.placeholder === 'slate') {
      photoBox.classList.add(`ph--${pkg.placeholder}`);
    }
    const img = photoBox.querySelector('img');
    img.alt = (pkg.photo && pkg.photo.alt) || pkg.name || '';
    if (pkg.photo && pkg.photo.url) {
      img.loading = 'lazy';
      img.decoding = 'async';
      img.addEventListener('load', () => photoBox.classList.add('has-photo'), { once: true });
      img.src = pkg.photo.url;
    }

    node.querySelector('.package-duration').textContent = pkg.duration || '';
    const badge = node.querySelector('.package-badge');
    if (pkg.badge) badge.textContent = pkg.badge; else badge.remove();
    node.querySelector('h3').textContent = pkg.name || '';
    node.querySelector('.package-desc').textContent = pkg.description || '';

    initFeatureSlideshow(node.querySelector('[data-package-features]'), pkg.features || []);

    const priceStrong = node.querySelector('.package-price strong');
    priceStrong.textContent = pkg.price_label ? `₹${pkg.price_label}` : 'Enquire';
    node.querySelector('.package-per').textContent = pkg.price_note || '';

    const cta = node.querySelector('[data-package]');
    cta.dataset.package = pkg.name || '';
    cta.classList.add(pkg.featured ? 'btn-primary' : 'btn-outline-dark');

    grid.appendChild(node);
  });
}

/* Package "included" bullets, one at a time on a short auto-rotating loop
   instead of a static list — pauses while the card is hovered. */
const FEATURE_CHECK_SVG =
  '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" aria-hidden="true"><path d="M20 6L9 17l-5-5"/></svg>';

function initFeatureSlideshow(box, features) {
  if (!box || !features.length) return;

  const stack = document.createElement('div');
  stack.className = 'feature-slide-stack';
  features.forEach((text, i) => {
    const slide = document.createElement('div');
    slide.className = 'feature-slide' + (i === 0 ? ' is-active' : '');
    slide.innerHTML = FEATURE_CHECK_SVG + '<span></span>';
    slide.querySelector('span').textContent = text;
    stack.appendChild(slide);
  });
  box.appendChild(stack);

  const slides = [...stack.querySelectorAll('.feature-slide')];
  let dots = [];
  if (slides.length > 1) {
    const dotsBox = document.createElement('div');
    dotsBox.className = 'feature-dots';
    slides.forEach((_, i) => {
      const dot = document.createElement('button');
      dot.type = 'button';
      dot.className = 'feature-dot' + (i === 0 ? ' is-active' : '');
      dot.setAttribute('aria-label', 'Show feature ' + (i + 1));
      dot.addEventListener('click', () => goTo(i));
      dotsBox.appendChild(dot);
    });
    box.appendChild(dotsBox);
    dots = [...dotsBox.querySelectorAll('.feature-dot')];
  }

  let current = 0;
  let timer = null;

  function goTo(index) {
    current = (index + slides.length) % slides.length;
    slides.forEach((el, i) => el.classList.toggle('is-active', i === current));
    dots.forEach((el, i) => el.classList.toggle('is-active', i === current));
  }
  function start() {
    if (prefersReducedMotion || slides.length < 2 || timer) return;
    timer = setInterval(() => goTo(current + 1), 2800);
  }
  function stop() {
    clearInterval(timer);
    timer = null;
  }

  start();
  const card = box.closest('.package-card');
  if (card) {
    card.addEventListener('mouseenter', stop);
    card.addEventListener('mouseleave', start);
  }
}

/* ------------------------------------------------------------------ */
/* Policies: open the matching accordion when linked from the footer   */
/* ------------------------------------------------------------------ */
function initPolicyLinks() {
  const openFromHash = () => {
    const target = document.querySelector(`details.policy${location.hash || '#none'}`);
    if (target) target.open = true;
  };
  window.addEventListener('hashchange', openFromHash);
  openFromHash();
}

/* ------------------------------------------------------------------ */
/* Interaction layer: scroll progress, hero depth, section tracking,   */
/* count-up figures, one-time reveals, card spotlight                  */
/* ------------------------------------------------------------------ */
function initScrollFx() {
  const bar = document.querySelector('.scroll-progress');
  const heroMedia = document.querySelector('.hero-media');
  let ticking = false;
  const update = () => {
    ticking = false;
    const max = document.documentElement.scrollHeight - window.innerHeight;
    if (bar) bar.style.transform = `scaleX(${max > 0 ? Math.min(window.scrollY / max, 1) : 0})`;
    if (heroMedia && !prefersReducedMotion && window.scrollY < window.innerHeight) {
      heroMedia.style.setProperty('--py', `${(window.scrollY * 0.18).toFixed(1)}px`);
    }
  };
  window.addEventListener('scroll', () => { if (!ticking) { ticking = true; requestAnimationFrame(update); } }, { passive: true });
  window.addEventListener('resize', update);
  update();
}

function initScrollSpy() {
  if (!('IntersectionObserver' in window)) return;
  const links = [...document.querySelectorAll('.nav-links a[href^="#"]:not(.nav-cta)')];
  const map = new Map(links.map(a => [a.getAttribute('href').slice(1), a]));
  const io = new IntersectionObserver(entries => {
    entries.forEach(en => {
      if (!en.isIntersecting) return;
      links.forEach(a => { a.classList.remove('is-current'); a.removeAttribute('aria-current'); });
      const link = map.get(en.target.id);
      if (link) { link.classList.add('is-current'); link.setAttribute('aria-current', 'true'); }
    });
  }, { rootMargin: '-45% 0px -50% 0px' });
  map.forEach((_, id) => { const el = document.getElementById(id); if (el) io.observe(el); });
}

function initCountUp() {
  const els = [...document.querySelectorAll('[data-count]')];
  if (!els.length || prefersReducedMotion || !('IntersectionObserver' in window)) return;
  const run = el => {
    const end = Number(el.dataset.count), suffix = el.dataset.suffix || '', t0 = performance.now(), dur = 1400;
    const tick = now => {
      const p = Math.min((now - t0) / dur, 1);
      el.textContent = Math.round(end * (1 - Math.pow(1 - p, 3))).toLocaleString('en-IN') + suffix;
      if (p < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  };
  const io = new IntersectionObserver(entries => entries.forEach(en => {
    if (en.isIntersecting) { io.unobserve(en.target); run(en.target); }
  }), { threshold: 0.6 });
  els.forEach(el => io.observe(el));
}

function initReveal() {
  if (prefersReducedMotion || !('IntersectionObserver' in window)) return;
  const targets = document.querySelectorAll('.trust-item, .destination-card, .season-item, .about-images, .about-content, .contact-form');
  const io = new IntersectionObserver(entries => entries.forEach(en => {
    if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); }
  }), { threshold: 0.12, rootMargin: '0px 0px -6% 0px' });
  targets.forEach((el, i) => { el.classList.add('reveal'); el.style.setProperty('--d', `${(i % 4) * 70}ms`); io.observe(el); });
}

function initPackageGlow() {
  document.addEventListener('pointermove', e => {
    const card = e.target.closest && e.target.closest('.package-card');
    if (!card) return;
    const r = card.getBoundingClientRect();
    card.style.setProperty('--mx', `${e.clientX - r.left}px`);
    card.style.setProperty('--my', `${e.clientY - r.top}px`);
  }, { passive: true });
}

function initMisc() {
  const year = document.getElementById('year');
  if (year) year.textContent = new Date().getFullYear();
  const date = document.getElementById('dates');   // no past travel dates
  if (date) date.min = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

/* ------------------------------------------------------------------ */
/* Trip video ("Highlights" card)                                      */
/* The thumbnail and the video link are both set in the admin panel    */
/* (Website Photos -> "Highlight video"). The link can be Instagram,   */
/* YouTube, Vimeo, Google Drive or a direct .mp4; it plays in a pop-up */
/* so visitors stay on the site. Unrecognised links open in a new tab. */
/* The video is only loaded when someone opens it.                     */
/* ------------------------------------------------------------------ */
const VIDEO_SLOT = 'proof-video-thumb';
const DEFAULT_VIDEO_URL = 'https://www.instagram.com/reel/DZNS5iTSrGv/';   // used until a link is saved in the admin panel

function currentVideoUrl() {
  return (SITE_LINKS && SITE_LINKS[VIDEO_SLOT]) || DEFAULT_VIDEO_URL;
}

/* Work out how to play a link. Returns {kind, ...} or null if it is not a usable http(s) link. */
function parseVideoUrl(raw) {
  let u;
  try { u = new URL(String(raw || '').trim()); } catch { return null; }
  if (u.protocol !== 'https:' && u.protocol !== 'http:') return null;
  const host = u.hostname.replace(/^(www|m)\./, '').toLowerCase();
  const parts = u.pathname.split('/').filter(Boolean);

  if (host === 'instagram.com') {
    const i = parts.findIndex(p => ['reel', 'reels', 'p', 'tv'].includes(p));
    const code = i >= 0 && parts[i + 1];
    if (code && /^[\w-]+$/.test(code)) {
      const type = parts[i] === 'reels' ? 'reel' : parts[i];
      const permalink = `https://www.instagram.com/${type}/${code}/`;
      return { kind: 'iframe', platform: 'Instagram', portrait: true, tall: true, permalink, src: `${permalink}embed/` };
    }
    return { kind: 'external', platform: 'Instagram' };
  }

  if (host === 'youtube.com' || host === 'youtube-nocookie.com' || host === 'youtu.be') {
    let id = null, portrait = false;
    if (host === 'youtu.be') id = parts[0];
    else if (parts[0] === 'watch') id = u.searchParams.get('v');
    else if (['shorts', 'embed', 'live', 'v'].includes(parts[0])) { id = parts[1]; portrait = parts[0] === 'shorts'; }
    if (id && /^[\w-]{11}$/.test(id)) {
      return { kind: 'iframe', platform: 'YouTube', portrait,
               src: `https://www.youtube-nocookie.com/embed/${id}?autoplay=1&rel=0&playsinline=1` };
    }
    return { kind: 'external', platform: 'YouTube' };
  }

  if (host === 'vimeo.com' || host === 'player.vimeo.com') {
    const id = parts.find(p => /^\d+$/.test(p));
    if (id) {
      const hash = parts[parts.indexOf(id) + 1];
      const h = hash && /^[a-f0-9]+$/i.test(hash) ? `&h=${hash}` : '';
      return { kind: 'iframe', platform: 'Vimeo', portrait: false,
               src: `https://player.vimeo.com/video/${id}?autoplay=1${h}` };
    }
    return { kind: 'external', platform: 'Vimeo' };
  }

  if (host === 'drive.google.com') {
    const i = parts.indexOf('d');
    const id = i >= 0 && parts[i + 1];
    if (id && /^[\w-]+$/.test(id)) {
      return { kind: 'iframe', platform: 'Google Drive', portrait: false,
               src: `https://drive.google.com/file/d/${id}/preview` };
    }
    return { kind: 'external', platform: 'Google Drive' };
  }

  if (/\.(mp4|webm|mov|m4v)$/i.test(u.pathname)) {
    return { kind: 'file', platform: '', src: u.href };
  }

  return { kind: 'external', platform: '' };
}

/* Point the card's "Watch on ..." link at the current video. */
function applyVideoLink() {
  const link = document.querySelector('[data-video-link]');
  if (!link) return;
  const url = currentVideoUrl();
  const info = parseVideoUrl(url);
  if (!info) return;   // keep the default link
  link.href = url;
  const label = link.querySelector('[data-video-link-label]');
  if (label) label.textContent = info.platform ? `Watch on ${info.platform}` : 'Watch video';
}

function initVideoModal() {
  const overlay = document.getElementById('videoModalOverlay');
  const closeBtn = document.getElementById('videoModalClose');
  const body = document.getElementById('videoModalBody');
  const modal = overlay && overlay.querySelector('.video-modal');
  const trigger = document.querySelector('[data-video-trigger]');
  if (!overlay || !closeBtn || !body || !modal || !trigger) return;

  function showFallback(url) {
    body.textContent = '';
    const p = document.createElement('p');
    p.className = 'video-loading';
    p.append("Couldn't load the video. ");
    const a = document.createElement('a');
    a.href = url; a.target = '_blank'; a.rel = 'noopener'; a.textContent = 'Watch it in a new tab instead';
    p.append(a, '.');
    body.appendChild(p);
  }

  function frame(portrait, tall) {
    const box = document.createElement('div');
    box.className = 'video-frame' + (portrait ? ' video-frame--portrait' : '') + (tall ? ' video-frame--tall' : '');
    return box;
  }

  /* "Not playing? Open it directly" — shown under every video as a safety net
     (ad-blockers / privacy settings can block embedded players). */
  let openLink = null;
  function setOpenLink(href, platform) {
    if (!openLink) {
      openLink = document.createElement('a');
      openLink.className = 'video-open';
      openLink.target = '_blank';
      openLink.rel = 'noopener';
      modal.appendChild(openLink);
    }
    openLink.href = href;
    openLink.textContent = platform ? `Video not playing? Open it on ${platform} ↗` : 'Video not playing? Open it in a new tab ↗';
  }

  function render(url, info) {
    body.textContent = '';
    modal.classList.remove('is-wide');

    if (info.kind === 'iframe') {
      if (!info.portrait) modal.classList.add('is-wide');
      const box = frame(info.portrait, info.tall);
      const iframe = document.createElement('iframe');
      iframe.src = info.src;
      iframe.title = 'Kashmir trip video';
      iframe.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
      iframe.allowFullscreen = true;
      iframe.referrerPolicy = 'strict-origin-when-cross-origin';
      box.appendChild(iframe);
      body.appendChild(box);
      return;
    }

    if (info.kind === 'file') {
      modal.classList.add('is-wide');
      const box = frame(false);
      const video = document.createElement('video');
      video.src = info.src;
      video.controls = true;
      video.autoplay = true;
      video.playsInline = true;
      video.onerror = () => showFallback(url);
      box.appendChild(video);
      body.appendChild(box);
    }
  }

  function open() {
    const url = currentVideoUrl();
    const info = parseVideoUrl(url);
    if (!info) { window.open(DEFAULT_VIDEO_URL, '_blank', 'noopener'); return; }
    if (info.kind === 'external') { window.open(url, '_blank', 'noopener'); return; }

    overlay.hidden = false;
    document.body.style.overflow = 'hidden';
    render(url, info);
    setOpenLink(info.permalink || url, info.platform);
    closeBtn.focus();
  }
  function close() {
    overlay.hidden = true;
    document.body.style.overflow = '';
    body.textContent = '';   // stops playback
    trigger.focus();
  }

  trigger.addEventListener('click', open);
  closeBtn.addEventListener('click', close);
  overlay.addEventListener('click', e => { if (e.target === overlay) close(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && !overlay.hidden) close(); });
}
