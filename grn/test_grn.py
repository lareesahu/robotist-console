"""Behavior/security regression suite, isolated temporary SQLite databases."""
import io
import json
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

    # --- skills and languages -------------------------------------------------

    def member(self, **overrides):
        self.login()
        self.post('/grn/admin/team', {'name': 'Skill Test'})
        pid = self.query('SELECT id FROM profiles')[0]['id']
        data = self.profile_data(**overrides)
        return pid, data

    def test_skills_and_languages_round_trip(self):
        pid, data = self.member(skills='ROS 2, PLC programming',
                                language_name_1='English', language_level_1='fluent',
                                language_name_2='Mandarin', language_level_2='native')
        self.assertEqual(self.post('/grn/admin/team/' + pid, data).status_code, 303)
        row = self.query('SELECT skills, languages FROM profiles')[0]
        self.assertEqual(json.loads(row['skills']), ['ROS 2', 'PLC programming'])
        self.assertEqual(json.loads(row['languages']), [{'name': 'English', 'level': 'fluent'},
                                                        {'name': 'Mandarin', 'level': 'native'}])
        editor = self.client.get('/grn/admin/team/' + pid).data
        self.assertIn(b'>ROS 2, PLC programming</textarea>', editor)
        self.assertIn(b'value="English" maxlength="40"', editor)
        self.assertIn(b'value="fluent" selected', editor)
        self.assertNotIn(b'[{&quot;name&quot;', editor)
        public = self.client.get('/grn/').data
        self.assertIn(b'<li>ROS 2</li>', public)
        self.assertIn(b'<li>PLC programming</li>', public)
        self.assertIn(b'English (Fluent)', public)
        self.assertIn(b'Mandarin (Native)', public)

    def test_skills_dedupe_and_short_items(self):
        pid, data = self.member(skills='ROS 2, ros 2, C, R, R&D (firmware), 中文')
        self.assertEqual(self.post('/grn/admin/team/' + pid, data).status_code, 303)
        self.assertEqual(json.loads(self.query('SELECT skills FROM profiles')[0]['skills']),
                         ['ROS 2', 'C', 'R', 'R&D (firmware)', '中文'])

    def test_skill_limit_and_version_unchanged(self):
        pid, data = self.member(skills=', '.join(f'Skill {n}' for n in range(1, 14)))
        self.assertEqual(self.post('/grn/admin/team/' + pid, data).status_code, 400)
        row = self.query('SELECT skills, version FROM profiles')[0]
        self.assertEqual(row['skills'], '[]')
        self.assertEqual(row['version'], 1)

    def test_skill_markup_rejected_and_ampersand_escaped(self):
        pid, data = self.member(skills='<script>alert(1)</script>')
        response = self.post('/grn/admin/team/' + pid, data)
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'Remove unsupported characters', response.data)
        data = self.profile_data(skills='R&D (firmware)')
        self.assertEqual(self.post('/grn/admin/team/' + pid, data).status_code, 303)
        self.assertIn(b'R&amp;D (firmware)', self.client.get('/grn/').data)
        self.assertNotIn(b'<script>alert', self.client.get('/grn/').data)

    def test_languages_need_a_level_and_a_single_level_per_language(self):
        pid, data = self.member(language_name_1='English', language_level_1='')
        self.assertIn(b'Choose a level for English.', self.post('/grn/admin/team/' + pid, data).data)
        data = self.profile_data(language_name_1='English', language_level_1='fluent',
                                 language_name_2='English', language_level_2='basic')
        self.assertIn(b'appears twice with different levels', self.post('/grn/admin/team/' + pid, data).data)
        data = self.profile_data(language_name_1='English', language_level_1='fluent',
                                 language_name_2='english', language_level_2='fluent')
        self.assertEqual(self.post('/grn/admin/team/' + pid, data).status_code, 303)
        self.assertEqual(len(json.loads(self.query('SELECT languages FROM profiles')[0]['languages'])), 1)

    def test_legacy_and_corrupt_rows_render_without_blocks(self):
        pid, data = self.member()
        self.assertEqual(self.post('/grn/admin/team/' + pid, data).status_code, 303)
        self.assertNotIn(b'skill-chips', self.client.get('/grn/').data)
        self.assertNotIn(b'language-line', self.client.get('/grn/').data)
        with closing(sqlite3.connect(Path(self.tmp.name) / 'grn.sqlite3')) as con:
            con.execute("UPDATE profiles SET skills='', languages='not json'")
            con.commit()
        public = self.client.get('/grn/')
        self.assertEqual(public.status_code, 200)
        self.assertNotIn(b'skill-chips', public.data)

    def test_public_change_needs_new_approval_evidence(self):
        pid, data = self.member(skills='ROS 2')
        self.assertEqual(self.post('/grn/admin/team/' + pid, data).status_code, 303)
        first_scope = self.query('SELECT consent_scope FROM profiles')[0]['consent_scope']
        self.assertEqual(len(first_scope), 64)
        changed = self.profile_data(version='2', skills='ROS 2, Python')
        blocked = self.post('/grn/admin/team/' + pid, changed)
        self.assertEqual(blocked.status_code, 400)
        self.assertIn(b'Record the new approval evidence reference', blocked.data)
        self.assertEqual(self.query('SELECT skills FROM profiles')[0]['skills'], '["ROS 2"]')
        approved = self.profile_data(version='2', skills='ROS 2, Python',
                                     consent_reference='Second approval email, 21 October 2026')
        self.assertEqual(self.post('/grn/admin/team/' + pid, approved).status_code, 303)
        self.assertNotEqual(self.query('SELECT consent_scope FROM profiles')[0]['consent_scope'], first_scope)
        unpublished = self.profile_data(version='3', published='', consent='', skills='ROS 2, Python, C++',
                                        consent_reference='Second approval email, 21 October 2026')
        self.assertEqual(self.post('/grn/admin/team/' + pid, unpublished).status_code, 303)
        republish = self.profile_data(version='4', skills='ROS 2, Python, C++',
                                      consent_reference='Second approval email, 21 October 2026')
        self.assertEqual(self.post('/grn/admin/team/' + pid, republish).status_code, 400)

    def test_failed_save_preserves_typed_skills(self):
        pid, data = self.member(skills='ROS 2, Python',
                                language_name_1='English', language_level_1='fluent')
        response = self.post('/grn/admin/team/' + pid, {**data, 'sort_order': '9999'})
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'>ROS 2, Python</textarea>', response.data)
        self.assertIn(b'value="fluent" selected', response.data)

    def test_team_list_shows_counts(self):
        pid, data = self.member(skills='ROS 2, Python',
                                language_name_1='English', language_level_1='fluent')
        self.assertEqual(self.post('/grn/admin/team/' + pid, data).status_code, 303)
        listing = self.client.get('/grn/admin/team').data
        self.assertIn(b'2 skills', listing)
        self.assertIn(b'1 language', listing)

    def test_skill_parser_limits(self):
        from grn.profile_fields import parse_languages, parse_skills
        self.assertEqual(parse_skills('ROS 2;PLC\n machine  vision'), ['ROS 2', 'PLC', 'machine vision'])
        self.assertRaises(ValueError, parse_skills, 'x' * 41)
        self.assertRaises(ValueError, parse_skills, ', '.join(f'S{n}' for n in range(13)))
        self.assertEqual(parse_languages(['', '', '', '', '', ''], ['', '', '', '', '', '']), [])
        self.assertRaises(ValueError, parse_languages, ['Klingon'], ['godlike'])


if __name__ == '__main__':
    unittest.main()
