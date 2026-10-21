"""Apply the skills/languages/consent_scope migration to the hosted PostgreSQL database.

Run once, before deploying code that reads the new columns:

    export ROBOTIST_DATABASE_URL=...
    python grn/migrations/apply_2026_10_21.py

Safety: every statement runs on one connection inside one transaction, so a partial
migration is impossible; lock acquisition is bounded so live traffic is never queued
behind it; the lock-timeout failure path is proven on a scratch table, never on the live
table; and the statements are re-run afterwards to prove idempotency.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import psycopg
from psycopg.rows import dict_row

from grn.profile_fields import languages_of, public_scope, skills_of

STATEMENTS = (
    "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS skills TEXT NOT NULL DEFAULT '[]'",
    "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS languages TEXT NOT NULL DEFAULT '[]'",
    "ALTER TABLE profiles ADD COLUMN IF NOT EXISTS consent_scope TEXT NOT NULL DEFAULT ''",
)
REPORT = """
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = current_schema() AND table_name = 'profiles'
ORDER BY ordinal_position
"""


def connect():
    url = os.getenv('ROBOTIST_DATABASE_URL')
    if not url:
        raise SystemExit('ROBOTIST_DATABASE_URL is not set.')
    return psycopg.connect(url, row_factory=dict_row, connect_timeout=15, autocommit=False,
                           sslmode='require', prepare_threshold=None)


def baseline(con):
    row = con.execute('SELECT count(*) AS rows, coalesce(max(version), 0) AS version FROM profiles').fetchone()
    print(f'baseline: {row["rows"]} profiles, max(version)={row["version"]}', flush=True)
    return row


def lock_timeout_test(url):
    """Prove the bounded-lock path on a scratch table, never touching profiles."""
    with connect() as holder:
        holder.execute('DROP TABLE IF EXISTS profiles_migration_probe')
        holder.execute('CREATE TABLE profiles_migration_probe (id TEXT PRIMARY KEY)')
        holder.commit()
        blocker = psycopg.connect(url, connect_timeout=15, autocommit=False, sslmode='require')
        blocker.execute('LOCK TABLE profiles_migration_probe IN ACCESS EXCLUSIVE MODE')
        runner = connect()
        try:
            runner.execute("SET LOCAL lock_timeout = '3s'")
            runner.execute('ALTER TABLE profiles_migration_probe ADD COLUMN label TEXT')
        except psycopg.errors.LockNotAvailable:
            runner.rollback()
            print('failure test: ALTER correctly aborted on lock_timeout (no change applied)', flush=True)
        else:
            raise SystemExit('failure test failed: the ALTER was not blocked by the held lock')
        finally:
            runner.close()
            blocker.rollback()
            blocker.close()
        holder.execute('DROP TABLE profiles_migration_probe')
        holder.commit()
        print('failure test: scratch table removed', flush=True)


def apply(con, label):
    con.execute("SET LOCAL lock_timeout = '5s'")
    for statement in STATEMENTS:
        con.execute(statement)
    con.commit()
    print(f'{label}: statements applied', flush=True)


def backfill(con):
    rows = con.execute('SELECT id, name, title, location, bio, academic_background, credentials, website, photo, '
                       "skills, languages FROM profiles WHERE published=1 AND consent_scope=''").fetchall()
    for row in rows:
        scope = public_scope(row, skills_of(row, row['id']), languages_of(row, row['id']))
        con.execute('UPDATE profiles SET consent_scope=%s WHERE id=%s', (scope, row['id']))
    con.commit()
    print(f'backfill: {len(rows)} published profile(s) given a baseline consent scope', flush=True)


def report(con):
    for row in con.execute(REPORT).fetchall():
        print('  {column_name:<16} {data_type:<12} null={is_nullable:<3} default={column_default}'.format(**row), flush=True)


def main():
    url = os.getenv('ROBOTIST_DATABASE_URL')
    if not url:
        raise SystemExit('ROBOTIST_DATABASE_URL is not set.')
    lock_timeout_test(url)
    with connect() as con:
        before = baseline(con)
        apply(con, 'apply')
        backfill(con)
        report(con)
    with connect() as con:
        apply(con, 're-run (idempotency)')
        after = baseline(con)
        report(con)
    if before['rows'] != after['rows']:
        raise SystemExit(f'row count changed: {before["rows"]} -> {after["rows"]}')
    print('OK: migration applied, idempotent, no rows added or removed', flush=True)


if __name__ == '__main__':
    main()
