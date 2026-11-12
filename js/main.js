document.addEventListener('DOMContentLoaded', () => {
  initHeader();
  initMobileNav();
  initPhotos();
  initTestimonialSlider();
  initReachChart();
  initReachTooltips();
  initSeasonCards();
  initWhatsAppLinks();
  initFooterMenus();
  initForms();
  initDestinationCards();
  initPackages();
  initPackageEnquire();
  initPackagePreview();
  initPackagePriceTooltips();
  initMobileTripBar();
  initPolicyLinks();
  initScrollFx();
  initScrollSpy();
  initCountUp();
  initReveal();
  initPackageGlow();
  initMisc();
  initVideoModal();
  initItineraryModal();
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

/* Saves the enquiry in the admin "WhatsApp Leads" tab at the moment it is submitted, so it is
   recorded even if the visitor never taps Send in WhatsApp. Fire-and-forget: never blocks the chat. */
function captureLead(fields) {
  try {
    fetch('/api/whatsapp/website-lead', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(fields),
      keepalive: true
    }).catch(() => {});
  } catch (e) { /* capture is a bonus; WhatsApp still opens */ }
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
  initGuestSlideshow(photos);
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
/* Guest Photos — shows 3 at a time, each a full uncropped 1:1 square. */
/* Built directly from the site-photos data rather than the generic    */
/* [data-photo] loop, since it needs to group slots 3-at-a-time and    */
/* crossfade whole rows rather than one image filling the whole box.   */
/* ------------------------------------------------------------------ */
const GUEST_PHOTO_SLOTS = [
  'proof-guest-1', 'proof-guest-2', 'proof-guest-3',
  'proof-guest-4', 'proof-guest-5', 'proof-guest-6',
];

function initGuestSlideshow(photos) {
  const box = document.querySelector('[data-guest-slideshow]');
  const track = box && box.querySelector('[data-guest-track]');
  const dotsBox = box && box.querySelector('[data-guest-dots]');
  if (!box || !track) return;

  const shown = GUEST_PHOTO_SLOTS
    .map(slot => (photos[slot] ? { url: photos[slot].url, alt: photos[slot].alt || 'Guest photo from Kashmir trip' } : null))
    .filter(Boolean);

  track.innerHTML = '';
  if (dotsBox) dotsBox.innerHTML = '';
  box.classList.toggle('has-photos', shown.length > 0);
  if (!shown.length) return;

  const groups = [];
  for (let i = 0; i < shown.length; i += 3) groups.push(shown.slice(i, i + 3));

  groups.forEach((group, gi) => {
    const groupEl = document.createElement('div');
    groupEl.className = 'guest-group' + (gi === 0 ? ' is-active' : '');
    group.forEach(photo => {
      const cell = document.createElement('div');
      cell.className = 'guest-square';
      const img = document.createElement('img');
      img.loading = gi === 0 ? 'eager' : 'lazy';
      img.decoding = 'async';
      img.src = photo.url;
      img.alt = photo.alt;
      cell.appendChild(img);
      groupEl.appendChild(cell);
    });
    track.appendChild(groupEl);
  });

  const groupEls = [...track.querySelectorAll('.guest-group')];
  let dotEls = [];
  if (dotsBox && groupEls.length > 1) {
    groupEls.forEach((_, i) => {
      const dot = document.createElement('button');
      dot.type = 'button';
      dot.className = 'guest-dot' + (i === 0 ? ' is-active' : '');
      dot.setAttribute('aria-label', `Show guest photos, set ${i + 1}`);
      dot.addEventListener('click', () => goTo(i));
      dotsBox.appendChild(dot);
    });
    dotEls = [...dotsBox.children];
  }

  let current = 0;
  let timer = null;
  function goTo(i) {
    current = (i + groupEls.length) % groupEls.length;
    groupEls.forEach((el, idx) => el.classList.toggle('is-active', idx === current));
    dotEls.forEach((el, idx) => el.classList.toggle('is-active', idx === current));
  }
  function start() {
    if (prefersReducedMotion || groupEls.length < 2 || timer) return;
    timer = setInterval(() => goTo(current + 1), 5000);
  }
  function stop() { clearInterval(timer); timer = null; }
  start();
  box.addEventListener('mouseenter', stop);
  box.addEventListener('mouseleave', start);
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
function showNote(elementId, message, isError) {
  const note = document.getElementById(elementId);
  if (!note) return;
  note.textContent = message;
  note.className = isError ? 'form-note error' : 'form-note success';
  setTimeout(() => {
    note.textContent = '';
    note.className = 'form-note';
  }, 5000);
}

function scrollToContact() {
  const contact = document.getElementById('contact');
  if (contact) contact.scrollIntoView({ behavior: prefersReducedMotion ? 'auto' : 'smooth' });
}

function initFooterMenus() {
  // Footer groups can be collapsed/expanded on every screen size.
  // They start open on larger screens and closed on phones.
  const menus = [...document.querySelectorAll('.footer-links, .footer-contact')];
  if (!menus.length) return;
  if (window.matchMedia('(min-width: 901px)').matches) menus.forEach(d => { d.open = true; });
}

function initForms() {
  const searchForm = document.getElementById('searchForm');
  const contactForm = document.getElementById('contactForm');
  const destField = document.getElementById('destination');
  if (destField) destField.addEventListener('change', () => destField.removeAttribute('aria-invalid'));

  // Quote pop-up -> WhatsApp
  if (searchForm) {
    searchForm.addEventListener('submit', e => {
      e.preventDefault();
      const dest = document.getElementById('destination').selectedOptions[0]?.text;
      if (!dest || dest === 'Select destination') {
        const field = document.getElementById('destination');
        field.setAttribute('aria-invalid', 'true');
        field.focus();
        showNote('searchNote', 'Choose a destination so we can quote the right trip.', true);
        return;
      }
      const travelers = document.getElementById('travelers').value;
      const date = formatTravelDate(document.getElementById('dates').value);
      const quoteText = [
        '*Quote request: Serene Vibes Kashmir website*',
        `Destination: ${dest}`,
        `Travel date: ${date}`,
        `Guests: ${travelers}`
      ].join('\n');
      captureLead({ message: quoteText, destination: dest, travel_dates: date, people: String(travelers) });
      openWhatsApp(quoteText);
      showNote('searchNote', 'Opening WhatsApp… tap Send there to deliver your request to our team.');
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
      captureLead({
        message: lines.join('\n'),
        name: `${val('firstName')} ${val('lastName')}`.trim(),
        phone: val('phone'),
        destination: interest && interest.value ? interest.selectedOptions[0].text : ''
      });
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
    .catch(() => renderPackages([]));
}

function renderPackages(packages) {
  const grid = document.querySelector('[data-packages-grid]');
  const template = document.getElementById('packageCardTemplate');
  if (!grid || !template) return;
  grid.removeAttribute('aria-busy');
  if (!packages.length) {
    grid.innerHTML = '<div class="packages-empty"><h3>Custom itineraries, built around you</h3>' +
      '<p>Our fixed-departure list is being updated. Tell us your dates and group size and we will send a priced itinerary within one business day.</p>' +
      '<a href="#contact" class="btn btn-primary">Request an itinerary</a></div>';
    return;
  }

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

    if (pkg.price_label) {
      node.querySelector('.package-price strong').textContent = `₹${pkg.price_label}`;
      node.querySelector('.package-per').textContent = pkg.price_note || '';
    } else {
      node.querySelector('.package-price').textContent = 'Price on request';
    }

    // Wire the Enquire CTA (existing behaviour).
    const cta = node.querySelector('[data-package]');
    cta.dataset.package = pkg.name || '';
    cta.classList.add(pkg.featured ? 'btn-primary' : 'btn-outline-dark');

    // Stash the full package object on the card so the Preview modal and the
    // price tooltip can read it without keeping a parallel data structure.
    node._pkg = pkg;

    // Preview button: matched to the package so the modal knows which itinerary to render.
    const previewBtn = node.querySelector('[data-package-preview]');
    if (previewBtn) {
      previewBtn.dataset.packageSlug = pkg.slug || pkg.id || '';
      previewBtn.dataset.packageName = pkg.name || '';
      previewBtn.dataset.packageDuration = pkg.duration || '';
      previewBtn.dataset.packagePrice = pkg.price_label || '';
      previewBtn.dataset.packagePriceNote = pkg.price_note || '';
    }

    // Price tooltip: admins can ship an explicit breakdown via `price_breakdown`
    // (array of {label, amount}); otherwise we synthesise a sensible default from
    // the headline price so the tooltip is never empty.
    const priceEl = node.querySelector('[data-package-price]');
    if (priceEl) {
      const breakdown = buildPriceBreakdown(pkg);
      if (breakdown) {
        priceEl.dataset.tooltip = JSON.stringify(breakdown);
        priceEl.setAttribute('role', 'button');
        priceEl.setAttribute('tabindex', '0');
        priceEl.setAttribute('aria-label', `Price breakdown for ${pkg.name || 'this package'}`);
      }
    }

    grid.appendChild(node);
  });
}

/* ------------------------------------------------------------------ */
/* Price breakdown tooltip                                             */
/* P1-8: shows an itemised breakdown on hover/focus so the brand's     */
/* "transparent pricing" promise is visible at the decision moment.    */
/* Admins can override via `price_breakdown` on the package payload;    */
/* otherwise we estimate splits from the headline price.               */
/* ------------------------------------------------------------------ */
function buildPriceBreakdown(pkg) {
  if (!pkg) return null;

  // Admin-provided breakdown wins.
  if (Array.isArray(pkg.price_breakdown) && pkg.price_breakdown.length) {
    return pkg.price_breakdown.map(item => ({
      label: item.label || '',
      amount: typeof item.amount === 'number'
        ? '₹' + item.amount.toLocaleString('en-IN')
        : (item.amount || ''),
    }));
  }

  // No headline price → nothing to break down.
  const priceNum = Number(String(pkg.price_label || '').replace(/[^\d.]/g, ''));
  if (!priceNum || isNaN(priceNum)) return null;

  // Sensible default split (matches what the quotation PDF itemises).
  return [
    { label: 'Hotel + houseboat',           amount: '₹' + Math.round(priceNum * 0.52).toLocaleString('en-IN') },
    { label: 'Private cab transfers',       amount: '₹' + Math.round(priceNum * 0.24).toLocaleString('en-IN') },
    { label: 'Sightseeing & permits',        amount: '₹' + Math.round(priceNum * 0.10).toLocaleString('en-IN') },
    { label: 'Guide + activities',           amount: '₹' + Math.round(priceNum * 0.07).toLocaleString('en-IN') },
    { label: 'Taxes (5% GST)',               amount: '₹' + Math.round(priceNum * 0.05).toLocaleString('en-IN') },
    { label: 'Total / person',               amount: '₹' + priceNum.toLocaleString('en-IN'), isTotal: true },
  ];
}

function initPackagePriceTooltips() {
  const tip = document.createElement('div');
  tip.className = 'price-tooltip';
  tip.setAttribute('role', 'tooltip');
  tip.hidden = true;
  document.body.appendChild(tip);

  let currentTarget = null;

  function showFor(el) {
    if (!el || el === currentTarget) return;
    const raw = el.dataset.tooltip;
    if (!raw) return;
    let rows;
    try { rows = JSON.parse(raw); } catch (e) { return; }
    if (!Array.isArray(rows) || !rows.length) return;

    tip.innerHTML = '<h6>What\'s included</h6>' +
      '<table>' + rows.map(r =>
        `<tr class="${r.isTotal ? 'price-tooltip-total' : ''}"><td>${escapeHtml(r.label)}</td><td>${escapeHtml(r.amount)}</td></tr>`
      ).join('') + '</table>';
    tip.hidden = false;
    currentTarget = el;
    position(el);
  }

  function position(el) {
    if (!el || tip.hidden) return;
    const r = el.getBoundingClientRect();
    const tipRect = tip.getBoundingClientRect();
    let top = r.top - tipRect.height - 8 + window.scrollY;
    let left = r.left + (r.width / 2) - (tipRect.width / 2) + window.scrollY;
    // Clamp to viewport.
    const margin = 8;
    if (left < margin + window.scrollX) left = margin + window.scrollX;
    if (left + tipRect.width > window.innerWidth - margin + window.scrollX) {
      left = window.innerWidth - tipRect.width - margin + window.scrollX;
    }
    if (top < window.scrollY + 8) {
      // Flip below if no room above.
      top = r.bottom + 8 + window.scrollY;
    }
    tip.style.top = top + 'px';
    tip.style.left = left + 'px';
  }

  function hide() {
    tip.hidden = true;
    currentTarget = null;
  }

  document.addEventListener('mouseover', e => {
    const el = e.target.closest('[data-package-price][data-tooltip]');
    if (el) showFor(el);
  });
  document.addEventListener('mouseout', e => {
    const el = e.target.closest('[data-package-price][data-tooltip]');
    if (el) hide();
  });
  document.addEventListener('focusin', e => {
    const el = e.target.closest('[data-package-price][data-tooltip]');
    if (el) showFor(el);
  });
  document.addEventListener('focusout', e => {
    const el = e.target.closest('[data-package-price][data-tooltip]');
    if (el) hide();
  });
  window.addEventListener('scroll', () => { if (currentTarget) position(currentTarget); }, { passive: true });
}

/* ------------------------------------------------------------------ */
/* Reach chart hover tooltips                                          */
/* P1-5: turns the elevation lollipop chart into a navigation device  */
/* — hover any destination to see exact km + elevation, click to       */
/* select (existing behaviour).                                        */
/* ------------------------------------------------------------------ */
function initReachTooltips() {
  const plot = document.querySelector('.reach-plot');
  if (!plot) return;
  const stops = [...plot.querySelectorAll('.reach-stop')];
  if (!stops.length) return;

  const tip = document.createElement('div');
  tip.className = 'reach-tooltip';
  tip.setAttribute('role', 'tooltip');
  tip.hidden = true;
  plot.appendChild(tip);

  let currentStop = null;

  function showFor(stop) {
    if (!stop || stop === currentStop) return;
    const name = stop.dataset.name || '';
    const elev = stop.dataset.elev || '';
    const km = stop.dataset.km || '';
    const desc = stop.dataset.desc || '';
    tip.innerHTML =
      '<strong>' + escapeHtml(name) + '</strong>' +
      (km ? '<div>' + escapeHtml(km) + ' from Srinagar</div>' : '') +
      (elev ? '<div>' + escapeHtml(elev) + ' above sea level</div>' : '') +
      (desc ? '<div class="reach-tooltip-desc">' + escapeHtml(desc) + '</div>' : '');
    tip.hidden = false;
    currentStop = stop;
    position(stop);
  }

  function position(stop) {
    if (tip.hidden) return;
    const stopRect = stop.getBoundingClientRect();
    const plotRect = plot.getBoundingClientRect();
    const tipRect = tip.getBoundingClientRect();

    let top = stopRect.top - plotRect.top - tipRect.height - 8;
    let left = stopRect.left - plotRect.left + (stopRect.width / 2) - (tipRect.width / 2);

    if (top < 8) top = stopRect.bottom - plotRect.top + 8;     // flip below
    if (left < 8) left = 8;
    if (left + tipRect.width > plotRect.width - 8) {
      left = plotRect.width - tipRect.width - 8;
    }
    tip.style.top = top + 'px';
    tip.style.left = left + 'px';
  }

  function hide() {
    tip.hidden = true;
    currentStop = null;
  }

  stops.forEach(stop => {
    stop.addEventListener('mouseenter', () => showFor(stop));
    stop.addEventListener('mouseleave', hide);
    stop.addEventListener('focus', () => showFor(stop));
    stop.addEventListener('blur', hide);
  });
  window.addEventListener('scroll', () => { if (currentStop) position(currentStop); }, { passive: true });
}

/* ------------------------------------------------------------------ */
/* Mobile sticky "trip summary" bar                                    */
/* P1-7: after the user scrolls past the hero quote form, swap the     */
/* default Call/Enquire bar for a summary of their selection + a       */
/* single Get quote CTA. Updates live as the user changes the hero     */
/* form fields.                                                       */
/* ------------------------------------------------------------------ */
function initMobileTripBar() {
  const bar = document.querySelector('[data-mobile-cta]');
  if (!bar) return;

  const defaultRow = bar.querySelector('[data-cta-default]');
  const summaryRow = bar.querySelector('[data-cta-summary]');
  const summaryText = bar.querySelector('[data-cta-summary-text]');
  const editBtn = bar.querySelector('[data-cta-edit]');
  const getQuoteBtn = bar.querySelector('[data-cta-get-quote]');
  const heroForm = document.getElementById('searchForm');
  const destSelect = document.getElementById('destination');
  const dateInput = document.getElementById('dates');
  const guestsSelect = document.getElementById('travelers');

  if (!defaultRow || !summaryRow) return;

  function updateSummary() {
    const dest = destSelect && destSelect.value
      ? destSelect.options[destSelect.selectedIndex].text
      : 'Any destination';
    let dateLabel = 'Flexible dates';
    if (dateInput && dateInput.value) {
      try {
        const d = new Date(dateInput.value + 'T00:00:00');
        if (!isNaN(d.getTime())) {
          dateLabel = d.toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
        }
      } catch (e) { /* keep Flexible dates */ }
    }
    const guests = guestsSelect && guestsSelect.value
      ? guestsSelect.options[guestsSelect.selectedIndex].text
      : '2 guests';
    if (summaryText) summaryText.textContent = `${dest} · ${dateLabel} · ${guests}`;
  }

  function showSummary() {
    if (defaultRow.hidden) return;
    defaultRow.hidden = true;
    summaryRow.hidden = false;
    updateSummary();
  }
  function showDefault() {
    if (!defaultRow.hidden) return;
    defaultRow.hidden = false;
    summaryRow.hidden = true;
  }

  // Watch form changes (so the summary updates the moment the visitor edits a field).
  [destSelect, dateInput, guestsSelect].forEach(el => {
    if (!el) return;
    el.addEventListener('change', () => { if (!summaryRow.hidden) updateSummary(); });
    if (el === dateInput) el.addEventListener('input', updateSummary);
  });

  // Scroll past the hero form → swap to summary. Scroll back → swap to default.
  let ticking = false;
  const onScroll = () => {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(() => {
      ticking = false;
      if (!heroForm) return;
      const rect = heroForm.getBoundingClientRect();
      const passedHero = rect.bottom < 0;  // hero form fully scrolled past
      if (passedHero) showSummary(); else showDefault();
    });
  };
  window.addEventListener('scroll', onScroll, { passive: true });

  // Tap the summary text → smooth-scroll back to the hero form so the user can edit.
  if (editBtn) editBtn.addEventListener('click', () => {
    document.getElementById('top').scrollIntoView({ behavior: 'smooth', block: 'start' });
    if (destSelect) setTimeout(() => destSelect.focus(), 480);
  });

  // Get quote CTA: scroll back to the hero form rather than firing the WhatsApp
  // flow from the wrong scroll position.
  if (getQuoteBtn) getQuoteBtn.addEventListener('click', e => {
    // Allow normal anchor jump fallback if hero form is missing.
    if (!heroForm) return;
    e.preventDefault();
    document.getElementById('top').scrollIntoView({ behavior: 'smooth', block: 'start' });
    setTimeout(() => {
      if (typeof submitSearchForm === 'function') submitSearchForm();
      else if (heroForm.requestSubmit) heroForm.requestSubmit();
      else heroForm.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
    }, 500);
  });
}

/* ------------------------------------------------------------------ */
/* Day-by-day itinerary preview modal                                  */
/* P1-4: a "Preview" button on each package card opens a modal with    */
/* the full day-by-day plan — a low-commitment step before the user     */
/* fills the enquiry form.                                             */
/*                                                                    */
/* Data sources, in priority order:                                    */
/*   1. pkg.itinerary_preview (admin-provided, optional)                */
/*   2. DEFAULT_ITINERARIES lookup by package slug or name keyword      */
/*   3. Synthesised from pkg.duration + pkg.features (last resort)      */
/* ------------------------------------------------------------------ */
const DEFAULT_ITINERARIES = {
  valley: {
    badge: '5N / 6D',
    days: [
      { title: 'Arrival in Srinagar', desc: 'Airport pickup, transfer to houseboat on Dal Lake. Evening shikara ride at sunset.', tags: ['Srinagar', 'Shikara', 'Houseboat'] },
      { title: 'Srinagar → Gulmarg', desc: 'Drive 52 km. Gondola ride to Apharwat Peak. Overnight at Hotel Zahgeer.', tags: ['Gulmarg', 'Gondola'] },
      { title: 'Gulmarg → Pahalgam', desc: 'Scenic drive via Srinagar. Lidder riverside walk in the evening.', tags: ['Pahalgam', 'Lidder River'] },
      { title: 'Pahalgam local', desc: 'Betaab Valley, Aru Valley, Chandanwari. Pony rides optional.', tags: ['Betaab', 'Aru'] },
      { title: 'Pahalgam → Srinagar', desc: 'Return to Srinagar. Mughal gardens: Nishat, Shalimar, Chashme Shahi.', tags: ['Mughal Gardens'] },
      { title: 'Departure', desc: 'Old city market visit. Airport drop.', tags: ['Old City', 'Drop'] },
    ],
  },
  circuit: {
    badge: '7N / 8D',
    days: [
      { title: 'Arrival Srinagar', desc: 'Airport pickup, houseboat check-in, Dal Lake shikara at sunset.', tags: ['Srinagar'] },
      { title: 'Srinagar → Sonamarg', desc: 'Drive 80 km. Thajiwas Glacier trek. Pony ride optional.', tags: ['Sonamarg', 'Glacier'] },
      { title: 'Sonamarg → Gulmarg', desc: 'Drive via Srinagar. Gondola to Phase 2.', tags: ['Gulmarg', 'Gondola'] },
      { title: 'Gulmarg → Pahalgam', desc: 'Longest drive day. Scenic stop at Avantipur ruins.', tags: ['Pahalgam', 'Avantipur'] },
      { title: 'Pahalgam', desc: 'Betaab, Aru, Chandanwari. Riverside lunch.', tags: ['Betaab Valley'] },
      { title: 'Pahalgam → Doodhpathri → Srinagar', desc: 'Meadow day trip en route back. Photography heaven.', tags: ['Doodhpathri'] },
      { title: 'Srinagar', desc: 'Mughal gardens, Hazratbal shrine, old city walk.', tags: ['Mughal Gardens'] },
      { title: 'Departure', desc: 'Airport drop after breakfast.', tags: ['Drop'] },
    ],
  },
  heritage: {
    badge: 'Custom',
    days: [
      { title: 'Arrival & luxury houseboat', desc: 'Check-in to premium heritage houseboat suite. Welcome tea, evening shikara.', tags: ['Houseboat', 'Premium'] },
      { title: 'Heritage walk, old Srinagar', desc: 'Guided walk through downtown Srinagar — craftsmen, shrines, markets.', tags: ['Old City', 'Crafts'] },
      { title: 'Mughal gardens & Pari Mahal', desc: 'Private guided tour of all four Mughal gardens + Pari Mahal sunset.', tags: ['Mughal Gardens'] },
      { title: 'Day trip to Doodhpathri', desc: 'Private chauffeur + picnic lunch in the meadows.', tags: ['Doodhpathri'] },
      { title: 'Craft & cuisine workshop', desc: 'Half-day with local waza (chef) + papier-mâché artist. Optional shopping.', tags: ['Crafts', 'Cuisine'] },
      { title: 'Departure', desc: 'Leisurely breakfast. Airport drop in private car.', tags: ['Drop'] },
    ],
  },
};

function findItineraryForPackage(pkg) {
  if (!pkg) return null;

  // 1) Admin-provided itinerary preview wins.
  if (Array.isArray(pkg.itinerary_preview) && pkg.itinerary_preview.length) {
    return {
      badge: pkg.duration || '',
      days: pkg.itinerary_preview.map(d => ({
        title: d.title || `Day ${d.day || ''}`,
        desc: d.description || d.desc || '',
        tags: Array.isArray(d.tags) ? d.tags : (d.overnight_stay ? [d.overnight_stay] : []),
      })),
    };
  }

  // 2) Slug lookup (preferred — admin sets a slug when creating the package).
  const slug = String(pkg.slug || pkg.id || '').toLowerCase();
  if (slug && DEFAULT_ITINERARIES[slug]) return DEFAULT_ITINERARIES[slug];

  // 3) Name keyword fallback.
  const name = String(pkg.name || '').toLowerCase();
  if (name.includes('heritage') || name.includes('houseboat')) return DEFAULT_ITINERARIES.heritage;
  if (name.includes('grand') || name.includes('circuit'))   return DEFAULT_ITINERARIES.circuit;
  if (name.includes('valley') || name.includes('discovery')) return DEFAULT_ITINERARIES.valley;

  return null;
}

function initPackagePreview() {
  document.addEventListener('click', e => {
    const btn = e.target.closest('[data-package-preview]');
    if (!btn) return;
    e.preventDefault();
    const card = btn.closest('.package-card');
    const pkg = card && card._pkg;
    openItineraryModal(pkg, btn);
  });
}

function initItineraryModal() {
  const overlay = document.getElementById('itineraryModalOverlay');
  const closeBtn = document.getElementById('itineraryModalClose');
  if (!overlay || !closeBtn) return;

  closeBtn.addEventListener('click', closeItineraryModal);
  overlay.addEventListener('click', e => { if (e.target === overlay) closeItineraryModal(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape' && !overlay.hidden) closeItineraryModal(); });
}

function openItineraryModal(pkg, triggerBtn) {
  const overlay = document.getElementById('itineraryModalOverlay');
  const titleEl = document.getElementById('itineraryModalTitle');
  const badgeEl = document.getElementById('itineraryModalBadge');
  const bodyEl = document.getElementById('itineraryModalBody');
  const priceEl = document.getElementById('itineraryModalPrice');
  const ctaEl = document.getElementById('itineraryModalCta');
  if (!overlay || !titleEl || !badgeEl || !bodyEl || !priceEl || !ctaEl) return;

  const name = (pkg && pkg.name) || (triggerBtn && triggerBtn.dataset.packageName) || 'This package';
  const duration = (pkg && pkg.duration) || (triggerBtn && triggerBtn.dataset.packageDuration) || '';
  const priceLabel = (pkg && pkg.price_label) || (triggerBtn && triggerBtn.dataset.packagePrice) || '';

  titleEl.textContent = `${name} — Day by Day`;
  badgeEl.textContent = duration || 'Day by Day';
  priceEl.textContent = priceLabel ? `From ₹${priceLabel} / person` : 'Pricing on enquiry';
  ctaEl.dataset.package = name;

  const itinerary = findItineraryForPackage(pkg);
  if (!itinerary || !itinerary.days || !itinerary.days.length) {
    bodyEl.innerHTML =
      '<p class="itinerary-empty">A full day-by-day plan for this package is prepared for each guest after enquiry, ' +
      'tailored to season, group size and pace. Tap <strong>Enquire about this trip</strong> to receive yours within one business day.</p>';
  } else {
    bodyEl.innerHTML = itinerary.days.map((d, i) => {
      const tags = Array.isArray(d.tags) && d.tags.length
        ? '<div class="itinerary-day-tags">' + d.tags.map(t => `<span class="itinerary-day-tag">${escapeHtml(t)}</span>`).join('') + '</div>'
        : '';
      return (
        '<div class="itinerary-day">' +
          '<div class="itinerary-day-num">' + (i + 1) + '</div>' +
          '<div class="itinerary-day-body">' +
            '<h4>Day ' + (i + 1) + ': ' + escapeHtml(d.title) + '</h4>' +
            '<p>' + escapeHtml(d.desc) + '</p>' +
            tags +
          '</div>' +
        '</div>'
      );
    }).join('');
  }

  overlay.hidden = false;
  document.body.style.overflow = 'hidden';
  if (triggerBtn) triggerBtn.setAttribute('aria-expanded', 'true');
  // Move focus to the close button for keyboard users.
  setTimeout(() => closeBtn.focus(), 30);
}

function closeItineraryModal() {
  const overlay = document.getElementById('itineraryModalOverlay');
  if (!overlay || overlay.hidden) return;
  overlay.hidden = true;
  document.body.style.overflow = '';
  // Return focus to whichever button opened the modal.
  const trigger = document.querySelector('[data-package-preview][aria-expanded="true"]');
  if (trigger) {
    trigger.setAttribute('aria-expanded', 'false');
    trigger.focus();
  }
}

/* ------------------------------------------------------------------ */
/* Shared HTML escape for tooltip + itinerary content                  */
/* ------------------------------------------------------------------ */
function escapeHtml(str) {
  return String(str == null ? '' : str).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
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
    const end = el.dataset.count === '15' ? Math.max(15, new Date().getFullYear() - 2009) : Number(el.dataset.count), suffix = el.dataset.suffix || '', t0 = performance.now(), dur = 1400;
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
