"""The catalogue sync: what it regenerates, and what it must never touch.

Everything derived from the live catalogue is written from one place, so a robot
added in the CMS reaches the assistant, the structured data, the sitemap and the
policy page without anybody remembering to do it. These tests pin both halves:
the regenerated parts change with the catalogue, and everything the sync does not
own - hand-written copy, the rest of each page - comes out untouched.
"""
import contextlib, importlib.util, io, os, pathlib, sys, unittest, urllib.error

# Two ways the sync can talk to the site: it fetches a product page to see
# whether the robot has one, and it reads the catalogue. Both are injected in
# the tests below, so the suite states the rule instead of the weather on the
# live host.

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location('sync_site_content', ROOT / 'catalog' / 'sync_site_content.py')
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)
builder_spec = importlib.util.spec_from_file_location('build_cookies_page', ROOT / 'catalog' / 'build_cookies_page.py')
builder = importlib.util.module_from_spec(builder_spec)
builder_spec.loader.exec_module(builder)

ROWS = [
    {'slug': 'pndbotics-adam', 'name': 'ADAM SP', 'category': 'humanoid', 'price': 'USD 89,000',
     'best': 'AI labs', 'specs': [('Model', 'ADAM SP'), ('Brand', 'PNDbotics'), ('WDP (USD)', 'USD 89,000'),
                                  ('Degrees of Freedom', '41-DOF')]},
    {'slug': 'new-robot', 'name': 'Brände New', 'category': 'companion', 'price': 'Coming soon',
     'best': 'lobbies', 'specs': [('Platform', 'Bionic humanoid'), ('Best for', 'lobbies')]},
]


class SyncTest(unittest.TestCase):
    def test_the_knowledge_block_names_every_robot_with_its_specs(self):
        block = sync.maxx_block(ROWS)
        self.assertIn('1. ADAM SP — PNDbotics [HUMANOID]', block)
        self.assertIn('Degrees of Freedom: 41-DOF', block)
        self.assertIn('2. Brände New [COMPANION]', block)
        self.assertIn('Best for: lobbies.', block)
        self.assertNotIn('WDP (USD)', block, 'the price already leads the live catalogue line')

    def test_the_markers_own_the_knowledge_block_and_nothing_else(self):
        page = 'PROMPT = `\n===\n\n/*MAXX-KNOWLEDGE:START*/\n1. old robot\n/*MAXX-KNOWLEDGE:END*/\n\n===\nEDEN\n`;'
        once = sync.sync_maxx(page, '1. ADAM SP')
        self.assertIn('1. ADAM SP', once)
        self.assertNotIn('1. old robot', once)
        self.assertIn('EDEN', once, 'the section after the block must survive')
        self.assertIn('PROMPT = `', once, 'the section before the block must survive')
        twice = sync.sync_maxx(once, '1. ADAM SP')
        self.assertEqual(once, twice, 'a second run must be a no-op')

    def test_a_page_without_markers_is_refused_rather_than_guessed_at(self):
        with self.assertRaises(SystemExit):
            sync.sync_maxx('PROMPT = `\n1. old robot\nEDEN\n`;', '1. ADAM SP')

    def test_the_structured_data_follows_the_catalogue(self):
        markup = '<meta name="x" content="24 commercial robots across 5 categories"> and Robotist offers 24 commercial robots across 5 categories:'
        updated = sync.sync_counts(markup, ROWS)
        self.assertIn('2 commercial robots across 2 categories', updated)
        self.assertIn('Robotist offers 2 commercial robots', updated)

    def test_the_sitemap_gains_missing_robots_and_the_policy_page(self):
        markup = '<urlset><url><loc>https://www.robotist.com.au/about.html</loc></url></urlset>'
        updated = sync.sync_sitemap(markup, ROWS)
        self.assertIn('/products/pndbotics-adam.html', updated)
        self.assertIn('/products/new-robot.html', updated)
        self.assertIn('/cookies.html', updated)
        self.assertIn('/about.html', updated, 'existing entries stay')
        again = sync.sync_sitemap(updated, ROWS)
        self.assertEqual(updated, again, 'nothing is added twice')

    def test_the_policy_page_is_rebuilt_from_its_own_copy(self):
        """Regenerating must reproduce the committed page, copy included.

        The sync rewrites cookies.html, so the authored policy text lives in
        catalog/cookies_content.html. If this test fails, a regeneration would
        quietly throw somebody's sentences away.
        """
        committed = (ROOT / 'cookies.html').read_text(encoding='utf-8').replace('\r\n', '\n')
        regenerated = builder.build(write=False).replace('\r\n', '\n')
        self.assertEqual(regenerated.split('\n'), committed.split('\n'),
                         'regenerating the policy page must not change a single line')
        self.assertIn('Cookie policy', (ROOT / builder.CONTENT_FILE).read_text(encoding='utf-8'))

    def test_a_robot_without_a_page_is_reported_not_invented(self):
        """A page the live host 404s is missing; a host that cannot answer is not
        a fault. The server is injected here, so this states the rule rather than
        the weather on the live site."""
        original = sync.fetch

        def gone(url):
            raise urllib.error.HTTPError(url, 404, 'Not Found', None, None)

        def unreachable(url):
            raise urllib.error.URLError('no route to host')

        try:
            sync.fetch = gone
            self.assertEqual(sync.missing_pages([{'slug': 'definitely-not-a-robot'}]),
                             ['definitely-not-a-robot'])
            sync.fetch = unreachable
            self.assertEqual(sync.missing_pages([{'slug': 'definitely-not-a-robot'}]), [],
                             'an unreachable host must never be reported as a missing page')
        finally:
            sync.fetch = original

    def test_an_unreadable_source_is_not_a_verdict(self):
        """Exit 3, not 0 and not 1: the catalogue could not be read, so nobody may
        decide that the site is stale and rewrite it from a guess."""
        original = sync.catalogue

        def cold():
            raise urllib.error.URLError('the catalogue host is cold')

        sync.catalogue = cold
        arguments = sys.argv
        sys.argv = ['sync_site_content', '--check', '--quiet']
        os.environ['ROBOTIST_SYNC_REEXEC'] = '1'
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(sync.main(), 3)
        finally:
            sync.catalogue = original
            sys.argv = arguments
