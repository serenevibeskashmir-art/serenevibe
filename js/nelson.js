/* Prev/next arrows for the horizontal card rows (destinations, seasons). Progressive enhancement only. */
(function () {
  function addArrows(row) {
    if (!row || row.dataset.nlArrows) return;
    row.dataset.nlArrows = '1';
    var bar = document.createElement('div');
    bar.className = 'nl-arrows';
    bar.innerHTML = '<button type="button" class="nl-arrow" aria-label="Previous">&#8592;</button><button type="button" class="nl-arrow" aria-label="Next">&#8594;</button>';
    row.parentNode.insertBefore(bar, row.nextSibling);
    var step = function (dir) {
      var card = row.firstElementChild;
      var w = card ? card.getBoundingClientRect().width + 20 : 300;
      row.scrollBy({ left: dir * w, behavior: 'smooth' });
    };
    bar.children[0].addEventListener('click', function () { step(-1); });
    bar.children[1].addEventListener('click', function () { step(1); });
  }
  function init() { addArrows(document.querySelector('.rd-bento')); addArrows(document.getElementById('seasonGrid')); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
