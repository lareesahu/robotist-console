# SEO workflow — Robotist

Version 1, 3 November 2026. This replaces opinion-led content planning. Every target below comes from a
query that someone actually typed, or from a competition gap observed in a live SERP. No invented volumes.

## What the data says

Collected 3 November 2026, English (Australia), from Google Autocomplete: 301 queries across 32 seed terms.
Full dataset in `docs/seo-keywords.json`.

- 101 queries are model-led ("gausium phantas", "keenon c40 price", "limx oli robot price").
- 96 are job-led ("robot for hotel cleaning", "inspection robot dog", "warehouse robot cleaner").
- 85 are category-led ("cleaning robot", "humanoid robot for sale").
- 13 are research-led ("humanoid robot for university research", "quadruped robot kit").
- 34 of the 301 carry explicit price or cost intent. Ten of sixteen stocked model names put "price" in the
  top autocomplete completions.
- Non-Australian price variants ("cleaning robot price in india", "… pakistan", "… kerala") exist but are
  not ours to serve.

## The audit finding that drives everything

Robotist does not rank for a single non-branded query we tested. Six SERP checks, zero appearances:

| Query | Robotist | Who ranks instead |
| --- | --- | --- |
| gausium phantas | no | gausium.com, taski.com, future-machines.com, okmbot.de |
| keenon c40 robot australia | no | robotcobot.com.au, robotsquare.com.au, hit-equipment.com.au |
| commercial cleaning robot australia price | no | robo-tek.com.au, workplacerobotics.com.au, aussierobots.com |
| humanoid robot for university research | no | nexthumanoid.com, humanoidhub.ai, originofbots.com |
| quadruped robot inspection price | no | robotpriceindex.com, bigbotstore.com, botsmarket.com |
| robot for hotel housekeeping australia | no | quantumrobotics.com.au, robotx.au, automaate.au |

It ranks 2nd for "robotist gausium phantas" — branded search only. The site has product pages and blog
posts; it has no page that answers the query a buyer actually types.

Two competitive fields, one gap:

- International price-index sites own model + price. They list a number; they cannot deliver, support or
  warrant anything in Australia.
- Australian resellers own category + australia. Their pages are thin catalogues.
- Nobody owns model + price + Australia. That is the gap, and it is ours by right: we stock the machine,
  we quote it, we ship it, we support it.

## The five layers

**Layer 1 — Money pages (24).** One page per stocked model at `/products/<model>.html`, extended rather
than duplicated: delivered price or a stated quote path, Australian availability, lead time, warranty and
support route, what is included, what is not. Target: `<model> price`, `<model> australia`,
`<model> review`. This is where the price belongs — the query demands it.

**Layer 2 — Australian job pages (12).** "Commercial cleaning robots Australia", "hotel housekeeping
robots", "quadruped inspection robots Australia", "robot rental for events Australia", "warehouse floor
cleaning robots". Same job questions the resellers answer badly, answered with our stock, prices and
landed-cost reality.

**Layer 3 — Comparison pages (8).** "Phantas vs C40-P1", "MagicDog Y1 vs Genisom M1", "LimX OLI vs ADAM U".
These are what AI answer engines cite, and robots.txt already allows GPTBot, PerplexityBot and ClaudeBot.

**Layer 4 — Editorial and signals.** Titles from the twelve-pattern system, aimed at credibility and
distribution, not at ranking. These carry the LinkedIn feed and the link acquisition.

**Layer 5 — Answer layer.** Every page carries a direct answer in the first 60 words, a spec table with
conditions, and FAQ schema that matches the visible text, so an AI engine can quote it without inventing.

## The weekly loop

1. **Harvest** — rerun the autocomplete sweep (the 32 seeds recorded in `docs/seo-keywords.json`) and pull Search
   Console queries for the site. New query that fits a lane gets a target.
2. **Brief** — target query, the answer in one sentence, the evidence IDs, the internal links, the CTA.
3. **Draft** — an agent writes against the brief at the word band for its page type.
4. **Gate** — the six-block publication gate in `docs/BLOG-STANDARD.md`: identity, commercial correctness,
   originality, claims and title, technical delivery, post-publication monitoring.
5. **Publish** — Lareesa publishes from the manager. Nothing self-publishes.
6. **Measure** — at 14, 30 and 60 days: impressions and average position for the target query, plus
   qualified inquiries attributed to the slug. A page with no impressions at 60 days gets revised or merged.

## Targets and honesty rules

- Priority is set by intent and by the SERP gap, never by a made-up search volume.
- A page is judged by qualified inquiries and impressions on its target query, not by traffic.
- Every price carries currency, configuration, offer type and last-checked date.
- An unavailable fact is written as unavailable. A competitor's number is never presented as our offer.
- No page targets a query we cannot serve — no Indian, Pakistani or Gulf price variants.

## What this changes about the plan

The 42-article calendar stays, but every article now carries a target query and a page type, and the money
pages come first. Titles still follow the twelve patterns; the one rule that changes is that a price belongs
in a title when the query itself contains price, because that is what the searcher typed. It stays out of
titles for job and category pages, where the reader is still deciding what kind of machine they need.

## Installed toolchain (2026-11-03)

Twelve MIT skills are now installed under `skills/seo/`, plus one orchestrator (`seo-blog-articles`):

| Stage | Skill |
| --- | --- |
| Strategy | `blog-strategy` |
| Cluster map | `seo-cluster` |
| Brief | `blog-brief` |
| Skeleton | `blog-outline` |
| Draft | `blog-write` |
| Claims | `blog-factcheck` |
| On-page gate | `blog-seo-check` |
| Schema | `blog-schema` |
| AI citation | `blog-geo`, `geo-citability`, `geo-content` |
| Page audit | `seo-page` |

Sources: AgriciDaniel/claude-seo, AgriciDaniel/claude-blog, zubair-trabzada/geo-seo-claude.

Titles come from the harvest, verbatim: an article may only lead with a phrase that appeared in
autocomplete for this market. Checked against the live SERP before a word is written.
