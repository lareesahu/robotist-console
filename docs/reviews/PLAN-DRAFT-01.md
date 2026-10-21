# GRN member profiles — skills and languages (dev plan)

Status: draft for review. Author: Hermes. Date: 21 October 2026.

## 1. Problem

The partner is recruiting GRN (Global Robotics Network) candidates now and needs the admin backend to
capture, per member: portrait photo, skill sets, and languages. Photo upload exists. Skill sets and
languages have no field anywhere: not in the deployed code, not in the production schema. Today they
can only be forced into the free-text "credentials" or bio boxes, and the public card cannot print
them.

## 2. Target identity (evidence, not assumption)

| Thing | Value | How established |
|---|---|---|
| Public origin | https://robotist.com.au/grn | 200, `x-render-origin-server: gunicorn`, `Cache-Control: no-store` |
| App service | robotist-console.onrender.com, service id `srv-dbblvl0u01pc73e82ab0` | Render API list (second workspace), `/grn/health` → `{"service":"robotist-grn","status":"ok"}` |
| Deploy repo | `github.com/lareesahu/robotist-console`, branch `main` | Render API `repo` field |
| Dev clone | `C:/Users/hunin/projects/robotist-console` | fresh clone of `main` @ 5b49627 |
| Data store | hosted PostgreSQL via `ROBOTIST_DATABASE_URL` | `grn/database.py`, `grn/app.py` config |
| Photos | Supabase storage via `ROBOTIST_SUPABASE_URL/KEY` (`grn/files.py`) | code |
| Admin surface | `/grn/admin` → `/grn/admin/team`, `/grn/admin/team/<id>` | code + live 302 to login |
| Admin auth | one shared password, `GRN_ADMIN_PASSWORD_HASH` env | code |

`robotist-ecommerce` is NOT the deploy target. It holds an older mirror of `grn/` (no `captcha.py`,
`notify.py`, `screening.py`; a newer unused workflow layer; local checkout sits on branch
`grn-form-workflow-review`). Changes must not be made there.

## 3. Current `profiles` schema (production)

`id, application_id, name, title, location, bio, website, photo, consent, published, sort_order,
version, updated_at, academic_background, credentials, consent_proposals, consent_materials,
consent_reference, consent_date, agreement_status, agreement_reference`

No skills, no languages. Confirmed in `grn/supabase-schema.sql` and in the live Postgres catalog.

## 4. Design

### 4.1 Storage

Two additive text columns on `profiles`:

* `skills TEXT NOT NULL DEFAULT ''` → JSON array of strings.
* `languages TEXT NOT NULL DEFAULT ''` → JSON array of `{"name": "...", "level": "..."}`.

Choice: JSON inside the existing single-table design rather than new `skills` / `languages` tables.
Reasons: no joins, no ORM, identical code on SQLite and PostgreSQL, one additive ALTER, trivially
reversible, and the read path is a whole-profile read today. Accepted cost: no SQL-level aggregation
or filtering across skills. If skill-based search or matching is ever needed, that is a separate
planned change with real tables; it is not needed for capture, display or partner review.

### 4.2 Validation and parsing (server-side, single home)

New module `grn/profile_fields.py`:

* `parse_skills(raw)` — split on comma, semicolon or newline; trim; collapse internal whitespace;
  drop empties; case-insensitive dedupe keeping the first spelling; max 12 items; each 2–40 chars;
  allowed characters: letters, digits, space and `. + # / & ( ) - _`; anything else (including
  `< > " ' ` ` and control characters) is rejected with the offending item named in the error.
* `parse_languages(names, levels)` — six fixed rows; a row with a blank name is ignored; a name with
  no level raises "Choose a level for X."; level must be one of `native, fluent, professional,
  conversational, basic`; duplicate names deduped case-insensitively; max 6 by construction.
* `skills_of(row)` / `languages_of(row)` — never raise: bad or legacy JSON returns an empty list.

Both fields optional. They do not change publishing rules, consent recording or the agreement status.

### 4.3 Admin editor (`/grn/admin/team/<ident>`)

* After "Relevant credentials": **Skill set (optional)** — one text input, helper text
  "Separate with commas, for example: ROS 2, PLC programming, machine vision", plus a `datalist` of
  twelve common suggestions. Free text stays allowed; no chips widget, no JavaScript framework.
* New block **Languages (optional)** — six rows of `[language name] [level select]`, blank rows
  ignored. Levels: Native or bilingual / Fluent / Professional / Conversational / Basic.
* Errors render in the existing `errors` list above the form; the typed values survive a failed save.

### 4.4 Team list (`/grn/admin/team`)

The row's small line gains `3 skills · 2 languages` when present, so completeness is visible without
opening each profile.

### 4.5 Public card (`/grn/templates/landing.html`, `#people`)

* Skill chips directly under the role line.
* A single compact line under the intro: **Languages** — "English (Fluent) · Mandarin (Native)".
* Both blocks disappear entirely when empty.

## 5. Schema change and migration

Production has no migration runner: `create_app` creates and alters tables only on the SQLite path;
the hosted PostgreSQL schema was created manually from `supabase-schema.sql`. The plan therefore:

1. Adds both columns to `grn/supabase-schema.sql` (documentation of record).
2. Extends the existing boot-time column check to run on **both** engines:
   * SQLite: current `PRAGMA table_info(profiles)` check plus `ALTER TABLE ... ADD COLUMN`.
   * PostgreSQL: `ALTER TABLE profiles ADD COLUMN IF NOT EXISTS skills TEXT NOT NULL DEFAULT ''`
     (same for `languages`), executed once at boot, inside `try/except` with an explicit rollback and
     a log line, so a failed migration can never stop the app serving.
3. Verifies the live catalog after deploy through `information_schema.columns`.

No destructive statement, no data backfill; existing rows read as empty lists. Rollback is the
commit revert — old code ignores the added columns.

## 6. Tests (`grn/test_grn.py`, unittest, temporary SQLite per test)

1. Skills round-trip: save "ROS 2, PLC programming" → stored as JSON, editor shows both, public card
   shows two chips.
2. Dedupe and casing: "ROS 2, ros 2" → one item, first spelling kept.
3. Over the limit: 13 skills → error shown, profile version unchanged, nothing saved.
4. Rejected characters: `<script>alert(1)</script>` produces an error naming the item; `R&D (firmware)`
   is accepted and renders escaped on the public card.
5. Languages round-trip with levels; duplicate "English"/"english" deduped; missing level errors.
6. Legacy row with empty strings → public card renders neither block, no stray headings.
7. Publish/unpublish, consent flags and the audit line behave exactly as before.

Gate: `python -m unittest grn.test_grn -v` — 13 existing tests plus the new ones, all green before
any push.

## 7. Deploy and verification

1. Commit on `main` in `robotist-console` (single commit, message naming the change).
2. Confirm the Render service has `autoDeploy: true` for `main` before pushing; push triggers the deploy.
3. Watch the deploy reach live (`/grn/health` ok, `/grn/` 200, `/grn/admin/login` 200).
4. Check the live PostgreSQL catalog for `skills` and `languages`; confirm no published profile changed.
5. Local demo-mode end-to-end with a real published profile: create draft → add skills and languages →
   publish → read the public card → unpublish. Screenshots as evidence.
6. Live editor round-trip needs the shared admin password, which is only stored as a hash on Render.
   If no credential exists in the vault, this step is reported as unverified with the reason, not
   claimed.

## 8. Out of scope

Application-form fields for skills and languages (the partner already has candidates), skill-based
search or matching, photo pipeline, and any change in `robotist-ecommerce`.

## 9. Size

One new module, edits to `app.py`, `supabase-schema.sql`, `templates/profile.html`,
`templates/team.html`, `templates/landing.html`, `static/grn.css`, plus the test file. One deploy.
