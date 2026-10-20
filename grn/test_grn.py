"""Behavior/security regression suite, isolated temporary SQLite databases."""
import io
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path
from contextlib import closing
from PIL import Image
from werkzeug.security import generate_password_hash
from grn.app import create_app


class GRNTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password_hash = generate_password_hash('test-password')

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app(dict(TESTING=True, SECRET_KEY='test-only', ADMIN_PASSWORD_HASH=self.password_hash,
                                  DATA_DIR=self.tmp.name, SESSION_COOKIE_SECURE=False))
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def post(self, path, data, client=None):
        client = client or self.client
        client.get(path)
        with client.session_transaction() as session:
            token = session['csrf']
        return client.post(path, data={**data, 'csrf': token})

    def query(self, query):
        with closing(sqlite3.connect(Path(self.tmp.name) / 'grn.sqlite3')) as con:
            con.row_factory = sqlite3.Row
            return con.execute(query).fetchall()

    def submit(self, **overrides):
        return self.post('/grn/apply', {**dict(name='Test Robotist', email='test@example.invalid', location='Test City', role='Robotics engineering', organization='Test organization', experience='PRIVATE EXPERIENCE', motivation='PRIVATE MOTIVATION', consent='yes', public_consent='yes'), **overrides})

    def login(self):
        return self.post('/grn/admin/login', {'password': 'test-password'})

    def approve(self):
        ident = self.query('SELECT id FROM applications')[0]['id']
        response = self.post('/grn/admin/applications/' + ident, {'version': '1', 'status': 'approved', 'notes': 'PRIVATE REVIEW'})
        self.assertEqual(response.status_code, 303)
        return ident, self.query('SELECT id FROM profiles')[0]['id']

    def profile_data(self, **overrides):
        return {'name': 'Public Test', 'title': 'Engineer', 'location': 'Test City', 'bio': 'Public biography', 'website': 'https://example.com', 'sort_order': '0', 'version': '1', 'consent': 'yes', 'consent_date':'2026-09-07','consent_reference':'Synthetic approval for this profile and website use', 'published': 'yes', **overrides}

    def test_full_cycle_and_privacy(self):
        self.assertEqual(self.submit().status_code, 303)
        visitor = self.app.test_client()
        self.assertEqual(visitor.get('/grn/admin').status_code, 302)
        self.assertEqual(self.login().status_code, 303)
        aid, pid = self.approve()
        self.assertNotIn(b'Test Robotist', visitor.get('/grn/').data)
        image = io.BytesIO()
        Image.new('RGB', (50, 50), 'blue').save(image, format='PNG')
        image.seek(0)
        self.assertEqual(self.post('/grn/admin/team/' + pid, self.profile_data(photo=(image, 'portrait.png'))).status_code, 303)
        public = visitor.get('/grn/').data
        for forbidden in (b'test@example.invalid', b'PRIVATE EXPERIENCE', b'PRIVATE MOTIVATION', b'PRIVATE REVIEW'):
            self.assertNotIn(forbidden, public)
        self.assertIn(b'Public Test', public)
        photo = self.query('SELECT photo FROM profiles')[0]['photo']
        response = visitor.get('/grn/photos/' + photo)
        self.assertEqual(response.status_code, 200)
        response.close()
        self.post('/grn/admin/applications/' + aid, {'version': '2', 'status': 'declined', 'notes': 'Changed'})
        self.assertNotIn(b'Public Test', visitor.get('/grn/').data)
        self.assertEqual(visitor.get('/grn/photos/' + photo).status_code, 404)

    def test_validation_csrf_and_duplicates(self):
        self.assertEqual(self.client.post('/grn/apply', data={'name': 'Bad'}).status_code, 400)
        self.assertEqual(self.post('/grn/apply', {'name': 'Incomplete'}).status_code, 400)
        self.assertEqual(self.submit().status_code, 303)
        self.assertEqual(self.submit().status_code, 303)
        self.assertEqual(len(self.query('SELECT * FROM applications')), 1)
        self.client.get('/grn/apply')
        with self.client.session_transaction() as s:
            token = s['csrf']
        self.assertEqual(self.client.post('/grn/apply', data={'csrf': token}, headers={'Origin': 'https://evil.invalid'}).status_code, 403)

    def test_stale_review_and_profile_rejected(self):
        self.submit()
        self.login()
        aid, pid = self.approve()
        self.assertEqual(self.post('/grn/admin/applications/' + aid, {'version':'1', 'status':'declined'}).status_code, 409)
        self.assertEqual(self.post('/grn/admin/team/' + pid, self.profile_data()).status_code, 303)
        self.assertEqual(self.post('/grn/admin/team/' + pid, self.profile_data()).status_code, 409)

    def test_unsafe_url_and_missing_consent(self):
        self.submit()
        self.login()
        _, pid = self.approve()
        self.assertEqual(self.post('/grn/admin/team/' + pid, self.profile_data(website='javascript:alert(1)')).status_code, 400)
        self.assertEqual(self.post('/grn/admin/team/' + pid, self.profile_data(consent='')).status_code, 400)
        self.assertEqual(self.query('SELECT published FROM profiles')[0]['published'], 0)

    def test_upload_rejects_disguised_code(self):
        self.submit()
        self.login()
        _, pid = self.approve()
        self.assertEqual(self.post('/grn/admin/team/' + pid, self.profile_data(photo=(io.BytesIO(b'<script>alert(1)</script>'), 'photo.jpg'))).status_code, 400)

    def test_session_logout_and_login_limit(self):
        self.login()
        self.post('/grn/admin/logout', {})
        self.assertEqual(self.client.get('/grn/admin').status_code, 302)
        for _ in range(4):
            self.assertEqual(self.post('/grn/admin/login', {'password':'wrong'}).status_code, 401)
        self.assertEqual(self.post('/grn/admin/login', {'password':'wrong'}).status_code, 429)

    def test_data_survives_new_app_instance(self):
        self.submit()
        app2 = create_app(dict(TESTING=True, SECRET_KEY='test-only', ADMIN_PASSWORD_HASH=self.password_hash, DATA_DIR=self.tmp.name, SESSION_COOKIE_SECURE=False))
        client = app2.test_client()
        self.post('/grn/admin/login', {'password':'test-password'}, client)
        self.assertIn(b'Test Robotist', client.get('/grn/admin').data)

    def test_xss_escaped_and_security_headers(self):
        self.submit()
        self.login()
        _, pid = self.approve()
        self.post('/grn/admin/team/' + pid, self.profile_data(name='<script>alert(1)</script>'))
        page = self.client.get('/grn/')
        self.assertNotIn(b'<script>', page.data)
        self.assertIn(b'&lt;script&gt;', page.data)
        self.assertIn('script-src https://assets.calendly.com', page.headers['Content-Security-Policy'])
        self.assertIn("script-src 'none'", self.client.get('/grn/admin').headers['Content-Security-Policy'])
        self.assertEqual(page.headers['Cache-Control'], 'no-store')

    def test_unpublish_and_manual_member(self):
        self.login()
        self.post('/grn/admin/team', {'name': 'Existing member'})
        pid = self.query('SELECT id FROM profiles')[0]['id']
        self.post('/grn/admin/team/' + pid, self.profile_data())
        self.assertIn(b'Public Test', self.client.get('/grn/').data)
        self.post('/grn/admin/team/' + pid, self.profile_data(version='2', published=''))
        self.assertNotIn(b'Public Test', self.client.get('/grn/').data)

    def test_refuses_data_in_static_tree(self):
        with self.assertRaises(RuntimeError):
            create_app(dict(SECRET_KEY='test', ADMIN_PASSWORD_HASH=self.password_hash, DATA_DIR=str(Path(__file__).parent / 'data')))

    def test_later_explicit_approval_is_distinct_from_preparation_permission(self):
        self.submit(public_consent='')
        self.login()
        _, pid = self.approve()
        self.assertEqual(self.query('SELECT consent FROM profiles')[0]['consent'], 0)
        self.assertEqual(self.post('/grn/admin/team/' + pid, self.profile_data(consent_reference='')).status_code, 400)
        self.assertNotIn(b'Public Test', self.client.get('/grn/').data)
        self.assertEqual(self.post('/grn/admin/team/' + pid, self.profile_data()).status_code, 303)

    def test_channel_permissions_and_agreement_evidence(self):
        self.login()
        self.post('/grn/admin/team', {'name':'Permission test'})
        pid=self.query('SELECT id FROM profiles')[0]['id']
        path='/grn/admin/team/'+pid
        self.assertEqual(self.post(path,self.profile_data(agreement_status='signed')).status_code,400)
        self.assertEqual(self.post(path,self.profile_data(consent_date='2099-01-01')).status_code,400)
        self.assertEqual(self.post(path,self.profile_data(agreement_status='signed',agreement_reference='PRIVATE AGREEMENT',consent_proposals='yes')).status_code,303)
        row=self.query('SELECT * FROM profiles')[0]
        self.assertEqual(row['consent_proposals'],1)
        self.assertEqual(row['consent_materials'],0)
        self.assertEqual(row['agreement_status'],'signed')
        self.assertNotIn(b'PRIVATE AGREEMENT',self.client.get('/grn/').data)
        self.assertEqual(self.post(path,self.profile_data(version='2',consent='',published='',consent_proposals='yes')).status_code,303)
        self.assertNotIn(b'Public Test',self.client.get('/grn/').data)

    def test_team_credentials_publish_without_url(self):
        self.login()
        self.post('/grn/admin/team', {'name': 'Team test'})
        pid = self.query('SELECT id FROM profiles')[0]['id']
        response = self.post('/grn/admin/team/' + pid, self.profile_data(website='', academic_background='Robotics degree', credentials='Integration certification'))
        self.assertEqual(response.status_code, 303)
        self.post('/grn/admin/logout', {})
        public = self.client.get('/grn/').data
        self.assertIn(b'Robotics degree', public)
        self.assertIn(b'Integration certification', public)
        self.assertEqual(self.query('SELECT website FROM profiles')[0]['website'], '')


if __name__ == '__main__':
    unittest.main()
