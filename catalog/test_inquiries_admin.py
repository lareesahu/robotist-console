"""Inquiry spam: the console can delete it, the form can ask for a human.

Almost everything that arrives through the public inquiry forms is spam, so the
console has to be able to clear it — one row at a time or in bulk — without
leaving the record in a state nobody can explain later. Deleting is audited;
the customer's own answers stop existing.

The captcha half is configuration-, not code-driven: with no keys the site
behaves exactly as before, and a captcha that cannot be reached never costs a
real inquiry.
"""
import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

from .app import create_app
from grn import captcha

CSRF = 'test-csrf'
RECAPTCHA = {'GRN_RECAPTCHA_SITE_KEY': 'public-key', 'GRN_RECAPTCHA_SECRET': 'secret-key'}


def google_says(payload):
    """Stand in for Google's siteverify response object."""
    class Response:
        def __enter__(self): return self
        def __exit__(self, *info): return False
        def read(self): return json.dumps(payload).encode()
    return lambda *args, **kwargs: Response()


class ConsoleTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app(dict(TESTING=True, DATA_DIR=self.tmp.name, SECRET_KEY='test',
                                   ADMIN_PASSWORD_HASH='unused', SESSION_COOKIE_SECURE=False,
                                   CATALOG_IMPORT_EXISTING=False))
        self.client = self.app.test_client()
        self.client.get('/cart')
        self.add('RQ-SPAM1', 'Cheap backlinks', 'spam@example.invalid')
        self.add('RQ-REAL1', 'Grace Hopper', 'grace@example.invalid')

    def tearDown(self):
        self.tmp.cleanup()

    def add(self, ident, name, email):
        with closing(sqlite3.connect(Path(self.tmp.name) / 'grn.sqlite3')) as con:
            con.execute('INSERT INTO inquiries(id,submission_token,name,email,message,items,source)'
                        ' VALUES (?,?,?,?,?,?,?)', (ident, ident, name, email, 'hello', '[]', 'contact'))
            con.commit()

    def rows(self):
        with closing(sqlite3.connect(Path(self.tmp.name) / 'grn.sqlite3')) as con:
            return {row[0] for row in con.execute('SELECT id FROM inquiries')}

    def audit(self):
        with closing(sqlite3.connect(Path(self.tmp.name) / 'grn.sqlite3')) as con:
            return ' | '.join(row[0] for row in con.execute('SELECT action FROM audit'))

    def sign_in(self, admin=True):
        with self.client.session_transaction() as session:
            session['csrf'] = CSRF
            session['admin'] = admin
            session['inquiry_token'] = 'token-1'


class DeleteInquiryTest(ConsoleTestCase):
    def test_a_signed_in_admin_deletes_one_inquiry(self):
        self.sign_in()
        response = self.client.post('/manage/inquiries/RQ-SPAM1/delete',
                                    data={'csrf': CSRF, 'status': 'all'})
        self.assertEqual(response.status_code, 303)
        self.assertEqual(self.rows(), {'RQ-REAL1'})
        self.assertIn('Inquiry deleted: Cheap backlinks <spam@example.invalid>', self.audit())

    def test_several_inquiries_go_at_once(self):
        self.add('RQ-SPAM2', 'More backlinks', 'spam@example.invalid')
        self.sign_in()
        response = self.client.post('/manage/inquiries/delete',
                                    data={'csrf': CSRF, 'status': 'all', 'id': ['RQ-SPAM1', 'RQ-SPAM2']})
        self.assertEqual(response.status_code, 303)
        self.assertEqual(self.rows(), {'RQ-REAL1'})

    def test_deleting_nothing_removes_nothing(self):
        self.sign_in()
        response = self.client.post('/manage/inquiries/delete', data={'csrf': CSRF, 'status': 'all'})
        self.assertEqual(response.status_code, 303)
        self.assertEqual(self.rows(), {'RQ-SPAM1', 'RQ-REAL1'})

    def test_a_stale_session_token_is_refused(self):
        self.sign_in()
        response = self.client.post('/manage/inquiries/RQ-REAL1/delete', data={'csrf': 'stale'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.rows(), {'RQ-SPAM1', 'RQ-REAL1'})

    def test_someone_who_is_not_an_admin_cannot_delete(self):
        self.sign_in(admin=False)
        response = self.client.post('/manage/inquiries/RQ-REAL1/delete', data={'csrf': CSRF})
        self.assertIn(response.status_code, (302, 401, 403))
        self.assertEqual(self.rows(), {'RQ-SPAM1', 'RQ-REAL1'})

    def test_an_unknown_reference_reports_that_it_was_already_gone(self):
        self.sign_in()
        response = self.client.post('/manage/inquiries/RQ-NOPE/delete',
                                    data={'csrf': CSRF, 'status': 'all'}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('was already gone', response.get_data(as_text=True))

    def test_the_console_offers_a_delete_control_on_every_row(self):
        self.sign_in()
        page = self.client.get('/manage/inquiries?status=all').get_data(as_text=True)
        self.assertEqual(page.count('name="id"'), 2)
        self.assertIn('Delete selected', page)
        self.assertIn('/manage/inquiries/RQ-SPAM1/delete', page)

    def test_the_detail_page_can_delete_the_inquiry_it_shows(self):
        self.sign_in()
        page = self.client.get('/manage/inquiries/RQ-SPAM1').get_data(as_text=True)
        self.assertIn('Delete this inquiry', page)
        self.assertIn('/manage/inquiries/RQ-SPAM1/delete', page)


class CaptchaTest(unittest.TestCase):
    def test_with_no_keys_every_submission_passes_as_before(self):
        with mock.patch.dict(os.environ, {'GRN_RECAPTCHA_SITE_KEY': '', 'GRN_RECAPTCHA_SECRET': ''}):
            self.assertEqual(captcha.verify(''), (True, 'not configured'))

    def test_a_configured_check_refuses_a_submission_with_no_token(self):
        with mock.patch.dict(os.environ, RECAPTCHA):
            allowed, reason = captcha.verify('')
        self.assertFalse(allowed)
        self.assertIn('no captcha token', reason)

    def test_a_token_google_confirms_is_accepted(self):
        with mock.patch.dict(os.environ, RECAPTCHA):
            with mock.patch.object(captcha.urllib.request, 'urlopen', google_says({'success': True, 'score': 0.9})):
                allowed, reason = captcha.verify('token', '203.0.113.4')
        self.assertTrue(allowed, reason)

    def test_a_low_score_is_refused(self):
        with mock.patch.dict(os.environ, RECAPTCHA):
            with mock.patch.object(captcha.urllib.request, 'urlopen', google_says({'success': True, 'score': 0.1})):
                allowed, reason = captcha.verify('token')
        self.assertFalse(allowed)
        self.assertIn('score', reason)

    def test_a_rejected_token_is_refused(self):
        with mock.patch.dict(os.environ, RECAPTCHA):
            with mock.patch.object(captcha.urllib.request, 'urlopen',
                                   google_says({'success': False, 'error-codes': ['timeout-or-duplicate']})):
                allowed, reason = captcha.verify('token')
        self.assertFalse(allowed)
        self.assertIn('timeout-or-duplicate', reason)

    def test_google_being_unreachable_does_not_discard_a_real_inquiry(self):
        with mock.patch.dict(os.environ, RECAPTCHA):
            with mock.patch.object(captcha.urllib.request, 'urlopen', side_effect=OSError('no route to host')):
                allowed, reason = captcha.verify('token')
        self.assertTrue(allowed)
        self.assertIn('unreachable', reason)


class CaptchaIsWiredTest(unittest.TestCase):
    """The keys, not the code, are what switch the check on in production."""

    def client(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        app = create_app(dict(TESTING=True, DATA_DIR=self.tmp.name, SECRET_KEY='test',
                              ADMIN_PASSWORD_HASH='unused', SESSION_COOKIE_SECURE=False,
                              CATALOG_IMPORT_EXISTING=False))
        client = app.test_client()
        client.get('/cart')
        return client

    def inquiries(self):
        with closing(sqlite3.connect(Path(self.tmp.name) / 'grn.sqlite3')) as con:
            return con.execute('SELECT id,name FROM inquiries').fetchall()

    def test_the_public_script_carries_the_site_key_when_one_is_configured(self):
        with mock.patch.dict(os.environ, RECAPTCHA):
            script = self.client().get('/assets/form-workflow.js').get_data(as_text=True)
        self.assertIn("var RECAPTCHA_SITE_KEY = 'public-key';", script)
        self.assertIn("formData.append('g-recaptcha-response', token);", script)

    def test_the_public_script_carries_no_key_when_the_check_is_off(self):
        with mock.patch.dict(os.environ, {'GRN_RECAPTCHA_SITE_KEY': '', 'GRN_RECAPTCHA_SECRET': ''}):
            script = self.client().get('/assets/form-workflow.js').get_data(as_text=True)
        self.assertIn("var RECAPTCHA_SITE_KEY = '';", script)

    def test_a_submission_without_a_token_is_refused_once_the_check_is_on(self):
        with mock.patch.dict(os.environ, RECAPTCHA):
            client = self.client()
            with client.session_transaction() as session:
                token, csrf = session['inquiry_token'], session['csrf']
            response = client.post('/inquiries', data={'csrf': csrf, 'submission_token': token,
                                                       'name': 'Grace Hopper', 'email': 'grace@example.invalid',
                                                       'message': 'Please quote one cleaning robot.'})
        self.assertEqual(response.status_code, 400)
        self.assertIn('captcha', response.get_data(as_text=True).lower())

    def test_a_submission_google_confirms_still_reaches_the_team(self):
        with mock.patch.dict(os.environ, RECAPTCHA):
            client = self.client()
            with client.session_transaction() as session:
                token, csrf = session['inquiry_token'], session['csrf']
            with mock.patch.object(captcha.urllib.request, 'urlopen', google_says({'success': True, 'score': 0.8})):
                response = client.post('/inquiries', data={'csrf': csrf, 'submission_token': token,
                                                           'g-recaptcha-response': 'good-token',
                                                           'name': 'Grace Hopper', 'email': 'grace@example.invalid',
                                                           'message': 'Please quote one cleaning robot.'})
        self.assertEqual(response.status_code, 303)
        self.assertEqual(len(self.inquiries()), 1)
