# GRN member profiles — skills and languages (dev plan v2)

Status: post-review revision. Author: Hermes. Date: 21 October 2026.
v1 review (ChatGPT, 8 MUST FIX) is recorded in `docs/reviews/GRN-SKILLS-LANGUAGES-REVIEW-01.md`.

## 1. Problem

The partner is recruiting GRN (Global Robotics Network) candidates now and needs the admin backend to
capture, per member: portrait photo, skill sets, and languages. Photo upload exists. Skill sets and
languages have no field anywhere: not in the deployed code, not in the production schema. Today they can
only be forced into the free-text "credentials" or bio boxes, and the public card cannot print them.

## 2. Target identity (evidence)

| Thing | Value | How established |
|---|---|---|
| Public origin | https://robotist.com.au/grn | 200, `x-render-origin-server: gunicorn` |
| App | `robotist-console.onrender.com`, service `srv-dbblvl0u01pc73e82ab0` | Render API; `/grn/health` → `{"service":"robotist-grn","status":"ok"}` |
| Entry point | `catalog.app:create_app()`, gunicorn, 1 worker / 4 threads | Render `startCommand` |
| Health check | `/grn/health`, `autoDeploy: yes`, plan **free** (no pre-deploy commands) | Render API |
| Deploy repo | `github.com/lareesahu/robotist-console`, `main`, HEAD 5b49627 | `git ls-remote` |
| Dev clone | `C:/Users/hunin/projects/robotist-console` | fresh clone |
| Data | hosted PostgreSQL, `ROBOTIST_DATABASE_URL` (Supabase session pooler) | Render env list; `grn/database.py` |
| Photos | Supabase storage (`grn/files.py`) | code |
| Admin | `/grn/admin/team`, one shared password, only `GRN_ADMIN_PASSWORD_HASH` stored | code + Render env |

`robotist-ecommerce` is NOT the deploy target (older `grn/` mirror, on branch `grn-form-workflow-review`).
No change is made there.

## 3. Current `profiles` schema

`id, application_id, name, title, location, bio, website, photo, consent, published, sort_order,
version, updated_at, academic_background, credentials, consent_proposals, consent_materials,
consent_reference, consent_date, agreement_status, agreement_reference`

No skills, no languages — confirmed in `grn/supabase-schema.sql` and in the live Postgres catalog.

## 4. Data design

### 4.1 Storage

* `skills TEXT NOT NULL DEFAULT '[]'` → JSON array of strings.
* `languages TEXT NOT NULL DEFAULT '[]'` → JSON array of `{"name": "...", "level": "..."}`.

`'[]'` (valid JSON), not `''`: every row the schema creates is readable without a special case.
JSON in TEXT rather than jsonb or side tables: the app reads whole profiles, has no ORM, runs the same SQL
on SQLite and PostgreSQL, and needs exactly one additive migration. Accepted cost: no SQL-level filtering
across skills; if matching or search is ever needed that is a separate change with real tables.

### 4.2 Parsing and validation — new module `grn/profile_fields.py`

Limits: 12 skills, 40 characters each, 6 languages, 40 characters each, raw input capped at 2000
characters. Allowed characters: Unicode letters, digits, space and `. + # / & ( ) - _ ' ’`. Rejected:
`< >` `"` backtick, control characters, anything else.

* `parse_skills(raw)` — split on comma, semicolon or newline; trim; collapse internal whitespace; drop
  empties; case-insensitive dedupe keeping the first spelling; 1–40 characters per item (so `C` and `R`
  are valid); more than 12 → `ValueError('Add at most 12 skills.')`; an item with a rejected character or
  an over-long item → error naming that item, truncated to 80 characters for display.
* `parse_languages(names, levels)` — six fixed rows; blank name → row ignored; name without level →
  `ValueError('Choose a level for English.')`; level must be one of `native, fluent, professional,
  conversational, basic`; the same name twice with different levels → error (never silently pick one);
  identical duplicates collapse; names validated with the rules above.
* `skills_json(...)` / `languages_json(...)` produce the stored text; `skills_field(row)` returns the
  comma-separated string for the editor; `language_rows(row)` returns six `(name, level)` pairs.
* `skills_of(row, profile_id)` / `languages_of(row, profile_id)` — `''`, `NULL` or `'[]'` → empty list.
  Genuinely corrupt JSON or a wrong JSON type logs `profile_fields: corrupt <field> on profile <id>`
  (id only, never content) and returns an empty list, so one bad row cannot take the public page down.
  Elements of the wrong type are dropped. All of this is tested.

Both fields are optional and do not change publication, consent or agreement rules on their own
(see 4.4 for the consent interaction).

### 4.3 Admin editor (`/grn/admin/team/<ident>`)

Three representations kept explicitly separate, each converted in one place and each tested:

1. **stored** — JSON text in the row;
2. **editable** — comma-separated skills string and six `(name, level)` rows, from `skills_field()` /
   `language_rows()`;
3. **failed submission** — rebuilt from `request.form` (`skills` raw string, `language_name_1..6`,
   `language_level_1..6`) so nothing typed is lost and JSON never leaks into the form.

UI:
* **Skill set (optional)** — one text input, helper "Up to 12, separated by commas. For example: ROS 2,
  PLC programming, machine vision", plus a `datalist` of twelve common suggestions. Free text allowed.
* **Languages (optional)** — six rows of `[language name] [level select]`, blank rows ignored, helper
  "Up to 6. Leave a row blank if it is not needed."
* Errors render in the existing `errors` list; typed values survive; no JavaScript framework added.

### 4.4 Consent — new public fields need new approval

Skills and languages become public the moment a published profile is saved. The existing rule (published
requires `consent` plus an approval date and evidence) covers the profile, not a disclosure added later.
Enforced in the route, not in helper text:

> If the stored profile is published and the submitted skills or languages differ from the stored values,
> the submitted `consent_date` and `consent_reference` must also differ from the stored ones.

Otherwise the save fails with: "Skills and languages are public. Record the new approval date and evidence
for this change, or unpublish the profile first." Unpublishing, editing, then republishing with fresh
approval is the other legal path. Both directions tested.

### 4.5 Team list (`/grn/admin/team`)

The row's small line gains `3 skills · 2 languages` when present.

### 4.6 Public card (`grn/templates/landing.html`, `#people`)

Skill chips under the role line; one compact line under the intro:
**Languages** — "English (Fluent) · Mandarin (Native)". Both blocks vanish when empty. Colours from the
existing GRN tokens (`#E6F2F8` text, `#24364B` rule, no magenta). Wrapping verified at 390 and 1440 px with
twelve chips so card height stays sane.

## 5. Migration (explicit, before the code)

Production has no migration runner and the Render plan is free, so there is no pre-deploy command and no
boot-time ALTER.

1. `grn/migrations/2026-10-21-profile-skills-languages.sql`:

```sql
SET lock_timeout = '5s';
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS skills    TEXT NOT NULL DEFAULT '[]';
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS languages TEXT NOT NULL DEFAULT '[]';
```

2. Applied by me against `ROBOTIST_DATABASE_URL` **before** the code deploy, by
   `grn/migrations/apply_2026_10_21.py`, which runs the statements twice (idempotency), then prints
   `information_schema.columns`. A lock timeout aborts rather than waiting behind live traffic.
3. `grn/supabase-schema.sql` gains both columns so fresh databases match production.
4. **Boot guard, not a swallowed error:** `create_app` (non-demo) runs
   `SELECT skills, languages FROM profiles LIMIT 1` once. If it fails it raises `RuntimeError`, gunicorn
   exits, `/grn/health` never answers, Render's health check rejects the deploy and the previous live
   version keeps serving. No path where new code serves against the old schema.
5. Baseline before migration: row count and `max(version)` of `profiles` recorded and printed.
6. Rollback: revert the commit. The columns stay (additive, ignored by old code) and data written into them
   is retained; no column is dropped as part of any rollback.

## 6. Tests

**SQLite / route level** (`python -m unittest grn.test_grn -v`, existing 13 + new):

1 skills round-trip: create → stored JSON → editor shows the comma string → public card shows chips.
2 dedupe and casing (`ROS 2, ros 2` → one); `C`, `R`, `R&D (firmware)`, `中文` accepted.
3 13 skills → error, version unchanged, nothing written.
4 `<script>alert(1)</script>` rejected naming the item; stored values render escaped on the public card.
5 languages round-trip with levels; missing level errors; duplicate name with two levels errors; identical
  duplicate collapses.
6 editing a profile that already has skills/languages shows them correctly (no JSON in the form).
7 failed save on an unrelated field (bad sort order) preserves typed skills and language rows.
8 published profile + changed skills + unchanged approval evidence → 400; with new evidence → saved.
9 legacy `''` row and malformed-JSON row → public card renders neither block, no stray headings, one log
  line, no 500.
10 publish/unpublish, consent flags, photo reference, audit rows and the optimistic `version` conflict
   behave as before; the audit records before→after of both new fields.
11 unauthenticated POST → redirected to login; origin/CSRF behaviour unchanged (regression test of
   existing code, nothing reimplemented).

**PostgreSQL against production, in one rolled-back transaction** (`grn/migrations/verify_2026_10_21.py`):
canary profile insert → save skills and languages → read back through `database.py`'s adapter → publish →
unpublish → stale-version update must fail → `ROLLBACK`. Proves real column types, the adapter and the
optimistic lock on the real server, and leaves no residue. Row count re-checked afterwards.

## 7. Deploy and verification

1. Commit on `main` (one commit), push → Render auto-deploys, health check `/grn/health`.
2. Deployed commit SHA via Render API must equal local `HEAD`.
3. `/grn/health` 200, `/grn/` 200, `/grn/admin/login` renders the sign-in page.
4. `information_schema` shows both columns with the `'[]'` default; existing rows untouched.
5. Local demo instance (`--demo`, own SQLite) is walked end to end: add skills and languages, publish, read
   the public card at 390 and 1440, unpublish, confirm the consent gate. Screenshots kept as evidence.
6. **Known limitation, stated not hidden:** I hold no GRN admin password (Render stores a hash only, the
   vault has no entry, her Chrome has no admin session). The live authenticated click-through on
   `robotist.com.au/grn/admin` therefore cannot be performed by me and is reported unverified. It becomes a
   three-minute walkthrough the moment she is signed in; the production write path is already covered by
   the rolled-back PostgreSQL canary.

## 8. Out of scope

Application-form fields (the partner already has candidates), skill-based search or matching, the photo
pipeline, the `robotist-ecommerce` mirror, any relational skills table.

## 9. Size

One new module, one migration plus two scripts, edits to `app.py`, `supabase-schema.sql`,
`templates/profile.html`, `templates/team.html`, `templates/landing.html`, `static/grn.css`, and tests.
One deploy.
