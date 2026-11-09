
"""Inject a per-model motion block into every product page.

Source of truth: motion-library/models.json (platform class per product slug)
plus motion-library/data/index.json (clip names/groups). The block is
region-marked so a re-run replaces it instead of stacking copies.
"""
import json, re, html, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / 'motion-library/models.json').read_text(encoding='utf-8'))
CLIPS = {c['id']: c for c in json.loads((ROOT / 'motion-library/data/index.json').read_text(encoding='utf-8'))['clips']}

CSS = """/* Motion records block (generated) */
.motion-block{border-top:1px solid var(--line, #1E2D3D);padding:clamp(44px,5vw,80px) clamp(20px,5.5vw,80px)}
.mb-inner{max-width:1280px;margin:0 auto}
.mb-narrow.motion-block{padding:clamp(36px,4vw,64px) 0}
.mb-narrow .mb-inner{max-width:1052px}
.motion-block .mb-head{display:flex;justify-content:space-between;align-items:baseline;gap:20px;flex-wrap:wrap;margin-bottom:22px}
.motion-block h2{margin:8px 0 0;font-size:clamp(22px,2.4vw,32px);font-weight:500;letter-spacing:-.03em}
.motion-block .mb-lede{margin:12px 0 0;color:#A9BACB;font-size:14px;line-height:1.7;max-width:62ch}
.motion-block .mb-basis{margin:10px 0 0;color:#7E93A6;font-size:12.5px;line-height:1.6;max-width:62ch}
.mb-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-top:26px}
.mb-card{display:block;text-decoration:none;border:1px solid var(--line, #1E2D3D);background:#0A1420;overflow:hidden;transition:border-color .2s,transform .2s}
.mb-card:hover{border-color:var(--accent, #4AA8C8);transform:translateY(-2px)}
.mb-card img{display:block;width:100%;aspect-ratio:16/10;object-fit:cover;background:#04101C}
.mb-card-body{padding:12px 14px 14px}
.mb-card-name{font-size:13.5px;font-weight:600;color:#F0F4F8;letter-spacing:-.01em}
.mb-card-spec{font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;color:#8FA3B5;margin-top:5px}
.mb-chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:26px}
.mb-chip{font-size:12px;color:#A8DCEF;border:1px solid var(--line, #1E2D3D);background:rgba(74,168,200,.06);padding:5px 11px;text-decoration:none}
.mb-chip:hover{border-color:var(--accent, #4AA8C8);color:#fff}
.mb-foot{margin:22px 0 0;font-size:12.5px;color:#8FA3B5}
.mb-foot a{color:#A8DCEF;border-bottom:1px solid #4AA8C8;text-decoration:none}
@media(max-width:820px){.mb-grid{grid-template-columns:1fr 1fr}}
@media(max-width:560px){.mb-grid{grid-template-columns:1fr}}
"""

def block(slug, title, wide=True):
    cls = DATA['models'].get(slug)
    if not cls:
        return None
    set_ids = [c for c in (DATA.get('modelClips', {}).get(slug) or DATA['clipSets'].get(cls, [])) if c in CLIPS]
    basis = DATA.get('modelBasis', {}).get(slug, '')
    view = f'/motion-library/?model={slug}'
    esc = html.escape(title)
    if set_ids:
        cards = []
        for cid in set_ids:
            c = CLIPS[cid]
            cards.append(
                f'<a class="mb-card" href="/motion-library/?clip={cid}&model={slug}">'
                f'<img src="/motion-library/thumbs/{cid}.webp" alt="{html.escape(c["name"])} — 23-joint rig" loading="lazy" decoding="async">'
                f'<div class="mb-card-body"><div class="mb-card-name">{html.escape(c["name"])}</div>'
                f'<div class="mb-card-spec">{c["group"]} · {c["seconds"]:g} s · {c["fps"]:g} fps</div></div></a>')
        body = ('<p class="mb-lede">Clips in the Robotist motion library that fit this body and what the '
                'maker says it can do. Each one opens in the 3D viewer on the rig that performs it.</p>'
                + (f'<p class="mb-basis">Why these: {html.escape(basis)}.</p>' if basis else '')
                + '<div class="mb-grid">' + ''.join(cards) + '</div>')
        foot = (f'{len(set_ids)} of {len(CLIPS)} library clips map to this model — '
                f'<a href="{view}">open the library filtered to {esc}</a> · '
                f'<a href="/motion-library/">all {len(CLIPS)} clips</a>')
    else:
        cats = DATA['recordCats'].get(cls, [])
        chips = ''.join(f'<a class="mb-chip" href="/library.html?cat={c}">{c} records</a>' for c in cats)
        chips += '<a class="mb-chip" href="/motion-library/?clip=wave">Wave, as a gesture study</a>'
        why = (basis[0].upper() + basis[1:] + '.') if basis else 'No humanoid motion set applies to this body.'
        if not why.endswith('.'):
            why += '.'
        body = (f'<p class="mb-lede">{(html.escape(why) + " ") if basis else ""}'
                'Nothing on this page is dressed up as a motion this platform performs. The nearest movement records are below.</p>'
                f'<div class="mb-chips">{chips}</div>')
        foot = f'<a href="/motion-library/">Browse all {len(CLIPS)} humanoid clips</a> · <a href="/library.html">searchable catalogue</a>'
    return (f'<!--MOTION:START — generated from motion-library/models.json, edit there and re-run tools/build_motion_blocks.py-->\n'
            f'<style>{CSS}</style>\n'
            f'<section class="motion-block{" motion-block--wide" if wide else " mb-narrow"}" aria-labelledby="mb-heading" data-model="{slug}" data-class="{cls}"><div class="mb-inner">\n'
            f'<div class="mb-head"><div><p class="eyebrow">Motion library</p>'
            f'<h2 id="mb-heading">{"Motions the " + esc + " can run" if set_ids else esc + ": no library clip fits this body"}</h2></div></div>\n'
            f'{body}\n'
            f'<p class="mb-foot">{foot}</p>\n'
            f'</div></section>\n<!--MOTION:END-->\n')

changed = []
for page in sorted((ROOT / 'products').glob('*.html')):
    slug = page.stem
    src = page.read_text(encoding='utf-8')
    m = re.search(r'<h1[^>]*>(.*?)</h1>', src, re.S)
    title = re.sub(r'<[^>]+>', '', m.group(1)).strip() if m else slug
    new = block(slug, title, wide=('companion-section' not in src))
    if not new:
        print('no class for', slug); continue
    if '<!--MOTION:START' in src:
        src = re.sub(r'<!--MOTION:START.*?<!--MOTION:END-->\n?', new, src, flags=re.S)
    else:
        anchor = '<section class="inquiry-section">'
        if anchor not in src:
            anchor = '</main>'
        if anchor not in src:
            print('no anchor in', slug); continue
        src = src.replace(anchor, new + anchor, 1)
    page.write_text(src, encoding='utf-8')
    changed.append(slug)

print('updated', len(changed), 'pages')
