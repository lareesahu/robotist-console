"""Keep everything on robotist.com.au that is derived from the catalogue in step.

The catalogue lives in the CMS and in the rendered pages; several things are
copied out of it into files: the Maxx knowledge block, the counts in the
homepage structured data, the sitemap, and the cookie policy page's shell. Each
of those drifted by hand at least once, so this script regenerates them from the
live catalogue and reports what changed.

    python catalog/sync_site_content.py --check   # exit 1 if anything is stale
    python catalog/sync_site_content.py --write   # regenerate in place
    python catalog/sync_site_content.py           # write, then report

Offline, or when the live catalogue cannot be read, the check passes with a
warning: a push must never be blocked by a network problem.
"""
import argparse, json, os, re, subprocess, sys, urllib.error, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = 'https://www.robotist.com.au'


def line_ending(path):
    """The repository's own line ending for this file.

    The committed blobs carry CRLF, so writing LF would turn a three-line change
    into a whole-file diff. The working copy is asked first, the committed blob
    second, which also repairs a copy that was already mangled.
    """
    if path.is_file():
        head = path.read_bytes()[:8000]
        if b'\r\n' in head:
            return '\r\n'
        if b'\n' in head:
            pass
        else:
            return ''
    try:
        blob = subprocess.run(['git', 'show', 'HEAD:' + path.relative_to(ROOT).as_posix()],
                              cwd=str(ROOT), capture_output=True, timeout=60).stdout
    except Exception:
        return '\r\n'
    return '\r\n' if b'\r\n' in blob[:8000] else ''
MAXX = ROOT / 'robotmaxx-chat.html'
START = '/*MAXX-KNOWLEDGE:START*/'
END = '/*MAXX-KNOWLEDGE:END*/'

# Labels already shown next to the robot, or commercial noise, so the block stays
# short enough to read on every answer.
REDUNDANT = {'model', 'brand', 'wdp (usd)', 'price', 'category', 'origin',
             'availability', 'warranty', 'deployment', 'support', 'best for', 'lead time'}
PRIORITY = ['variants', 'platform', 'configuration', 'total dof', 'degrees of freedom',
            'height', 'dimensions', 'hands', 'gripper', 'arms', 'arm dof', 'payload',
            'dual-arm payload', 'speed', 'max speed', 'runtime', 'battery', 'coverage',
            'cleaning', 'precision', 'obstacle clearance', 'terrain', 'range', 'ai compute',
            'onboard compute', 'ai engine', 'software', 'curriculum', 'navigation', 'vision',
            'teleoperation', 'voice interaction', 'safety', 'connectivity', 'actuators',
            'motion capture', 'finish', 'drive system', 'charge time', 'lifting height',
            'single-arm reach', 'min passage width']
SPEC_LIMIT = 8


def fetch(url, timeout=60):
    request = urllib.request.Request(url, headers={'User-Agent': 'robotist-site-sync'})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode('utf-8', 'ignore')


def catalogue():
    """The robots the site is actually showing right now, with their page specs."""
    rows = json.loads(fetch(SITE + '/api/catalogue'))['robots']
    for row in rows:
        row['specs'] = page_specs(row['slug'])
    return rows


def page_specs(slug):
    """The specification rows the product page publishes for one robot.

    Read from the repository's own page when it has one, so a routine check is a
    single request; CMS-only robots fall back to their published page.
    """
    path = ROOT / 'products' / (slug + '.html')
    try:
        page = path.read_text(encoding='utf-8') if path.is_file() else fetch(SITE + '/products/' + slug + '.html')
    except Exception:
        return []
    specs = []
    for match in re.finditer(r'class="(?:companion-)?spec-label">(.*?)</span><span class="(?:companion-)?spec-value">(.*?)</span>', page, re.S):
        label = re.sub(r'<[^>]+>', '', match.group(1)).strip()
        value = re.sub(r'<[^>]+>', '', match.group(2)).strip()
        if label and value:
            specs.append((label, value))
    return specs


def maxx_block(rows):
    """The technical detail Maxx reads when the live block is not enough."""
    lines = []
    for index, row in enumerate(rows, 1):
        specs = [(label, value) for label, value in row['specs'] if label.lower() not in REDUNDANT]
        specs.sort(key=lambda item: PRIORITY.index(item[0].lower()) if item[0].lower() in PRIORITY else len(PRIORITY))
        body = '. '.join(label + ': ' + value for label, value in specs[:SPEC_LIMIT])
        brand = next((value for label, value in row['specs'] if label.lower() == 'brand'), '')
        head = '%d. %s%s [%s]' % (index, row['name'], ' — ' + brand if brand else '', (row['category'] or 'robot').upper())
        tail = ('Best for: %s.' % row['best']) if row['best'] else ''
        lines.append((head + '\n   ' + (body + '. ' if body else '') + tail).rstrip())
    return '\n\n'.join(lines)


def sync_maxx(markup, block):
    """Replace the knowledge block between its markers.

    The markers are the only part of that page the sync owns. A page without them
    is refused rather than guessed at: a wrong insertion point would silently
    swallow the rest of Maxx's brief.
    """
    if START not in markup or END not in markup:
        raise SystemExit('robotmaxx-chat.html: the MAXX-KNOWLEDGE markers are missing — '
                         'put them around the knowledge block, then run the sync again')
    head, rest = markup.split(START, 1)
    _, tail = rest.split(END, 1)
    return head + START + '\n' + block + '\n' + END + tail


def live_counts():
    """The counts the served homepage states, so the file agrees with the page.

    The homepage compiles its own structured data from the rendered cards, so its
    numbers win over anything this script could count from the API list.
    """
    match = re.search(r'(\d+) commercial robots across (\d+) categories', fetch(SITE + '/'))
    return (int(match.group(1)), int(match.group(2))) if match else None


def sync_counts(markup, rows, counts=None):
    """The homepage structured data quotes how many robots there are."""
    count, families = counts or (len(rows), len({(row['category'] or 'robot').lower() for row in rows}))
    updated = re.sub(r'\d+ commercial robots across \d+ categories',
                     '%d commercial robots across %d categories' % (count, families), markup)
    return re.sub(r'Robotist offers \d+ commercial robots',
                  'Robotist offers %d commercial robots' % count, updated)


def sync_sitemap(markup, rows):
    """Every robot the site sells has a page, and a policy page exists now."""
    present = set(re.findall(r'<loc>(.*?)</loc>', markup))
    additions = []
    for row in rows:
        url = SITE + '/products/' + row['slug'] + '.html'
        if url not in present:
            additions.append(url)
    policy = SITE + '/cookies.html'
    if policy not in present:
        additions.append(policy)
    if not additions:
        return markup
    entries = ''.join('<url><loc>%s</loc></url>' % url for url in additions)
    return markup.replace('</urlset>', entries + '</urlset>', 1)


def cookies_page(write=False):
    """The policy page reuses the site's nav and footer, so it is regenerated too."""
    import importlib.util
    path = ROOT / 'catalog' / 'build_cookies_page.py'
    spec = importlib.util.spec_from_file_location('build_cookies_page', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build(write=write)


def plan(rows):
    """Every file this run would change, and its new text. Writes nothing."""
    changes = {}
    maxx = MAXX.read_text(encoding='utf-8')
    updated = sync_maxx(maxx, maxx_block(rows))
    if updated != maxx:
        changes[MAXX] = updated
    home = ROOT / 'index.html'
    markup = home.read_text(encoding='utf-8')
    try:
        counts = live_counts()
    except Exception:
        counts = None
    updated = sync_counts(markup, rows, counts)
    if updated != markup:
        changes[home] = updated
    sitemap = ROOT / 'sitemap.xml'
    markup = sitemap.read_text(encoding='utf-8')
    updated = sync_sitemap(markup, rows)
    if updated != markup:
        changes[sitemap] = updated
    cookies = ROOT / 'cookies.html'
    rebuilt = cookies_page()
    if rebuilt != cookies.read_text(encoding='utf-8'):
        changes[cookies] = rebuilt
    return changes


def missing_pages(rows):
    """Robots with neither a page in the repository nor one the site serves.

    A robot published through the CMS gets its page rendered on request, so only
    the server answering 404 counts as missing; a slow or unreachable request is
    ignored rather than reported as a fault.
    """
    absent = []
    for row in rows:
        if (ROOT / 'products' / (row['slug'] + '.html')).is_file():
            continue
        try:
            fetch(SITE + '/products/' + row['slug'] + '.html')
        except urllib.error.HTTPError as error:
            if error.code == 404:
                absent.append(row['slug'])
        except Exception:
            continue
    return absent


# Two interpreters live on this machine and only one carries BeautifulSoup. The
# sync is called from a git hook, from cron and by hand, so it re-runs itself
# under an interpreter that has the dependency instead of failing on whichever
# python the caller happened to use.
INTERPRETERS = [
    'C:/Users/hunin/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe',
    'python3', 'python',
]


def require_beautifulsoup():
    try:
        import bs4  # noqa: F401
        return
    except ImportError:
        pass
    if os.environ.get('ROBOTIST_SYNC_REEXEC'):
        print('site sync needs BeautifulSoup: no interpreter on this machine provides it.')
        raise SystemExit(2)
    tried = []
    for candidate in INTERPRETERS:
        if os.path.abspath(candidate) == os.path.abspath(sys.executable):
            continue
        try:
            probe = subprocess.run([candidate, '-c', 'import bs4'], capture_output=True, timeout=120)
        except Exception as error:
            tried.append('%s (%s)' % (candidate, error.__class__.__name__))
            continue
        if probe.returncode == 0:
            # Hand the work to that interpreter and pass its exit code straight
            # back. os.execve is not dependable on Windows, a child is.
            environment = dict(os.environ, ROBOTIST_SYNC_REEXEC='1')
            handed = subprocess.run([candidate, os.path.abspath(__file__)] + sys.argv[1:], env=environment)
            raise SystemExit(handed.returncode)
        tried.append(candidate)
    print('site sync needs BeautifulSoup. Tried: %s' % (', '.join(tried) or 'no other interpreter found'))
    raise SystemExit(2)


def main():
    require_beautifulsoup()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='report drift without writing (exit 1 when stale)')
    parser.add_argument('--write', action='store_true', help='regenerate the derived files')
    parser.add_argument('--quiet', action='store_true', help='print nothing when everything is current')
    args = parser.parse_args()
    try:
        rows = catalogue()
    except Exception as error:
        # Not a verdict about the content: the source could not be read (a cold
        # host, a dropped connection, DNS). Exit 3 so the caller fails open
        # instead of committing a "repair" built on a guess.
        print('site sync skipped: the live catalogue could not be read (%s)' % error, file=sys.stderr)
        return 3
    try:
        changes = plan(rows)
    except ModuleNotFoundError as error:
        # Two interpreters live on this machine and only one carries bs4; say so
        # instead of showing a traceback that reads like a real sync failure.
        print('site sync needs %s: run it with an interpreter that has BeautifulSoup '
              '(for example the hermes-agent venv python).' % error.name)
        return 2
    absent = missing_pages(rows)
    if args.check:
        if not changes and not absent:
            if not args.quiet:
                print('site sync: %d robots, nothing stale' % len(rows))
            return 0
        for path in changes:
            print('stale: %s' % path.relative_to(ROOT))
        for slug in absent:
            print('missing product page: %s' % slug)
        print('run: python catalog/sync_site_content.py --write')
        return 1
    for path, text in changes.items():
        path.write_text(text, encoding='utf-8', newline=line_ending(path))
        print('updated: %s' % path.relative_to(ROOT))
    for slug in absent:
        print('missing product page: %s' % slug)
    if not changes and not args.quiet:
        print('site sync: %d robots, nothing stale' % len(rows))
    return 0


if __name__ == '__main__':
    sys.exit(main())
