# Robotist Global Robotists Network

Local implementation, not deployed. Base: `lareesahu/robotist-ecommerce`, commit `c355546747da825dd7bcf6687ecedf0dd2a17c11`. GRN is independent of Edenne and does not use the existing untracked `leads/` workflow.

## Review locally

From the repository root, with Python 3.12:

```powershell
python -m pip install -r grn/requirements.txt
python -m grn.app --demo --port 5187
```

Open `http://127.0.0.1:5187/grn/`. Management: `http://127.0.0.1:5187/grn/admin`. The explicit loopback demo uses password `robotist-local-review`, displays a local-only banner, and stores its SQLite database and processed portraits in `../grn-review-data`, outside the static repository. Demo sessions expire on restart; submitted data survives. No seeded people or real applicant records are supplied. Never run demo mode as a publicly reachable service. The module's CLI binds only to 127.0.0.1.

```powershell
python -m unittest grn.test_grn -v
```

## What works

- Existing homepage navigation link and invitation between leadership and service packages.
- GRN introduction, contribution areas, process, public team directory and Robert's confirmed Calendly inline booking widget, with a direct-link fallback.
- Validated application intake with name, email, city/country, organization, professional URL, contribution area, experience, motivation, review consent and separate optional profile permission.
- Persistent application queue; search and status filters; manual pending/approved/declined decisions; private notes and timestamped action history.
- Approval creates a private profile draft. Publication requires profile details and permission. Decline or return to pending unpublishes it. No email is automatically sent.
- Team CMS also supports existing members: create private draft, edit, upload/replace portrait, order, publish and unpublish.
- Portrait upload validates actual image contents, resizes to 1200px maximum and re-encodes as JPEG without metadata. Draft photographs are not publicly accessible.
- CSRF checks, same-origin POST checks, signed HttpOnly sessions, production Secure cookies, password hashing, login/submission limits, parameterized SQL, HTML escaping, no-store responses, strict CSP and optimistic edit conflict detection.
- Duplicate email submissions receive the same confirmation and preserve the existing record; this prevents revealing who has applied and avoids overwriting an in-review application.

## Implementation plan and deployment gate

The current website is a Render static service, `robotist` (`srv-d7egikd7vvec73f79q80`). Its checked-in `render.yaml` publishes the repository root and auto-deploys `main`. The separate blog webhook is not an appropriate applicant-data store. The locally present untracked leads API has unauthenticated read/update routes. Neither is modified here.

1. **Completed locally:** add the GRN module and narrowly scoped homepage entry points; test intake, review, profile management, storage and privacy boundaries.
2. **Content review before release:** confirm final application questions, contribution categories, membership criteria and public copy. These are proposed defaults, not founder-approved policy. Do not imply guaranteed jobs, earnings, acceptance, response times or existing network size. Approvals remain human decisions.
3. **Account/storage decision:** choose the Robotist-owned service/account. Run this module as one Python web service with a persistent disk outside the source tree (e.g. `/var/data/robotist-grn`). A single-instance SQLite service is sufficient for this initial review workload. Configure backups of the database AND portraits; use SQLite's backup API or a consistent snapshot, not an arbitrary copy during writes. Multi-instance deployment requires a shared database and object storage migration first.
4. **Production configuration:** provide `GRN_SECRET_KEY` (random persistent secret), `GRN_ADMIN_PASSWORD_HASH` (Werkzeug-generated hash of a strong operator password), and `GRN_DATA_DIR`. Install `grn/requirements.txt`, start `gunicorn 'grn.app:create_app()' --bind 0.0.0.0:$PORT --workers 1`. Production cookies require HTTPS. No live credential is embedded or stored in this repository.
5. **Same-origin routing:** route `/grn/*` and `/grn` from the Robotist domain to the GRN service while preserving paths, cookies and the external host. Configure a trusted reverse proxy deliberately; the app does not blindly trust forwarded headers. If routing via a subdomain instead, set an explicit Robotist home/privacy base URL in templates before release. Verify browser cookies, form POSTs, redirects and uploaded images through the final public origin. Static hosting alone cannot execute these Python routes. No rewrite or Render changes have been made.
6. **Static publish exclusion:** the static site currently publishes `.`. Before any push, make the static build publish only the website files or otherwise exclude `grn/` Python/templates/tests, `leads/`, `webhook/`, dependency trees and private build files. Never store the database, passwords, backups or raw uploads in the static tree. The application actively refuses an in-repo data directory. Do not deploy the homepage links before the `/grn/` route works.
7. **Calendly:** the parent task supplied Robert's confirmed event during implementation: `https://calendly.com/robertvicencio/30min`, using `https://assets.calendly.com/assets/external/widget.js`. The earlier placeholder is superseded. The public landing page alone permits the Calendly script/frame/style domains; management pages retain a no-script CSP. Booking has a direct-link fallback. Verify the event, time zone, mobile layout and booking flow before release; no appointment has been booked by this task.
8. **Release verification:** production HTTPS/cookie test, authorization test, actual upload/publication/unpublish cycle, storage restart recovery, backup restore, edge rate limiting and applicant privacy review. Confirm GRN-specific privacy wording and a manual contact/retention/deletion procedure. The current link uses the existing site policy; its applicability to GRN is not assumed verified.
9. **Separate approval:** deploy/publish only after explicit release authorization. This task does not push, alter a Render service, send applicant email, change accounts or configure a recurring job.

## Operational limitations

This first management version has one shared administrator credential, not individual accounts or role-based access. Audit events show actions and times, not individual reviewer attribution. Rotate the shared password plus session secret to invalidate old sessions. A future shared catalog management shell can reuse the application factory/auth/storage conventions, but the catalog is not integrated here.

Application limits are per socket IP in SQLite. Behind a proxy this can group visitors under one proxy address; add trusted edge throttling before release. Anonymous users cannot retrieve applications or status by email. Application correction/contact and retention/deletion are manual operations, not implemented self-service flows. Photos replaced or unpublished remain in private storage for recoverability; define retention before production.

The local preview serves existing public website assets only for integration review. It does not prove existing third-party catalogue widgets, lead submission or other unrelated services work locally. No existing founder profiles are silently migrated into GRN.

## Original brief evidence

Parent session `01a07ada-e746-7060-8941-ae0ca3165b55`, original JSONL `C:/Users/hunin/.codex/sessions/2026/09/07/rollout-2026-09-07T15-52-41-01a07ada-e746-7060-8941-ae0ca3165b55.jsonl`: line 54 requests landing integration, team CMS, application review and Robert's Calendly; line 128 confirms **Global Robotists Network**; lines 263 and 277 authorize starting. The delegated task limits execution to local work without publication.


### Calendly observation — 7 September 2026
The supplied `/robertvicencio/30min` event loads successfully in the local inline widget but currently displays **15 Minute Meeting / 15 min** in Calendly. The public GRN copy is duration-neutral. No provider settings were changed and no booking was made.


## 8 September 2026 update

Current name: Global Robotics Network, superseding the historical name above after user approval. Admin profile permissions now record website/proposals/capability-material scope, approval date and evidence. Agreement status/reference are private and independent from application approval. Existing records are preserved, with missing older permission evidence flagged on edit. No signing, automatic email or deployment occurs.
