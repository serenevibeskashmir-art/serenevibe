/* Hotel slideshow — "Verified Stays" card
   Pulls hotel names + photos from /api/hotels (backend/routes/hotels.py),
   which reads the same hotel list the itinerary PDF uses. Every photo is
   shown in turn with its hotel's name; nothing here touches pdf_service.py. */
(function () {
  'use strict';

  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const SLIDE_MS = 4200;

  function init() {
    const box = document.querySelector('[data-hotel-slideshow]');
    const track = box && box.querySelector('[data-hotel-track]');
    const dotsBox = box && box.querySelector('[data-hotel-dots]');
    if (!box || !track) return;

    fetch('/api/hotels', { cache: 'no-cache' })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => build(box, track, dotsBox, (data && data.hotels) || []))
      .catch(() => {});
  }

  function build(box, track, dotsBox, hotels) {
    // One slide per photo, captioned with that photo's hotel — a hotel with
    // three photos gets three slides in a row, each still naming the hotel.
    const slides = [];
    hotels.forEach((hotel) => {
      (hotel.images || []).forEach((src) => {
        slides.push({ src, name: hotel.name, place: hotel.place });
      });
    });
    if (!slides.length) return; // leave the placeholder icon showing

    slides.forEach((slide, i) => {
      const el = document.createElement('div');
      el.className = 'hotel-slide' + (i === 0 ? ' is-active' : '');
      el.innerHTML =
        '<img loading="' + (i === 0 ? 'eager' : 'lazy') + '" decoding="async" ' +
        'src="' + escapeAttr(slide.src) + '" alt="' + escapeAttr(slide.name) + '">' +
        '<div class="hotel-slide-caption">' +
          '<span class="hotel-slide-name">' + escapeHtml(slide.name) + '</span>' +
          '<span class="hotel-slide-place">' + escapeHtml(slide.place) + '</span>' +
        '</div>';
      track.appendChild(el);
    });
    box.classList.add('has-photos');

    const slideEls = [...track.querySelectorAll('.hotel-slide')];
    let dotEls = [];
    if (dotsBox && slideEls.length > 1) {
      slideEls.forEach((_, i) => {
        const dot = document.createElement('button');
        dot.type = 'button';
        dot.className = 'hotel-dot' + (i === 0 ? ' is-active' : '');
        dot.setAttribute('aria-label', 'Show photo ' + (i + 1));
        dot.addEventListener('click', () => goTo(i));
        dotsBox.appendChild(dot);
      });
      dotEls = [...dotsBox.querySelectorAll('.hotel-dot')];
    }

    let current = 0;
    let timer = null;

    function goTo(index) {
      current = (index + slideEls.length) % slideEls.length;
      slideEls.forEach((el, i) => el.classList.toggle('is-active', i === current));
      dotEls.forEach((el, i) => el.classList.toggle('is-active', i === current));
    }

    function start() {
      if (prefersReducedMotion || slideEls.length < 2 || timer) return;
      timer = setInterval(() => goTo(current + 1), SLIDE_MS);
    }
    function stop() {
      clearInterval(timer);
      timer = null;
    }

    start();
    box.addEventListener('mouseenter', stop);
    box.addEventListener('mouseleave', start);
  }

  function escapeHtml(str) {
    return String(str || '').replace(/[&<>"']/g, (c) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    }[c]));
  }
  function escapeAttr(str) {
    return escapeHtml(str);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
