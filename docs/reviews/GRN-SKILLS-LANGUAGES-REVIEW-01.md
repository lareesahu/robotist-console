# Review 01 — ChatGPT, 21 Oct 2026

Source: https://chatgpt.com/c/6ad8d883-825c-83e9-a477-bf82ea579ba4

Reviewed against the plan and the existing robotist-console code at commit 5b49627.

MUST FIX — production blockers

1. PostgreSQL migration on application boot is the wrong place.

The proposed ALTER TABLE ... ADD COLUMN IF NOT EXISTS runs during Flask startup, potentially once per Gunicorn worker, restart, or scale-up event.

PostgreSQL's ALTER TABLE takes an ACCESS EXCLUSIVE lock, even for these relatively inexpensive column additions. It can block production reads and writes. 
postgresql.org

Concurrent startup attempts create unnecessary lock contention.

A database permissions failure or lock timeout leaves the schema unchanged.

Required: Execute one versioned, idempotent migration before the new application is activated. Render supports pre-deploy commands on eligible paid web services; otherwise execute a controlled manual migration. Include a lock timeout and verify the resulting schema before deploying dependent code. 
Render Docs

2. The proposed migration failure handling is actively dangerous.

"A failed migration can never stop the app serving."

This is precisely backwards.

The new editor's UPDATE and the public rendering code will depend on columns that might not exist. Swallowing migration errors allows the deployment to appear healthy while profile saves fail with PostgreSQL errors.

The existing PostgresConnection wrapper also has no rollback() method. The proposed explicit rollback will not work against that interface without modification.

Required: Migration failures must fail the deployment, not become warnings. Do not serve the new version against an incompatible schema.

3. The existing consent model does not automatically authorize publishing new fields.

Skills and languages are new public disclosures.

The current profile form records approval of the specialist's exact profile details. Its consent checkbox remains checked on subsequent edits.

That means an administrator could add skills and languages to an already published profile and save without obtaining approval for those additions.

Required: Treat changes to these public fields as changes requiring fresh approval evidence. Prevent publishing materially changed profile details under stale consent. The existing consent workflow must enforce this, not merely display instructional text.

4. The storage invariant is inconsistent with the proposed default.

You propose JSON arrays stored as text, but default both fields to ''.

An empty string is not valid JSON.

That forces every reader to tolerate a value the schema deliberately creates.

Required: Use '[]' as the default for both fields, including migrations and SQLite table initialization. Make new writes produce valid JSON consistently.

For this limited feature, JSON encoded in TEXT is defensible. PostgreSQL JSONB would offer better database-level validation and future querying, but is not necessary if you deliberately accept application-enforced JSON integrity.

5. Schema compatibility and Render health are insufficiently verified.

The existing /grn/health executes SELECT 1. It does not prove that the new columns exist, that profile queries work, or that the templates can render them.

A successful deployment and HTTP 200 health response can coexist with a broken profile editor.

Required: Fail startup or deployment on missing required schema, and verify actual profile reads and writes before declaring the release successful.

6. No PostgreSQL integration tests despite changing PostgreSQL execution.

Every proposed test uses SQLite. That does not validate the production migration or the custom psycopg adapter in grn/database.py.

Required PostgreSQL tests:

Migrate an existing populated schema, then rerun the migration.

Preserve preexisting data and version numbers.

Create, edit, publish and unpublish a profile through Flask routes.

Verify transaction rollback when a save fails.

Verify optimistic locking rejects stale versions.

Simulate a migration failure and verify deployment is blocked.

7. The form's storage-to-display conversion is underspecified.

The editor expects comma-separated skills, but the database stores JSON. The language editor expects six input pairs, but storage uses JSON objects.

The existing profile() handler constructs its form model using dict(row) and manually restores submitted fields after validation errors.

Without explicit conversion in both directions, editing saved records can expose JSON syntax or overwrite data with malformed values.

Required: Separate the database representation, editable form representation and failed-submission representation. Test each transition.

8. Production editor verification is not optional.

Section 7 explicitly permits the live editor round-trip to remain unverified.

That is not an acceptable release gate for an admin feature whose primary purpose is saving member data.

Required: Obtain authorized admin access and test a private canary record against production, or establish equivalent authenticated staging verification followed by a controlled production smoke test. Never use a real member's profile as disposable test data.

SHOULD FIX — correctness, security and maintainability

9. Language validation is incomplete.

parse_languages() specifies accepted proficiency values but does not define:

Maximum length and permitted characters for language names.

Whitespace and Unicode normalization.

Handling of repeated names with conflicting levels.

Handling of a selected proficiency with no language name.

Maximum accepted raw input size.

Silent deduplication of English (Fluent) and english (Basic) is undesirable. Reject contradictory entries instead of arbitrarily keeping one.

10. Skill validation rejects legitimate skills.

Minimum two characters rejects C, an actual programming language. The restrictive character list may reject legitimate technology names.

Also, displaying the rejected input verbatim can create unnecessarily large error messages.

Use bounded input sizes, meaningful normalization and Jinja escaping. A restrictive character whitelist is not a substitute for output escaping.

11. Silently swallowing corrupted JSON hides production defects.

"skills_of(row) / languages_of(row) — never raise: bad or legacy JSON returns an empty list."

Legacy empty values should be handled. Corrupt JSON, wrong JSON types and malformed language objects are different problems.

Returning an empty list for everything hides corrupted member data.

Log detectable corruption without exposing private profile information. Add tests for malformed and incorrectly typed stored values.

12. Audit logging does not adequately cover these changes.

The existing audit entries record general saves and permission states, not exactly which public profile fields changed.

Skills and languages can affect how Robotist represents a specialist's qualifications.

Record their before/after changes and the associated approval evidence. Avoid logging unrelated confidential application details.

13. Your rollback description is misleading.

"Rollback is the commit revert."

A commit revert rolls back application code, not the database schema.

The added columns remain, and data written into them remains. That is acceptable for an additive migration, but document it accurately. Do not drop columns to roll back this release.

14. The migration needs an operational record.

Updating supabase-schema.sql changes how fresh databases are created; CREATE TABLE IF NOT EXISTS does not upgrade existing production tables.

Add a separately executable, versioned migration and record its successful application.

Before execution, verify a recoverable production backup and establish a baseline of existing profiles.

15. Test coverage misses important behavior.

Add tests for:

Editing existing profiles that already contain skills and languages.

Preserving entered values after unrelated validation failures.

Rejecting malformed levels and duplicate languages with conflicting proficiency.

Escaping public fields independently of the input whitelist.

Rejecting unauthorized and CSRF-protected modifications.

Requiring updated consent evidence for changed public fields.

Repeated POSTs and stale-version conflicts.

Rendering a published profile with malformed stored JSON.

Preserving unrelated profile fields, photo references and consent state.

The existing 13 tests plus seven broadly described cases are not sufficient release evidence.

16. Verification needs to bind the live domain to the exact deploy.

Your checks prove endpoints respond, not necessarily that the intended commit is running on the public domain.

Verify the actual deployed Git SHA, migration completion, live domain behavior, sample profile data and Render error logs.

Check the deployment's configured health-check path, not merely whether /grn/health responds when requested manually.

NICE TO HAVE — improvements that should not delay this feature

17. Make the field limits explicit in the interface. State the maximum 12 skills and six languages. A native datalist does not communicate either limit.

18. Check long-content and mobile layouts. Twelve skill chips can easily create excessive card height. Test wrapping, accessibility and narrow screens.

19. Future-proof language identifiers only if the product requires it. ISO language codes could help later, but are unnecessary for manually entered public profiles.

20. Do not prematurely normalize skills into relational tables. The current scope does not justify extra tables or joins. Validated JSON arrays are sufficient until filtering, matching or analytics become actual requirements.

VERDICT: REVISE — the boot-time migration, failure handling, consent enforcement, PostgreSQL test gap and missing production editor verification block shipping.

ChatGPT can make mistakes. Check important info.
Latest response




High
