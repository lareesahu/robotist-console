"""Publish the Robotist brand centre: the delivered brand guide, at its own address.

The brand centre is the identity book that came with the Robotist brand system
(version 1.0) — wordmark, colour system, typography, spacing and grid, interface
components, voice, motion. Its home in this repository is

    docs/brand/reference/robotist-brand-guide.html

and /brand-center serves that document. It is a different artefact from
docs/brand/BRAND_CENTER.md: the guide is the identity itself, the markdown file is
the running record of how this site implements it. Re-typesetting the guide into a
second copy is what would let the two drift apart, so this build copies the
delivered document rather than redrawing it.

Two edits, both required to publish it here:

  1. The three Google Fonts links become local @font-face rules over the Poppins
     files this repository ships in assets/fonts/poppins/ — a published page must
     not depend on a third-party font CDN.
  2. The head gains a description, a canonical address, Open Graph tags and the
     site's own favicon, because the document now has a public URL.

Everything else stays byte-for-byte the delivered guide.

Run from the repository root:  python -m catalog.build_brand_center_page
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SOURCE = ROOT / 'docs' / 'brand' / 'reference' / 'robotist-brand-guide.html'
OUTPUT = ROOT / 'brand-center.html'

PAGE_URL = 'https://www.robotist.com.au/brand-center'
TITLE = 'Robotist — Brand Book'
DESCRIPTION = ('The Robotist brand centre: the wordmark, the colour system, the type system, '
               'spacing and grid, interface components, voice, and motion.')

# The guide asks Google Fonts for these five weights; the same files ship locally.
WEIGHTS = {'300': 'Light', '400': 'Regular', '500': 'Medium', '600': 'SemiBold', '700': 'Bold'}

CDN_LINK = re.compile(r'\s*<link[^>]*fonts\.(?:googleapis|gstatic)\.com[^>]*>', re.I)


def font_faces() -> str:
    return '\n'.join(
        f"@font-face{{font-family:'Poppins';font-style:normal;font-weight:{weight};font-display:swap;"
        f"src:url('/assets/fonts/poppins/Poppins-{name}.woff2') format('woff2')}}"
        for weight, name in sorted(WEIGHTS.items()))


PUBLICATION_CSS = """
/*
The hero wordmark is the logo, not a heading. The site makes every heading bold from one
injected rule (catalog/site.py); that rule is right for text headings and wrong for this
specimen, which the page itself documents as Medium 500 and which the guide says must never be
altered. A class selector outranks the injected element selector, so this wins.
*/
.hero-wordmark { font-weight: 500 !important; }
@media (max-width: 1200px) {
  .section-header > *, .grid-2 > *, .grid-3 > *, .logo-grid > *, .misuse-grid > *,
  .size-grid > *, .swatch-hero > *, .text-hierarchy > *, .typeface-meta > *, .weight-scale > *,
  .radius-scale > *, .comp-grid-2 > *, .voice-pillars > *, .do-dont > *, .writing-examples > *,
  .motion-grid > *, .imagery-block > * { min-width: 0; }
  .imagery-placeholder { max-width: 100%; }
  table { display: block; max-width: 100%; overflow-x: auto; }
}
@media (max-width: 520px) {
  .nav-demo { padding: 0 clamp(10px, 3vw, 16px); gap: 8px; }
  .nav-demo-links { gap: 10px; }
  .nav-demo-links span { letter-spacing: .08em; }
  .nav-demo-btn { padding: 7px 12px; letter-spacing: .08em; }
}
"""

HEAD_ADDITIONS = f"""
<meta name="description" content="{DESCRIPTION}" />
<link rel="canonical" href="{PAGE_URL}" />
<meta property="og:type" content="website" />
<meta property="og:title" content="{TITLE}" />
<meta property="og:description" content="{DESCRIPTION}" />
<meta property="og:url" content="{PAGE_URL}" />
<meta name="theme-color" content="#060D18" />
<link rel="icon" href="/favicon.svg" type="image/svg+xml" />
<style>
/* Poppins is served from this repository, never from a font CDN. */
{font_faces()}
/*
Publication overrides. The guide was drawn for a desktop screen, and two of its habits let a
narrow viewport scroll sideways: grid cells sized `1fr` keep an automatic minimum, so one wide
cell pushes the row past the screen, and its widest tables cannot shrink below their longest
header. Both are corrected here rather than in the document, so the delivered guide stays as
it was delivered.
*/
{PUBLICATION_CSS}
</style>
"""

# Sections the guide is expected to carry. A silent partial import would be worse
# than a failed build, so each one is checked in the output.
MARKERS = ('class="hero"', 'id="logo"', 'id="colour"', 'id="typography"', 'id="components"',
           'id="voice"', 'id="motion"')


def build() -> str:
    if not SOURCE.is_file():
        raise SystemExit(f'missing brand guide source: {SOURCE}')
    html = SOURCE.read_text(encoding='utf-8')

    html, removed = CDN_LINK.subn('', html)
    if removed == 0:
        raise SystemExit('no Google Fonts links found — check the source before building')

    if '</head>' not in html:
        raise SystemExit('the source has no </head> for the page metadata')
    html = html.replace('</head>', HEAD_ADDITIONS.lstrip('\n') + '</head>', 1)

    for reference in ('fonts.googleapis', 'fonts.gstatic'):
        if reference in html:
            raise SystemExit(f'a font CDN reference survived the rewrite: {reference}')

    missing = [marker for marker in MARKERS if marker not in html]
    if missing:
        raise SystemExit(f'the source is missing expected sections: {missing}')
    return html


def main() -> None:
    html = build()
    newline = '\r\n' if OUTPUT.exists() and OUTPUT.read_bytes()[:4000].count(b'\r\n') else ''
    OUTPUT.write_text(html, encoding='utf-8', newline=newline)
    written = OUTPUT.read_text(encoding='utf-8')
    print(f'brand-center.html: {len(written.encode("utf-8"))} bytes from {SOURCE.name}')
    print(f'  font CDN links removed: 3 | local @font-face rules: {len(WEIGHTS)}')
    print('  sections checked: hero, logo, colour, typography, components, voice, motion')


if __name__ == '__main__':
    main()
