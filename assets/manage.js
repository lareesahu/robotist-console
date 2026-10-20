/* ═══════════════════════════════════════════════════════════════════════
   ROBOTIST — console helpers (assets/manage.js)
   ───────────────────────────────────────────────────────────────────────
   Served at /assets/manage.js. The /manage pages run under a strict policy
   (script-src 'self'), so destructive confirmations live here rather than in
   an inline handler. A form or button carrying data-confirm asks before the
   request goes out; anything without it submits untouched.
   ═══════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  document.addEventListener('submit', function (event) {
    var form = event.target;
    if (!form || form.tagName !== 'FORM') { return; }
    var button = event.submitter || null;
    var message = (button && button.getAttribute('data-confirm')) || form.getAttribute('data-confirm');
    if (message && !window.confirm(message)) { event.preventDefault(); }
  });
})();
