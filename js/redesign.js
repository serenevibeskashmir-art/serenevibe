/* Redesign layer: small behaviours for the new sections.
   (Header scroll state, quote form, packages and photos are still handled by main.js.) */
(function () {
  'use strict';

  // Destination tiles: jump to the enquiry form and pre-fill the message
  document.querySelectorAll('.rd-tile[data-trip]').forEach(function (tile) {
    tile.addEventListener('click', function (e) {
      e.preventDefault();
      var name = tile.dataset.trip;
      if (typeof scrollToContact === 'function') scrollToContact();
      else { var c = document.getElementById('contact'); if (c) c.scrollIntoView({ behavior: 'smooth' }); }
      var interest = document.getElementById('tripInterest');
      if (interest) interest.value = 'custom';
      var message = document.getElementById('message');
      if (message && !message.value) {
        message.value = 'I am interested in a trip to ' + name + ', Kashmir. Please share available packages and pricing.';
      }
    });
  });

  // "How it works": highlight the step you hover, focus or tap
  var steps = document.querySelectorAll('#rdSteps li');
  function activate(li) {
    steps.forEach(function (s) { s.classList.toggle('is-active', s === li); });
  }
  steps.forEach(function (li) {
    li.addEventListener('mouseenter', function () { activate(li); });
    li.addEventListener('focus', function () { activate(li); });
    li.addEventListener('click', function () { activate(li); });
  });
})();

/* Seasons: the section takes on the colour of the season you are looking at.
   Starts on the current season; hover, focus, tap or swipe changes it. */
(function () {
  'use strict';
  var strip = document.querySelector('.season-strip');
  var grid = document.getElementById('seasonGrid');
  if (!strip || !grid) return;
  var cards = Array.prototype.slice.call(grid.querySelectorAll('.season-card'));
  if (!cards.length) return;

  function key(card) {
    var m = /season-detail-(\w+)/.exec(card.getAttribute('aria-controls') || '');
    return m ? m[1] : '';
  }
  function inSeason(card, month) {
    var a = +card.dataset.start, b = +card.dataset.end;
    return a <= b ? month >= a && month <= b : month >= a || month <= b;
  }
  var now = new Date().getMonth() + 1;
  var current = cards.filter(function (c) { return inSeason(c, now); })[0] || cards[0];

  function selected() {
    return cards.filter(function (c) { return c.getAttribute('aria-expanded') === 'true'; })[0] || current;
  }
  function tone(card) { strip.dataset.tone = key(card); }
  tone(current);

  // Phones: open the swipe row on the current season
  if (window.matchMedia('(max-width: 760px)').matches) {
    var first = grid.querySelector('.season-item');
    var cur = current.closest('.season-item');
    if (first && cur) grid.scrollLeft = cur.offsetLeft - first.offsetLeft;
  }

  cards.forEach(function (c) {
    c.addEventListener('mouseenter', function () { tone(c); });
    c.addEventListener('focus', function () { tone(c); });
    // main.js toggles aria-expanded on click; read it after that has run
    c.addEventListener('click', function () { setTimeout(function () { tone(selected()); }, 0); });
  });
  grid.addEventListener('mouseleave', function () { tone(selected()); });

  // Phones: the card nearest the left edge of the swipe row sets the tone
  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      if (!window.matchMedia('(max-width: 760px)').matches) return;
      entries.forEach(function (e) {
        if (e.isIntersecting && e.intersectionRatio > 0.6) tone(e.target.querySelector('.season-card'));
      });
    }, { root: grid, threshold: [0.6] });
    Array.prototype.forEach.call(grid.querySelectorAll('.season-item'), function (i) { io.observe(i); });
  }
})();
