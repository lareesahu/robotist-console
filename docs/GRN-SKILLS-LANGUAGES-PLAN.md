# GRN member profiles — skills and languages (dev plan, final)

Status: FINAL (fourth revision). Closes review 01 (8 MUST FIX), review 02 (5 MUST FIX) and review 03 (3 MUST
FIX). Author: Hermes. Date: 21 October 2026. Reviews kept in `docs/reviews/`.

## 1. Problem

The partner is recruiting GRN (Global Robotics Network) candidates now and needs the admin backend to
capture, per member: portrait photo, skill sets, and languages. Photo upload exists. Skill sets and
languages have no field anywhere — not in the deployed code, not in the production schema. Today they can
only be forced into the free-text "credentials" or bio boxes, and the public card cannot print them.

## 2. Target identity (evidence)

| Thing | Value | How established |
|---|---|---|
| Public origin | https://robotist.com.au/grn | 200, `x-render-origin-server: gunicorn` |
| App | `robotist-console.onrender.com`, service `srv-dbblvl0u01pc73e82ab0` | Render API; `/grn/health` → `{"service":"robotist-grn","status":"ok"}` |
| Entry | `catalog.app:create_app()`, gunicorn, free plan, `autoDeploy: yes`, health check `/grn/health` | Render API |
| Deploy repo | `github.com/lareesahu/robotist-console`, `main`, HEAD 5b49627 | `git ls-remote` |
| Dev clone | `C:/Users/hunin/projects/robotist-console` | fresh clone |
| Data | hosted PostgreSQL via `ROBOTIST_DATABASE_URL` | Render env list; `grn/database.py` |
| Admin | `/grn/admin/team/<id>`, one shared password (only its hash stored) | code + Render env |

`robotist-ecommerce` is not the deploy target (older `grn/` mirror on a review branch). No change there.

## 3. Current `profiles` schema

`id, application_id, name, title, location, bio, website, photo, consent, published, sort_order, version,
updated_at, academic_background, credentials, consent_proposals, consent_materials, consent_reference,
consent_date, agreement_status, agreement_reference` — no skills, no languages (verified in
`grn/supabase-schema.sql` and in the live catalogue).

## 4. Data design

### 4.1 Columns

* `skills TEXT NOT NULL DEFAULT '[]'` — JSON array of strings.
* `languages TEXT NOT NULL DEFAULT '[]'` — JSON array of `{"name","level"}`.
* `consent_scope TEXT NOT NULL DEFAULT ''` — SHA-256 over the public disclosure fields, recording exactly
  what the current approval covers (see 4.4).

`'[]'` is valid JSON, so every schema-created row reads without a special case. JSON in TEXT instead of
side tables or `jsonb`: the app reads whole profiles, has no ORM, runs the same SQL on SQLite and
PostgreSQL, and needs one additive migration. Cost accepted: no SQL-level filtering across skills.

### 4.2 `grn/profile_fields.py` (new)

Limits 12 skills / 40 chars, 6 languages / 40 chars, raw input capped at 2000 chars. Allowed: Unicode
letters, digits, space, `. + # / & ( ) - _ ' ’`. Rejected: `< > "` backtick, control characters.

* `parse_skills(raw)` — split on comma, semicolon or newline; trim; collapse inner whitespace; drop empties;
  case-insensitive dedupe keeping first spelling; 1–40 chars (`C`, `R` valid); >12 → `ValueError`.
  A bad item raises an error naming it, truncated to 80 chars.
* `parse_languages(names, levels)` — 6 rows; blank name ignored; name without level → error naming the
  language; level ∈ `native, fluent, professional, conversational, basic`; same name twice with different
  levels → error; identical duplicates collapse.
* `skills_json`, `languages_json`, `skills_field(row)` (comma string for the editor), `language_rows(row)`
  (six `(name, level)` pairs), `skills_of(row, id)`, `languages_of(row, id)` — `''`/`NULL`/`'[]'` → `[]`;
  corrupt JSON logs `profile_fields: corrupt <field> on profile <id>` (id only) and returns `[]`; wrong
  element types dropped. One bad row can never break the public page.
* `public_scope(profile_dict)` — the hash used by the consent rule; covers name, title, location, bio,
  academic_background, credentials, website, photo, skills, languages.

### 4.3 Editor (`/grn/admin/team/<ident>`)

Stored / editable / failed-submission are kept separate and converted in one place each:
`skills_field()` + `language_rows()` for the form; on error the page rebuilds from `request.form`
(`skills`, `language_name_1..6`, `language_level_1..6`), so typed input survives and JSON never reaches the
form. UI: **Skill set (optional)** — one input with the helper "Up to 12, separated by commas. For example:
ROS 2, PLC programming, machine vision" and a `datalist` of twelve suggestions; **Languages (optional)** —
six `[name] [level select]` rows, helper "Up to 6. Leave a row blank if it is not needed." No JS framework.

### 4.4 Consent — bound to the exact public disclosure, atomic

The route already does everything inside `BEGIN IMMEDIATE`, which becomes
`pg_advisory_xact_lock(726268191)` on PostgreSQL and serialises writers, so the checks below are atomic with
the write (review 02 #C). After that lock the route re-reads the current row and compares it with the
submission:

> If the profile will be published, and the hash of the submitted public fields differs from the stored
> `consent_scope`, then the submitted `consent_reference` must differ from the stored one.

Failure message: "This changes what is shown publicly. Record the new approval evidence reference for this
change, or unpublish the profile." On every successful save with `published=1`, `consent_scope` is set to
the submitted hash; the audit log records the reference change and the skills/languages before→after.

Why this is the right rule: evidence text (not calendar date) is what changes, so two approvals on the same
day are recordable (review 02 #A); a first publication moves the reference from empty to the actual evidence
so it passes; an unpublished profile whose public fields changed and is then published with the stale
reference is blocked (review 02 #3, the transition bypass); nothing is required when public fields are
unchanged.

### 4.5 Team list and public card

Team list row gains `3 skills · 2 languages`. Public card (`landing.html#people`) gains skill chips under
the role line and one compact line under the intro: **Languages** — "English (Fluent) · Mandarin (Native)".
Both vanish when empty. GRN tokens only (`#E6F2F8` text, `#24364B` rule, no magenta). Wrapping checked at 390
and 1440 px with twelve chips.

## 5. Migration (explicit, atomic, before the code)

Render free plan has no pre-deploy command, so no boot-time ALTER (review 02: manual-before-deploy accepted).

`grn/migrations/2026-10-21-profile-skills-languages.sql`:

```sql
SET LOCAL lock_timeout = '5s';
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS skills        TEXT NOT NULL DEFAULT '[]';
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS languages     TEXT NOT NULL DEFAULT '[]';
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS consent_scope TEXT NOT NULL DEFAULT '';
```

`grn/migrations/apply_2026_10_21.py` runs all three inside **one transaction** (so a partial migration is
impossible), on one connection, `autocommit=False`, and:

1. prints the baseline (`count(*)`, `max(version)`) before touching anything;
2. **failure test first, on an isolated probe table:** creates `profiles_migration_probe`, holds
   `ACCESS EXCLUSIVE` on that probe from a second connection, runs the same DDL against it with
   `lock_timeout='3s'`, asserts a lock timeout, then drops the probe. The live `profiles` table is never
   locked by a test (review 03 #1).
3. applies for real, commits, prints `information_schema.columns`;
4. **backfill baseline scopes:** for rows with `published=1 AND consent_scope=''`, computes the scope
   hash of their stored public fields and writes it, so an unrelated administrative edit does not demand
   fresh consent while any real public change still does (review 03 #3). Prints the row count; a no-op when
   there are no published rows;
5. re-runs the whole thing (idempotency) and prints a second, identical catalogue report;
6. exits non-zero on any unexpected result. **I check the exit code before pushing; nothing is deployed
   unless it is zero** — that is the explicit prevention of deploying after a migration failure.

`grn/supabase-schema.sql` gains all three columns so fresh databases match production.

**Boot guard, fail closed:** `create_app` (non-demo) runs `SELECT skills, languages, consent_scope FROM
profiles LIMIT 1`. On failure it raises `RuntimeError`; gunicorn exits, `/grn/health` never answers, Render
keeps the previous deployment serving. Rollback = revert the commit; columns stay, data stays, no drop.

## 6. Tests

**SQLite / route level** (`python -m unittest grn.test_grn -v`, 13 existing + new):

1 skills round-trip create → JSON → editor comma string → public chips.
2 dedupe/casing; `C`, `R`, `R&D (firmware)`, `中文` accepted.
3 13 skills → error, version unchanged, nothing written.
4 `<script>alert(1)</script>` rejected by name; stored values escaped on the public card.
5 languages round-trip; missing level errors; duplicate name with two levels errors; identical duplicate
  collapses.
6 editing an existing profile shows skills/languages correctly (no JSON in the form).
7 failed save on an unrelated field preserves typed skills and language rows.
8 consent: published profile + changed skills + unchanged reference → error; with a new reference → saved
  and `consent_scope` updated; unpublished draft + changed fields + old reference → publish blocked;
  first publication with fresh evidence → allowed.
9 legacy `''` row and malformed-JSON row → no stray headings, no 500, one log line.
10 publish/unpublish, consent flags, photo reference, audit rows and the version conflict behave as before.
11 unauthenticated POST → login redirect (regression test of existing behaviour).

**PostgreSQL, production server, rolled back** (`grn/migrations/verify_2026_10_21.py`): one connection,
`autocommit=False`, no intermediate commit (review 02 #B): insert canary profile → write skills/languages →
read back through `database.py` → publish → unpublish → stale-version update must fail → `ROLLBACK`;
`connection.info.transaction_status` asserted INTRANS before the rollback; then a **fresh** connection
asserts zero canary rows, zero canary audit rows and unchanged counts.

**Authenticated walkthrough on an isolated database** — executed in a real browser (Playwright) against a local
demo instance on its own SQLite file; screenshots in `docs/reviews/evidence/`: real `/grn/admin/login` session, real
templates, real routes: sign in → create a member → save skills and languages → publish → read the public GRN
page rendered by that instance (chips, language line, 390 and 1440 px) → confirm the consent gate rejects a
silent public change → unpublish → delete the member. Nothing is written to production and no test profile can
appear on the live site (review 03 #2). The production write path is covered only by the rolled-back canary.
What stays outside my reach is a click on the Render-hosted admin page itself, because I hold no admin
password — reported as such, never as verified.

## 7. Deploy and verification

1. Migration applied, backfilled where needed, and verified (section 5, exit code 0).
2. One commit on `main`, pushed → Render auto-deploy, health check `/grn/health`.
3. Deployed commit SHA from the Render API must equal local `HEAD`.
4. `/grn/health` 200, `/grn/` 200, `/grn/admin/login` renders the sign-in page.
5. Live site's published profiles unchanged; `information_schema` shows the three columns with defaults.
6. Result reported with what is verified and the one thing that is not (the Render-hosted admin click),
   plus the local walkthrough evidence.

## 8. Out of scope

Application-form fields (the partner already has candidates), skill-based search or matching, the photo
pipeline, `robotist-ecommerce`, any relational skills table.

## 9. Size

One new module, one migration + three scripts, edits to `app.py`, `supabase-schema.sql`,
`templates/profile.html`, `templates/team.html`, `templates/landing.html`, `static/grn.css`, tests. One deploy.
