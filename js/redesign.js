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
