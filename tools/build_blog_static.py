#!/usr/bin/env python3
"""Build the static, crawlable HTML page for every published blog post.

Why this exists
---------------
The blog is rendered client-side from ``blog-posts.json`` (``blog-post.html?slug=...``).
Search and AI answer engines do not execute that JavaScript, so each published post also
gets a pre-rendered page at ``blog/<slug>.html`` containing the article, its meta tags
(description, canonical, Open Graph, Twitter) and schema.org JSON-LD (BlogPosting,
BreadcrumbList and FAQPage) baked into the served HTML.

The platform serves ``/blog/<slug>.html`` from disk when the file exists, and renders it on
demand otherwise (``catalog.app.render_blog_page``), so a published post is always served as
crawlable HTML - never a 404 and never an empty JavaScript shell.

Usage
-----
    python tools/build_blog_static.py            # rebuild every published post
    python tools/build_blog_static.py <slug>     # rebuild one post

Run it (and commit the result) after publishing or editing a post. Drafts
(``"status": "draft"``) are never written to disk.
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = 'https://www.robotist.com.au'


def load_posts():
    return json.loads((ROOT / 'blog-posts.json').read_text(encoding='utf-8'))


def cover_url_for(post):
    rel = post.get('coverUrl') or ('blog/covers/%s.jpg' % post['slug'])
    if rel.startswith('http'):
        return rel
    return '/' + rel.lstrip('/')


def date_only(value):
    if not value:
        return None
    value = str(value)
    if re.match(r'^\d{4}-\d{2}-\d{2}', value):
        return value[:10]
    try:
        return datetime.strptime(value, '%B %d, %Y').strftime('%Y-%m-%d')
    except ValueError:
        return None


def build_toc(content):
    """Mirror of buildTOC() in blog-post.html: h3/h4 only, needs at least three."""
    heads = list(re.finditer(r'<h([34])([^>]*)>(.*?)</h\1>', content, re.S))
    if len(heads) < 3:
        return '', content
    nav, out, last = [], [], 0
    for i, m in enumerate(heads):
        rid = 'section-%d' % i
        out.append(content[last:m.start()])
        out.append('<h%s%s id="%s">%s</h%s>' % (m.group(1), m.group(2), rid, m.group(3), m.group(1)))
        last = m.end()
        text = re.sub(r'<[^>]+>', '', m.group(3)).strip()
        cls = ' toc-h4' if m.group(1) == '4' else ''
        nav.append('<li><a href="#%s" class="%s">%s</a></li>' % (rid, cls, text))
    out.append(content[last:])
    toc = ('<nav class="toc-sidebar"><div class="toc-title">On this page</div>'
           '<ul class="toc-list">' + ''.join(nav) + '</ul></nav>')
    return toc, ''.join(out)


def faq_html(post):
    faq = post.get('faq') or []
    if not faq:
        return ''
    items = ''.join(
        '<div class="faq-item"><h3>%s</h3><p>%s</p></div>' % (f['q'], f['a']) for f in faq)
    return '<section class="article-faq"><h2>Frequently asked questions</h2>%s</section>' % items


def abs_url(value):
    return value if value.startswith('http') else SITE + value


def json_ld(post):
    page_url = '%s/blog/%s.html' % (SITE, post['slug'])
    cover = abs_url(cover_url_for(post))
    published = date_only(post.get('publishedAt') or post.get('date'))
    modified = date_only(post.get('dateModified') or post.get('publishedAt') or post.get('date'))
    article = {
        '@context': 'https://schema.org',
        '@type': 'BlogPosting',
        'headline': post['title'],
        'description': post.get('metaDescription') or post.get('excerpt'),
        'image': [cover],
        'datePublished': published,
        'dateModified': modified,
        'author': {'@type': 'Organization', 'name': 'Robotist', 'url': SITE + '/'},
        'publisher': {'@type': 'Organization', 'name': 'Robotist',
                      'logo': {'@type': 'ImageObject', 'url': SITE + '/robotist-og.jpg'}},
        'mainEntityOfPage': {'@type': 'WebPage', '@id': page_url},
        'url': page_url,
        'articleSection': post.get('category'),
        'keywords': ', '.join(post.get('keywords') or []),
    }
    crumb = {
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        'itemListElement': [
            {'@type': 'ListItem', 'position': 1, 'name': 'Home', 'item': SITE + '/'},
            {'@type': 'ListItem', 'position': 2, 'name': 'Blog', 'item': SITE + '/blog.html'},
            {'@type': 'ListItem', 'position': 3, 'name': post['title'], 'item': page_url},
        ],
    }
    objs = [article, crumb]
    if post.get('faq'):
        objs.append({
            '@context': 'https://schema.org',
            '@type': 'FAQPage',
            'mainEntity': [
                {'@type': 'Question', 'name': f['q'],
                 'acceptedAnswer': {'@type': 'Answer', 'text': f['a']}}
                for f in post['faq']],
        })
    objs = [{k: v for k, v in o.items() if v is not None} for o in objs]
    return json.dumps(objs, ensure_ascii=False, separators=(',', ':'))


def article_html(post, toc, body):
    return '''
    <div class="article-cover"><img src="%s" alt=""></div>
    <div class="article-wrap">
      %s
      <article class="article">
        <div class="article-category">%s</div>
        <h1>%s</h1>
        <div class="article-meta"><span>%s</span><span class="article-meta-dot"></span><span>%s read</span></div>
        <div class="article-content">%s</div>
        %s
        <div class="article-cta">
          <h3>Ready to deploy?</h3>
          <p>Tell us about your use case and we'll recommend the right robot — with pricing, lead time, and deployment requirements.</p>
          <a href="/contact.html">Request a Quote</a>
        </div>
      </article>
    </div>''' % (cover_url_for(post), toc, post['category'], post['title'],
                 post['date'], post['readTime'], body, faq_html(post))


def related_html(post, published):
    others = [p for p in published if p['slug'] != post['slug']][:3]
    cards = ''.join('''
          <a href="/blog/%s.html" class="related-card">
            <div class="related-card-category">%s</div>
            <div class="related-card-title">%s</div>
            <div class="related-card-meta">%s · %s read</div>
          </a>''' % (r['slug'], r['category'], r['title'], r['date'], r['readTime'])
                    for r in others)
    return '''
    <section class="related">
      <h2>Related Articles</h2>
      <div class="related-grid">%s
      </div>
    </section>''' % cards


def build_page(template, post, published):
    seo_title = post.get('seoTitle') or post['title']
    seo_desc = post.get('metaDescription') or post.get('excerpt')
    page_url = '%s/blog/%s.html' % (SITE, post['slug'])
    og_image = abs_url(cover_url_for(post))

    def sub(text, old, new, what):
        if text.count(old) != 1:
            raise SystemExit('%s: anchor for %s not found exactly once' % (post['slug'], what))
        return text.replace(old, new, 1)

    page = template
    page = sub(page, '<title id="page-title">Article — Robotist</title>',
               '<title id="page-title">%s — Robotist Blog</title>' % seo_title, 'title')
    page = sub(page, '<meta name="description" id="page-desc" content="Robotist blog article">',
               '<meta name="description" id="page-desc" content="%s">' % seo_desc, 'description')
    page = sub(page, '<link rel="canonical" id="page-canonical" href="https://www.robotist.com.au/blog-post.html">',
               '<link rel="canonical" id="page-canonical" href="%s">' % page_url, 'canonical')
    page = sub(page, '<meta property="og:title" id="og-title" content="Article — Robotist">',
               '<meta property="og:title" id="og-title" content="%s">' % seo_title, 'og:title')
    page = sub(page, '<meta property="og:description" id="og-desc" content="Robotist blog article">',
               '<meta property="og:description" id="og-desc" content="%s">' % seo_desc, 'og:description')
    page = sub(page, '<meta property="og:url" id="og-url" content="https://www.robotist.com.au/blog-post.html">',
               '<meta property="og:url" id="og-url" content="%s">' % page_url, 'og:url')
    page = sub(page, '<meta property="og:image" id="og-image" content="">',
               '<meta property="og:image" id="og-image" content="%s">' % og_image, 'og:image')
    page = sub(page, '<meta name="twitter:title" id="tw-title" content="Article — Robotist">',
               '<meta name="twitter:title" id="tw-title" content="%s">' % seo_title, 'tw:title')
    page = sub(page, '<meta name="twitter:description" id="tw-desc" content="Robotist blog article">',
               '<meta name="twitter:description" id="tw-desc" content="%s">' % seo_desc, 'tw:description')
    page = sub(page, '<meta name="twitter:image" id="tw-image" content="">',
               '<meta name="twitter:image" id="tw-image" content="%s">' % og_image, 'tw:image')
    page = sub(page, '</head>',
               '<script type="application/ld+json">%s</script>\n</head>' % json_ld(post), 'json-ld')

    toc, body = build_toc(post['content'])
    page = sub(page, '<div id="article-container"></div>',
               '<div id="article-container">%s\n</div>' % article_html(post, toc, body), 'article')
    page = sub(page, '<div id="related-container"></div>',
               '<div id="related-container">%s\n</div>' % related_html(post, published), 'related')

    start_marker = "<script>\nconst slug = new URLSearchParams"
    start = page.find(start_marker)
    if start == -1:
        raise SystemExit('%s: boot script not found' % post['slug'])
    end = page.index('</script>', start) + len('</script>')
    page = page[:start] + page[end:]

    for old_ref, new_ref in (('src="images/', 'src="/images/'),
                            ('href="index.html', 'href="/index.html'),
                            ('href="compare.html"', 'href="/compare.html"'),
                            ('href="about.html"', 'href="/about.html"'),
                            ('href="contact.html"', 'href="/contact.html"'),
                            ('href="blog.html"', 'href="/blog.html"'),
                            ('src="robots-cut/', 'src="/robots-cut/')):
        page = page.replace(old_ref, new_ref)

    page = page.replace('<!DOCTYPE html>\n',
                        '<!DOCTYPE html>\n<!-- Generated page — built from blog-posts.json by '
                        'tools/build_blog_static.py. Rebuild after editing the post. -->\n', 1)
    return page


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    posts = load_posts()
    published = [p for p in posts if p.get('status') != 'draft']
    template = (ROOT / 'blog-post.html').read_text(encoding='utf-8')
    written = []
    for post in published:
        if only and post['slug'] != only:
            continue
        page = build_page(template, post, published)
        out = ROOT / 'blog' / (post['slug'] + '.html')
        out.write_text(page, encoding='utf-8')
        written.append(post['slug'])
    print('wrote %d page(s): %s' % (len(written), ', '.join(written)))


if __name__ == '__main__':
    main()
