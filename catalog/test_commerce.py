import json
import tempfile
import unittest
from bs4 import BeautifulSoup
from .app import create_app


class InquiryFlowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app(dict(TESTING=True, DATA_DIR=self.tmp.name, SECRET_KEY='test', ADMIN_PASSWORD_HASH='unused', SESSION_COOKIE_SECURE=False, CATALOG_IMPORT_EXISTING=False))
        self.client = self.app.test_client()
        self.client.get('/cart')

    def tearDown(self):
        self.tmp.cleanup()

    def post(self, path, **data):
        with self.client.session_transaction() as s:
            data.setdefault('csrf', s['csrf'])
            data.setdefault('submission_token', s.get('inquiry_token'))
        return self.client.post(path, data=data)

    def test_cart_submission_snapshot_duplicate_and_private_review(self):
        self.assertEqual(self.post('/cart/add', slug='fourier-gr-3').status_code, 303)
        self.assertEqual(self.post('/cart/update', **{'quantity_fourier-gr-3': '3'}).status_code, 303)
        self.assertEqual(self.post('/cart/update', **{'quantity_fourier-gr-3': '0'}).status_code, 400)
        self.assertEqual(self.post('/cart/add', slug='does-not-exist').status_code, 404)
        values = dict(name='Cart test', email='cart@example.invalid', message='Three robots for evaluation')
        self.assertEqual(self.post('/cart/submit', **values).status_code, 303)
        self.assertEqual(self.post('/cart/submit', **values).status_code, 303)
        with self.app.app_context():
            rows = self.app.extensions['grn_services']['db']().execute('SELECT * FROM inquiries').fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(json.loads(rows[0]['items'])[0]['quantity'], 3)
            ident = rows[0]['id']
        self.assertEqual(self.client.get('/manage/inquiries/'+ident).status_code, 302)
        self.assertIn('Your request', self.client.get('/inquiry/received').text)
        with self.client.session_transaction() as s:
            self.assertEqual(s['inquiry_cart'], {})
            s['admin'] = True
        self.assertIn('Quantity 3', self.client.get('/manage/inquiries/'+ident).text)
        self.assertEqual(self.post('/manage/inquiries/'+ident, status='reviewing', notes='Internal only', version='1').status_code, 303)
        self.assertEqual(self.post('/manage/inquiries/'+ident, status='closed', version='1').status_code, 409)
        self.assertIn('Internal only', self.client.get('/manage/inquiries/'+ident).text)
        self.client.get('/cart')
        self.post('/cart/add', slug='fourier-gr-3')
        self.assertEqual(self.post('/cart/submit', **values).status_code, 303)
        with self.app.app_context():
            self.assertEqual(self.app.extensions['grn_services']['db']().execute('SELECT count(*) FROM inquiries').fetchone()[0], 2)

    def test_contact_form_routes_locally_and_validates(self):
        page = BeautifulSoup(self.client.get('/contact.html').text, 'html.parser')
        form = page.select_one('#inquiry-form')
        self.assertEqual(form['action'], '/inquiries')
        self.assertTrue(form.select_one('[name=csrf]')['value'])
        self.assertTrue(form.select_one('[name=submission_token]')['value'])
        script = self.client.get('/assets/form-workflow.js').text
        self.assertNotIn('https://formspree.io/f/mnjevgjq', script)
        self.assertIn('/inquiries', script)
        self.assertEqual(self.client.post('/inquiries', data={}).status_code, 400)
        self.assertEqual(self.post('/inquiries', name='Test', email='invalid', message='Inquiry').status_code, 400)
        self.assertEqual(self.post('/inquiries', name='<script>test</script>', email='contact@example.invalid', message='Contact inquiry').status_code, 303)
        with self.client.session_transaction() as s:
            s['admin'] = True
            ident = s['inquiry_receipt']
        html = self.client.get('/manage/inquiries/'+ident).text
        self.assertIn('&lt;script&gt;test&lt;/script&gt;', html)
        self.assertIn('Contact inquiry', html)

    def test_onepage_application_and_cart_buttons(self):
        self.assertEqual(self.client.get('/grn/apply').location, '/grn/#application')
        html = self.client.get('/grn/').text
        self.assertIn('hero-application', html)
        self.assertIn('name="experience"', html)
        page = BeautifulSoup(self.client.get('/products/fourier-gr-3.html').text, 'html.parser')
        self.assertTrue(page.select_one('form[action="/cart/add"] [name="slug"][value="fourier-gr-3"]'))
        self.assertTrue(page.select_one('body > .inquiry-cart-link'))

    def test_requirements_preserves_multiple_answers(self):
        html = self.client.get('/requirements.html').text
        self.assertNotIn('https://formspree.io/f/mnjevgjq', html)
        self.assertIn('name="form_kind"', html)
        self.assertEqual(self.post('/inquiries', form_kind='requirements', customer_name='Test company', country='Australia', email='requirements@example.invalid', decision_chain=['End User','Integrator']).status_code, 303)
        with self.client.session_transaction() as s:
            s['admin'] = True
            ident = s['inquiry_receipt']
        html = self.client.get('/manage/inquiries/'+ident).text
        self.assertIn('End User, Integrator', html)
        self.assertIn('Australia', html)


if __name__ == '__main__':
    unittest.main()
