-- GRN member profiles: skills, languages and the consent scope hash.
-- Additive only. Apply before deploying code that reads these columns.
-- Run inside one transaction; see apply_2026_10_21.py which also tests
-- the lock-timeout path and re-runs these statements to prove idempotency.
SET LOCAL lock_timeout = '5s';

ALTER TABLE profiles ADD COLUMN IF NOT EXISTS skills        TEXT NOT NULL DEFAULT '[]';
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS languages     TEXT NOT NULL DEFAULT '[]';
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS consent_scope TEXT NOT NULL DEFAULT '';
