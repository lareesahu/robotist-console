"""Outbound notification e-mail for new submissions (inquiries and applications).

The platform stores every submission in its database first. This module is the
single place that also hands a new one to e-mail, so the team hears about a lead
or an application without watching the console. It is deliberately fail-open:
a mail problem writes one log line and never breaks the visitor's submission.

Environment (set on the Render service; when no route is configured the site
behaves exactly as before and logs one line per submission):

  NOTIFY_EMAILS       comma-separated recipients; defaults to the team list

Delivery routes, tried in this order:

  1. RESEND_API_KEY                     Resend over HTTPS (api.resend.com)
  2. ZOHO_MAIL_CLIENT_ID +              the Zoho Mail API over HTTPS, sending
     ZOHO_MAIL_CLIENT_SECRET +          as the mailbox itself - no new vendor
     ZOHO_MAIL_REFRESH_TOKEN            and no DNS change
  3. ZOHO_EMAIL + ZOHO_APP_PASSWORD     plain SMTP (smtp.zoho.com:465)

Route 3 is what this was built on and it cannot work on a free Render web
service: Render blocks outbound traffic to ports 25, 465 and 587 on free
instances, so the send times out. Routes 1 and 2 both run over HTTPS, which is
not blocked. MAIL_FROM optionally overrides the From address; SMTP_HOST and
SMTP_PORT override the SMTP route's endpoint.

Submissions that do not look genuine are stored but never e-mailed, so the
notification channel keeps its signal (the "dozens of junk inquiries"
incident). The rules live in grn/screening.py, which the console also reads, so
the gate and the console badge cannot disagree.
"""

import json
import os
import smtplib
import ssl
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formataddr

DEFAULT_RECIPIENTS = ('lareesa@robotist.com.au', 'robert@robotist.com.au')

SOURCE_LABELS = {
    'contact': 'contact form',
    'requirements': 'deployment requirements form',
    'cart': 'robot cart',
}


def _setting(name, fallback=''):
    return (os.environ.get(name) or fallback).strip()


def _recipients():
    raw = _setting('NOTIFY_EMAILS', ','.join(DEFAULT_RECIPIENTS))
    return [address.strip() for address in raw.split(',') if address.strip()]


def _one_line(value):
    """Collapse a submitted value onto one line for subjects and fields."""
    return ' '.join(str(value or '').split())


def _spam_reason(name, email, company, interest, message):
    """Why this submission should not be e-mailed, or '' when it should.

    The rules live in grn/screening.py, which the console also imports, so the
    notification gate and the badge in the console can never disagree.
    """
    try:
        from .screening import screen
    except ImportError:  # loaded as a loose module by a script
        from screening import screen
    return screen({'name': name, 'email': email, 'company': company,
                   'interest': interest, 'message': message})


def _stamp():
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')


def _send(subject, body, reply_to=''):
    sender = _setting('ZOHO_EMAIL')
    password = _setting('ZOHO_APP_PASSWORD')
    host = _setting('SMTP_HOST', 'smtp.zoho.com')
    port = int(_setting('SMTP_PORT', '465') or 465)

    message = EmailMessage()
    message['From'] = formataddr(('Robotist website', sender))
    message['To'] = ', '.join(_recipients())
    if reply_to:
        message['Reply-To'] = reply_to
    message['Subject'] = subject
    message.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(host, port, timeout=30, context=context) as client:
        client.login(sender, password)
        client.send_message(message)


def _route():
    """Which delivery route the environment offers, or '' when none is set.

    HTTPS routes come first on purpose: the SMTP route cannot work on a free
    Render web service, because Render blocks outbound ports 25, 465 and 587.
    """
    if _setting('RESEND_API_KEY'):
        return 'resend'
    if (_setting('ZOHO_MAIL_REFRESH_TOKEN') and _setting('ZOHO_MAIL_CLIENT_ID')
            and _setting('ZOHO_MAIL_CLIENT_SECRET')):
        return 'zoho-mail-api'
    if _setting('ZOHO_EMAIL') and _setting('ZOHO_APP_PASSWORD'):
        return 'smtp'
    return ''


def _dispatch(route, subject, body, reply_to=''):
    """Send over the chosen route. Raises on any failure."""
    if route == 'resend':
        _send_via_resend(subject, body, reply_to)
    elif route == 'zoho-mail-api':
        _send_via_zoho_mail(subject, body, reply_to)
    else:
        _send(subject, body, reply_to)


USER_AGENT = 'robotist-website/1.0 (+https://robotist.com.au)'


def _request(url, data=None, headers=None, method='POST'):
    """One HTTPS call, parsed as JSON. Raises on refusal or garbage.

    The User-Agent is not decoration: api.resend.com sits behind Cloudflare,
    which answers Python's default 'Python-urllib/3.x' with 403 Forbidden
    before the request ever reaches the API.
    """
    merged = {'User-Agent': USER_AGENT, 'Accept': 'application/json'}
    merged.update(headers or {})
    request = urllib.request.Request(url, data=data, headers=merged,
                                     method=method)
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode('utf-8', 'replace')
    return json.loads(body) if body.strip() else {}



def _sender_address():
    """The From address: MAIL_FROM when set, otherwise the Zoho mailbox."""
    return _setting('MAIL_FROM') or _setting('ZOHO_EMAIL')


def _post_json(url, payload, headers):
    merged = dict(headers or {})
    merged['Content-Type'] = 'application/json'
    return _request(url, json.dumps(payload).encode('utf-8'), merged)


def _post_form(url, fields, headers):
    merged = dict(headers or {})
    merged['Content-Type'] = 'application/x-www-form-urlencoded'
    return _request(url, urllib.parse.urlencode(fields).encode('utf-8'), merged)


def _send_via_resend(subject, body, reply_to=''):
    """Resend over HTTPS (443). The From domain must be verified at Resend."""
    payload = {
        'from': _sender_address(),
        'to': _recipients(),
        'subject': subject,
        'text': body,
    }
    if reply_to:
        payload['reply_to'] = reply_to
    result = _post_json('https://api.resend.com/emails', payload,
                        {'Authorization': 'Bearer ' + _setting('RESEND_API_KEY')})
    if not result.get('id'):
        raise RuntimeError('resend refused it: ' + json.dumps(result)[:200])


def _zoho_access_token():
    """Swap the stored Zoho refresh token for an access token over HTTPS."""
    query = urllib.parse.urlencode({
        'refresh_token': _setting('ZOHO_MAIL_REFRESH_TOKEN'),
        'client_id': _setting('ZOHO_MAIL_CLIENT_ID'),
        'client_secret': _setting('ZOHO_MAIL_CLIENT_SECRET'),
        'grant_type': 'refresh_token',
    })
    result = _post_json('https://accounts.zoho.com/oauth/v2/token?' + query, None, {})
    token = result.get('access_token')
    if not token:
        raise RuntimeError('zoho refused the token: ' + json.dumps(result)[:200])
    return token


def _send_via_zoho_mail(subject, body, reply_to=''):
    """Zoho Mail API over HTTPS, sending as the mailbox itself."""
    headers = {'Authorization': 'Zoho-oauthtoken ' + _zoho_access_token()}
    accounts = _request('https://mail.zoho.com/api/accounts', None, headers,
                        method='GET').get('data') or []
    if not accounts:
        raise RuntimeError('the token cannot see a Zoho Mail account')
    account_id = str(accounts[0].get('accountId') or accounts[0].get('accountid') or '')
    fields = {
        'fromAddress': _sender_address(),
        'toAddress': ','.join(_recipients()),
        'subject': subject,
        'content': body,
        'mailFormat': 'plaintext',
    }
    if reply_to:
        fields['replyTo'] = reply_to
    result = _post_form(f'https://mail.zoho.com/api/accounts/{account_id}/messages',
                        fields, headers)
    if not result.get('data'):
        raise RuntimeError('zoho mail refused it: ' + json.dumps(result)[:200])


def _deliver(kind, reference, subject, body, email, spam_seen):
    """Check configuration and the spam gate, then send. True when mailed."""
    route = _route()
    if not route:
        print(f'[notify] {kind} {reference} stored; mail is not configured')
        return False
    reason = _spam_reason(*spam_seen)
    if reason:
        print(f'[notify] {kind} {reference} stored; looks like spam ({reason})')
        return False
    try:
        _dispatch(route, subject, body, reply_to=email)
    except Exception as error:
        hint = ''
        if route == 'smtp':
            hint = (' (this host blocks outbound SMTP; set RESEND_API_KEY or the '
                    'Zoho Mail API credentials to send over HTTPS)')
        print(f'[notify] {kind} {reference} stored; mail failed via {route}: '
              f'{error}{hint}')
        return False
    print(f'[notify] {kind} {reference} mailed to ' + ', '.join(_recipients())
          + f' via {route}')
    return True


def notify_inquiry(row):
    """E-mail the team about one stored inquiry row. Never raises.

    row keys: id, name, email, company, location, phone, interest, message,
    source, items (cart snapshot: dict slug -> quantity, or the stored list of
    item dicts, optional), details (requirements dict field -> [answers],
    optional).
    """
    try:
        reference = row.get('id', '')
        name = _one_line(row.get('name')) or 'Unknown sender'
        email = (row.get('email') or '').strip()
        company = _one_line(row.get('company'))

        source = SOURCE_LABELS.get(row.get('source'), row.get('source') or 'website')
        subject = 'Robotist website inquiry - {}{}'.format(name, f' ({company})' if company else '')

        lines = [
            f'New website inquiry - {name}',
            '',
            f'Reference: {reference}',
            f'Source: {source}',
            f'Received: {_stamp()}',
            '',
            f'Name: {name}',
            f'E-mail: {email}',
        ]
        for label, key in (('Company', 'company'), ('Location', 'location'),
                           ('Phone', 'phone'), ('Interest', 'interest')):
            if row.get(key):
                lines.append(f'{label}: {_one_line(row.get(key))}')
        lines += ['', 'Message:', str(row.get('message') or '(none)')]

        items = row.get('items') or {}
        if items:
            lines += ['', 'Cart:']
            if isinstance(items, dict):
                for slug, quantity in items.items():
                    lines.append(f'- {quantity} x {slug}')
            else:
                for entry in items:
                    label = entry.get('name') or entry.get('slug') or 'robot'
                    lines.append(f'- {entry.get("quantity", 1)} x {label}')
        details = row.get('details') or {}
        if details:
            lines += ['', 'Deployment requirements:']
            for field_name, answers in details.items():
                lines.append(f'- {field_name}: ' + '; '.join(str(a) for a in answers))

        lines += ['', f'Reply to this e-mail to answer {name} directly.']
        return _deliver('inquiry', reference, subject, '\n'.join(lines), email,
                        (name, email, company, row.get('interest'), row.get('message')))
    except Exception as error:
        print(f'[notify] inquiry {row.get("id", "")} stored; mail failed: {error}')
        return False


def notify_application(row):
    """E-mail the team about one stored GRN application. Never raises.

    row keys mirror the applications table: id, name, email, location,
    organization, role, website, experience, motivation, service_regions,
    availability, public_consent.
    """
    try:
        reference = row.get('id', '')
        name = _one_line(row.get('name')) or 'Unknown applicant'
        email = (row.get('email') or '').strip()
        role = _one_line(row.get('role'))

        subject = 'GRN application - {}{}'.format(name, f' ({role})' if role else '')
        lines = [
            f'New GRN application - {name}',
            '',
            f'Reference: {reference}',
            f'Received: {_stamp()}',
            '',
            f'Name: {name}',
            f'E-mail: {email}',
        ]
        for label, key in (('Location', 'location'), ('Organization', 'organization'),
                           ('Contribution', 'role'), ('Website', 'website'),
                           ('Service regions', 'service_regions'), ('Availability', 'availability')):
            if row.get(key):
                lines.append(f'{label}: {_one_line(row.get(key))}')
        lines += [
            '',
            'Experience:',
            str(row.get('experience') or '(none)'),
            '',
            'Motivation:',
            str(row.get('motivation') or '(none)'),
            '',
            'Public profile consent: ' + ('yes' if row.get('public_consent') else 'no'),
            '',
            f'Reply to this e-mail to answer {name} directly.',
        ]
        return _deliver('application', reference, subject, '\n'.join(lines), email,
                        (name, email, row.get('organization'), role, ''))
    except Exception as error:
        print(f'[notify] application {row.get("id", "")} stored; mail failed: {error}')
        return False
