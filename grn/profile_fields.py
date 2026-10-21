"""Skill and language fields for GRN member profiles.

Stored as JSON text on the profiles row; the editor, the CMS list and the public
card read them through the helpers here so the three representations never mix.
"""
import hashlib
import json
import logging
import re

log = logging.getLogger(__name__)

SKILL_MAX = 12
SKILL_LEN = 40
LANGUAGE_MAX = 6
LANGUAGE_LEN = 40
RAW_MAX = 2000
LEVELS = (('native', 'Native or bilingual'), ('fluent', 'Fluent'), ('professional', 'Professional'),
          ('conversational', 'Conversational'), ('basic', 'Basic'))
LEVEL_LABELS = dict(LEVELS)
LEVEL_SHORT = {'native': 'Native', 'fluent': 'Fluent', 'professional': 'Professional',
               'conversational': 'Conversational', 'basic': 'Basic'}
# Letters and digits in any script, plus the punctuation real skill names use.
ALLOWED_EXTRA = set(" .+#/&()-_'’·")

SCOPE_FIELDS = ('name', 'title', 'location', 'bio', 'academic_background', 'credentials', 'website', 'photo')


def _text(value):
    return re.sub(r'\s+', ' ', (value or '')).strip()


def _check(item, label, limit):
    if len(item) > limit:
        raise ValueError(f'Shorten “{item[:80]}” to {limit} characters or fewer.')
    for char in item:
        if char.isalnum() or char in ALLOWED_EXTRA:
            continue
        raise ValueError(f'Remove unsupported characters from this {label}: “{item[:80]}”.')
    return item


def parse_skills(raw):
    """Comma, semicolon or newline separated -> ordered, de-duplicated list."""
    items, seen = [], set()
    for part in re.split(r'[,;\n]', (raw or '')[:RAW_MAX]):
        item = _text(part)
        if not item:
            continue
        _check(item, 'skill', SKILL_LEN)
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        items.append(item)
    if len(items) > SKILL_MAX:
        raise ValueError(f'Add at most {SKILL_MAX} skills.')
    return items


def parse_languages(names, levels):
    """Six fixed editor rows -> list of {'name', 'level'}."""
    names = list(names or [])
    levels = list(levels or [])
    items, seen = [], {}
    for index in range(LANGUAGE_MAX):
        name = _text(names[index]) if index < len(names) else ''
        if not name:
            continue
        level = (levels[index] if index < len(levels) else '') or ''
        level = level.strip().lower()
        _check(name, 'language', LANGUAGE_LEN)
        if not level:
            raise ValueError(f'Choose a level for {name}.')
        if level not in LEVEL_LABELS:
            raise ValueError(f'Choose a level for {name}.')
        key = name.casefold()
        if key in seen:
            if seen[key] != level:
                raise ValueError(f'{name} appears twice with different levels.')
            continue
        seen[key] = level
        items.append({'name': name, 'level': level})
    return items


def _load(raw, field, ident=''):
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        log.warning('profile_fields: corrupt %s on profile %s', field, ident or 'unknown')
        return []
    if not isinstance(value, list):
        log.warning('profile_fields: corrupt %s on profile %s', field, ident or 'unknown')
        return []
    if field == 'skills':
        return [item for item in value if isinstance(item, str) and item.strip()]
    cleaned = []
    for item in value:
        if not isinstance(item, dict):
            continue
        name = item.get('name')
        level = item.get('level')
        if isinstance(name, str) and name.strip() and level in LEVEL_LABELS:
            cleaned.append({'name': name, 'level': level})
    return cleaned


def skills_of(row, ident=''):
    return _load(row['skills'] if row is not None and 'skills' in row.keys() else '', 'skills', ident)


def languages_of(row, ident=''):
    return _load(row['languages'] if row is not None and 'languages' in row.keys() else '', 'languages', ident)


def skills_json(items):
    return json.dumps(list(items or []), ensure_ascii=False)


def languages_json(items):
    return json.dumps(list(items or []), ensure_ascii=False)


def skills_field(row):
    return ', '.join(skills_of(row))


def language_rows(row):
    rows = [(item['name'], item['level']) for item in languages_of(row)]
    return rows + [('', '')] * (LANGUAGE_MAX - len(rows))


def language_line(items):
    return ' · '.join(f"{item['name']} ({LEVEL_SHORT.get(item['level'], item['level'])})" for item in items)


def public_scope(values, skills, languages):
    """Hash of exactly what a visitor would see, for the consent rule."""
    payload = {key: _text(str(values.get(key) or '')) for key in SCOPE_FIELDS}
    payload['skills'] = [item.casefold() for item in skills]
    payload['languages'] = [[item['name'].casefold(), item['level']] for item in languages]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def with_public_fields(row):
    """Dict copy of a profile row with the parsed lists attached for templates."""
    profile = dict(row)
    ident = profile.get('id', '')
    profile['skill_list'] = skills_of(row, ident)
    profile['language_list'] = languages_of(row, ident)
    profile['language_line'] = language_line(profile['language_list'])
    return profile
