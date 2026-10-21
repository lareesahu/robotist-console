# Reviews 02 and 03 — ChatGPT, 21 October 2026

Conversation: https://chatgpt.com/c/6ad8da81-23a0-83ea-9dc2-69ecdb358ba2

## Review 02 — version 2 of the plan, verdict REVISE

1) MUST FIX still open

#3 — Consent bypass remains. The rule checks stored.published, not the transition to submitted.published. An unpublished
profile can acquire skills/languages and later be published using old approval evidence. Require consent covering the
actual disclosed fields on every transition to published. Merely changing metadata does not establish consent.

#6 — Migration failure testing incomplete. Running the migration twice proves idempotency, not failure safety. Test lock
timeout, partial migration, and explicit prevention of deployment after migration failure.

#8 — Authenticated production verification remains open. The PostgreSQL canary exercises database operations, not the
authenticated Flask route, session handling, CSRF, form submission, or deployed template. Honest disclosure is correct,
but it does not constitute release verification. Require an authorized owner-admin smoke test before final release sign-off.

2) New MUST FIX introduced by these changes

A — Consent date requirement breaks same-day edits. Requiring both consent_date and consent_reference to change means two
legitimate approvals on the same day cannot be recorded accurately. Require new evidence tied to the exact disclosure,
without requiring a different calendar date.

B — Production canary rollback is not demonstrably safe. The plan assumes database.py operations share one transaction.
If the adapter opens independent connections or commits internally, ROLLBACK cannot undo those writes. Explicitly require
one connection, no intermediate commits, and verification that both profile and audit records are absent afterward.

C — Consent gate needs atomic enforcement. Publication state, submitted fields, approval evidence, and optimistic version
must be checked against the same current database state inside the write transaction.

3) Verdict: REVISE

Manual migration before deploy: ACCEPTABLE. Render Free has no pre-deploy command. An additive manual migration, verified
before pushing, with a fail-closed boot guard is a reasonable production strategy.
Consent rule: NOT ENOUGH. Fix publication-transition bypasses, same-day approvals, and evidence binding.
Missing admin password: ACCEPTABLE as a testing limitation, not as completed release verification.

## Review 03 — version 3 of the plan, verdict REVISE

1) MUST FIX still open

#1 — Production migration test risks an outage. Holding ACCESS EXCLUSIVE on the live profiles table blocks ordinary reads and
writes. Run the lock-timeout failure test against an isolated database, not production.

#2 — Authenticated walkthrough exposes test data publicly. Publishing a canary through a local Flask instance connected to
production PostgreSQL makes that profile visible on the actual live site until deletion. Use an isolated database for the
authenticated walkthrough; retain the rolled-back production canary for database verification.

#3 — Existing published profiles have no consent_scope. Their default '' guarantees that even an unrelated administrative
edit triggers a new-consent requirement. Backfill verified existing publication scopes or explicitly handle legacy records
without requiring fresh consent for unchanged disclosures.

2) Verdict: REVISE — three remaining production blockers, all with bounded fixes.

## Review 04 — final version, verdict SHIP

1) MUST FIX still open: None identified. All three remaining blockers from v3 are resolved in the v4 plan.

2) Verdict: SHIP — approved for implementation and deployment, conditional on the specified tests, migration verification,
and production checks passing. The unverified Render-hosted admin walkthrough is an explicitly documented limitation, not a
release blocker given the isolated authenticated route tests and rolled-back production PostgreSQL canary.
