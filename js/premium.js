/* Opens WhatsApp with the quote / enquiry details already filled in. */
(function () {
  var PHONE = '919419766510';
  function val(id) { var el = document.getElementById(id); return el ? (el.value || '').trim() : ''; }
  function open(lines) {
    var text = lines.filter(Boolean).join('\n');
    window.open('https://wa.me/' + PHONE + '?text=' + encodeURIComponent(text), '_blank', 'noopener');
  }
  var q = document.getElementById('quoteBtn');
  if (q) q.addEventListener('click', function () {
    var dest = val('dest');
    open([
      'Hello Serene Vibes Kashmir, I would like a quote.',
      dest && dest.indexOf('Select') !== 0 ? 'Destination: ' + dest : '',
      val('when') ? 'Travel date: ' + val('when') : '',
      'Guests: ' + val('guests')
    ]);
  });
  var e = document.getElementById('enquiryBtn');
  if (e) e.addEventListener('click', function () {
    var pk = val('pk');
    open([
      'Hello Serene Vibes Kashmir, I would like a custom itinerary.',
      'Name: ' + (val('fn') + ' ' + val('ln')).trim(),
      val('em') ? 'Email: ' + val('em') : '',
      val('ph') ? 'Phone: ' + val('ph') : '',
      pk && pk.indexOf('Select') !== 0 ? 'Package: ' + pk : '',
      val('msg') ? 'Requirements: ' + val('msg') : ''
    ]);
  });
})();
