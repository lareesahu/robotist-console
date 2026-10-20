/* ═══════════════════════════════════════════════════════════════════════
   ROBOTIST — Shared lead-form workflow (assets/form-workflow.js)
   ───────────────────────────────────────────────────────────────────────
   Single source of truth for the inquiry workflow across all 24 lead
   forms: the full-page contact form (#inquiry-form) and the 23 "Inquire"
   modal forms (#inquiry-modal form). Vanilla JS, zero dependencies.

   Workflow:  idle → validating → submitting → success | error
   Spam guards (preserved from commit 2f5bc49): honeypot (_gotcha) + 3s
   minimum time-to-submit. Accessible: aria-live status, inline field
   errors (aria-invalid/aria-describedby), dialog semantics + focus trap
   + focus return for the modal, keyboard (Enter submit / Esc close),
   visible focus-visible outline, respects prefers-reduced-motion.
   ═══════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  var FORMSPREE_ENDPOINT = 'https://formspree.io/f/mnjevgjq';
  /* Filled in by the server (catalog/app.py) when the reCAPTCHA check is on. */
  var RECAPTCHA_SITE_KEY = '';
  var MIN_SUBMIT_MS = 3000;
  var FALLBACK_EMAIL = 'robert@robotist.com.au';
  var VALID_FIELDS = ['name', 'email', 'message'];

  /* ── Minimal injected styles (tokens from the Robotist design system) ── */
  var CSS = [
    '.rbf-status{display:none;align-items:flex-start;gap:10px;width:100%;padding:14px 16px;font-family:var(--font-body,system-ui,sans-serif);font-size:14px;font-weight:300;line-height:1.6;text-align:left;border:1px solid transparent;margin:2px 0 0;}',
    '.rbf-status.is-visible{display:flex;}',
    '.rbf-status.rbf-success{color:#B7F0D3;background:rgba(62,207,142,0.10);border-color:rgba(62,207,142,0.35);}',
    '.rbf-status.rbf-error{color:#FFC7C9;background:rgba(229,72,77,0.10);border-color:rgba(229,72,77,0.35);}',
    '.rbf-status.rbf-info{color:#A8DCEF;background:rgba(74,168,200,0.10);border-color:rgba(74,168,200,0.30);}',
    '.rbf-field-error{display:none;font-family:var(--font-body,system-ui,sans-serif);font-size:12px;font-weight:400;color:#E5484D;letter-spacing:0.01em;margin-top:4px;}',
    '.rbf-field-error.is-visible{display:block;}',
    '.inquiry-field.has-error input,.inquiry-field.has-error select,.inquiry-field.has-error textarea{border-color:rgba(229,72,77,0.6);}',
    '.rbf-spinner{display:inline-block;width:14px;height:14px;border:2px solid rgba(3,8,16,0.35);border-top-color:#030810;border-radius:50%;vertical-align:-2px;margin-right:8px;animation:rbf-spin 0.7s linear infinite;}',
    '@keyframes rbf-spin{to{transform:rotate(360deg);}}',
    '.btn-primary[disabled]{opacity:0.7;cursor:not-allowed;transform:none !important;}',
    'a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible{outline:2px solid var(--accent,#4AA8C8);outline-offset:2px;}',
    '@media (prefers-reduced-motion: reduce){.btn-primary,.rbf-spinner{animation-duration:1.4s !important;transition:none !important;}}'
  ].join('\n');

  function injectStyles() {
    if (document.getElementById('rbf-workflow-css')) return;
    var style = document.createElement('style');
    style.id = 'rbf-workflow-css';
    style.textContent = CSS;
    document.head.appendChild(style);
  }

  /* ── Status live region ────────────────────────────────────────────── */
  function getStatus(form) {
    var status = form.querySelector('.rbf-status');
    if (!status) {
      status = document.createElement('div');
      status.className = 'rbf-status';
      status.setAttribute('role', 'status');
      status.setAttribute('aria-live', 'polite');
      var anchor = form.querySelector('.inquiry-submit-wrap') || form.querySelector('button[type="submit"]');
      if (anchor && anchor.parentNode) anchor.parentNode.insertBefore(status, anchor);
      else form.appendChild(status);
    }
    return status;
  }

  function setStatus(form, type, message) {
    var s = getStatus(form);
    s.className = 'rbf-status is-visible ' + (type ? 'rbf-' + type : '');
    s.setAttribute('role', type === 'error' ? 'alert' : 'status');
    s.textContent = message;
    return s;
  }

  function clearStatus(form) {
    var s = form.querySelector('.rbf-status');
    if (s) { s.className = 'rbf-status'; s.textContent = ''; }
  }

  /* ── Inline field validation ───────────────────────────────────────── */
  var FIELD_RULES = [
    { name: 'name',    test: function (v) { return v.trim().length >= 2; },                msg: 'Please enter your name.' },
    { name: 'email',   test: function (v) { return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v.trim()); }, msg: 'Please enter a valid email address.' },
    { name: 'message', test: function (v) { return v.trim().length >= 5; },                msg: 'Please tell us a little about your requirements.' }
  ];

  function fieldWrap(field) { return field.closest('.inquiry-field') || field.parentNode; }

  function fieldErrorEl(field) {
    var wrap = fieldWrap(field);
    var err = wrap.querySelector('.rbf-field-error');
    if (!err) {
      err = document.createElement('p');
      err.className = 'rbf-field-error';
      err.id = (field.id || field.name) + '-error';
      wrap.appendChild(err);
    }
    return err;
  }

  function setFieldError(field, message) {
    fieldWrap(field).classList.add('has-error');
    field.setAttribute('aria-invalid', 'true');
    var err = fieldErrorEl(field);
    err.textContent = message;
    err.classList.add('is-visible');
    field.setAttribute('aria-describedby', err.id);
  }

  function clearFieldError(field) {
    fieldWrap(field).classList.remove('has-error');
    field.removeAttribute('aria-invalid');
    var err = fieldErrorEl(field);
    if (err) err.classList.remove('is-visible');
    field.removeAttribute('aria-describedby');
  }

  function validate(form) {
    var firstInvalid = null;
    var valid = true;
    FIELD_RULES.forEach(function (rule) {
      var field = form.querySelector('[name="' + rule.name + '"]');
      if (!field) return;
      if (!rule.test(field.value)) {
        setFieldError(field, rule.msg);
        if (!firstInvalid) firstInvalid = field;
        valid = false;
      } else {
        clearFieldError(field);
      }
    });
    if (firstInvalid) firstInvalid.focus();
    return valid;
  }

  /* ── Button state helpers ──────────────────────────────────────────── */
  function setButtonLoading(btn) {
    if (!btn) return;
    if (!btn.dataset.label) btn.dataset.label = btn.textContent.trim();
    btn.disabled = true;
    btn.setAttribute('aria-busy', 'true');
    btn.innerHTML = '<span class="rbf-spinner" aria-hidden="true"></span>Sending…';
  }

  function resetButton(btn, label) {
    if (!btn) return;
    btn.disabled = false;
    btn.removeAttribute('aria-busy');
    btn.innerHTML = '';
    btn.textContent = label || btn.dataset.label || 'Send Inquiry';
  }

  /* ── Success / error presenters ────────────────────────────────────── */
  function showSuccess(form, btn, opts) {
    var nameField = form.querySelector('[name="name"]');
    var name = nameField ? nameField.value.trim() : '';
    var msg = 'Thanks' + (name ? ', ' + name : '') +
      '! Your inquiry is on its way. We\u2019ll reply within one business day.';
    setStatus(form, 'success', msg);
    form.setAttribute('aria-busy', 'false');
    if (btn) { btn.textContent = 'Sent — Thank you!'; btn.disabled = true; }

    if (opts.isModal) {
      setTimeout(function () {
        closeInquiry();
        form.reset();
        clearStatus(form);
        resetButton(btn);
      }, 2200);
    } else {
      form.reset();
      setTimeout(function () { resetButton(btn); }, 4000);
    }
  }

  function showError(form, btn) {
    setStatus(form, 'error',
      'Something went wrong sending your inquiry. Please try again, or email ' +
      FALLBACK_EMAIL + ' directly.');
    resetButton(btn);
  }

  /* ── Submit handler factory ────────────────────────────────────────── */
  function makeSubmitHandler(opts) {
    opts = opts || {};
    return function (event) {
      event.preventDefault();
      var form = event.target;
      var btn = form.querySelector('button[type="submit"]');
      clearStatus(form);

      /* 3-second minimum submit guard (anti-bot) */
      var ts = parseInt(form.dataset.ts || '0', 10);
      if (ts && (Date.now() - ts < MIN_SUBMIT_MS)) {
        form.dataset.ts = String(Date.now()); /* re-arm so the next real attempt passes */
        setStatus(form, 'info', 'Please wait a moment, then submit again.');
        if (btn) btn.textContent = 'Please wait…';
        setTimeout(function () { if (btn && !btn.disabled) resetButton(btn); }, 1600);
        return false;
      }

      /* Honeypot: silently accept (bots see success, nothing is sent) */
      var gotcha = form.querySelector('input[name="_gotcha"]');
      if (gotcha && gotcha.value) {
        form.reset();
        showSuccess(form, btn, opts);
        return false;
      }

      /* Field validation */
      if (!validate(form)) {
        setStatus(form, 'error', 'Please fix the highlighted fields below.');
        return false;
      }

      /* Submit */
      var formData = new FormData(form);
      setButtonLoading(btn);
      form.setAttribute('aria-busy', 'true');

      function deliver() {
        fetch(FORMSPREE_ENDPOINT, {
          method: 'POST',
          body: formData,
          headers: { 'Accept': 'application/json' }
        }).then(function (response) {
          if (response.ok) {
            showSuccess(form, btn, opts);
          } else {
            return response.json().then(
              function () { throw new Error('Formspree HTTP ' + response.status); },
              function () { throw new Error('Formspree HTTP ' + response.status); }
            );
          }
        }).catch(function () {
          showError(form, btn);
        });
      }

      /* reCAPTCHA: the server sets RECAPTCHA_SITE_KEY when the check is switched
         on. Invisible v3 proves the submission came from a browser running our
         page; a v2 checkbox on the form posts its own g-recaptcha-response and
         needs nothing here. Both fail soft — a captcha that will not load must
         never cost a real inquiry, and the server decides. */
      function captchaToken(done) {
        if (!RECAPTCHA_SITE_KEY) { done(''); return; }
        var widget = form.querySelector('.g-recaptcha, [data-recaptcha-widget]');
        if (!widget && !(window.grecaptcha && grecaptcha.execute)) {
          var script = document.createElement('script');
          script.src = 'https://www.google.com/recaptcha/api.js?render=' + encodeURIComponent(RECAPTCHA_SITE_KEY);
          script.async = true;
          script.onload = function () { captchaToken(done); };
          script.onerror = function () { done(''); };
          document.head.appendChild(script);
          return;
        }
        if (!(window.grecaptcha && grecaptcha.execute)) { done(''); return; }
        grecaptcha.ready(function () {
          grecaptcha.execute(RECAPTCHA_SITE_KEY, { action: 'inquiry' }).then(function (token) {
            done(token || '');
          }, function () { done(''); });
        });
      }

      captchaToken(function (token) {
        if (token) { formData.append('g-recaptcha-response', token); }
        deliver();
      });

      return false;
    };
  }

  /* ── Inquiry modal (a11y: dialog semantics + focus trap + return) ──── */
  var modal = null;
  var lastFocused = null;
  var FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), ' +
    'select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

  function setupModal() {
    modal = document.getElementById('inquiry-modal');
    if (!modal) return;

    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    if (!modal.hasAttribute('tabindex')) modal.setAttribute('tabindex', '-1');

    var title = modal.querySelector('.inquiry-title');
    var desc = modal.querySelector('.inquiry-desc');
    if (title) { if (!title.id) title.id = 'inquiry-modal-title'; modal.setAttribute('aria-labelledby', title.id); }
    if (desc) { if (!desc.id) desc.id = 'inquiry-modal-desc'; modal.setAttribute('aria-describedby', desc.id); }

    /* click outside to close */
    modal.addEventListener('click', function (e) { if (e.target === modal) closeInquiry(); });

    /* trap Tab within the dialog */
    modal.addEventListener('keydown', function (e) {
      if (e.key !== 'Tab') return;
      var focusables = Array.prototype.slice.call(modal.querySelectorAll(FOCUSABLE))
        .filter(function (el) { return el.offsetParent !== null; });
      if (!focusables.length) return;
      var first = focusables[0];
      var last = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    });
  }

  window.openInquiry = function () {
    if (!modal) return;
    lastFocused = document.activeElement;
    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
    var firstInput = modal.querySelector('input:not([name="_gotcha"]), select, textarea');
    if (firstInput) setTimeout(function () { firstInput.focus(); }, 0);
    else setTimeout(function () { modal.focus(); }, 0);
  };

  window.closeInquiry = function () {
    if (!modal) return;
    modal.style.display = 'none';
    document.body.style.overflow = '';
    if (lastFocused && typeof lastFocused.focus === 'function') lastFocused.focus();
  };

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && modal && modal.style.display === 'flex') closeInquiry();
  });

  /* ── Wire up ───────────────────────────────────────────────────────── */
  function wireForm(form, opts) {
    if (!form) return;
    if (!form.dataset.ts) form.dataset.ts = String(Date.now());
    form.addEventListener('submit', makeSubmitHandler(opts));
    form.addEventListener('input', function (e) {
      var t = e.target;
      if (t && t.name && VALID_FIELDS.indexOf(t.name) !== -1) clearFieldError(t);
    });
  }

  function init() {
    injectStyles();
    wireForm(document.getElementById('inquiry-form'), { isModal: false });
    setupModal();
    var modalForm = modal ? modal.querySelector('form') : null;
    wireForm(modalForm, { isModal: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
