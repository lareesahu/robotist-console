"""Forward selected mailbox messages on a daily schedule.

The Robotist mailbox (Zoho) receives Formspree notifications for the proposal
pages. Zoho offers no forwarding rule on this plan, and SMTP/IMAP out of the
operator's own network is blocked, so the console — which already talks to Zoho
and Resend from Render — does the reading and the resending instead.

State is the IMAP \Seen flag: a message is marked read only after the forward is
accepted by Resend, so a failed run retries itself on the next tick.
"""
import base64
import email
import imaplib
import json
import logging
import os
import threading
import time
import urllib.request
from datetime import datetime, timedelta
from email.header import decode_header, make_header
from email.message import EmailMessage

LOG = logging.getLogger(__name__)

IMAP_HOST = lambda: os.environ.get('IMAP_HOST', 'imap.zoho.com')
DEFAULT_SENDERS = 'formspree'


def _decode(value):
    try:
        return str(make_header(decode_header(value or '')))
    except Exception:
        return value or ''


def _text_of(message):
    """Readable text for the operator: plain part, else the HTML with tags off."""
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_type() == 'text/plain' and 'attachment' not in (part.get('Content-Disposition') or ''):
                return part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', 'replace')
        for part in message.walk():
            if part.get_content_type() == 'text/html':
                return part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', 'replace')
        return ''
    payload = message.get_payload(decode=True) or b''
    return payload.decode(message.get_content_charset() or 'utf-8', 'replace')


def _strip_html(text):
    out = []
    inside = False
    for char in text:
        if char == '<':
            inside = True
            continue
        if char == '>':
            inside = False
            out.append(' ')
            continue
        if not inside:
            out.append(char)
    return ''.join(out)


def _send_via_resend(payload):
    key = os.environ.get('RESEND_API_KEY', '').strip()
    if not key:
        raise RuntimeError('RESEND_API_KEY is not set on this service.')
    body = json.dumps(payload).encode('utf-8')
    request = urllib.request.Request('https://api.resend.com/emails', data=body, method='POST', headers={
        'Authorization': 'Bearer ' + key,
        'Content-Type': 'application/json',
        # Cloudflare in front of api.resend.com refuses Python's default agent.
        'User-Agent': 'robotist-console/1.0',
        'Accept': 'application/json',
    })
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode('utf-8') or '{}')


def run(destination=None, senders=None, limit=25, dry=False):
    """Forward unread messages from the given senders. Returns a run report."""
    destination = destination or os.environ.get('MAIL_FORWARD_TO', 'lareesa@pulse-branding.com')
    senders = senders or os.environ.get('MAIL_FORWARD_SENDERS', DEFAULT_SENDERS)
    user = os.environ.get('ZOHO_EMAIL', '').strip()
    password = os.environ.get('ZOHO_APP_PASSWORD', '').strip()
    report = {'ok': False, 'destination': destination, 'senders': [], 'found': 0, 'forwarded': [], 'failed': [], 'dry_run': dry}
    if not user or not password:
        report['error'] = 'ZOHO_EMAIL / ZOHO_APP_PASSWORD are not set on this service.'
        return report
    box = None
    try:
        box = imaplib.IMAP4_SSL(IMAP_HOST(), 993, timeout=60)
        box.login(user, password)
        box.select('INBOX')
        seen_ids = []
        for sender in [part.strip() for part in senders.split(',') if part.strip()]:
            report['senders'].append(sender)
            status, data = box.search(None, 'UNSEEN', 'FROM', '"%s"' % sender)
            if status != 'OK':
                report['failed'].append({'sender': sender, 'error': 'search refused: %s' % (data,)})
                continue
            for number in [n for n in (data[0] or b'').split() if n][:limit]:
                if number in seen_ids:
                    continue
                seen_ids.append(number)
                report['found'] += 1
                try:
                    status, raw = box.fetch(number, '(RFC822)')
                    if status != 'OK' or not raw or not raw[0]:
                        raise RuntimeError('fetch returned no message')
                    original = email.message_from_bytes(raw[0][1])
                    subject = _decode(original.get('Subject')) or '(no subject)'
                    sender_header = _decode(original.get('From'))
                    received = _decode(original.get('Date'))
                    body = _text_of(original)
                    if '<html' in body.lower():
                        body = _strip_html(body)
                    message = EmailMessage()
                    message['From'] = os.environ.get('MAIL_FROM', user)
                    message['To'] = destination
                    message['Subject'] = '[Robotist] ' + subject
                    message.set_content(
                        'Forwarded from the Robotist mailbox.\n'
                        'From: %s\nDate: %s\nSubject: %s\n\n%s\n' % (sender_header, received, subject, body.strip()[:20000])
                    )
                    message.add_attachment(raw[0][1], maintype='message', subtype='rfc822', filename=(subject[:60] or 'message') + '.eml')
                    if dry:
                        report['forwarded'].append({'subject': subject, 'from': sender_header, 'note': 'dry run'})
                        continue
                    payload = {
                        'from': message['From'],
                        'to': [destination],
                        'subject': message['Subject'],
                        'text': message.get_payload()[0].get_content(),
                        'attachments': [{
                            'filename': 'original.eml',
                            'content': base64.b64encode(raw[0][1]).decode('ascii'),
                            'content_type': 'message/rfc822',
                        }],
                    }
                    _send_via_resend(payload)
                    box.store(number, '+FLAGS', '\\Seen')
                    report['forwarded'].append({'subject': subject, 'from': sender_header})
                except Exception as error:
                    report['failed'].append({'message': str(error)[:300]})
        report['ok'] = not report['failed']
    except Exception as error:
        report['error'] = '%s: %s' % (type(error).__name__, error)
        report['failed'].append({'connect': str(error)[:300]})
    finally:
        if box is not None:
            try:
                box.close()
            except Exception:
                pass
            try:
                box.logout()
            except Exception:
                pass
    return report


def _next_run(hour=8):
    now = datetime.now()
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target


def _loop(hour=8):
    while True:
        wait = (_next_run(hour) - datetime.now()).total_seconds()
        time.sleep(max(60, wait))
        try:
            report = run()
            LOG.warning('mail forward: %s', json.dumps(report)[:800])
        except Exception as error:
            LOG.warning('mail forward crashed: %s', error)


def register_mailforward(app):
    """Expose a manual run route and start the daily thread."""
    db, admin, limited, audit = (app.extensions['grn_services'][k] for k in ('db', 'admin_required', 'limited', 'audit'))

    @app.get('/manage/mail-forward/run')
    @admin
    def mail_forward_run():
        from flask import jsonify, request
        dry = request.args.get('dry') == '1'
        return jsonify(run(destination=request.args.get('to'), dry=dry))

    if os.environ.get('MAIL_FORWARD_ENABLED', '').strip() == '1' and not app.testing:
        hour = int(os.environ.get('MAIL_FORWARD_HOUR', '8'))
        threading.Thread(target=_loop, args=(hour,), daemon=True, name='mail-forward').start()
