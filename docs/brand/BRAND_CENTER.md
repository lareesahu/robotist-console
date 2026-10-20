# Robotist Brand Center

**Status: current extension standard, locked 8 September 2026.**

Read this before designing or implementing any Robotist website extension. Extend the homepage's established system; do not create a new visual identity for each route. The verified implementation reference is commit `89db6028f55f13bbe9d07e839407b31743119949`. A newer explicit user direction can change this standard; an AI's stylistic preference cannot.

## Authority and scope

1. Exact current user instructions and named assets.
2. This current Brand Center, with the source-linked [design map](../design/DESIGN_SYSTEM.md) and [motion system](../design/MOTION_SYSTEM.md).
3. Homepage `index.html` tokens/components and the verified reference captures.
4. General skills and aesthetic suggestions, only where the above leave room.

The homepage is the style authority. Existing code is not automatically approval: legacy GRN Poppins faces and old compressed tracking still exist in lower-priority CSS for other contexts. They are **superseded for public extensions** by `grn/static/robotist-foundation.css`. Do not copy them. Historical documents under `history/` are evidence, not active guidance.

Scope: the Robotist corporate website and compatible public extensions, including GRN, inquiry cart, receipts and admin sign-in. Preserve the authenticated dashboard's management sidebar. Do not impose this layout on distinct Eden/Edenne experiences or unrelated projects. This is not permission to redesign existing homepage content or motion.

## Binding user direction

- ?wait the navbar isn't universal? robotist have universal elemetns, don't keep reinventing new stuff? ? session `01a07b07-9ba3-7ea3-a615-2f5c7adcbcb9`, line 4530, 2026-09-07T20:09:35.533Z.
- ?then fix umtil everything passed. also letter spacing is bizare ,  copy the style of homepage ok?? ? same session, line 5048, 2026-09-07T20:39:32.640Z.
- ?lock in the details in the brand center so nmo future extention work will drift? ? C:\Users\hunin\.codex\sessions\2026\09\07\rollout-2026-09-07T16-41-31-01a07b07-9ba3-7ea3-a615-2f5c7adcbcb9.jsonl:5372 (2026-09-08T05:50:35.455Z).

These establish reuse, homepage alignment and persistent constraints. They do not mean a human reviewed every screenshot or approved every future variation.

## Brand character and content

Observed homepage character: precise robotics, dark technical presentation, restrained cyan emphasis, direct product language and generous separation between meaningful sections. Keep brand expression in typography, actual robot imagery, proportion and content; avoid decorative complexity.

GRN is an independent specialist network for robotics engineering, software development, integration, deployment and technical support. Preserve its one-page introduction with the application in the hero. Do not imply employment, guaranteed projects/hours/income, automatic public profiles or signed collaboration terms. Application review/contact consent and separate profile-publication approval remain distinct. Preserve accurate content from the supplied GRN document; do not invent testimonials, partner logos, counts, credentials or commercial promises.

## Typography ? copy the homepage, not the old GRN theme

| Role | Locked reference |
|---|---|
| Main and body font | `--font-main` / `--font-body`: `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif` |
| Public headings | Weight **700 (bold)** — every heading, H1 included — tracking **-0.02em**; no stronger negative tracking. Lareesa, 11 October 2026: "the headings especially H1 should always be bold". Enforced from one injected rule in `catalog/site.py`, not per page |
| Body, labels, inputs, buttons | **Normal letter spacing**; never inherit uppercase-label tracking |
| Homepage hero reference | `clamp(40px,4.8vw,76px)`, line-height 1.1; copy its type character, not its homepage-only nowrap layout |
| GRN hero | Existing `clamp(44px,4.6vw,72px)` desktop composition; mobile **34px / 1.1** |
| GRN introduction | Desktop **16px / 1.75**, weight 300; mobile **14px / 1.5** |
| GRN form heading | Desktop **28px**, mobile **26px**, weight 600 |
| Form label / input / button | **13px / 16px / 14px** respectively |
| Form progress / privacy | **12px**, normal tracking |
| Small uppercase GRN labels | Weight 500, **0.16em**; an intentional label treatment, never body styling |
| Shared nav links | Inherit homepage **11px, weight 300, 0.14em**; do not restyle locally |
| Shared nav CTA | Inherit homepage **11px, weight 500, 0.12em** |

Do not add a new font dependency. Do not reintroduce Poppins to public extensions, squeeze words to force a line, or shrink essential copy to 10?11px to fit a screen. Responsive line breaks must retain actual spaces between words.

## Headings are bold, from one rule — 11 October 2026

**Direction.** Every heading is bold: the H1 and everything below it. Lareesa, 11 October 2026: "There's a problem in all of Robotist work. The headings especially H1 should always be bold." The pages had drifted to **600** on headings and **300** on the brand book's section titles, neither of which reads as bold.

**One source.** `HEADING_WEIGHT` in `catalog/site.py` is injected by `consent()` — the single point every HTML response already passes through — as `h1,h2,h3,h4,h5,h6{font-weight:700 !important}`. The pages dress headings with classes (`.hero-h1`, `.section-title`) and some set the weight inline, so `!important` is what makes a brand rule hold against 25 page stylesheets and any future generator. Verified: h1/h2/h3 computed at **700** on the homepage, about, compare, FAQ, cookies, terms, a product page, the 404 page and the brand centre, at 1440 and 375, with no horizontal overflow.

**One deliberate exception.** The hero wordmark on the brand centre is the logo, not a heading. The guide documents it as Poppins **Medium 500** and says it must never be altered, so `catalog/build_brand_center_page.py` re-asserts `.hero-wordmark{font-weight:500 !important}` in its publication overrides. Section titles on that page are headings and are bold.

## Color and geometry

| Token / role | Value |
|---|---|
| Homepage background scale `--bg-0` through `--bg-4` | `#030810`, `#060D18`, `#0C1828`, `#142035`, `#1E3550` |
| Primary cyan / dim / light | `#4AA8C8` / `#2E8FB5` / `#A8DCEF` |
| Homepage primary text / secondary text | `#F0F4F8` / `#8A9BB0` |
| GRN inherited text / muted / rule | `#E6F2F8` / `#AABACB` / `#24364B` |
| Homepage magenta | `#D9468C`, reserved for its existing semantic uses; not an additional GRN accent |
| Shared nav height | `--nav-h:72px` |
| Homepage gutter / container | `clamp(24px,6vw,80px)` / `1400px` |
| GRN anchor offset | `calc(var(--nav-h) + 24px)` = **96px** |
| Public action corner radius | **2px** |
| Existing GRN form panel | **8px**, one purposeful application container; no nested decorative card system |

Reuse existing tokens instead of inventing near-duplicate colors. Dark surfaces, fine rules and restrained accent use are deliberate. Do not introduce generic gradients, glass panels, oversized pills or excessive cards. Readability and contrast still matter; a dark brand is not permission for illegible text.

## Universal elements and component ownership

- **Navbar and footer content/style source:** `index.html` (`nav.nav#mainNav`, `footer.footer`).
- **Shared extraction and scoped styles:** `catalog/site_shell.py`; endpoint `/grn/site-shell.css`. Do not copy/paste another navbar/footer into a new template.
- **Public template entry:** `grn/templates/base.html`, consuming `robotist_navigation` and `robotist_footer`.
- **Shared behavior:** `grn/static/site-shell.js`; homepage mobile dimensions also use `mobile-usability.css`.
- **Public typography and inherited-layout corrections:** `grn/static/robotist-foundation.css`, loaded after route styles.
- **GRN hero and two-step form:** `grn/templates/landing.html`, `hero-application.html`, `grn/static/hero-form.css`, `application.js`.
- **Bottom-right floating corner:** the Maxx chat launcher (`.chatbot-widget`, `z-index: 600`) owns it. The inquiry-cart pill (`.inquiry-cart-link`, `z-index: 599`) stacks 16px above the launcher through `grn/static/cart.css` and fades out while `.chatbot-window.open`. Do not reposition or re-layer either element per route.

For an extension in another framework, adapt this same source/system rather than silently inventing a replacement. If a structural refactor is necessary, preserve rendered markup, links, typography and behavior; verify consumers together. Update a shared element at its owner, not through divergent per-route variants.

## Assets and composition

Use the existing `images/logo.svg` and `grn/static/grn-robot.png`, keeping their proportions. No replacement wordmark, generated lookalike or unrelated robot. The [baseline manifest](reference/baseline.json) records asset hashes and the inspected screenshots.

Preserve the one-page GRN section order, desktop text/form split, subdued existing robot image and hero application. On mobile, stack naturally and keep the first-step action in the hero at the reference **390?844** size; the verified button ended around **745px**. At smaller heights, allow ordinary scrolling instead of shrinking essential text or clipping fields. Keep accurate terms, FAQ and booking fallback available. Do not copy homepage-specific spatial effects into a form simply because they exist on the homepage.

## Interaction and accessibility constraints

- Header remains one row, including at 320px width; protect logo aspect ratio and mobile menu target.
- Anchors clear the fixed navbar; use the shared height, not a hard-coded 25px offset.
- Opening the mobile menu focuses its first link. Keyboard traversal includes all links and the toggle. Escape closes and returns focus. Leaving the header or resizing closes the disclosure.
- Inputs use at least 16px text; primary interactive targets are at least 44 CSS px. The checkbox's associated label supplies its full target.
- Preserve labels, required validation, Back value retention, first-invalid focus, step focus transfer, error text and confirmation receipt. Hidden fields must not trap validation.
- FAQ remains keyboard-operable native disclosure. Keep visible focus and skip-to-content above the fixed header.
- No unnecessary animation. Reduced motion preserves state changes and keyboard operation while removing transitions/smooth scrolling. Preserve existing homepage motion elsewhere.

## Required extension review

Before implementation, read this document and compare the target against the homepage and [reference captures](reference/baseline.json). State the inherited components and any required new pattern. New patterns must be justified by the task and use this system.

For UI implementation, use the scoped UI Excellence workflow; audit-only stays read-only. Verify actual rendered desktop, laptop and mobile states, including keyboard, reduced motion, form failure/success where applicable, overflow and correct asset loading. Compare against baseline before declaring completion. A build, detector or self-assigned score alone is insufficient.

When a user explicitly changes a rule, preserve the old evidence, update this current view plus design/motion maps and the project Bible, and record exactly what was requested versus what was verified. Never silently relax these constraints. This is a required contributor/agent contract, not a technical guarantee that every future tool will comply.

## Section rhythm, tier rows and the heading scale — 22 September 2026

Lareesa: *"the landing page now has too many consecutive sections of 3 card layout"* — then, on the audit, *"ok do it"*.

**Finding (measured on the live DOM, 1440px).** Between the catalogue and the footer the page ran five consecutive multi-card sections — Why, Leadership, GRN, Services, Deployment — four of them the identical three-column divided panel. The GRN band is only 330px tall, so it never registered as a break. Section headings used six different sizes for the same level (37.4 / 40 / 43.2 / 48 / 52 / 64px) and section padding ran 0 / 76 / 80 / 100 / 120 / 160px, with the brands band at zero bottom padding colliding into the catalogue.

**Service Packages is now a tier list, not a card row.** Three full-width rows: tier label and name on the left, that tier's feature list in two columns in the middle, CTA right-aligned. Tier 2 keeps its emphasis through a background fill and a 2px inset cyan rule — a highlighted row, not a card. **Each tier keeps its own feature wording.** No shared feature matrix was invented: the tiers list different, tier-specific capabilities, and merging them into one comparison grid would have required asserting which tier includes what.

**One heading scale, one band rhythm.** `--h2-section` (`clamp(28px,3vw,48px)`) for standard sections, `--h2-band` (`clamp(24px,3vw,40px)`) for full-width bands, `--band-pad` (`clamp(80px,9vw,120px)`) for band padding alongside the existing `--section-pad`. The scenarios band keeps its 64px display title as the single deliberate exception — it is a full-bleed immersive slider, not a section opening. The leadership section moved from a hard-coded 120px to `--section-pad`.

**Also corrected:** the deployment step titles were `h4` directly under the section `h2`; they are `h3` now, so the document outline has no skipped level.

**Preserved deliberately:** the catalogue card system (one grid, one card size, CMS-coupled markup), the leadership triptych chosen the same day, all motion, every colour, font and corner radius, and the homepage's own type weights — the homepage is the authority for its own sections, so the band headings keep their existing 500/300 weights rather than being forced to the extension weight of 600.

**Verified:** local and live renders at 1440 / 1100 / 390px inspected; the three tier rows measure identical column offsets with single-line tier names; no horizontal overflow at any width; no console errors; contrast and asset loading unchanged. `python -m unittest grn.test_grn catalog.test_integration catalog.test_admin catalog.test_commerce catalog.test_product_drafting catalog.test_production catalog.test_assistant` — 51 tests, OK.

**Still open, found in the same audit:** 54 interactive targets under 44px at 390px, including the 43px inquiry-cart button — that markup is generated by the catalogue/CMS path, not by `index.html`, so it was left for a separate change.

## Sequence, deployment rail and touch targets — 22 September 2026 (same-day second pass)

Lareesa, on being asked which remaining option to take: *"just fucking finish everything you can do, why on earth would you stop to check. NEVVER STOP TO CHECK!"* Recorded as §7.5 of the Caelum operating rules: finish the whole approved scope in one run.

**Section order changed.** Leadership now sits after the deployment section, immediately before the inquiry CTA. Its `id="leadership"` anchor is unchanged, so the "Team" links on `compare.html` and the product pages still resolve. The reason is rhythm: with Service Packages as tier rows, Why and Leadership were the last two card grids still touching; the new order leaves no two adjacent card-grid sections. Order is now hero → brands → catalogue → compare → scenarios → why → GRN invitation → services → deployment → leadership → inquiry → Eden.

**Deployment is a horizontal rail.** Six numbered 38px nodes sit on a single 1px hairline that begins and ends exactly on the first and last node centres (measured: rail spans 19px to 1110.7px against node centres at 19px and 1111px). The old 3x2 bordered cell matrix is gone; it read as a second grid, which was the complaint. Titles reserve three lines so all six paragraphs start on one baseline (measured identical top at 585px). At ≤1100px the rail is hidden and the steps fall back to 3-up, then 1-up at ≤600px.

**Touch targets.** The `≤560px` rule in `grn/static/cart.css` was shrinking the add-to-cart button to 43px; it now holds a 44px minimum. In `index.html` a `@media (pointer: coarse)` block gives the catalogue filter pills, the "Compare all robots" link and the card name link a 44px+ target on touch devices only, so the compact desktop pill row is unchanged. Measured on a touch context at 390px: 44 / 44 / 47px.

**Brand drift corrected.** `grn/static/cart.css` set the inquiry-cart pill and the add-to-cart button in Poppins. The Brand Center already declares the homepage stack the public surface standard and forbids reintroducing Poppins; both now use the homepage font stack. This is the only place Poppins appeared in a live public stylesheet.

**Verified:** local renders at 1440 / 1100 / 390px inspected (deployment rail, tier rows, re-sequenced page), no horizontal overflow at any width, body-copy baselines and rail endpoints measured in the DOM, 51 project tests OK, then the deployed page checked live.


## Why Robotist and Team — direction applied — 22 September 2026

Lareesa, choosing from the four-direction board: *"Hero=D, Catalogue=D, Why Robotist=B, Services=D, Deployment=D, Team=B, Closing CTA=D"*. Two sections change; the rest of the homepage stays exactly as it is.

**Why Robotist → scroll-stacked cards (direction B).** The three advantages are now full-width cards that stack as the page scrolls: `position: sticky` with a stepped top offset, and a scroll-linked scale and dim applied per card (the card behind sits around 0.95 scale / 0.9 opacity at the point the next one covers it). The 3-column divided panel is gone, which was the last place the page repeated that skeleton at two levels. Copy, numbering, icons, rules and the existing surface tokens are unchanged; the section keeps its header block. The handler is rAF-throttled, uses a passive scroll listener, and does nothing at all under `prefers-reduced-motion: reduce`.

**Team → alternating editorial rows (direction B).** The triptych tiles are replaced by one founder per row: a 380px portrait (4:5 on desktop, 4:3 on phones) alternating left / right / left against a text column, separated by hairlines. The markup, classes, ids, portraits, tags and LinkedIn links are the same components as before — this is a layout change, not new components — so `index.html#leadership` still resolves for the "Team" links on `compare.html` and every product page. The ghost index numerals are hidden in this treatment; the bio measure is capped at 68ch.

**Verified:** rendered at 1440 / 1180 / 390 with the stack and the row alternation measured in the DOM (alternation confirmed as image-left / image-right / image-left at 380px on desktop and laptop; single column on phones), no horizontal overflow at any width, no console errors, and the project suite passing 51 tests. Both sections were inspected as rendered, not from source.

## First-paint, spacing and CTA clearance — 22 September 2026

Lareesa: *"it loads very strange. also some spacing is crazy. and for the CTA box, the margin needs optimization don't let any element touch border"*.

**First paint.** The hero is built on a fixed 3D scene (`spline-viewer`, hosted off-site) with `.hero-bg` as a solid colour and the headline pinned to the viewport bottom. Until that scene paints, the first screen is an empty black field with text low in the frame. `.spline-fixed` now carries a still frame behind the scene — `images/robotist-og.jpg` under a 0.35→0.72 dark wash, a local asset per this Brand Center — so the first screen reads as a designed dark scene from the first paint. The 3D scene still paints over it when it loads; nothing else about the hero was changed.

**Spacing.** The scroll-stacked Why section carried its own `padding-bottom: 12vh` on top of the section's standard 160px, leaving a 290px void after the last card. That padding is removed; the tail is now the section padding plus the card's own margin.

**CTA clearance.** The service tier rows used `42px 30px` inner padding (was `40px 12px`), and the action rail keeps 4px extra, so the tier name, feature list and Get-a-quote button all clear the row borders. Measured clearances: 30px left/right, 42–43px top/bottom.

**Verified:** rendered at 1440 and 390, hero inspected at 0.6s and 3.6s after load, tier rows measured for border clearance, no console errors, project suite green.

## Evidence and history

Baseline images are **agent-inspected production captures from 8 September 2026**, not human approval: [desktop](reference/final-desktop.jpg), [laptop](reference/final-laptop.jpg), [mobile](reference/final-mobile.jpg). See [verification](reference/VERIFICATION-2026-09-08.md). Historical contradictory drafts are retained under [history](history/2026-09-08-before-lock-brand.md) and are explicitly superseded here.


## Product media and AI copy extension ? 8 September 2026

Product editor and product pages retain their existing layouts and shared visual language. Video players use a responsive 16:9 frame, descriptive titles, native keyboard controls, no autoplay and a visible fallback link in the brand's light cyan. Do not paste arbitrary embed HTML or create new player chrome. Customer-facing drafts use natural plain text with no raw Markdown markers; source quotations remain in the private editor, separate from customer copy. DeepSeek V4 Flash handles text and Flash Vision handles images/scanned pages, per the user's clarification. Filled claims remain unreviewed until checked; preserve existing manual values and explicit publication.

## Identity mark and favicon — 15 September 2026

Lareesa supplied the Robotist identity mark (`07-circular-bowl`: geometric R with the cyan counter dot) and directed that it become the brand icon and favicon on every Robotist page, applied globally rather than page by page. Canonical files: `favicon.svg` (the mark on her rendered `#0A0E14` tile), `favicon-32.png`, `favicon-16.png`, `favicon.ico`, `apple-touch-icon.png` (180). Her supplied sources are kept in `docs/brand/reference/`.

Applied in exactly two places: the page transformer `catalog/site.py` (`with_brand_icons`) rewrites the icon links on every page the website app serves, and `grn/templates/base.html` carries the same four tags for the GRN and admin templates. No individual page keeps its own copy. Do not add page-by-page favicon variants.

Eden is excluded for now: Eden pages (`eden*.html`, `old-eden.html`, `eden/`, `eden-chat/`, `eden-world/`) are served the previous mark from `/eden/favicon.svg`, `/eden/favicon-32.png`, `/eden/favicon.ico` and `/eden/apple-touch-icon.png` until Eden's own identity is decided. When it is, replace those four files instead of editing Robotist pages.

Verified 15 September 2026: a local run of the site app returns the four canonical tags on the homepage and the `/eden/` variants on Eden pages; `/favicon.svg`, `/favicon.ico` and `/apple-touch-icon.png` all return 200. The same run confirms the inquiry pill clears the Maxx launcher by 16px and hides while the chat window is open.

## Catalogue cards — 15 September 2026

One grid, one card size, at every breakpoint. `#robotGrid` holds every published robot as the same `.robot-card` component: 1:1 image panel, category tag top-left, flagship badge top-right, then an info block with name, price, best-for and the inquiry-cart button. Emphasis comes from order and the badge, never from a different card geometry — the retired featured/mid/small rows put three sizes on one page and read as chaos.

Column ladder **4 / 3 / 2** (desktop / ≤1100px / ≤700px). The info block has a minimum height, one-line name and best-for on desktop, and a clamped two-to-three-line best-for on phones, so rows stay level. On narrow phones the category tag is hidden rather than truncated.

The CMS depends on this markup: publishing a new robot copies `#robotGrid .robot-card` as its card template and the publish gate requires that selector to exist (`catalog/site.py` `homepage()` and `catalog/app.py` publish action). Change the card markup and those two together, then re-run the catalog tests.

## Sensitive assets and the reveal veil — 20 September 2026

Lareesa's direction: *"when uploading assets for the new robots etc. add an NSFW toggle for the individual asset be it image or video. if something is marked NSFW, then blur it and make it reveal on click/tap like how we did it before for the landing page eden section."*

The flag belongs to the asset, never to the robot. Each uploaded image and each saved product video carries its own `nsfw` boolean; one sensitive gallery photo never hides the rest of the record.

- **Editor (`catalog/static/app.js`, `catalog/static/admin.css`).** The toggle sits under every image with an accessibility description, and under every video row. Ticking it blurs that thumbnail immediately — the editor does not wait for a save — and the thumbnail reveals and hides on click. Editor-only classes: `.nsfw-check`, `.nsfw-mediabox`, `.nsfw-peek` (44px minimum target, matching every other editor button).
- **Every public surface that shows a cover is veiled.** Complete list, so nothing is assumed covered by omission: the product page hero and gallery images and the product videos (`catalog/site.py`, both page families), the homepage catalogue card (`catalog/site.py`), the inquiry cart item (`catalog/commerce.py` + `grn/templates/cart.html`), and the RobotMaxx chat product card (`catalog/app.py` `/api/catalogue` carries `nsfw`, `index.html` builds the same veil). Adding a new surface that renders `/catalog/images/<id>` means veiling it here.
- **The component.** `assets/nsfw-veil.css` + `assets/nsfw-veil.js`. `.nsfw-host` supplies the positioning context, `.nsfw-blur` blurs the media, `.nsfw-veil` is a real `button` with a rose `18+` pill, the hint `Tap to reveal` and a visible focus ring. It is a **toggle**: one delegated capture handler reveals on click, tap, Enter or Space, and the next tap veils the asset again. The revealed state stands the full veil down to a small bordered `Hide again` chip in the bottom-right corner, so the control is never invisible-but-focusable and never one-way. The handler cancels the surrounding link, so a veil inside the cart link or a catalogue card toggles instead of navigating. Same mechanism as the Eden stage veil on the homepage, and the label is deliberately short so it stays one line inside an 85px thumbnail.
- **Link previews.** A flagged cover is removed from `og:image`, so a social or chat preview cannot show what the page itself hides.
- **Stated decision, not an oversight.** The blur is presentational: a visitor who copies the `/catalog/images/<id>` URL still gets the bytes, because a click-to-reveal control needs them to be fetchable. Blocking the file server-side would break the reveal she asked for. Treat the flag as editorial, not as access control.
- **Conditional payload.** The stylesheet and script are added only to a page that actually carries a veiled asset. A catalogue with no flagged assets ships the previous bytes exactly.
- **Reduced motion.** Transitions are removed; the revealed state and keyboard operation remain.

Verified 20 September 2026 against a local run of the site app, not from the code alone: the editor blurs a thumbnail when the box is ticked and reveals it on click; the product page hides the hero and the gallery image and reveals the hero on click (`product-hero-image nsfw-host revealed`); the catalogue card hides its image with the name, price and cart button intact. `python -m unittest grn.test_grn catalog.test_integration catalog.test_admin catalog.test_commerce catalog.test_product_drafting catalog.test_production catalog.test_assistant` — 51 tests, OK.

## Catalogue cards lose the hover layer — 20 September 2026

Lareesa, on the homepage grid: *"the product card on landing page has product name already why does it still have hover effect"* … *"remove the hover"*. She is right: the card carried two generations of markup. The hover layer (`.robot-overlay`) predated the 15 September card rework; the info block added then already shows the name, price and best-for, so the hover repeated two facts and added only the description.

Removed outright at her direction, from `index.html` (all 24 cards), `mobile-usability.css`, and the overlay CSS block. The card is now: 1:1 image panel, category tag, flagship badge, info block. Hover keeps only the existing image scale and shine — no layer appears over the image. The whole card stays clickable to the product page; that behaviour now finds its link through `.robot-info-name`, and the veil is excluded from it so tapping a veil never navigates.

One consequence handled rather than dropped: the description only ever appeared in that hover layer, and both the catalogue ItemList JSON-LD and the assistant's catalogue read it from the card. Each card now carries `data-desc` (13 of the 24 static cards have one; the rest fall back to their category, exactly as before), and `catalog/site.py` writes `data-desc` when it renders a published robot. Verified: the ItemList on the homepage still carries 24 entries with their descriptions.

## Scenario backgrounds are local — 21 September 2026

The homepage Real-World Applications slider had six background images hotlinked to
`files.manuscdn.com`; that host began refusing them and the slides rendered empty for a period nobody
noticed. All six are now local files, `images/scenario-{farming,security,hospitality,housekeeping,music,dance}.webp`
(1600x900, 14–28 KB each), and nothing on the homepage loads imagery from a third-party host.

Rule going forward: a background or hero image on this site is stored in the repository. Hotlinking a
CDN we do not control is what turned six slides blank. The set was generated to one brief — dark
cinematic, one focal point, generous negative space, lower half dark enough for the caption, no logos
or lettering in frame — so the six read as one family beside the existing product photography.

## Featured band, hover sweep and the Why layout — 23 September 2026

Lareesa: *"for the comparison page, do you mean to show half the body of the humanoids? right now all the legs are poking out"* · *"for the landing page product card, i like the hover over effect, but can you make the gradient box move upward, and make it go half slowly and on a curve. make it less opaque as well"* · *"add a featured product section, update the system to allow the admin to toggle which ones to feature on the back end"* · *"for the sticky stack cards section, make it left/right layout on the wide screen view"*.

**Compare thumbnails.** `.c-media img` relied on a percentage `max-height`, which does not resolve inside a grid item, so a tall cut-out grew past the 72px plate and hung its legs out of it. The plate now clips and the image takes a definite absolute box; humanoid rows show head to hips (`.g-humanoid .c-media img`), and the wide machines keep the whole-body fit.

**Card hover.** The image sweep now moves upward rather than sideways, over 3s on an eased curve, at 0.07 alpha.

**Featured band.** A new `#featured` section sits directly above the catalogue and renders the robots the admin flags. It reuses the catalogue's own card component — the publish gate and the ItemList still read `#robotGrid` only — and the section is absent from the page until something is flagged.

**Why section.** At 1100px and wider the header is the left column and stays with the reader while the three cards stack on the right.

## Catalogue: no card glow, an ice-blue studio well, the category bento — 26 September 2026

Lareesa: *"on the product cards remove the glow effect. and for the product card add our ice blue bg to make the product pop"* · *"also show a bento section of robot categories on top of the collections, where each links to the filtered collection display below"*.

**The glow is gone.** Two layers carried it: `.robot-card.tone-dark::before` (a cyan radial behind the four near-black shells) and the hover box-shadow `rgba(74,168,200,…)`, declared twice — the copy lower in the stylesheet was the one that actually showed. Both are removed. Hover keeps the 1.02 lift, the border lift and a neutral `rgba(0,0,0,0.45)` shadow. The upward image sweep she asked for on 23 September stays.

**The ice-blue well.** `.robot-card-img-wrap` is now an inset plate — `linear-gradient(178deg, #F2FAFE 0%, #D9EEF9 55%, #A8DCEF 100%)`, radius 10px, 8px margin, 20px padding — built on the brand ice blue `--accent-light: #A8DCEF`. Every card carries it, CMS-published robots included, so `.needs-plate` no longer declares its own grey plate; it now only drops the contact shadow for opaque photographs. The contact ellipse and the image drop-shadow were re-cut for a light ground (0.30 and 0.24 alpha instead of 0.55 and 0.40).

**Category bento.** `#categoryBento` sits between the catalogue header and `#robotGrid`: five tiles sized to what each family actually holds — Humanoid span 4×2, Quadruped span 2×2, then Companion / Cleaning / Industrial at span 2, on a six-column grid (two columns at ≤900px, one column at ≤560px, where a half-width tile could not hold a label and a machine without colliding). The two large tiles keep the label bottom-left with the machine beside it; the three small ones put the label on top and stand the machine on the bottom edge so a small family still shows its robot at full size.

Each tile is a `button[data-filter]` and runs the same `applyCatalogueFilter()` the header pills run, then scrolls the grid to the top (`scroll-margin-top: 96px` clears the 72px nav) — the pills and the tiles can never show different states. Counts are rewritten from the rendered `#robotGrid` on load, so a robot published from the admin is counted the moment it appears, and a family with no machines hides its tile.

Verified 26 September 2026 against a local run of the page, not the code alone: `python -m unittest grn.test_grn catalog.test_integration catalog.test_admin catalog.test_commerce catalog.test_product_drafting catalog.test_production catalog.test_assistant` — 54 tests, OK. A tile click on Quadruped reports 6 cards shown / 18 hidden, the pill row switches to Quadruped with the tile's `aria-pressed` set, and the page scrolls to the grid. Looked at 1440 / 1024 / 390 — the bento, the ice-blue well on a card, and the filtered state.
