## 2026-10-13 - Notifications: why the mail never left, and the route that works

The notification was configured correctly all along - `NOTIFY_EMAILS` on the service already reads
`lareesa@robotist.com.au,robert@robotist.com.au`, and the sending code has been live since 12 October.
Nothing arrived because **Render blocks outbound SMTP**: a free web service cannot open a connection to
ports 25, 465 or 587, so `smtp.zoho.com:465` times out. The service's own log agrees, and it is the
only notification line in four days, written two minutes after the deploy that added the feature:

    [notify] inquiry RQ-7D48B8DE55 stored; mail failed: timed out

`grn/notify.py` now chooses a delivery route instead of assuming SMTP: **Resend over HTTPS**
(`RESEND_API_KEY`), then the **Zoho Mail API over HTTPS** (`ZOHO_MAIL_CLIENT_ID`, `ZOHO_MAIL_CLIENT_SECRET`,
`ZOHO_MAIL_REFRESH_TOKEN`), then plain SMTP for a host that allows it. Whichever is configured gets used;
with none configured the site behaves exactly as before. `MAIL_FROM` overrides the From address, the log
line now names the route and the reason, and a failed SMTP send says in the log that this host blocks it.
Both HTTPS routes keep the spam gate and stay fail-open: a mail problem never breaks a visitor's submission.

Neither HTTPS route is live yet, and each is one credential away: Resend answers
`The robotist.com.au domain is not verified` (the account's key is valid - it is a sending-only key, so
listing domains is refused - but the domain itself has to be added and verified with DNS records), and the
Zoho Mail API needs an API client created in the Zoho account. Either way it is a switch to flip, not a
code change, and no deploy.

- Verification: `python -m pytest -q catalog grn` = 110 passed, including 12 new tests in
  `catalog/test_notify_routes.py` covering route order, the Resend payload, the Zoho token swap and
  message post, the refusal logs, and that the spam gate still wins over any route.
- Diagnosis evidence: Render's changelog "Free web services will no longer allow outbound traffic to SMTP
  ports" (25, 465 and 587 blocked since 26 September 2025); the log line above; and a direct HTTPS probe
  against Resend returning `domain is not verified`.

## 2026-10-13 - Spam can be deleted, and the form can ask for a human

Every inquiry the console showed had to be kept: there was no way to remove one, so spam piled up in
the list next to real leads. `/manage/inquiries` now carries a checkbox per row, a Delete control per
row and a bulk "Delete selected" action, and the inquiry page has its own. Deleting is a real delete —
the row and the customer's answers stop existing — because that is the point of clearing spam and an
archive nobody opens helps nobody. It is not silent: each deletion writes one line to the activity log
naming the reference and the contact it came from. Both routes also require the console's session
token, so a stale or forged post is refused, and both are behind the admin check.

The captcha half is Google reCAPTCHA, wired so the keys switch it on rather than the code.
`grn/captcha.py` asks Google to confirm a submission when `GRN_RECAPTCHA_SECRET` is set; the public
inquiry script carries `GRN_RECAPTCHA_SITE_KEY` to the browser (invisible v3, and a v2 checkbox on the
form works unchanged). With either value missing the check is skipped and the site behaves exactly as
it did before. A captcha that cannot be reached lets the submission through on purpose: no bot can
cause that, and dropping a real customer's message is worse than one missed check.

Console confirmations live in `assets/manage.js`, served at `/assets/manage.js`, because the `/manage`
pages run under `script-src 'self'` and cannot carry an inline handler.

- Verification: `python -m pytest -q catalog grn` = 98 passed, including 17 new tests in
  `catalog/test_inquiries_admin.py` for single and bulk deletion, the session-token and admin guards,
  the audit line, the console controls, and captcha off / unanswered / confirmed / low score /
  unreachable. Served locally on this main-based worktree and looked at `/manage/inquiries` at 1280:
  three rows, one checkbox each, badge and Delete in their own right-hand column, bulk action under the
  list.

## 2026-10-12 - A new inquiry or application now e-mails the team

Both intake paths stored their rows in the database and stopped there: nothing left the server when a
visitor sent the contact form, the deployment requirements form, the cart request or a GRN
application, so a lead could sit unseen in the console. `grn/notify.py` is now the one place that
hands a new submission to e-mail, wired into `catalog/commerce.py` (every inquiry source) and
`grn/app.py` (applications). It reads `ZOHO_EMAIL`, `ZOHO_APP_PASSWORD` and `NOTIFY_EMAILS` from the
service environment; until those are set the site behaves exactly as before and logs one line per
submission.

The mailer is deliberately fail-open: the row is already committed before the mail is attempted, so
a mail problem becomes one log line and never fails the visitor's submission. Obvious spam - the
same keyword list, blocked mail domains, link-heavy and gibberish rules as the leads pipeline - is
stored but not mailed, keeping the notification channel signal-only. Each inquiry mail carries the
reference, source, contact fields, message and the cart or requirements detail, with a Reply-To of
the submitter so answering goes straight to the lead.

`catalog/test_notify.py` covers the mailer with a recorded SMTP double: recipients and Reply-To,
spam kept out of the inbox, a broken mail server leaving the stored submission intact, unconfigured
deployments staying quiet, and both live flows mailing exactly once per new row.

## 2026-10-11 - Headings are bold, from one rule

Every heading on the site is bold now: the H1 and everything below it. The pages had drifted to
600 on headings and the brand book's section titles to a 300 light weight, so "bold" was not what
any of them rendered. Lareesa's direction, 11 October 2026: "the headings especially H1 should
always be bold".

`HEADING_WEIGHT` in `catalog/site.py` is injected by `consent()` - the one point every HTML
response already passes through - as `h1,h2,h3,h4,h5,h6{font-weight:700 !important}`. The pages
dress headings with classes (`.hero-h1`, `.section-title`) and some set the weight inline, so
`!important` is what lets one rule hold against 25 page stylesheets and any future generator.
Checked: h1/h2/h3 compute to 700 on the homepage, about, compare, FAQ, cookies, terms, a product
page, the 404 page and the brand centre, at 1440 and 375, with no horizontal overflow.

The brand centre's hero wordmark is the deliberate exception: it is the logo, the guide documents
it as Poppins Medium 500 and says it must never be altered, so the brand-centre builder re-asserts
`.hero-wordmark{font-weight:500 !important}` in its publication overrides. The guide's section
titles are headings and are bold.

## 2026-10-11 - The brand centre is the delivered brand guide

`/brand-center` served a re-typeset copy of `docs/brand/BRAND_CENTER.md` — the record of how this
site implements the brand, not the brand itself. The page is now the identity document that came
with the brand system: `docs/brand/reference/robotist-brand-guide.html`, published at

    https://www.robotist.com.au/brand-center

`catalog/build_brand_center_page.py` copies that document into `brand-center.html` and makes two
changes: its three Google Fonts links become local @font-face rules over
`assets/fonts/poppins/*.woff2` (a published page in this repository never depends on a font CDN),
and the head gains a description, a canonical address, Open Graph tags and the site favicon.
A small "publication overrides" block stops the guide's `1fr` grids and its widest tables from
pushing a narrow viewport sideways — the document is otherwise untouched, so it stays identical to
what was delivered. Poppins now ships in this repository in five weights, converted to woff2.

## 2026-09-30 - Automation: the site's derived content follows the live catalogue by itself
- catalog/sync_site_content.py is the one command that keeps everything copied out of the catalogue in step with it: the Maxx knowledge block (between /*MAXX-KNOWLEDGE:START*/ and :END*/ markers it owns and refuses to guess at), the "N commercial robots across M categories" counts in the homepage structured data, the product and policy URLs in sitemap.xml, and the regenerated cookie policy page. `--check` reports drift and exits 1 without writing; `--write` regenerates. Reads each robot's specs from the repository's own product pages and only fetches the one robot that lives in the CMS. Offline it passes with a warning, so a network problem can never block a push.
- catalog/build_cookies_page.py now reads the policy copy from catalog/cookies_content.html, so regenerating the page cannot overwrite a sentence somebody wrote, and writes with the repository's own line ending (asked from the working copy, then from the committed blob) so a three-line change stays a three-line change. catalog/test_site_sync.py pins both, including that a regeneration reproduces the committed page line for line.
- .githooks/pre-push (installed with `git config core.hooksPath .githooks`) runs the check before every push: stale files are regenerated and the push is refused so the commit carries them; a missing interpreter or a crash passes the push quietly rather than blocking it.
- ~/AppData/Local/hermes/ops/robotist-site-sync.py is the scheduled version: silent while nothing is stale, and when something is it regenerates, runs the 57 catalog tests, commits and pushes, printing a receipt for the job log. It resolves an interpreter that has BeautifulSoup, because the bundled one does not.
- Both entry points are now immune to the interpreter trap: the sync hands itself to an interpreter that has BeautifulSoup (a child process — os.execve segfaults on Windows) and the hook/wrapper probe the same way before they decide anything, so any caller - cron, hook, another agent, by hand - gets the same result instead of an eight-error "test failure" that is really a missing dependency.
- Tests run through catalog/run_tests.py, which hands itself to an interpreter that can import the suite: `python -m unittest discover` under the bundled interpreter reports eight import errors that are really just a missing BeautifulSoup. The scheduled wrapper uses the same entry point.
- Verification: drift injected into index.html (25 -> 99) was detected and repaired end to end by the scheduled script, which committed and pushed the fix on its own; the pre-push hook refused a real push until the regenerated commit was included; run_tests.py run with the interpreter that lacks BeautifulSoup still reports 57 tests OK.
## 2026-09-30 - One sync runner for every project, and a format rule for recaps
- The Robotist guard was rebuilt on shared machinery so the next project is a config file, not another one-off: ~/AppData/Local/hermes/scripts/project-sync.py reads .hermes-sync.json (check / write / tests / files / interpreter candidates) and does everything the bespoke wrapper did - silent when current, regenerate, test, roll back on a failed test, commit, push. ~/AppData/Local/hermes/scripts/install-sync-guard.sh writes the pre-push hook into any repository and points core.hooksPath at it; the hook regenerates into the working tree and refuses the push, and passes quietly when no interpreter can run the check.
- The runner probes interpreters by running the project's own check command (0 current, 1 stale, anything else is not a verdict), so no caller can be broken by this machine's several pythons. scripts/robotist-site-sync.py is now a delegator, which keeps the cron job stable.
- Cross-project rules extracted from today's failures (ownership markers, line endings, fail-open, silence when unchanged, interpreter probing, prove-the-trigger, fetch-before-trusting the working tree) are recorded in the Hermes AGENTS.md as a general contract, not as Robotist trivia.
- Verification: drifting index.html to '88 commercial robots' was detected by the installed hook and regenerated back to 25 with the push refused; the scheduled entry point is silent with exit 0 when current.
## 2026-09-29 - Cookie consent: one notice, one stored choice, analytics held until accepted
- catalog/site.py: ANALYTICS_TAG now declares Google Analytics 4 consent defaults with analytics_storage denied (ad_storage/ad_user_data/ad_personalization denied too) and reads the answer back out of the robotist_consent cookie (6 months, SameSite=Lax, Secure on https) before measurement starts; window.robotistConsent exposes choice()/set()/clear(), set() pushes gtag('consent','update'), clear() denies, expires _ga* across every scope Google may have used and notifies the page.
- New CONSENT_BANNER (brand tokens, dark card bottom-left, Accept analytics / Reject, one media query for phones, focus-visible outlines) plus consent() which injects the notice before </body> and adds a "Cookie settings" link into the footer-bottom row, from the single after_request point that already carried the analytics tag (consent(analytics(body))). Idempotent, skipped on pages with their own CSP (/manage).
- New public /cookies.html policy page (essential robotist_grn, robotist_consent, _ga; the cookieless pre-choice state; Google and YouTube's privacy-enhanced embeds; change/withdraw controls). Generated by catalog/build_cookies_page.py from about.html's tokens, nav and footer so the header/footer cannot drift.
- Verification: 50 catalog tests + 13 grn tests green, including the new catalog/test_consent.py (banner once per page, defaults before measurement, footer link, policy content, admin untouched, idempotent injection). In her own Chrome: fresh visit = empty cookie jar and no GA cookies; Accept = robotist_consent=granted plus _ga/_ga_WCTLN70HXT and the notice disappears; Reject = consent only, no analytics cookies; Clear = jar empty and the notice returns on reload. Commits 2d35fa9, 515113c, d519a48, d748605.
## 2026-09-29 - Maxx: live specifications, current company facts, public list prices
- catalog/app.py: catalogue_digest() now carries each robot's published technical specifications (spec: fields from the CMS document, else the product page's own spec markup), cached 600s, with the enrichment wrapped so a bad page can never fail an answer. published() is fetched once per row and handed to the spec reader instead of queried twice.
- robotmaxx-chat.html: SYSTEM_PROMPT replaced with the 25-robot specification set, Chris Liu named as Co-Founder & CTO, listed prices quotable with "price on request" handling, card tags on exact live slugs; ROBOT_CARDS now holds all 25 slugs and reloads itself from /api/catalogue; auto-detection matches the longest robot name and caps at three cards. index.html's Maxx prompt gained the company block and the public-price rule.
- Root cause found for a 500 that appeared mid-work: plain_text was imported inside catalogue_rows(), invisible to sibling closures, so the spec enrichment raised and (unguarded) broke /api/assistant. Fixed by importing at module level; catalog/test_assistant.py now fails if the scope regresses.
- Verification: 10 assistant tests green; live homepage widget and /robotmaxx-chat.html both answered with current specs, prices, CTO and valid card slugs.
## 2026-09-26 - Catalogue cards: glow removed, ice-blue well, category bento
- Product cards: removed both cyan glow layers (.robot-card.tone-dark::before radial + the hover box-shadow, which was declared twice); hover keeps the lift, border lift and a neutral shadow. The upward image sweep stays.
- .robot-card-img-wrap is now an inset ice-blue studio well (linear-gradient 178deg #F2FAFE -> #D9EEF9 -> #A8DCEF, radius 10px, 8px margin, 20px padding) on every card, CMS robots included; .needs-plate no longer declares its own grey plate. Contact shadow 0.30 alpha, image drop-shadow 0.24 alpha for the light ground.
- New #categoryBento between the catalogue header and #robotGrid: five button[data-filter] tiles (Humanoid span 4x2, Quadruped span 2x2, Companion/Cleaning/Industrial span 2 on six columns; 2 cols <=900px, 1 col <=560px). Each tile runs the same applyCatalogueFilter() as the pills and scrolls the grid (scroll-margin-top 96px). Counts read from the rendered grid on load; an empty family hides its tile.
- Files: index.html (card CSS, bento CSS/HTML, filter JS). Docs: docs/brand/BRAND_CENTER.md.
- Verification: python -m unittest grn.test_grn catalog.test_integration catalog.test_admin catalog.test_commerce catalog.test_product_drafting catalog.test_production catalog.test_assistant = 54 tests OK. Tile click Quadruped -> 6 shown / 18 hidden, pill synced, aria-pressed set; looked at 1440/1024/390.
## 2026-09-23 - Nav consistency, button geometry, hero light
- Both nav buttons are inline-flex boxes of equal height (42px desktop, 44px in the phone drawer) so labels sit on the optical centre.
- The 11 companion product pages now carry the same logo.svg (they used a text wordmark) plus the five links and the Join us / Get started pair.
- Hero: a light layer behind the machine (one bloom, two faint beams, 38s transform/opacity drift, off under prefers-reduced-motion); the 3D wrapper is transparent so the light glows around the silhouette.
- ui-excellence gate passed (full scope); 54/54 tests green.

## 2026-09-30 - Audit find-and-fix: named audience, FAQ, terms, share image on every page
- Prompted by the Pulse AI audit of the live site. The audit's own checks were part of the problem: engine parsing required `name=` before `content=` on meta tags, so this Webflow-shaped export scored as having no meta description, no og:image and no canonical; a partner strip built from `<img alt="Unitree">` did not count as proof because the alt text is a brand name rather than the word "partner". Those parsers now read attributes in any order, the navigation check counts the navigation rather than every link on the page, and a partner strip counts from wording as well as from image alt text (fixed in the pulse-ai repo).
- index.html: hero now states the audience in its own line ("For hotels, hospitals, logistics operators and facilities teams." — .hero-audience, brand tokens, 15px/1.6, one media query, kept visible on a phone unlike .hero-sub). The meta description, the og description and the share copy name the same buyer.
- New /faq.html: twelve real buyer questions (buy vs rent, deployment time, safety, integration, shipping, support, the AI assistant, privacy), each answered from what is established here — no invented figures, SLAs or credentials — with a valid FAQPage block (12 questions) plus nav and footer from the locked shell.
- New /terms.html: plain-language terms for quotes, rentals and purchases, covering when a contract forms, what a quote includes, payment mechanics, shipping and risk, safe use, IP, liability and New South Wales governing law, with a note that the signed agreement prevails. Written for clarity, not as legal drafting: it should be replaced by counsel-approved wording before it is relied on.
- Footers on index, about, blog, blog-post, compare, contact, cookies, landing, requirements, faq and terms now carry a legal row (FAQ / Terms / Cookies / Privacy) plus FAQ and Terms entries in the Company column. eden.html and eden-strategy.html are left alone: the Brand Center keeps Eden's world separate from the corporate pages.
- Share metadata completed on blog, blog-post, business-plan, landing, eden, eden-strategy, robotmaxx-chat (og:image, og:url, twitter card) and canonical added where missing (robotmaxx-chat, eden, eden-strategy); robotmaxx-chat gained its own description. sitemap.xml now lists faq, terms and cookies.
- Verification: full unittest suite green; served locally (python -m catalog.app --local --port 8880) and looked at 1440 and 375: hero line renders on one line, FAQ and terms pages inherit the nav, type and footer, footer legal row present on every page checked, FAQPage JSON-LD parses. Known, pre-existing: on a short laptop viewport (~820px tall) the hero CTA row sits behind the consent card — the same in the previous commit, not introduced here.

## 2026-10-10 - A public 404, and a URL for the brand center
- The 404 a visitor saw was the console's error page: it told them their action was not saved and offered "Back to GRN". catalog/app.py now registers its own 404 handler: console paths (/grn, /manage, /catalog, /work) keep error.html, API paths (/grn/api/, /manage/api/) keep the JSON envelope, and everything else renders the new public 404.html with the site's own nav and footer and a 404 status.
- New 404.html: eyebrow, "This page moved, or never existed.", a short reassurance, and eight real destinations (home, catalogue, compare, services, blog, FAQ, contact, cookies) plus the way back. noindex, follow. Built by catalog/build_404_page.py, which takes head, stylesheet, nav, footer and scripts from the site's own pages through the same helpers as build_cookies_page.py, so it cannot drift from the shell.
- The Brand Center was only a markdown file, so it now has an address: /brand-center (and /brand-center.html) renders brand-center.html, generated from docs/brand/BRAND_CENTER.md by catalog/build_brand_center_page.py - hero, numbered contents rail with a current-section marker, the document as an article (22 sections, 2 tables), nav and footer from the shell. The source document is untouched; the build repairs the "?" characters its encoding pass left where long dashes and quotation marks belong.
- Responsive and layout: body is a flex column here, so a content-sized grid could push main past the viewport (992px at 768). Both pages set explicit minmax(0,1fr) tracks and min-width:0; measured overflow is 0 at 1440/1180/1024/768/375, and hero, rail, article and logo all start at the same left edge (80/61/46/16).
- Verification: served locally on the main-based worktree (python -m catalog.app --local --port 8781) - /brand-center 200 with the document, an unknown URL 404 with the new page and no console copy, /cookies.html and /compare.html unchanged 200, /grn/nope still the console template, /grn/api/nope still the JSON envelope. Looked at 1440 and 375 for both pages.

## 2026-10-13 - Notifications actually land: a working route, and the header Cloudflare wanted
- The route code shipped earlier had a hole: api.resend.com sits behind Cloudflare, which answers Python's default `Python-urllib/3.x` User-Agent with 403 Forbidden before the request reaches the API. `_request()` in grn/notify.py now sends `User-Agent: robotist-website/1.0 (+https://robotist.com.au)` and `Accept: application/json` on every call, so all three routes (Resend, Zoho Mail API, SMTP) carry them.
- Route in force: Resend over HTTPS. Render holds RESEND_API_KEY (Resend, sending access) and MAIL_FROM = `Robotist website <notifications@pulse-branding.com>`; recipients stay `lareesa@robotist.com.au, robert@robotist.com.au`. pulse-branding.com is already verified at Resend, so mail sends today; the sender reads from a Pulse address with Reply-To set to the visitor, so a reply still reaches the customer.
- To send as @robotist.com.au instead, robotist.com.au has to be verified at Resend. The domain is already created there (id e475b9f0-7fd2-45e4-a76d-9e44374d59db, region us-east-1, status not_started); three records at GoDaddy DNS (nameservers ns73/ns74.domaincontrol.com) complete it: TXT `resend._domainkey` = the p= value from the Resend domain page, CNAME `rsend` = rsend.forge.rmta.net, CNAME `send` = send.forge.rmta.net. Then set RESEND_API_KEY/MAIL_FROM on Render to the robotist.com.au address and remove nothing else.
- Verified by running the deployed module itself (worktree at origin/main) with the Resend credentials: log line `[notify] inquiry RQ-TESTROUTE1 mailed to lareesa@robotist.com.au, robert@robotist.com.au via resend`, and the Resend log showing that message `sent` to both recipients and the earlier direct test `delivered` to lareesa@robotist.com.au. catalog/test_notify_routes.py gained RequestHeaders (two tests) pinning the User-Agent and header precedence; full suite 112 passed.

## 2026-10-13 - Screening: only a genuine inquiry rings the phone

Lareesa: "can you make a screening on the inquiries we received? Only send notification on ones
that are genuine inquiries."

- **What the inbox actually held.** 25 inquiries, September to October 2026: 19 form-spam (prize-scam
  links to telegra.ph, SEO pitches, and machine-generated "what is your price" bots in a dozen
  languages) against 6 genuine ones (two of our own tests, plus Mike Powrie, Sadhana, and dennis xie).
  Every one of the 19 was e-mailed to `lareesa@` and `robert@`.
- **The rules now live in one place: `grn/screening.py`.** `screen(row)` returns `''` when a submission
  should be notified, otherwise a short reason (`link-in-message`, `keyword:seo`, `gibberish`,
  `generated-name and odd-address`, ...). `grn/notify.py` reads it for the e-mail gate and the console
  reads it for a badge, so the two can never disagree.
- **The asymmetry is the design.** A genuine inquiry held back is a lost customer, so one weak signal is
  never enough — `generated-name`, `placeholder-company`, `odd-address`, `price-ask`, `shouting` and
  `no-company-vague-interest` only count in pairs. Spam in the inbox is merely annoying, so one strong
  signal decides: `disposable-email`, `link-in-message`, `link-heavy`, `keyword:<word>`, `gibberish`.
- **Measured against the real backlog:** 19 of 25 held back, 6 notified, and the 6 are exactly the rows a
  human would call real. `catalog/test_screening.py` pins that result with the real field values, so a
  future rule edit cannot quietly cost a customer.
- **The console shows the decision.** Each held row carries a "not notified" badge whose tooltip is the
  reason, and the inquiry page says whether the team was e-mailed. The submission is still stored either
  way — screening decides the notification, not whether the record exists.

## 2026-10-13 - Blog: seven drafts from the Robotist World LinkedIn feed

Lareesa: "can you look at all the linkedin posts we've made on robotist world. find the ones that are not time
related. and filter out the ones relevant to our models... generate blog drafts for our robotist website
backend? just save it there as drafts, make sure you embed links to the product, and make sure you include
the images."

- **The sweep.** All 45 published posts on the RobotistWorld LinkedIn page were reviewed. Time-bound posts
  (the daily "Robotics News" round-ups, festival and event greetings, "over the last few days" recaps, the
  page-update note, the Bloomberg share) were excluded, and repeated posts collapsed.
- **Seven drafts written** from the evergreen, model-relevant material: RAIBO2's marathon and what
  quadruped endurance means for buyers; ANYbotics Shift and inspection as infrastructure; Innodata's
  motion-capture lab and the humanoid data pipeline; AGIBOT and Chimelong's 300-robot deployment; a
  university/lab platform guide; the Humanoid Expectation Gap (after Robert's article); working dogs vs
  robotic quadrupeds (after Robert's article).
- **Saved as drafts in the blog store.** Each is a normal `blog-posts.json` entry carrying
  `"status": "draft"`, `"source": "linkedin"` and the source post URL. `blog.html`, `landing.html` and
  `blog-post.html` now filter `status !== 'draft'`, so drafts never render publicly; the three live posts
  carry no status field and are unaffected. Publishing a draft = set its status to `published`.
- **Images.** Each draft has a 1664x928 cover in `blog/covers/`, built from the Robotist World card for the
  same story (raw cards archived outside the repo), plus at least one product render from `robots-cut/`
  embedded in the copy.
- **Product links.** Every draft links two to four catalogue pages (`/products/...`). Facts were checked
  against primary sources (KAIST/Nature, ANYbotics, Innodata, RobotAIGeek/PR Newswire) and those sources
  are linked at the foot of each post.

## 2026-10-13 - Blog SEO/GEO layer: pre-rendered post pages, structured data, sitemap

Lareesa: "can you also make sure it's always SEO and GEO optimized?"

- **Every published post now has a crawlable page.** `tools/build_blog_static.py` bakes
  `blog/<slug>.html` from `blog-posts.json` + `blog-post.html`: the full article in the served HTML,
  title/description/canonical/Open Graph/Twitter meta, and schema.org JSON-LD (BlogPosting +
  BreadcrumbList, plus FAQPage when the post has FAQs). Search engines and AI answer engines read
  HTML without running JavaScript; the dynamic `blog-post.html?slug=` template still works and now
  canonicalises to the static URL.
- **Clean URLs everywhere.** Blog cards, related links and canonicals use `/blog/<slug>.html`. If a
  post has no pre-rendered page yet (the RankSpot webhook commits `blog-posts.json` directly),
  the platform renders the page on demand (`catalog.app.render_blog_page`), so a published post
  is always served as crawlable HTML and can never 404.
- **Sitemap gains published posts automatically.** `catalog/site.py` `sitemap()` appends every
  published blog URL next to the published robots; drafts are excluded by status. The robots.txt
  GEO layer (GPTBot, PerplexityBot, ClaudeBot, Google-Extended, Applebot-Extended) and the
  `llms.txt` / `ai.txt` discovery files already cover answer-engine access.
- **The seven LinkedIn drafts carry SEO/GEO fields** - `seoTitle`, `metaDescription`, `faq` (three
  Q&As each) and `dateModified`. The template renders the FAQ section and emits FAQPage schema for
  any post that has `faq`; posts without the fields fall back to title/excerpt.
- **Workflow:** after publishing or editing a post, run `python tools/build_blog_static.py` and
  commit the rebuilt page. Drafts are never written to disk.
- Verified: `catalog.test_integration` (including a new blog test: sitemap inclusion/exclusion,
  static page 200 with JSON-LD, 302 fallback) plus site-sync, commerce and consent suites pass;
  generated pages re-parsed for meta and JSON-LD; `node --check` clean on the patched templates.

## 2026-10-13 - Blog manager in the Content Manager
- The Content Manager (/manage/) gained a Blog section: /manage/blog/ lists every post in blog-posts.json (drafts first) with a full-article draft preview, one-click-with-confirm publish, and unpublish.
- Publish/unpublish flips the status in blog-posts.json and commits it (GITHUB_TOKEN); unpublish also removes the committed page so a draft can never keep a live URL. The dashboard shows a "Blog posts" collection and a "Blog drafts to review" metric.
- Tests: catalog/test_integration.py - auth, counts, preview banner and noindex, publish/unpublish round-trip.
