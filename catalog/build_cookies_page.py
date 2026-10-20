"""Build cookies.html from the design system and shell of the existing pages.

The policy page reuses the site's own tokens, navigation and footer rather than
inventing a second header, so it cannot drift out of step with the rest of the
site. Run from the repository root:  python scripts/build_cookies_page.py
"""
import re, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from catalog.site_shell import _rules
from bs4 import BeautifulSoup

SOURCE='about.html'
KEEP=re.compile(r'^(?:\*|html|body|a|img|h1|h2|h3|p|ul|li|em|strong|:root|\.btn-)')
KEEP_SCOPED=re.compile(r'\.(?:nav|footer)(?:[-\s.:#\[]|$)')

def keep(selector):
    for part in selector.split(','):
        part=part.strip()
        if not part:continue
        if KEEP.match(part) or KEEP_SCOPED.search(part):return True
    return False

def shell_css():
    page=(ROOT/SOURCE).read_text(encoding='utf-8')
    css='\n'.join(re.findall(r'<style[^>]*>(.*?)</style>',page,re.S))
    kept=[]
    for selector,body in _rules(css):
        if selector.startswith('@media'):
            inner=[s+'{'+b+'}' for s,b in _rules(body) if keep(s)]
            if inner:kept.append(selector+'{'+''.join(inner)+'}')
        elif not selector.startswith('@') and keep(selector):
            kept.append(selector+'{'+body+'}')
    return '\n'.join(kept)

def shell_parts():
    page=BeautifulSoup((ROOT/SOURCE).read_text(encoding='utf-8'),'html.parser')
    nav=str(page.select_one('nav.nav'))
    footer=str(page.select_one('footer.footer'))
    # The inquiry modal lives on other pages only, so the call-out here is a plain link.
    nav=nav.replace(' onclick="openInquiry();return false"','')
    return nav,footer

POLICY_CSS="""
/* ── Cookie policy page ── */
.policy{max-width:820px;margin:0 auto;padding:calc(72px + clamp(56px,9vw,110px)) var(--gutter) clamp(70px,10vw,120px)}
.policy-eyebrow{font-size:11px;letter-spacing:.22em;text-transform:uppercase;color:var(--accent);margin-bottom:18px}
.policy-title{font-size:clamp(34px,5.4vw,58px);line-height:1.08;font-weight:300;letter-spacing:-.02em;margin-bottom:20px}
.policy-lede{font-size:clamp(15px,1.6vw,17px);line-height:1.7;color:var(--grey-1);max-width:66ch}
.policy-updated{margin-top:16px;font-size:12px;letter-spacing:.04em;color:var(--grey-2)}
.policy h2{margin:clamp(38px,5vw,56px) 0 14px;font-size:clamp(19px,2.4vw,24px);font-weight:500;letter-spacing:-.01em}
.policy h3{margin:26px 0 8px;font-size:15px;font-weight:600}
.policy p,.policy li{font-size:15px;line-height:1.75;color:var(--grey-1)}
.policy p+p{margin-top:14px}
.policy ul{margin:12px 0 0;padding-left:20px;display:grid;gap:8px}
.policy a{color:var(--accent-light);text-decoration:underline;text-underline-offset:3px}
.policy strong{color:var(--white);font-weight:600}
.policy-choice{margin-top:18px;padding:14px 16px;border:1px solid var(--grey-3);border-radius:12px;background:var(--bg-1);font-size:14px;color:var(--white)}
.policy-actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:16px}
.policy-actions button{font:inherit;font-size:14px;cursor:pointer;border-radius:999px;padding:11px 20px;min-height:44px;border:1px solid var(--accent);background:var(--accent);color:var(--bg-0);font-weight:600}
.policy-actions button.ghost{background:transparent;border-color:var(--grey-3);color:var(--white);font-weight:500}
.policy-actions button.link{background:transparent;border-color:transparent;color:var(--grey-1);text-decoration:underline;text-underline-offset:3px;padding-left:4px;font-weight:400}
.policy-actions button:focus-visible{outline:2px solid var(--accent-light);outline-offset:2px}
.policy-table{width:100%;margin-top:18px;border-collapse:collapse;font-size:14px}
.policy-table th{text-align:left;font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--grey-2);font-weight:500;padding:0 14px 10px 0;border-bottom:1px solid var(--grey-3)}
.policy-table td{padding:14px 14px 14px 0;border-bottom:1px solid var(--bg-3);color:var(--grey-1);vertical-align:top;line-height:1.6}
.policy-table td:first-child{color:var(--white);font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px;white-space:nowrap}
.policy-table td:last-child{padding-right:0}
.policy-note{margin-top:22px;padding:16px 18px;border-left:2px solid var(--accent);background:var(--bg-1);border-radius:0 12px 12px 0}
@media(max-width:640px){
  .policy-table,.policy-table tbody,.policy-table tr,.policy-table td{display:block;width:100%}
  .policy-table thead{display:none}
  .policy-table tr{padding:14px 0;border-bottom:1px solid var(--bg-3)}
  .policy-table td{border:0;padding:2px 0}
}
"""

CONTENT_FILE='catalog/cookies_content.html'

def policy_content():
    """The authored policy copy, kept in its own file so a regenerated page can
    never overwrite a sentence somebody wrote."""
    return (ROOT/CONTENT_FILE).read_text(encoding='utf-8').split('-->\n',1)[-1].strip()



SCRIPT="""<script>
// ── NAV SCROLL ──
const nav = document.getElementById('mainNav');
if (nav) {
  window.addEventListener('scroll', () => {
    nav.classList.toggle('scrolled', window.scrollY > 60);
  }, { passive: true });
}

// ── HAMBURGER MENU TOGGLE ──
const hamburger = document.querySelector('.nav-hamburger');
const navLinks = document.querySelector('.nav-links');

if (hamburger && navLinks) {
  hamburger.addEventListener('click', (e) => {
    e.preventDefault();
    navLinks.classList.toggle('open');
    hamburger.classList.toggle('active');
  });

  navLinks.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', () => {
      navLinks.classList.remove('open');
      hamburger.classList.remove('active');
    });
  });
}

// ── COOKIE CHOICE ──
(function () {
  const api = window.robotistConsent;
  const status = document.getElementById('policy-choice');
  const describe = (value) => value === 'granted'
    ? 'Analytics cookies are on. Thank you — this site can now measure which pages are useful.'
    : value === 'denied'
      ? 'Analytics cookies are off. The site works normally, we simply count visits without cookies.'
      : 'You have not chosen yet, so analytics cookies are off.';

  function paint() {
    if (status) status.textContent = api ? describe(api.choice()) : 'This page needs JavaScript enabled to record your choice.';
  }

  // The notice in the corner writes the same choice, so the line above follows it.
  window.addEventListener('robotist:consent', paint);

  document.querySelectorAll('[data-consent]').forEach(button => {
    button.addEventListener('click', () => {
      if (!api) return;
      const value = button.getAttribute('data-consent');
      if (value === 'clear') api.clear(); else api.set(value);
      paint();
    });
  });

  paint();
})();
</script>"""

def og_block(description):
    """The social card every other page carries, kept for this page too."""
    return f"""<meta property="og:type" content="website">
<meta property="og:url" content="https://www.robotist.com.au/cookies.html">
<meta property="og:title" content="Cookie policy — Robotist">
<meta property="og:description" content="{description}">
<meta property="og:image" content="https://www.robotist.com.au/robotist-og.jpg">
<meta property="og:image:alt" content="Robotist — global robotics platform">
<meta property="og:site_name" content="Robotist">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="https://www.robotist.com.au/robotist-og.jpg">"""


def build(write=True):
    """Return the policy page, writing it unless the caller only wants to compare."""
    nav,footer=shell_parts()
    description='How robotist.com.au uses cookies: the essential cookies that keep the site working, the analytics cookies that wait for your consent, and how to change your choice.'
    page=f"""<!DOCTYPE html>
<html lang="en">
<head>
<link rel="icon" href="/favicon.svg">
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">

<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#030810">
<title>Cookie policy — Robotist | Global Robotics Platform</title>
<meta name="description" content="{description}">
<meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large">
{og_block(description)}

<link rel="canonical" href="https://www.robotist.com.au/cookies.html">

<style>
{shell_css()}
{POLICY_CSS}
</style>
</head>
<body>
{nav}

{policy_content()}

{footer}

{SCRIPT}
</body>
</html>
"""
    if write:
        (ROOT/'cookies.html').write_text(page,encoding='utf-8',newline=('\r\n' if (ROOT/'cookies.html').read_bytes()[:4000].count(b'\r\n') else ''))
    return page

if __name__=='__main__':
    print('cookies.html written:',len(build()),'bytes')
