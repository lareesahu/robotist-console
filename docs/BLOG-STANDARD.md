# Robotist blog standard

One home for how a Robotist article is written, sourced, illustrated, tagged and checked. The pipeline
mechanics live in `hermes/robotist-blog/PIPELINE.md`; this file owns the editorial bar. Where the two
disagree, this file wins and the pipeline gets fixed.

Owner: Lareesa publishes. Drafts only, always.

**Version 2 — 3 November 2026.** Revised after the external review saved at
`docs/reviews/2026-11-03-chatgpt-review-of-blog-plan.md`: a model Profile is no longer owed to every
model, Buyer Guide is a first-class type, numeric quotas were replaced with evidence and commercial
requirements, and the gate now checks intent overlap, decision value and whether the offer can be
fulfilled. Where v1 and v2 disagree, v2 wins.

---

## 1. Three article types

| Type | Words | Job | Where it comes from |
|---|---|---|---|
| Signal | 500–700 | Explain one robotics development and what it changes for a buyer | LinkedIn post, catalogue fact, industry event with a real angle |
| Profile | 700–1,800, no minimum if the buyer question is answered | One model: what it is, what it costs, who should buy it, what it cannot do | `blog-plan.json` inventory, only when it clears the bar below |
| Verdict | 1,200–2,600 | Rank several models against a published rubric for one buying job | `blog-plan.json` pilot |
| Buyer Guide | 1,000–1,800 | Cost, feasibility, procurement and operating requirements for one buying job | `blog-plan.json` pilot |

**A model on the shelf is not an article owed.** A Profile exists only when it carries at least three
decision-relevant findings the product page does not, and answers a question the product page leaves
open. Where it would repeat the product page, expand the product page instead of creating a second URL.
A Verdict borrows Profiles as sources; it never repeats them. A Buyer Guide carries the money and the
site conditions, which neither of the other types can hold.

---

## 2A. Titles

A title is the article's first claim, and the only part most readers see. Two things must be true at once:
a busy procurement lead opens it, and nothing in it would embarrass us if that lead's director read it.

**The twelve patterns** (full table with mechanisms and risks in `docs/blog-plan.json`): price isn't the
cost · direct price comparison · specification contradiction · expensive mistake · overlooked dependency ·
buyer's hard question · suitability challenge · deal-breaker list · technical misconception · operational
scenario · marginal-cost decision · evidence-gap reveal.

**Titles are search-led (Lareesa, 2026-11-03).** A title starts with the phrase people actually type —
"commercial cleaning robots", "floor scrubber robot", "cleaning robots for hotels" — pulled from autocomplete
data, not invented. Then it adds the specific promise that earns the click. Clever-but-unsearchable titles
("The Route Decides More Than the Robot Does") are banned: they read well and rank for nothing. Title 55-62
characters, keyword first, colon or dash before the promise. Slugs repeat the keyword phrase in the same
order, lower-case, hyphenated. seoTitle may be shorter but must still lead with the keyword.

**Money is never the subject (Lareesa, 2026-11-03).** Price analysis is not what makes a robot article
worth reading, and it is not why anybody buys a robot. An article may state a price as a fact in a sentence.
It may not be built around price, cost, payback, runtime-per-dollar or a comparison table of figures. Write
about what the machine does, what changes on the site, what fails, and what the buyer has to decide. Money is
a detail inside the story, never the story.

**Price is not the frame.** A price leads at most one title in five, and only where price is the buyer's
actual question: a cost guide, a marginal-cost verdict, a verification-before-you-pay piece. Everywhere else
the headline leads with the decision, the constraint or the misconception, and the price sits in the body.
A catalogue where every headline carries a number reads as a price list and stops earning credibility.

**Every title passes all seven checks mechanically:**

1. Named entity — every model name resolves to one catalogue product ID and an approved configuration.
2. Number validation — every price, percentage, figure, duration and count traces to a fact or a
   reproducible calculation.
3. Price freshness — a price in a title needs an approved offer record checked within 30 days, with
   configuration and currency.
4. Promise integrity — no "replaces staff", "guaranteed ROI", "proven safer", "eliminates downtime".
5. Answer coverage — the article contains an identifiable, evidence-based answer to the title's question.
6. Evidentiary alignment — a title implying testing, ranking or measured performance links to that kind of
   evidence.
7. Duplicate targeting — no title whose intent duplicates an existing page without a materially different
   answer.

A question mark is not a loophole. The title generator emits a structured claim list (model IDs, claim
type, value, formula, fact IDs), and the checker validates the claims, then the arithmetic, then whether
the configurations are comparable.

## 2B. Evidence status

Every claim carries one status: `verified_manufacturer_spec`, `verified_commercial_offer`,
`independent_report`, `robotist_observation`, `editorial_inference`, `unknown`, `conflict`. An `unknown`
never becomes a plausible sentence, and a `conflict` stops the claim until it is resolved. A less-documented
model still gets its Profile — it just states what is known and what is not, instead of being padded.

## 2. The reader, and the one question

Write for a person who has budget authority and a real site, not a robotics enthusiast. They are asking
one question while reading: **what would this actually do for me, and what will it cost me to find out?**

Every section answers part of that. A section that only restates the spec sheet gets cut.

- Named buyer: facility manager, hotel GM, lab director, plant engineer, integrator, procurement lead.
- One call to action per article, written for that buyer's decision: "Request an inspection configuration
  quote" for a plant engineer, "Request the research configuration and documentation" for a lab director.
  Never a generic contact link.
- Their fear: buying a demo, not a product. Lead time, spares, integration, support, resale.
- Their constraint: a budget that has to be defended to someone else.

---

## 3. Voice — humanized, not decorated

Applies to every sentence, heading, caption and meta description.

1. **A person says it.** Active voice, a real subject doing a real verb. "Keenon rates the C40-P1 at
   1,100 m²/h" — not "a coverage rate of 1,100 m²/h is quoted".
2. **Concrete beats abstract.** "45 kg payload" beats "impressive carrying capacity". "USD 7,999" beats
   "competitively priced".
3. **One idea per sentence.** Vary the length. A run of same-length sentences is machine cadence.
4. **No hype vocabulary.** Banned: revolutionary, groundbreaking, game-changing, cutting-edge,
   state-of-the-art, next-generation, seamless, empower, elevate, unlock, leverage, robust solution,
   future-proof, unleash, transform. Replace each with the fact it was hiding.
5. **No AI tells.** No "In today's fast-paced world", no "It's important to note", no three-item tricolon
   for rhythm, no em-dash-as-personality, no rhetorical question as a section opener, no summary
   paragraph that repeats the previous one.
6. **Speak the trade's language, then explain it once.** Expand an abbreviation on first use in the body:
   `IMU (inertial measurement unit)`, `SLAM (simultaneous localisation and mapping)`, `WDP (wholesale
   dealer price)`. Never expand inside a quote, code or a product name.
7. **Admit the limit.** Every Profile names at least one thing the model does badly, or a buyer for whom
   it is the wrong purchase. This is what makes the rest believable.
8. **Read it aloud before it ships.** If a line would not survive being said to a colleague, rewrite it.

---

## 4. Research — real, traceable, dated

A Profile is built from a research pack saved at `hermes/robotist-blog/research/<slug>.md` before writing.
The pack holds every number used, with its source URL.

- **Specs:** the manufacturer's own product page or datasheet. Link it inline where the claim appears.
- **Price:** catalogue WDP if published, otherwise the vendor quote. Always with currency and an
  `as of <Month YYYY>` note. Prices move; an undated price is a defect.
- **Capability claims:** manufacturer claim vs independent evidence are different things. Write
  "Keenon claims 15 hours" until something verifies it. Never present a claim as a measured result.
- **Independent sources:** two credible ones per Profile beyond the vendor (trade press, university,
  integrator write-up), and they must actually say what is attributed to them.
- **Never invent:** market sizes, deployment counts, customer names, competitor prices, test results.
  No checkable number, no claim.
- **Every technical claim carries its operating condition.** Keenon's 15 hours is sweeping; scrubbing is
  about 5. Phantas ~1,180 m²/h is a rated rate; Gausium's practical efficiency is 350–700 m²/h. MagicDog Y1
  is 150 kg maximum payload and 45 kg dynamic payload. A number without its condition is a defect.
- **Label the evidence class** for every performance statement: manufacturer specification / manufacturer
  demonstration / independent reported result / Robotist-verified finding / unverified. Never blend two
  classes into one sentence.

### 4.1 The price data model

One price record feeds the catalogue, the product page and the article. A price is only published when the
record carries: currency, configuration, price type (public list / indicative / dealer quote), date
confirmed, freight and tax exclusions, geographic scope, and source URL. A competitor's or a reseller's
number is never presented as Robotist's offer.
- **No testing claim we did not earn.** These are spec-based profiles informed by dealer access. Say that
  in the method line. A false "we tested it" costs more than the article is worth.

---

## 5. Structure

### Profile (1,200–1,800 words)

| Section | Length | Must contain |
|---|---|---|
| Opening | 90–130 | The model, the job it does, the price, who it suits — no wind-up |
| What it is | 250–350 | Form factor, degrees of freedom, compute, sensors, payload, runtime, weight, IP rating, each with its condition |
| What it does in a working day | 300–400 | Two or three concrete scenarios with numbers, not adjectives |
| What it costs | 150–250 | Unit price, delivery and duty, consumables or service, three-year total, lead time |
| What it does badly | 150–250 | At least two honest limits, and the buyer for whom it is wrong |
| How it compares | 150–250 | Two or three alternatives named, one line each, link the Verdict that ranks them |
| What to do next | 80–120 | The decision, the proof to ask for, the call to action |

A comparison table goes in only when real alternatives exist in the catalogue. An FAQ goes in only when
there are four questions buyers actually ask — never to fill a template. A Profile without either is not
a defect.

### Signal (500–700 words)

Two opening paragraphs, three to five `h3` sections, one image, three FAQs, a closing paragraph that says
what a buyer should do with the story. No dates, no "this week", nothing that expires.

---

## 6. Hyperlinking

- **Inline, on the phrase that carries the claim.** Not "click here", not a bare URL, never a link dump at
  the end.
- **Cite every material external claim**, on the phrase that carries it. There is no link quota: a piece
  built from two solid sources is fine, and a piece that pads to six weak ones is not.
- **Link the primary product page and any genuinely relevant catalogue alternative.** No fixed count: an
  article about one machine links one product page, and that is correct.
- **Related articles as they exist.** No sibling-article quota while the blog is still thin; add the link
  when the article is published.
- One link per target. If the same page would be linked twice, the second mention is plain text.
- Competitor product pages may be linked where the comparison is the service being delivered — a Verdict
  that will not name the field is not a ranking. A Profile names alternatives and links the Verdict.

---

## 7. Metadata and tags

Enforced by `commit_draft.py` (limits are hard):

| Field | Rule |
|---|---|
| `slug` | lowercase, hyphens, 3–6 words, no dates, no "best" unless it is a Verdict |
| `title` | says what the article proves; 45–65 characters, no clickbait |
| `seoTitle` | ≤ 62 characters, includes the model name |
| `metaDescription` | ≤ 158 characters, one concrete fact and one benefit, no "learn more" |
| `excerpt` | two sentences, 25–40 words, written for a human scanning a feed |
| `keywords` | 3–6, buyer-phrased, no duplicates of the title verbatim |
| `category` | reuse an existing category; never invent a new one without checking |
| `date` | ISO `YYYY-MM-DD` |
| `readTime` | calculated, not guessed |
| `faq` | 3–5 question/answer pairs, buyer voice, each answer 40–80 words |
| `format` | `signal` or `profile` — enables the stricter Profile checks |
| `tags` | 3–5 from the taxonomy below |

### Tag taxonomy (controlled)

Pick 3–5, one from each axis where possible:

- **Form:** humanoid, quadruped, wheeled-humanoid, cleaning, mobile-manipulator, industrial-arm, companion-head
- **Job:** inspection, security-patrol, cleaning, logistics, research, education, hospitality, teleoperation, quality-control, interaction
- **Buyer:** facility-manager, hotel, university, plant-engineer, integrator, venue, care-provider
- **Stage:** evaluate, buy, deploy, maintain

Free-text tags are a defect. Additions go in this list, not in the article.

---

## 8. Images

Every article ships a hero cover, and as many working figures as it can honestly support. A figure that
only decorates is dropped; a drawing that carries the buying logic (a floor-plan fit, a shift timeline, a
cost stack) beats a photograph of the same robot on a white background.

**Where they go.** A figure sits directly after the section it proves, never between a heading and its first
sentence, never inside the opening two paragraphs, roughly one per 450 words. Placement is decided in the
outline, not after writing.

**Spec:**

| Use | Size | Ratio | Format |
|---|---|---|---|
| Cover | 1664 × 928 (pipeline output) | 16:9 | JPEG, ≤ 300 KB |
| Inline figure | ≥ 1600 px wide master | 3:2 or 16:9 | WebP, ≤ 250 KB |
| Detail crop | ≥ 1200 px | 1:1 | WebP |

- Real product photography first: the robot in a real environment, at its working scale.
- The catalogue cut-outs (`robots-cut/<name>.webp`, 525–1200 px, transparent) are for covers and
  comparison strips. They are not inline figures: a cut-out floating on a page proves nothing.
- **Alt text** describes what is visible in ≤ 125 characters. **Caption** ≤ 20 words, says what to notice,
  carries the credit when the image is not ours.
- Rights recorded per file in `docs/image-rights.md`: vendor press kit, our own photograph, or licensed.
- Never hotlink, never stretch, never put text in an image, never use a stock photo of a different robot,
  never generate an image with an AI model without Lareesa's explicit yes for that article
  (SOUL §6.6). If the only image available is a cut-out, the article waits for a press kit rather than
  shipping a weak figure.

---

## 9. The gate — pass/fail before a draft is committed

Each line is pass or fail. One fail stops the article.

1. Every number traceable to the research pack, the price carries its type, configuration and `as of` date,
   and every performance claim carries its operating condition and evidence class (§4).
2. At least two honest limits, and a stated buyer this model does not suit.
3. No banned hype words (grep the list in §3.4).
4. Word count inside the band for its type — and no padding to reach it.
5. Every material external claim cited inline; product links to the models actually discussed.
6. Metadata inside its limits; tags from the taxonomy; FAQ answers in buyer voice where an FAQ exists.
7. A hero cover, plus any figure the article needs; alt text and caption on each; vendor material labelled.
8. Image rights recorded.
9. Read aloud once, by me, at the end.
10. `python commit_draft.py --draft <file> --dry-run` returns no problems.
11. **Intent check.** The primary question this article answers is not already answered by an existing
    product page or article. If it is, consolidate or differentiate before writing.
12. **At least three decision-relevant findings** the product page does not carry. If they cannot be
    sourced, the standalone article does not ship.
13. **Commercial approval.** Someone confirms the model is orderable in the stated configuration, that a
    quote can be issued for the target destination, that the lead time, warranty, support and integration
    claims are supportable, and that the call to action reaches a real response process.
14. **Lead tracking.** The article carries its slug into the inquiry form so qualified inquiries are
    attributable.

`--dry-run` is the last step before commit. A draft that fails it never reaches her review queue.

---

## 10. Freshness and the update loop

- Prices, lead times and firmware change. Each article carries a `Last checked: <Month YYYY>` line in the
  body, a `dateModified` field, and the name of who approved the technical and commercial facts.
- Event-triggered review, not a calendar sweep: re-open an article when the model is revised, the supplier
  changes price, a firmware capability changes materially, or availability changes. A quarterly pass still
  runs on live articles, but it is the floor.
- A Verdict is re-scored when any model in it changes price by more than 10 %, or when a new model joins
  the same job.

## 10.1 Publishing requirements

Every article ships with: one primary intent nobody else on the site owns, a self-canonical URL, a
descriptive title, crawlable internal links, accessible tables with headers, structured data that matches
what the page actually shows, and submission for indexing with Search Console checked after two weeks.
Markup is not a rich-result guarantee and is never reported as one.

---

## 11. What the pipeline already enforces, and what this adds

`commit_draft.py` already refuses: missing required fields, a draft that is not `status: draft`, fewer
than three FAQs, fewer than three keywords, `seoTitle` over 62, `metaDescription` over 158, fewer than two
`/products/` links, no embedded image, no cover.

This standard adds the Profile checks (`format: "profile"`): word count, external citations, tag taxonomy,
image count and alt text, an `as of` price line, and the banned-word list. They are enforced in the same
validator so a Profile cannot slip through while a Signal still passes exactly as before.
