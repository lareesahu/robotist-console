# GRN incumbent design map

Review scope: live /grn/, not a portfolio redesign. Persuade mode with an embedded application task. Single H1, split desktop hero, form in the first viewport, stacked mobile flow, fine rule-separated lower sections, native disclosure FAQ.

Shared navbar/footer source: index.html, extracted by catalog/site_shell.py; mobile interaction grn/static/site-shell.js. GRN tokens and Poppins faces: grn/static/experience.css. Hero sizing, form details and breakpoints: grn/static/hero-form.css. Form behavior: grn/static/application.js.

Protected strengths: recognizable Robotist shell and robot asset; visible hero form; clear cyan main action; content remains understandable without animated effects; independent-work and privacy expectations stated accurately.

Observed defects are recorded in ../../.ui-evidence/GRN-UI-REVIEW.md. Fix those within this system, not by creating a separate public shell.


## Implemented homepage alignment ? 2026-09-08

The user's newer correction supersedes the incumbent GRN Poppins typography. Public flow content now inherits the homepage system font tokens exposed by catalog/site_shell.py. Headings use homepage weight 600 and tracking -0.02em. Body/form tracking is normal; restrained uppercase labels remain consistent with Robotist. grn/static/robotist-foundation.css is the public-flow adaptation, loaded after existing page styles. Original homepage source and named imagery are unchanged.

Mobile intro 14px; labels 13px; inputs 16px and at least 44 CSS px (fractional rendering can report 43.99px). Anchor margin uses shared --nav-h plus 24px. New mobile keyboard disclosure focuses its first link, cycles with the toggle, closes with Escape/focus leaving/resize. These adaptations repair the reviewed flows without creating a new navbar.
