# Robotist website and administration

The application factory `catalog.app:create_app()` serves the existing Robotist website, the GRN landing/application flow and one authenticated management workspace. It reuses the GRN Flask application and session; there is no separate catalog login or user database.

## Routes

- `/grn/`: public Global Robotics Network landing page, published team profiles and Robert's supplied Calendly embed.
- `/grn/` hero: two-step private application submission and same-page receipt. `/grn/apply` redirects here.
- `/cart`: robot inquiry cart, quantities, customer details and request confirmation; no payment.
- `/manage/inquiries`: private customer inbox for carts, contact/modal forms and deployment requirements; status, notes and activity.
- `/manage/`: authenticated overview with real application and collection counts.
- `/manage/login`: administrator sign-in; the old `/grn/admin/login` route also works.
- `/manage/catalog/`: upload-first Robots editor, sourced proposals, human review and publication.
- `/grn/admin`: application inbox, search, decisions and private notes.
- `/grn/admin/team`: Team Members collection and photo/profile editor.

There are two CMS collections, Robots and Team Members. Applications are a review workflow. Approval creates a private team draft; publication is a separate choice requiring permission. No automatic emails or bookings are sent.

## Local operation

Install `catalog/requirements.txt`. Run from the repository root:

```text
python -m catalog.app --local --data-dir <private-directory-outside-repository> --port 8880
```

Open `/manage/`. First use asks the owner to choose a password in the browser. Later visits use sign-in. The loopback-only setup stores a password hash and stable session secret in `admin-config.json` in the private data directory. No automatic login or default admin password. This is one shared administrator credential, not individual staff accounts or an SSO system.

Keep the private directory backed up. It contains `grn.sqlite3`, `photos/`, `catalog/catalog.sqlite3`, `catalog/uploads/` and local configuration. Source documents never become public; only published images and content do. Copying a running SQLite database requires its backup API or stopping the process so WAL transactions are preserved.

## Production handoff — not deployed

The previous site is static. A persistent Python web service is needed to run these routes under the same origin. The candidate configuration is `render-grn.yaml`; it does not replace the existing static service automatically. Set `GRN_SECRET_KEY`, `GRN_ADMIN_PASSWORD_HASH` (Werkzeug password hash), and `GRN_DATA_DIR` to a persistent private directory outside the repository. Serve through HTTPS; production cookies are Secure/HttpOnly/SameSite=Lax. Public first-admin setup is disabled. On Render set `ROBOTIST_TRUST_PROXY=1`: exactly one forwarding proxy supplies the client address and HTTPS scheme for rate limits and same-origin form checks; forwarded host is not trusted. Leave this disabled for direct local serving. Verify forwarding behavior on the deployed service before domain cutover.

For real drafting set `DEEPSEEK_API_KEY` on the server. Requests go only to `https://api.deepseek.com/responses`: `deepseek-v4-flash` for text and `deepseek-v4-flash-vision-exp` when sources include images or scanned PDF pages. PDF text is extracted locally; scanned pages are rendered locally before sending to Vision (up to 30 images/pages per draft). Credentials never belong in client code. Supported empty fields are filled with unreviewed, attributed drafts. Existing/manual values are preserved; conflicting candidates remain for an explicit choice. Text quotes are checked against source text; visual evidence must be checked by the reviewer. No automatic publishing. Document import remains a separate rules-based option.

Sensitive assets: every uploaded image, and every saved product video, carries its own NSFW toggle. A flagged asset is blurred behind a veil that reveals it on click or tap on every public surface that shows a cover — the product page (hero, gallery, videos, both page families), the homepage catalogue card, the inquiry cart item and the RobotMaxx chat product card — and a flagged cover is omitted from link previews (no `og:image`). The blur is presentational, not access control: the reveal needs the file to stay fetchable. The flag is per asset, never per robot, and stays a draft change until the robot is published again.

Product videos: save up to six titled YouTube, Vimeo or public HTTPS MP4/WebM URLs. The server validates and normalizes links rather than accepting arbitrary iframe HTML. The editor previews saved videos; product previews and published snapshots render the same responsive players with no autoplay. Vimeo unlisted hashes are retained. External playback still depends on the host allowing embedding. Customer-facing catalog fields are rendered as escaped plain text, with Markdown formatting removed.

Published robot records overlay existing homepage/product/comparison/sitemap templates from one frozen database snapshot. Imported static pages stay available until replaced by a reviewed CMS publication. The two original product template families are retained. Existing prices, assets, robot categories and unrelated website components are not automatically corrected by this import.

## Verification

`python -m unittest grn.test_grn catalog.test_integration catalog.test_admin catalog.test_commerce`

Inquiry records share the private GRN database and admin authentication. Robots and quantities are snapshotted at submission. Repeated submissions reuse their request reference; stale admin edits are rejected. Source contact and requirements forms are adapted at runtime to the same-origin inbox. The original static source and historical Formspree submissions are not migrated. Quoted is a manually recorded status; no quote or customer email is sent automatically.

Browser tests on a separate local data directory cover login/logout, robot image/document upload and publication, application review, team portrait upload, publication/unpublication, and mobile layout widths. Test credentials and synthetic records are not production accounts. Live AI inference, deployment, email delivery and completed Calendly bookings remain outside verified scope.
