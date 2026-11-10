"""Put the landing page's navigation on every page of the site.

The home page nav is the reference: fixed, 72px, hairline dropdowns on Industries,
Join us / Get started on the right, hamburger under 900px. Product pages still
carry the older `companion-nav` strip and the blog and library carry a plain
five-link bar, so the site reads as three different websites.

This injects one self-contained bundle (`#mainNav` scoped CSS, the nav markup,
and 20 lines of JS) and removes the page's own navigation. Scoping every rule to
`#mainNav` beats the page's own `.nav` / `.companion-nav` rules without having to
surgery each stylesheet.

Run:  python tools/sync_nav.py [--dry-run] [pages...]
"""
import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MARK = 'data-nav="canonical"'

NAV_HTML = '''<nav class="nav" id="mainNav" data-nav="canonical">
  <a href="/" class="nav-logo"><img src="/images/logo.svg" alt="Robotist" style="height:28px;width:auto;" width="132" height="28"></a>
  <ul class="nav-links">
    <li><a href="/#catalogue">Catalogue</a></li>
    <li><a href="/#services">Services</a></li>
    <li class="nav-sub">
      <a href="/industries/hotels.html" class="nav-sub-toggle" aria-haspopup="true" aria-expanded="false">Industries<span class="nav-caret" aria-hidden="true"></span></a>
      <div class="nav-submenu" role="menu" aria-label="Industries">
        <a role="menuitem" href="/industries/hotels.html">Hotels &amp; hospitality<span>Cleaning, delivery and guest service</span></a>
        <a role="menuitem" href="/industries/facilities.html">Cleaning &amp; facilities<span>Contract cleaners, offices, venues</span></a>
        <a role="menuitem" href="/industries/warehousing.html">Warehousing &amp; logistics<span>Large floors, between-shift cleaning</span></a>
        <a role="menuitem" href="/industries/retail.html">Retail &amp; showrooms<span>Floors, stock moves, customer help</span></a>
      </div>
    </li>
    <li><a href="/compare.html">Compare</a></li>
    <li><a href="/motion-library/">Motion library</a></li>
    <li><a href="/blog.html">Blog</a></li>
    <li><a href="/about.html">About</a></li>
    <li><a href="/contact.html">Contact</a></li>
  </ul>
  <div class="nav-actions">
    <a href="/grn/" class="nav-cta nav-cta--ghost">Join us</a>
    <a href="/contact.html" class="nav-cta">Get Started</a>
  </div>
  <button class="nav-hamburger" aria-label="Menu" aria-expanded="false">
    <span></span><span></span><span></span>
  </button>
</nav>'''

NAV_CSS = '''<style id="site-nav-css">
/* Site navigation — identical on every page, scoped to #mainNav so a page's own
   .nav / .companion-nav rules cannot drift from it. */
#mainNav{position:fixed;top:0;left:0;right:0;z-index:900;height:72px;display:flex;align-items:center;
  justify-content:space-between;padding:0 clamp(24px,6vw,80px);transition:background .4s,border-color .4s;
  font-family:'Inter',system-ui,-apple-system,'Segoe UI',sans-serif}
#mainNav.scrolled{background:rgba(3,8,16,.88);backdrop-filter:blur(24px);-webkit-backdrop-filter:blur(24px);
  border-bottom:1px solid rgba(74,168,200,.08)}
#mainNav .nav-logo{display:flex;align-items:center;text-decoration:none}
#mainNav .nav-logo img{height:28px;width:auto;display:block}
#mainNav .nav-links{display:flex;align-items:center;gap:40px;list-style:none;margin:0;padding:0}
#mainNav .nav-links a{font-weight:300;font-size:11px;letter-spacing:.14em;text-transform:uppercase;
  color:#8FA3B5;text-decoration:none;transition:color .2s}
#mainNav .nav-links a:hover{color:#fff}
#mainNav .nav-actions{display:flex;align-items:center;gap:12px}
#mainNav .nav-cta{display:inline-flex;align-items:center;justify-content:center;min-height:42px;line-height:1;
  font-weight:500;font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#03080F;background:#4AA8C8;
  padding:0 26px;text-decoration:none;transition:background .2s,transform .15s}
#mainNav .nav-cta--ghost{background:transparent;color:#8FA3B5;border:1px solid rgba(255,255,255,.18)}
#mainNav .nav-cta:hover{background:#63B9D6;transform:translateY(-1px)}
#mainNav .nav-cta--ghost:hover{color:#fff;border-color:rgba(255,255,255,.45)}
#mainNav .nav-sub{position:relative}
#mainNav .nav-caret{display:inline-block;width:6px;height:6px;margin-left:8px;border-right:1.5px solid currentColor;
  border-bottom:1.5px solid currentColor;transform:rotate(45deg) translateY(-2px);opacity:.55;transition:transform .18s}
#mainNav .nav-sub:hover .nav-caret,#mainNav .nav-sub:focus-within .nav-caret{transform:rotate(-135deg) translateY(-2px);opacity:1}
#mainNav .nav-sub:hover .nav-sub-toggle,#mainNav .nav-sub:focus-within .nav-sub-toggle{color:#F0F4F8}
#mainNav .nav-submenu{position:absolute;top:calc(100% + 16px);left:-18px;padding:4px 0;min-width:300px;
  background:#03080F;border:1px solid rgba(255,255,255,.09);border-radius:0;box-shadow:0 22px 48px rgba(0,0,0,.55);
  opacity:0;visibility:hidden;transform:translateY(6px);transition:opacity .18s,transform .18s,visibility .18s;z-index:60}
#mainNav .nav-sub::after{content:"";position:absolute;top:100%;left:-18px;width:300px;height:20px}
#mainNav .nav-sub:hover .nav-submenu,#mainNav .nav-sub:focus-within .nav-submenu{opacity:1;visibility:visible;transform:none}
#mainNav .nav-submenu a{display:block;padding:11px 18px;border-left:2px solid transparent;font-size:11px;
  letter-spacing:.14em;text-transform:uppercase;color:#8FA3B5;text-decoration:none}
#mainNav .nav-submenu a span{display:block;margin-top:5px;font-size:10px;letter-spacing:.06em;text-transform:none;
  color:rgba(143,163,181,.72);line-height:1.45}
#mainNav .nav-submenu a:hover{color:#fff;border-left-color:#4AA8C8;background:transparent}
#mainNav .nav-submenu a:hover span{color:rgba(234,241,247,.75)}
#mainNav .nav-hamburger{display:none;flex-direction:column;gap:5px;cursor:pointer;background:none;border:none;padding:6px}
#mainNav .nav-hamburger span{display:block;width:24px;height:1px;background:#8FA3B5;transition:transform .2s,opacity .2s}
#mainNav .nav-hamburger.active span:nth-child(1){transform:rotate(45deg) translateY(6px)}
#mainNav .nav-hamburger.active span:nth-child(2){opacity:0}
#mainNav .nav-hamburger.active span:nth-child(3){transform:rotate(-45deg) translateY(-6px)}
@media(max-width:900px){
  #mainNav .nav-links{display:none;flex-direction:column}
  #mainNav .nav-links.open{display:flex;position:absolute;top:72px;left:0;right:0;background:rgba(3,8,16,.97);
    backdrop-filter:blur(24px);padding:18px 24px;gap:14px;z-index:400;border-bottom:1px solid rgba(74,168,200,.1)}
  #mainNav .nav-hamburger{display:flex}
  #mainNav .nav-submenu{position:static;opacity:1;visibility:visible;transform:none;background:transparent;
    border:0;box-shadow:none;padding:6px 0 0 12px;min-width:0}
  #mainNav .nav-sub::after{display:none}
  #mainNav .nav-submenu a{padding:8px 0;font-size:14px;letter-spacing:.02em;text-transform:none;color:#A9BACB}
  #mainNav .nav-submenu a span{display:none}
  #mainNav .nav-links a{font-size:14px;letter-spacing:.02em;text-transform:none;color:#A9BACB;padding:6px 0}
  #mainNav .nav-actions{gap:8px}
  #mainNav .nav-cta{padding:0 14px;min-height:38px;font-size:10px}
  #mainNav .nav-cta--ghost{display:none}
}
</style>'''

NAV_JS = '''<script id="site-nav-js">
(function () {
  var nav = document.getElementById('mainNav');
  if (!nav) return;
  var links = nav.querySelector('.nav-links');
  var burger = nav.querySelector('.nav-hamburger');
  var onScroll = function () { nav.classList.toggle('scrolled', window.scrollY > 60); };
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
  if (burger) {
    burger.addEventListener('click', function (e) {
      e.preventDefault();
      var open = links.classList.toggle('open');
      burger.classList.toggle('active', open);
      burger.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }
})();
</script>'''

OLD_NAV_RE = re.compile(r'<(nav|header)\b[^>]*class="[^"]*(?:nav|companion-nav)[^"]*"[\s\S]{0,4000}?</\1>')


def patch(page):
    src = page.read_text(encoding='utf-8')
    if MARK in src:
        if '/motion-library/' in src and '>Motion library<' in src:
            return 'already canonical'
        # canonical nav shipped before the viewer existed: add the item only
        m = re.search(r'(<li><a href="/compare.html">Compare</a></li>)', src)
        if m:
            src = src[:m.end()] + '\n    <li><a href="/motion-library/">Motion library</a></li>' + src[m.end():]
            page.write_text(src, encoding='utf-8')
            return 'canonical + motion library item'
        return 'already canonical (no compare item)'
    m = OLD_NAV_RE.search(src)
    if not m:
        return 'no nav found'
    markup = NAV_HTML
    if page.name == 'index.html':
        # The home page owns the reference design: keep its own scoped styles and
        # its own nav script (which also fades the Spline hero), only bring the
        # menu items in line so the site reads as one navigation.
        markup = markup.replace(
            '<a href="/contact.html" class="nav-cta">Get Started</a>',
            '<a href="/contact.html" onclick="openInquiry();return false" class="nav-cta">Get Started</a>')
        src = src[:m.start()] + markup + src[m.end():]
        page.write_text(src, encoding='utf-8')
        return 'nav replaced (home, own css/js kept)'
    fixed = 'position:fixed' in src[:m.end()] or 'position: fixed' in src[:m.end()]
    src = src[:m.start()] + markup + src[m.end():]
    if 'id="site-nav-css"' not in src:
        src = src.replace('</head>', NAV_CSS + '\n</head>', 1)
    if not fixed:
        src = src.replace('</head>', '<style id="site-nav-offset">body{padding-top:72px}</style>\n</head>', 1)
    if '</body>' in src:
        src = src.replace('</body>', NAV_JS + '\n</body>', 1)
    else:
        src += '\n' + NAV_JS
    page.write_text(src, encoding='utf-8')
    return 'nav replaced' + ('' if fixed else ' + offset')


SITE_PAGES = [
    'index.html', 'about.html', 'compare.html', 'contact.html', 'cookies.html',
    'faq.html', 'terms.html', '404.html', 'library.html', 'blog.html',
    'blog-post.html', 'motion-library/index.html',
    *sorted(p.name for p in (ROOT / 'blog').glob('*.html')),
    *['industries/' + p.name for p in sorted((ROOT / 'industries').glob('*.html'))],
    *sorted(p.name for p in (ROOT / 'reviews').glob('*.html')),
]


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    dry = '--dry-run' in sys.argv
    targets = [ROOT / a for a in args] if args else [
        ROOT / a for a in SITE_PAGES
    ]
    for page in targets:
        if not page.exists():
            print(page.name, 'missing')
            continue
        src = page.read_text(encoding='utf-8')
        status = 'would replace' if dry else patch(page)
        if dry:
            status = 'already canonical' if MARK in src else ('no nav found' if not OLD_NAV_RE.search(src) else 'would replace')
        print(f'{page.relative_to(ROOT).as_posix():46} {status}')
