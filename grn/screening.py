"""Screening: does a submission look like a genuine inquiry, or like spam?

The website stores every submission. This module answers one narrower question:
should this one be allowed to *e-mail* the team? A notification channel only
works while its signal is worth reading — the inquiries console held a month of
prize-scam links and multi-language "what is your price" bots, and every one of
them rang Robert and Lareesa.

The rules are written against the real submissions in the database (September to
October 2026), and the two failure modes are not symmetrical:

  * A genuine inquiry held back is a lost customer — so a single weak signal is
    never enough. Weak signals only count in pairs.
  * A spam notification is an annoyance — so one strong signal is enough.

`screen(row)` returns '' when the row should be notified, otherwise a short
reason for the log line and the console badge. Every rule is deliberately
readable: this list is the product decision, not a black box.
"""

import re

# One of these is enough on its own: the patterns that a real customer cannot
# plausibly produce.
PLACEHOLDER_COMPANIES = (
    'google', 'google llc', 'none', 'n/a', 'na', 'null', 'nil', '-', '--',
    'asdf', 'asdfasdf', 'test', 'testtest', 'company', 'your company',
    'no company', 'unknown', 'x', 'xx', 'xxx', 'qwerty', 'foo', 'bar',
)

DEFAULT_SPAM_KEYWORDS = (
    'seo,backlink,guest post,guest-post,link building,casino,gambling,viagra,'
    'crypto,bitcoin,investment,forex,escort,dating,loan,lottery,winner,'
    'porn,xxx,cialis,pharmacy,payday,free trial,nigerian,prince,'
    # the patterns actually seen in this inbox
    'telegra.ph,giveaway,lamborghini,rolls-royce,playstation,ps5,xbox,'
    'per month,earn $,profit,digital marketing agency,organic traffic,'
    'rank on the first page,smo services,ppc services,'
)

BLOCKED_MAIL_DOMAINS = (
    'mailinator.com', 'tempmail', 'guerrillamail', '10minutemail', 'yopmail',
    'throwaway', 'dispostable', 'getnada', 'sharklasers', 'trashmail',
)

# "RobertOvamb", "Richardwew", "Robertdrore": two capitalised runs glued
# together, which the form-spam services generate and real people rarely type.
CAMEL_NAME = re.compile(r'^[A-Z][a-z]{3,}[A-Z][a-z]{2,}$')

# An e-mail local part carrying a digit run or an interleaved digit
# ("gregoryj8tl2g", "joshuaguerrero2v7t40d", "neerajmadhu3654") — a weak hint
# on its own, because plenty of real people own addresses like this.
ODD_LOCAL_PART = re.compile(r'\d{2,}|[a-z]{3,}\d[a-z]')

# A short message asking the price, in whichever language the bot picked.
PRICE_ASK = re.compile(
    r'\b(price|prices|pricing|preis|precio|prezzi|prix|preço|cena|cenę|cenu|'
    r'cijenu|cijena|çmim|çmimin|çmimi|prys|verð|harga|цена|قیمت|価格|가격|'
    r'գինը|գին|ราคา|giá|価格)\b',
    re.IGNORECASE,
)

URL = re.compile(r'https?://|www\.|telegra\.ph', re.IGNORECASE)

# Words that a genuine inquiry about robots very often contains. Used only to
# soften a "short message in a foreign language" reading.
GENUINE_HINTS = (
    'robot', 'robots', 'price', 'quote', 'quotation', 'cost', 'budget',
    'demo', 'demonstration', 'lease', 'rent', 'rental', 'hire', 'buy',
    'purchase', 'order', 'ship', 'shipping', 'delivery', 'stock', 'inquiry',
    'interested', 'requirement', 'requirements', 'specification', 'specs',
    'deployment', 'warehouse', 'factory', 'hotel', 'restaurant', 'hospital',
    'school', 'mall', 'retail', 'security', 'cleaning', 'service', 'support',
    'maintenance', 'warranty', 'trial', 'pilot', 'invoice', 'agent',
    'distributor', 'partner', 'partnership', 'integration', 'custom',
)


def _one_line(value):
    return ' '.join(str(value or '').split())


def _keywords():
    return [word.strip().lower() for word in DEFAULT_SPAM_KEYWORDS.split(',') if word.strip()]


def _email_domain(email):
    return (email or '').rsplit('@', 1)[-1].strip().lower()


def screen(row):
    """'' when the submission should be notified, else a short reason.

    row keys: name, email, company, interest, message (source and phone are
    accepted and currently unused).
    """
    name = _one_line(row.get('name'))
    email = _one_line(row.get('email'))
    company = _one_line(row.get('company'))
    interest = _one_line(row.get('interest'))
    message = str(row.get('message') or '')
    flat = ' '.join(message.split())

    domain = _email_domain(email)
    if domain and any(blocked in domain for blocked in BLOCKED_MAIL_DOMAINS):
        return 'disposable-email'

    if URL.search(message):
        if len(flat) < 400:
            return 'link-in-message'
        if len(URL.findall(message)) >= 2:
            return 'link-heavy'

    blob = ' '.join([name, email, company, interest, flat]).lower()
    for keyword in _keywords():
        if keyword in blob:
            return 'keyword:' + keyword

    if len(flat) > 20:
        non_ascii = sum(1 for char in flat if ord(char) > 127)
        if non_ascii / len(flat) > 0.6:
            return 'gibberish'

    # ---- weak signals, only meaningful in pairs -------------------------
    weak = []

    if CAMEL_NAME.match(name):
        weak.append('generated-name')

    if company.lower() in PLACEHOLDER_COMPANIES:
        weak.append('placeholder-company')

    local = (email.split('@')[0] or '')
    if ODD_LOCAL_PART.search(local):
        weak.append('odd-address')

    if interest.lower() in ('', 'other') and not company:
        weak.append('no-company-vague-interest')

    lowered = flat.lower()
    if flat and len(flat) < 200 and PRICE_ASK.search(flat) \
            and not any(hint in lowered for hint in ('robot', 'unit', 'machine')):
        weak.append('price-ask')

    if len(flat) >= 20 and sum(1 for char in flat if char.isupper()) / len(flat) > 0.7:
        weak.append('shouting')

    if len(weak) >= 2:
        return ' and '.join(weak)

    return ''


def main():
    """Run the screen over a JSON dump of inquiries (used to review a backlog)."""
    import json
    import sys

    rows = json.load(open(sys.argv[1], encoding='utf-8')) if len(sys.argv) > 1 else []
    flagged = 0
    for row in rows:
        reason = screen(row)
        flagged += bool(reason)
        print(('HELD  ' if reason else 'notify') + ' | ' + (row.get('id') or '?') + ' | '
              + (row.get('name') or '')[:20].ljust(20) + ' | ' + (reason or 'looks genuine'))
    print(f'\n{len(rows)} rows, {flagged} held back, {len(rows) - flagged} notified')


if __name__ == '__main__':
    main()
