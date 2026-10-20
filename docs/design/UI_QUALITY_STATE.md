# UI Quality State

Machine state is linked by .ui-excellence.json. Assessments require evidence; bootstrap does not pass a stage.

<!-- ui-excellence:start -->
## Current pipeline evidence

Machine state: `docs/design/UI_QUALITY_STATE.json`. Scores are recorded review judgments, not human approval.

- BRAND: 4/4 — The pane is an alpha tint of the existing dark navy with the existing cyan accent, type scale and radius language; no new font, colour or component.

- TASTE: 4/4 — Catalogue now reads as product imagery on panes rather than white plates: cut-outs float with contact shadows and 88% fit, and the four dark shells get a rim glow instead of disappearing.

- IMPECCABLE: 4/4 — Every element clears the pane; card heights uniform at both breakpoints; all 24 cut-outs load after the extension fix; scripted scroll at 60fps.

- MOTION: 3/4 — No animation changed; the pane, contact shadow and rim are static and existing hover/reveal behaviour is untouched.

Entry stage: VERIFY. Active task: none.

Rendered verification: recorded 2026-09-23T08:15:09.988Z; run gate to check freshness.

Protected strengths: Hero, motion and 3D scene unchanged; Why Robotist stack, services tier rows, deployment rail, team rows and closing CTA untouched; Catalogue copy, prices, order, badges and product links unchanged; No horizontal overflow at 1440/1180/390

Known deficiencies: The chrome-skeleton cut-out keeps a faint rim past card scale; Four near-black shells depend on the rim glow for silhouette separation; Product, compare and GRN pages still carry the old white-plate cards
<!-- ui-excellence:end -->

<!-- 2026-09-23 audit pass -->
## Site-wide audit fixes — 2026-09-23

The 37-page design audit (`hermes/reports/robotist-audit-full`) landed in four commits (9c2bfbe,
b4df035, 9d72906, 8d3a07a): AA contrast for every dim text token, 44px targets on nav/footer/form
links, Poppins removed from the public product stylesheets, Eden alt text and meta descriptions,
lazy loading below the fold, and the Qisheng pane stating the missing photograph.

The scores and captures recorded above predate those edits, so their fingerprint no longer matches
the source. The page-state evidence is stale until the stage reviews are rerun on the current build.
