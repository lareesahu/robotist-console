"""Prove the new profile columns work on the production PostgreSQL server without leaving residue.

Every write happens on one connection inside one transaction that is rolled back at the end;
the assertions afterwards use a fresh connection and must show nothing was kept.

    export ROBOTIST_DATABASE_URL=...
    python grn/migrations/verify_2026_10_21.py
"""
import json
import os
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import psycopg
from psycopg import pq
from psycopg.rows import dict_row

from grn.database import connect as adapter_connect
from grn.profile_fields import languages_of, public_scope, skills_of


def url():
    value = os.getenv('ROBOTIST_DATABASE_URL')
    if not value:
        raise SystemExit('ROBOTIST_DATABASE_URL is not set.')
    return value


def counts(con):
    return {
        'profiles': con.execute('SELECT count(*) AS n FROM profiles').fetchone()['n'],
        'audit': con.execute('SELECT count(*) AS n FROM audit').fetchone()['n'],
    }


def check(condition, message):
    if not condition:
        raise SystemExit('FAIL: ' + message)
    print('ok: ' + message, flush=True)


def main():
    ident = 'canary-' + uuid.uuid4().hex
    canary = con = psycopg.connect(url(), row_factory=dict_row, connect_timeout=15, autocommit=False,
                                   sslmode='require', prepare_threshold=None)
    before = counts(canary)
    try:
        canary.execute('INSERT INTO profiles(id,name) VALUES (%s,%s)', (ident, 'Migration canary'))
        row = canary.execute('SELECT skills,languages,consent_scope,version FROM profiles WHERE id=%s', (ident,)).fetchone()
        check(row['skills'] == '[]' and row['languages'] == '[]' and row['consent_scope'] == '',
              'new columns default to [] and an empty scope')

        skills = ['ROS 2', 'PLC programming']
        languages = [{'name': 'English', 'level': 'fluent'}, {'name': 'Mandarin', 'level': 'native'}]
        scope = public_scope(row | {'name': 'Migration canary', 'title': '', 'location': '', 'bio': '', 'academic_background': '',
                                    'credentials': '', 'website': '', 'photo': ''}, skills, languages)
        canary.execute('UPDATE profiles SET skills=%s,languages=%s,consent_scope=%s,published=1,consent=1,'
                       'consent_reference=%s,version=version+1 WHERE id=%s AND version=%s',
                       (json.dumps(skills, ensure_ascii=False), json.dumps(languages, ensure_ascii=False), scope,
                        'Canary approval evidence', ident, row['version']))
        saved = canary.execute('SELECT * FROM profiles WHERE id=%s', (ident,)).fetchone()
        check(skills_of(saved, ident) == skills and languages_of(saved, ident) == languages,
              'skills and languages round-trip through the JSON columns')
        check(saved['published'] == 1 and saved['consent_scope'] == scope, 'publication and consent scope stored')

        canary.execute('UPDATE profiles SET published=0 WHERE id=%s', (ident,))
        check(canary.execute('SELECT published FROM profiles WHERE id=%s', (ident,)).fetchone()['published'] == 0,
              'unpublish works')

        stale = canary.execute('UPDATE profiles SET name=%s WHERE id=%s AND version=%s', ('Other', ident, 1))
        check(stale.rowcount == 0, 'stale version update is rejected')

        check(canary.info.transaction_status == pq.TransactionStatus.INTRANS,
              'all canary writes are still inside one uncommitted transaction')
    finally:
        canary.rollback()

    after_connection = psycopg.connect(url(), row_factory=dict_row, connect_timeout=15, autocommit=False,
                                       sslmode='require', prepare_threshold=None)
    after = counts(after_connection)
    check(after_connection.execute('SELECT 1 FROM profiles WHERE id=%s', (ident,)).fetchone() is None,
          'canary row is gone after rollback')
    check(before == after, f'row counts unchanged ({after})')
    after_connection.close()

    adapter = adapter_connect(None, url())
    row = adapter.execute('SELECT id,skills,languages,consent_scope FROM profiles LIMIT 1').fetchone()
    if row is not None:
        skills_of(row, row['id']), languages_of(row, row['id'])
    adapter.close()
    print('OK: production schema verified, canary rolled back, no residue', flush=True)


if __name__ == '__main__':
    main()
