"""Notification e-mail: a stored submission also reaches the team inbox."""
import os
import tempfile
import unittest
from unittest import mock

from .app import create_app
from grn import notify

CREDENTIALS = dict(ZOHO_EMAIL='robotist@example.invalid', ZOHO_APP_PASSWORD='test-only',
                   NOTIFY_EMAILS='first@example.invalid, second@example.invalid',
                   RESEND_API_KEY='')


class FakeSMTP:
    """Stands in for smtplib.SMTP_SSL and records what would be sent."""

    instances = []

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port = host, port
        self.sent = []
        self.user = None
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def login(self, user, password):
        self.user = (user, password)

    def send_message(self, message):
        self.sent.append(message)


class BrokenSMTP(FakeSMTP):
    def login(self, user, password):
        raise OSError('mail server unreachable')


def inquiry(**overrides):
    row = dict(id='RQ-TEST1', name='Ada Lovelace', email='ada@example.invalid',
               company='Analytical Engines', location='London', phone='+44 20 1',
               interest='Humanoids', message='We would like to evaluate two ADAM units.',
               source='contact', items={}, details={})
    row.update(overrides)
    return row


class NotificationUnitTest(unittest.TestCase):
    def setUp(self):
        FakeSMTP.instances = []
        self.env = mock.patch.dict(os.environ, CREDENTIALS)
        self.env.start()
        self.smtp = mock.patch.object(notify.smtplib, 'SMTP_SSL', FakeSMTP)
        self.smtp.start()

    def tearDown(self):
        self.smtp.stop()
        self.env.stop()

    def sent(self):
        return [message for client in FakeSMTP.instances for message in client.sent]

    def test_inquiry_notification_reaches_the_team(self):
        row = inquiry(items={'fourier-gr-3': 3}, details={'use_case': ['Factory demo', 'Expo stand']})
        self.assertTrue(notify.notify_inquiry(row))
        message, = self.sent()
        self.assertEqual(message['To'], 'first@example.invalid, second@example.invalid')
        self.assertEqual(message['Reply-To'], 'ada@example.invalid')
        self.assertIn('Ada Lovelace', message['Subject'])
        body = message.get_content()
        self.assertIn('RQ-TEST1', body)
        self.assertIn('contact form', body)
        self.assertIn('evaluate two ADAM units', body)
        self.assertIn('- 3 x fourier-gr-3', body)
        self.assertIn('use_case: Factory demo; Expo stand', body)
        self.assertEqual(FakeSMTP.instances[0].user, ('robotist@example.invalid', 'test-only'))

    def test_stored_cart_items_render_with_names(self):
        row = inquiry(source='cart', message='Cart request',
                      items=[{'slug': 'fourier-gr-3', 'name': 'Fourier GR-3', 'quantity': 3}])
        self.assertTrue(notify.notify_inquiry(row))
        message, = self.sent()
        self.assertIn('- 3 x Fourier GR-3', message.get_content())

    def test_junk_is_stored_without_mail(self):
        self.assertFalse(notify.notify_inquiry(inquiry(message='Cheap backlinks and guest posts for your site')))
        self.assertFalse(notify.notify_inquiry(inquiry(email='bot@mailinator.com')))
        self.assertFalse(notify.notify_inquiry(inquiry(message='See http://one.invalid and http://two.invalid')))
        self.assertEqual(self.sent(), [])

    def test_mail_failures_never_reach_the_visitor(self):
        with mock.patch.object(notify.smtplib, 'SMTP_SSL', BrokenSMTP):
            self.assertFalse(notify.notify_inquiry(inquiry()))

    def test_unconfigured_mailer_is_a_no_op(self):
        with mock.patch.dict(os.environ, {'ZOHO_EMAIL': '', 'ZOHO_APP_PASSWORD': '',
                                          'RESEND_API_KEY': '',
                                          'ZOHO_MAIL_CLIENT_ID': '',
                                          'ZOHO_MAIL_CLIENT_SECRET': '',
                                          'ZOHO_MAIL_REFRESH_TOKEN': ''}):
            self.assertFalse(notify.notify_inquiry(inquiry()))
        self.assertEqual(FakeSMTP.instances, [])

    def test_application_notification_reaches_the_team(self):
        row = dict(id='APP-1', name='Grace Hopper', email='grace@example.invalid',
                   location='New York', organization='US Navy', role='Systems integration',
                   website='https://example.invalid', experience='Fifteen years of integration work.',
                   motivation='I want to help operators deploy robots safely.',
                   service_regions='North America', availability='Q1', public_consent=1)
        self.assertTrue(notify.notify_application(row))
        message, = self.sent()
        self.assertIn('GRN application', message['Subject'])
        self.assertIn('Grace Hopper', message['Subject'])
        self.assertEqual(message['Reply-To'], 'grace@example.invalid')
        self.assertIn('Fifteen years of integration work.', message.get_content())


class NotificationFlowTest(unittest.TestCase):
    def setUp(self):
        FakeSMTP.instances = []
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app(dict(TESTING=True, DATA_DIR=self.tmp.name, SECRET_KEY='test',
                                   ADMIN_PASSWORD_HASH='unused', SESSION_COOKIE_SECURE=False,
                                   CATALOG_IMPORT_EXISTING=False))
        self.client = self.app.test_client()
        self.client.get('/cart')
        self.env = mock.patch.dict(os.environ, CREDENTIALS)
        self.env.start()
        self.smtp = mock.patch.object(notify.smtplib, 'SMTP_SSL', FakeSMTP)
        self.smtp.start()

    def tearDown(self):
        self.smtp.stop()
        self.env.stop()
        self.tmp.cleanup()

    def post(self, path, **data):
        with self.client.session_transaction() as session:
            data.setdefault('csrf', session['csrf'])
            data.setdefault('submission_token', session.get('inquiry_token'))
        return self.client.post(path, data=data)

    def test_a_new_inquiry_notifies_exactly_once(self):
        values = dict(name='Grace Hopper', email='grace@example.invalid',
                      message='Please quote one cleaning robot for our office.')
        self.assertEqual(self.post('/inquiries', **values).status_code, 303)
        self.assertEqual(self.post('/inquiries', **values).status_code, 303)
        messages = [message for client in FakeSMTP.instances for message in client.sent]
        self.assertEqual(len(messages), 1)
        self.assertIn('Grace Hopper', messages[0]['Subject'])
        with self.app.app_context():
            ident = self.app.extensions['grn_services']['db']().execute('SELECT id FROM inquiries').fetchone()['id']
        self.assertIn(ident, messages[0].get_content())

    def test_a_new_application_notifies(self):
        payload = dict(name='Test Robotist', email='test@example.invalid', location='Test City',
                       role='Robotics engineering', organization='Test organization',
                       experience='PRIVATE EXPERIENCE', motivation='PRIVATE MOTIVATION',
                       consent='yes', public_consent='yes')
        self.assertEqual(self.post('/grn/apply', **payload).status_code, 303)
        messages = [message for client in FakeSMTP.instances for message in client.sent]
        self.assertEqual(len(messages), 1)
        self.assertIn('Test Robotist', messages[0]['Subject'])

    def test_a_junk_inquiry_is_stored_and_silent(self):
        values = dict(name='SEO Offer', email='seo@example.invalid',
                      message='Buy casino backlinks, cheapest rates')
        self.assertEqual(self.post('/inquiries', **values).status_code, 303)
        self.assertEqual(FakeSMTP.instances, [])
        with self.app.app_context():
            count = self.app.extensions['grn_services']['db']().execute('SELECT count(*) FROM inquiries').fetchone()[0]
        self.assertEqual(count, 1)
