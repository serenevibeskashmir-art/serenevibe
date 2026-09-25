/* ============================================================
   Kashmir Travel Assistant: chat widget for the public site.

   - Only appears if the server says the assistant is switched on
     and configured (GET /api/assistant/status).
   - Sends the conversation to POST /api/assistant/chat.
   - When the assistant proposes a trip, shows a plan card with a
     "Send this plan to WhatsApp" button (opens a pre-filled chat
     with your number: the number lives in js/main.js).
   - Hotel photos the assistant is asked to show appear as small photo
     cards under its reply (server-built links only).
   - Any "Chat on WhatsApp" chip or message opens WhatsApp straight
     away (pre-filled with the plan) and is never sent to the AI.
   - Everything from the server is inserted with textContent, never
     as HTML.
   ============================================================ */
(function () {
  'use strict';

  var STORAGE_KEY = 'svk_assistant_v1';
  var MAX_SEND = 12;        // messages sent to the server each turn
  var MAX_KEEP = 40;        // messages remembered for this browser tab
  var FETCH_TIMEOUT = 25000;

  var STARTERS = [
    'Plan a trip within my budget',
    '6 days for 4 people from Delhi',
    "What's included in the package?",
    'Show me hotel photos',
    'Best time to visit Kashmir?',
    'Honeymoon trip ideas'
  ];
  var WELCOME = "Hi! I'm the Serene Vibes Kashmir travel assistant. Tell me your budget, how many of you are travelling, and for how many days, and I'll suggest a route with an estimate. Our team confirms the final price on WhatsApp.";

  var state = { messages: [], busy: false, open: false };
  var ui = {};   // DOM references, filled by build()

  /* ---------- tiny helpers ---------- */
  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text != null) node.textContent = text;
    return node;
  }

  function svg(pathD, size, extra) {
    var ns = 'http://www.w3.org/2000/svg';
    var s = document.createElementNS(ns, 'svg');
    s.setAttribute('viewBox', '0 0 24 24');
    s.setAttribute('width', size || 20);
    s.setAttribute('height', size || 20);
    s.setAttribute('fill', 'none');
    s.setAttribute('stroke', 'currentColor');
    s.setAttribute('stroke-width', '2');
    s.setAttribute('stroke-linecap', 'round');
    s.setAttribute('stroke-linejoin', 'round');
    s.setAttribute('aria-hidden', 'true');
    (Array.isArray(pathD) ? pathD : [pathD]).forEach(function (d) {
      var p = document.createElementNS(ns, 'path');
      p.setAttribute('d', d);
      s.appendChild(p);
    });
    if (extra) s.setAttribute('class', extra);
    return s;
  }

  var ICON = {
    sparkle: 'M12 3l1.9 5.6L19.5 10.5l-5.6 1.9L12 18l-1.9-5.6L4.5 10.5l5.6-1.9L12 3zM19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15z',
    close: 'M18 6L6 18M6 6l12 12',
    send: 'M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z',
    reset: ['M3 12a9 9 0 1 0 3-6.7', 'M3 4v5h5']
  };

  function store() {
    try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state.messages.slice(-MAX_KEEP))); } catch (e) { /* private mode */ }
  }
  function restore() {
    try {
      var saved = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || '[]');
      if (Array.isArray(saved)) {
        state.messages = saved.filter(function (m) {
          return m && (m.role === 'user' || m.role === 'assistant') && typeof m.content === 'string';
        });
      }
    } catch (e) { state.messages = []; }
  }

  /* ---------- WhatsApp hand-off ---------- */
  function waUrl(text) {
    if (typeof whatsappUrl === 'function') return whatsappUrl(text);          // defined in main.js
    return 'https://wa.me/919419766510?text=' + encodeURIComponent(text);
  }

  function planToWhatsApp(plan) {
    var lines = [
      'Hi Serene Vibes Kashmir! \uD83D\uDC4B I planned this trip with your Travel Assistant:',
      '',
      '*' + plan.title + '*',
      'Route: ' + plan.route
    ];
    if (plan.duration) lines.push('Duration: ' + plan.duration);
    if (plan.travellers) lines.push('Travellers: ' + plan.travellers);
    lines.push('Estimate: ' + plan.estimate);
    if (plan.highlights && plan.highlights.length) lines.push('Highlights: ' + plan.highlights.join(', '));
    if (plan.notes) lines.push('Note: ' + plan.notes);
    lines.push('', 'Could you please confirm availability and the final quote?');
    return lines.join('\n');
  }

  // "Chat on WhatsApp", "whatsapp", "WhatsApp now"... These go straight to WhatsApp, never to the AI.
  var WA_INTENT = /whats\s?app/i;
  var WA_CHIP_LABEL = 'Chat on WhatsApp';
  function isWhatsAppIntent(text) {
    text = String(text || '');
    return text.length <= 60 && WA_INTENT.test(text);
  }

  function lastPlan() {
    for (var i = state.messages.length - 1; i >= 0; i--) {
      if (state.messages[i].plan) return state.messages[i].plan;
    }
    return null;
  }

  // Pre-filled message for our team: the last trip plan if there is one, otherwise what the visitor told the assistant.
  function handoffText() {
    var plan = lastPlan();
    if (plan) return planToWhatsApp(plan);
    var said = state.messages
      .filter(function (m) { return m.role === 'user' && !isWhatsAppIntent(m.content); })
      .slice(-4)
      .map(function (m) { return '- ' + m.content; });
    var lines = ['Hello Serene Vibes Kashmir! I was using the trip assistant and would like help planning a Kashmir trip.'];
    if (said.length) lines = lines.concat(['', 'What I told the assistant:'], said);
    return lines.join('\n');
  }

  function openWhatsAppHandoff(userText) {
    if (state.busy) return;
    var text = handoffText();
    var url = waUrl(text);

    state.messages.push({ role: 'user', content: userText || WA_CHIP_LABEL });
    state.messages.push({
      role: 'assistant',
      content: 'Opening WhatsApp for you. Tap Send there to deliver your details to our team.',
      waText: text,
      suggestions: []
    });
    ui.input.value = '';
    autosize();
    store();      // saved first: if the browser has to leave this page for WhatsApp, the chat is still here on return
    render();

    // This runs inside the visitor's tap/click, so pop-up blockers allow it.
    var win = window.open(url, '_blank');
    if (win) { win.opener = null; } else { window.location.href = url; }
  }

  /* ---------- rendering ---------- */
  function renderPlan(plan) {
    var card = el('section', 'sva-plan');
    card.setAttribute('aria-label', 'Suggested trip plan');
    card.appendChild(el('p', 'sva-plan-label', 'Suggested plan'));
    card.appendChild(el('h3', 'sva-plan-title', plan.title));

    var dl = el('dl');
    function row(label, value, cls) {
      if (!value) return;
      dl.appendChild(el('dt', null, label));
      dl.appendChild(el('dd', cls || null, value));
    }
    row('Route', plan.route);
    row('Duration', plan.duration);
    row('Travellers', plan.travellers);
    row('Estimate', plan.estimate, 'sva-plan-estimate');
    card.appendChild(dl);

    if (plan.highlights && plan.highlights.length) {
      var ul = el('ul');
      plan.highlights.forEach(function (h) { ul.appendChild(el('li', null, h)); });
      card.appendChild(ul);
    }
    if (plan.notes) card.appendChild(el('p', 'sva-plan-note', plan.notes));

    var cta = el('a', 'btn btn-wa btn-full', '\uD83D\uDCF2 Send this plan to WhatsApp');
    cta.href = waUrl(planToWhatsApp(plan));
    cta.target = '_blank';
    cta.rel = 'noopener';
    card.appendChild(cta);
    return card;
  }

  // Hotel photo cards. Photo links come from our own server (or an https link you saved in the admin panel).
  var SAFE_PHOTO = /^(https:\/\/|\/api\/assistant\/hotel-photo\/)/;

  function renderHotels(hotels) {
    var wrap = el('div', 'sva-hotels');
    hotels.forEach(function (h) {
      if (!h || !h.name) return;
      var card = el('section', 'sva-hotel');
      card.setAttribute('aria-label', h.name + (h.place ? ', ' + h.place : ''));

      var head = el('p', 'sva-hotel-name', h.name);
      if (h.place) head.appendChild(el('span', 'sva-hotel-place', h.place));
      card.appendChild(head);

      var note = el('p', 'sva-hotel-note', 'Photos are not available here yet. Our team can share them on WhatsApp.');
      var row = el('div', 'sva-hotel-photos');
      (Array.isArray(h.photos) ? h.photos : []).forEach(function (src) {
        if (typeof src !== 'string' || !SAFE_PHOTO.test(src)) return;
        var link = el('a', 'sva-hotel-photo');
        link.href = src;
        link.target = '_blank';
        link.rel = 'noopener';
        link.setAttribute('aria-label', 'Open a larger photo of ' + h.name);
        var img = document.createElement('img');
        img.alt = h.name + (h.place ? ', ' + h.place : '');
        img.loading = 'lazy';
        img.referrerPolicy = 'no-referrer';   // some hotel websites refuse photos requested from other sites
        img.addEventListener('error', function () {
          link.remove();
          if (!row.children.length) row.replaceWith(note);   // every photo failed: say so instead of a blank box
        });
        img.src = src;
        link.appendChild(img);
        row.appendChild(link);
      });
      card.appendChild(row.children.length ? row : note);
      wrap.appendChild(card);
    });
    return wrap.children.length ? wrap : null;
  }

  function renderMessage(m) {
    var wrap = el('div', 'sva-msg ' + (m.role === 'user' ? 'sva-msg--user' : 'sva-msg--bot'));
    wrap.appendChild(el('p', 'sva-bubble', m.content));
    if (m.plan) wrap.appendChild(renderPlan(m.plan));
    if (Array.isArray(m.hotels) && m.hotels.length) {
      var gallery = renderHotels(m.hotels);
      if (gallery) wrap.appendChild(gallery);
    }
    if (m.waText) {
      var again = el('a', 'sva-chip sva-chip--wa', 'Open WhatsApp again');
      again.href = waUrl(m.waText);
      again.target = '_blank';
      again.rel = 'noopener';
      wrap.appendChild(again);
    }
    return wrap;
  }

  function renderChips() {
    ui.chips.textContent = '';
    if (state.busy) return;
    var last = state.messages[state.messages.length - 1];
    var options = [];
    if (!state.messages.length) options = STARTERS;
    else if (last && last.role === 'assistant' && Array.isArray(last.suggestions)) options = last.suggestions;
    options = options.filter(function (t) { return !isWhatsAppIntent(t); });   // we add the real one below
    options.forEach(function (text) {
      var b = el('button', 'sva-chip', text);
      b.type = 'button';
      b.addEventListener('click', function () { send(text); });
      ui.chips.appendChild(b);
    });
    var talked = state.messages.some(function (m) { return m.role === 'user'; });
    if (talked && !(last && last.waText)) {
      var wa = el('button', 'sva-chip sva-chip--wa', WA_CHIP_LABEL);
      wa.type = 'button';
      wa.addEventListener('click', function () { send(WA_CHIP_LABEL); });
      ui.chips.appendChild(wa);
    }
  }

  function scrollDown() { ui.log.scrollTop = ui.log.scrollHeight; }

  function render() {
    ui.log.textContent = '';
    ui.log.appendChild(renderMessage({ role: 'assistant', content: WELCOME }));
    state.messages.forEach(function (m) { ui.log.appendChild(renderMessage(m)); });
    if (state.busy) {
      var t = el('div', 'sva-msg sva-msg--bot');
      var dots = el('div', 'sva-bubble sva-typing');
      dots.setAttribute('role', 'status');
      dots.setAttribute('aria-label', 'Assistant is typing');
      dots.appendChild(el('i')); dots.appendChild(el('i')); dots.appendChild(el('i'));
      t.appendChild(dots);
      ui.log.appendChild(t);
    }
    renderChips();
    scrollDown();
  }

  function showError(message, retryText) {
    var wrap = el('div', 'sva-msg sva-msg--bot sva-msg--error');
    wrap.appendChild(el('p', 'sva-bubble', message));
    var actions = el('div', 'sva-retry');
    if (retryText) {
      var retry = el('button', 'sva-chip', 'Try again');
      retry.type = 'button';
      retry.addEventListener('click', function () { wrap.remove(); send(retryText, true); });
      actions.appendChild(retry);
      actions.appendChild(document.createTextNode(' '));
    }
    var wa = el('a', 'sva-chip', 'Message us on WhatsApp');
    wa.href = waUrl('Hello Serene Vibes Kashmir! I was using the trip assistant and would like help planning a Kashmir trip.');
    wa.target = '_blank';
    wa.rel = 'noopener';
    wa.style.display = 'inline-block';
    wa.style.textDecoration = 'none';
    actions.appendChild(wa);
    wrap.appendChild(actions);
    ui.log.appendChild(wrap);
    scrollDown();
  }

  /* ---------- talking to the server ---------- */
  function setBusy(on) {
    state.busy = on;
    ui.send.disabled = on;
    ui.input.disabled = on;
    ui.panel.setAttribute('aria-busy', on ? 'true' : 'false');
  }

  function send(text, isRetry) {
    text = String(text || '').trim();
    if (!text || state.busy) return;
    if (!isRetry && isWhatsAppIntent(text)) { openWhatsAppHandoff(text); return; }
    if (!isRetry) state.messages.push({ role: 'user', content: text });
    ui.input.value = '';
    autosize();
    setBusy(true);
    store();
    render();

    var payload = state.messages.slice(-MAX_SEND).map(function (m) { return { role: m.role, content: m.content }; });
    var ctrl = 'AbortController' in window ? new AbortController() : null;
    var timer = ctrl ? setTimeout(function () { ctrl.abort(); }, FETCH_TIMEOUT) : null;

    fetch('/api/assistant/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: payload }),
      signal: ctrl ? ctrl.signal : undefined
    })
      .then(function (res) {
        return res.json().catch(function () { return {}; }).then(function (data) { return { ok: res.ok, data: data }; });
      })
      .then(function (out) {
        if (!out.ok || !out.data.reply) {
          throw new Error(out.data.error || 'Something went wrong. Please try again.');
        }
        state.messages.push({
          role: 'assistant',
          content: out.data.reply,
          plan: out.data.plan || null,
          hotels: out.data.hotels || [],
          suggestions: out.data.suggestions || []
        });
        store();
        setBusy(false);
        render();
      })
      .catch(function (err) {
        setBusy(false);
        render();
        var msg = err && err.name === 'AbortError'
          ? 'That took too long. Please try again.'
          : (err && err.message) || 'Something went wrong. Please try again.';
        showError(msg, text);
      })
      .then(function () { if (timer) clearTimeout(timer); if (state.open && !state.busy) ui.input.focus(); });
  }

  /* ---------- open / close ---------- */
  function open() {
    if (state.open) return;
    state.open = true;
    ui.panel.classList.add('is-open');
    ui.launcher.setAttribute('aria-expanded', 'true');
    if (window.matchMedia('(max-width: 640px)').matches) document.body.style.overflow = 'hidden';
    render();
    ui.input.focus();
  }

  function close() {
    if (!state.open) return;
    state.open = false;
    ui.panel.classList.remove('is-open');
    ui.launcher.setAttribute('aria-expanded', 'false');
    document.body.style.overflow = '';
    ui.launcher.focus();
  }

  function reset() {
    if (state.busy) return;
    state.messages = [];
    store();
    render();
    ui.input.focus();
  }

  function autosize() {
    ui.input.style.height = 'auto';
    ui.input.style.height = Math.min(ui.input.scrollHeight, 110) + 'px';
  }

  /* ---------- build the DOM ---------- */
  function build() {
    var launcher = el('button', 'sva-launcher');
    launcher.type = 'button';
    launcher.setAttribute('aria-haspopup', 'dialog');
    launcher.setAttribute('aria-expanded', 'false');
    launcher.setAttribute('aria-controls', 'svaPanel');
    launcher.setAttribute('aria-label', 'Ask our Kashmir Travel Assistant');
    launcher.appendChild(svg(ICON.sparkle, 22));
    launcher.appendChild(el('span', 'sva-launcher-long', 'Ask our Kashmir Travel Assistant'));
    launcher.appendChild(el('span', 'sva-launcher-short', 'Ask AI'));

    var panel = el('div', 'sva-panel');
    panel.id = 'svaPanel';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-label', 'Kashmir Travel Assistant');

    var head = el('div', 'sva-head');
    var headIcon = el('span', 'sva-head-icon');
    headIcon.appendChild(svg(ICON.sparkle, 20));
    var headText = el('div', 'sva-head-text');
    headText.appendChild(el('h2', 'sva-title', 'Kashmir Travel Assistant'));
    headText.appendChild(el('p', 'sva-sub', 'AI assistant \u00B7 estimates only'));
    var resetBtn = el('button', 'sva-icon-btn');
    resetBtn.type = 'button';
    resetBtn.setAttribute('aria-label', 'Start a new chat');
    resetBtn.title = 'New chat';
    resetBtn.appendChild(svg(ICON.reset, 18));
    var closeBtn = el('button', 'sva-icon-btn');
    closeBtn.type = 'button';
    closeBtn.setAttribute('aria-label', 'Close assistant');
    closeBtn.appendChild(svg(ICON.close, 20));
    head.append(headIcon, headText, resetBtn, closeBtn);

    var log = el('div', 'sva-log');
    log.setAttribute('role', 'log');
    log.setAttribute('aria-live', 'polite');
    log.tabIndex = 0;
    var chips = el('div', 'sva-chips');

    var form = el('form', 'sva-form');
    var input = el('textarea', 'sva-input');
    input.rows = 1;
    input.maxLength = 600;
    input.placeholder = 'e.g. \u20B960,000, 4 people, from Delhi, 6 days';
    input.setAttribute('aria-label', 'Your message');
    var sendBtn = el('button', 'sva-send');
    sendBtn.type = 'submit';
    sendBtn.setAttribute('aria-label', 'Send message');
    sendBtn.appendChild(svg(ICON.send, 18));
    form.append(input, sendBtn);

    var foot = el('p', 'sva-foot', 'AI suggestions are estimates. Our team confirms final prices and availability.');

    panel.append(head, log, chips, form, foot);
    document.body.append(launcher, panel);

    ui = { launcher: launcher, panel: panel, log: log, chips: chips, input: input, send: sendBtn };

    launcher.addEventListener('click', open);
    closeBtn.addEventListener('click', close);
    resetBtn.addEventListener('click', reset);
    form.addEventListener('submit', function (e) { e.preventDefault(); send(input.value); });
    input.addEventListener('input', autosize);
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(input.value); }
    });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && state.open) close(); });

    // Any element with data-open-assistant opens the chat (e.g. a "Plan with AI" button).
    document.addEventListener('click', function (e) {
      var t = e.target.closest && e.target.closest('[data-open-assistant]');
      if (t) { e.preventDefault(); open(); }
    });
  }

  /* ---------- start only if the assistant is live ---------- */
  function init() {
    fetch('/api/assistant/status', { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : { enabled: false }; })
      .then(function (s) {
        if (!s || !s.enabled) return;
        restore();
        build();
      })
      .catch(function () { /* offline or API down: no assistant, no error shown */ });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
