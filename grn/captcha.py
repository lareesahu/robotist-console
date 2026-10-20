"""Google reCAPTCHA for the public inquiry forms.

Switch it on with two environment variables, nothing else:

  GRN_RECAPTCHA_SITE_KEY   public site key, sent to the browser
  GRN_RECAPTCHA_SECRET     secret key, used for the server-side check

With both set, every inquiry submission must carry a ``g-recaptcha-response``
token that Google confirms; the browser half (invisible reCAPTCHA v3) is wired in
``assets/form-workflow.js`` and pointed at the site key by ``catalog/app.py``.
With either value unset the check is skipped, so turning it on is a configuration
change rather than a deploy — and an environment that loses its keys cannot lock
real customers out of the form.

A v2 checkbox widget also works: its hidden ``g-recaptcha-response`` field is
posted normally, and the server check is identical.
"""

import json
import os
import urllib.parse
import urllib.request

VERIFY_URL = 'https://www.google.com/recaptcha/api/siteverify'

# v3 scores the request from 0.0 (almost certainly a bot) to 1.0. Ten is the
# lowest sane ceiling: real people answering a short contact form land well above.
MINIMUM_SCORE = 0.5

TIMEOUT = 10


def site_key():
    return (os.getenv('GRN_RECAPTCHA_SITE_KEY') or '').strip()


def secret():
    return (os.getenv('GRN_RECAPTCHA_SECRET') or '').strip()


def enabled():
    return bool(site_key() and secret())


def verify(token, remote_addr=''):
    """Return ``(allowed, reason)``.

    Unconfigured → allowed, so the site behaves exactly as it did before.
    Configured and unanswered or rejected → refused.
    Configured but Google is unreachable → allowed, because no bot can cause that
    and dropping a real customer's message is worse than one missed check.
    """
    if not enabled():
        return True, 'not configured'
    if not (token or '').strip():
        return False, 'no captcha token'
    payload = urllib.parse.urlencode({
        'secret': secret(),
        'response': (token or '').strip(),
        'remoteip': remote_addr or '',
    }).encode()
    try:
        with urllib.request.urlopen(VERIFY_URL, data=payload, timeout=TIMEOUT) as response:
            result = json.load(response)
    except Exception as error:  # network, DNS, TLS, malformed body
        return True, 'captcha unreachable: %s' % error
    if not result.get('success'):
        codes = result.get('error-codes') or ['unknown']
        return False, 'captcha rejected: %s' % ','.join(codes)
    score = result.get('score')
    if score is not None and float(score) < MINIMUM_SCORE:
        return False, 'captcha score %.2f below %.2f' % (float(score), MINIMUM_SCORE)
    return True, 'ok'
