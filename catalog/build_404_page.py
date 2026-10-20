"""Build 404.html — the public not-found page.

The site's 404 used to fall through to the console's error template, which talked
about saving an action and offered "Back to GRN". A visitor who mistypes an
address gets this page instead: the site's own navigation and footer, a plain
explanation, and the real destinations.

Run from the repository root:  python -m catalog.build_404_page
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from catalog.build_cookies_page import SCRIPT, og_block, shell_css, shell_parts  # noqa: E402

PAGE_CSS = """
/* ── Not found page ── */
.nf{max-width:var(--container);min-width:0;padding:calc(var(--nav-h) + clamp(56px,9vw,112px)) var(--gutter) clamp(64px,9vw,112px)}
.nf-eyebrow{font-size:11px;letter-spacing:.22em;text-transform:uppercase;color:var(--accent);margin-bottom:18px}
.nf-title{font-size:clamp(32px,5vw,56px);line-height:1.08;font-weight:300;letter-spacing:-.02em;max-width:22ch;text-wrap:balance}
.nf-lede{margin-top:20px;font-size:clamp(15px,1.6vw,17px);line-height:1.7;color:var(--grey-1);max-width:60ch}
.nf-grid{margin-top:clamp(36px,5vw,56px);display:grid;grid-template-columns:minmax(0,1fr);gap:14px;max-width:1000px}
@media(min-width:640px){.nf-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(min-width:1180px){.nf-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}
.nf-card{display:block;padding:20px 22px;border:1px solid var(--grey-3);border-radius:12px;background:var(--bg-1);text-decoration:none;transition:border-color .25s ease,background .25s ease}
.nf-card:hover{border-color:var(--accent);background:var(--bg-2)}
.nf-card .t{display:block;font-size:16px;color:var(--white);font-weight:500}
.nf-card .s{display:block;margin-top:6px;font-size:13px;line-height:1.6;color:var(--grey-1)}
.nf-card:focus-visible{outline:2px solid var(--accent-light);outline-offset:2px}
.nf-actions{margin-top:clamp(32px,4vw,44px);display:flex;flex-wrap:wrap;gap:16px;align-items:center}
.nf-actions .nf-home{display:inline-flex;align-items:center;min-height:44px;padding:0 22px;border-radius:999px;background:var(--accent);color:var(--bg-0);font-weight:600;text-decoration:none}
.nf-actions .nf-home:focus-visible{outline:2px solid var(--accent-light);outline-offset:2px}
.nf-actions .nf-talk{display:inline-flex;align-items:center;min-height:44px;color:var(--accent-light);text-decoration:underline;text-underline-offset:3px}
@media(max-width:640px){.nf-grid{grid-template-columns:1fr}}
"""

DESTINATIONS = [
    ("Home", "What Robotist is, and the work it does", "/"),
    ("Robot catalogue", "The machines, with full technical specifications", "/#catalogue"),
    ("Compare robots", "Every machine, side by side", "/compare.html"),
    ("Services", "Integration, deployment and maintenance", "/#services"),
    ("Blog", "What is changing in commercial robotics", "/blog.html"),
    ("FAQ", "The questions we are asked most", "/faq.html"),
    ("Contact", "Ask a question, or start a project", "/contact.html"),
    ("Cookie policy", "What the site stores, and how to change it", "/cookies.html"),
]


def main():
    nav, footer = shell_parts()
    description = ("The address you followed is not on the Robotist site. Every published page, "
                   "from the robot catalogue to the contact form, is one click away.")
    cards = "\n".join(
        f'      <a class="nf-card" href="{href}"><span class="t">{title}</span>'
        f'<span class="s">{sub}</span></a>'
        for title, sub, href in DESTINATIONS)
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<link rel="icon" href="/favicon.svg">
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">

<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#030810">
<title>Page not found — Robotist</title>
<meta name="description" content="{description}">
<meta name="robots" content="noindex, follow">
{og_block(description)}

<link rel="canonical" href="https://www.robotist.com.au/404.html">

<style>
{shell_css()}
{PAGE_CSS}
</style>
</head>
<body>
{nav}

<main class="nf" id="main">
  <p class="nf-eyebrow">404</p>
  <h1 class="nf-title">This page moved, or never existed.</h1>
  <p class="nf-lede">The address you followed is not on the site. Nothing was lost, and nothing was
    submitted. Here is the way back.</p>
  <div class="nf-grid">
{cards}
  </div>
  <div class="nf-actions">
    <a class="nf-home" href="/">Back to the home page</a>
    <a class="nf-talk" href="/contact.html">Talk to the team</a>
  </div>
</main>

{footer}

{SCRIPT}
</body>
</html>
"""
    target = ROOT / '404.html'
    newline = '\r\n' if target.exists() and target.read_bytes()[:4000].count(b'\r\n') else ''
    target.write_text(page, encoding='utf-8', newline=newline)
    text = target.read_text(encoding='utf-8')
    leftovers = [w for w in ('GRN', 'action was not saved', 'Back to GRN') if w.lower() in text.lower()]
    print(f"404.html: {len(text)} bytes | console leftovers: {leftovers or 'none'}")


if __name__ == '__main__':
    main()
