"""The cookie notice, the stored choice and the policy page.

These tests pin what a visitor is promised: analytics waits for an answer, the
notice appears once per page and nowhere it should not, and the policy page can
always be reached to change the answer.
"""
import re, tempfile, unittest
from unittest.mock import patch
from .app import create_app
from .site import CONSENT_COOKIE, CONSENT_SECONDS, consent

KEY = '«redacted:sk-…»'
PUBLIC_PAGES = ['/', '/about.html', '/contact.html', '/robotmaxx-chat.html', '/compare.html']


class ConsentTest(unittest.TestCase):
    def build(self, directory, **env):
        patcher = patch.dict(__import__('os').environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        return create_app(dict(TESTING=True, SECRET_KEY='test', ADMIN_PASSWORD_HASH='unused',
                               DATA_DIR=directory, CATALOG_IMPORT_EXISTING=False))

    def test_every_public_page_offers_the_choice_once(self):
        with tempfile.TemporaryDirectory() as directory:
            client = self.build(directory, DEEPSEEK_API_KEY=KEY).test_client()
            for page in PUBLIC_PAGES:
                body = client.get(page).get_data(as_text=True)
                self.assertEqual(body.count('id="robotist-consent"'), 1, page + ' must offer the cookie choice once')
                self.assertIn('data-consent="granted"', body, page)
                self.assertIn('data-consent="denied"', body, page)
                self.assertIn('href="/cookies.html"', body, page)

    def test_analytics_waits_for_the_answer(self):
        with tempfile.TemporaryDirectory() as directory:
            client = self.build(directory, DEEPSEEK_API_KEY=KEY).test_client()
            body = client.get('/').get_data(as_text=True)
            self.assertIn("gtag('consent','default'", body, 'analytics defaults must be declared before measurement')
            self.assertRegex(body, r"analytics_storage:\(read\(\)==='granted'\?'granted':'denied'\)")
            self.assertIn("ad_storage:'denied'", body)
            self.assertIn(CONSENT_COOKIE, body, 'the stored choice must be the cookie the banner reads')
            self.assertIn("gtag('consent','update'", body, 'accepting must lift the restriction in place')
            self.assertIn("indexOf('_ga')!==0", body, 'withdrawing consent must also remove the analytics cookies')
            self.assertIn('cookieless', body.lower() + client.get('/cookies.html').get_data(as_text=True).lower())

    def test_the_policy_stays_reachable_after_the_choice(self):
        with tempfile.TemporaryDirectory() as directory:
            client = self.build(directory, DEEPSEEK_API_KEY=KEY).test_client()
            for page in PUBLIC_PAGES:
                body = client.get(page).get_data(as_text=True)
                expected = 1 if 'class="footer-bottom"' in body else 0
                self.assertEqual(body.count('class="robotist-cookie-settings"'), expected,
                                 page + ' must link the cookie policy exactly where it has a footer to hold it')
                self.assertEqual(body.count('id="robotist-consent"'), 1, page + ' must still offer the choice')
            policy = client.get('/cookies.html')
            self.assertEqual(policy.status_code, 200)
            text = policy.get_data(as_text=True)
            for marker in ['robotist_grn', CONSENT_COOKIE, '_ga', 'Google Analytics', 'YouTube', 'data-consent="clear"']:
                self.assertIn(marker, text, 'the policy must cover ' + marker)
            self.assertEqual(text.count('class="robotist-cookie-settings"'), 1)

    def test_the_admin_screen_is_left_alone(self):
        with tempfile.TemporaryDirectory() as directory:
            client = self.build(directory, DEEPSEEK_API_KEY=KEY).test_client()
            body = client.get('/manage').get_data(as_text=True)
            self.assertNotIn('id="robotist-consent"', body, 'the admin screen carries its own policy and must stay untouched')

    def test_injection_is_idempotent(self):
        once = consent('<html><body><div class="footer-bottom"><span class="footer-copy">© 2026</span></div></body></html>')
        twice = consent(once)
        self.assertEqual(once, twice, 'a page must not collect a second banner or a second footer link')
        self.assertEqual(twice.count('class="robotist-cookie-settings"'), 1)
        self.assertEqual(twice.count('id="robotist-consent"'), 1)

    def test_markup_without_a_body_is_returned_unchanged(self):
        for markup in ['{"robots": []}', '<div>fragment</div>', '']:
            self.assertEqual(consent(markup), markup)

    def test_the_stored_choice_lasts_about_six_months(self):
        self.assertEqual(CONSENT_SECONDS, 6 * 30 * 24 * 60 * 60)
