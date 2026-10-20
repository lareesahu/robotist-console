"""Mail delivery routes: HTTPS when the host blocks SMTP.

A free Render web service cannot open a connection to ports 25, 465 or 587, so
the SMTP route times out there and no notification is ever sent. These tests
cover the two HTTPS routes (Resend, and the Zoho Mail API), the order they are
chosen in, and what the log says when a send fails.
"""
import io
import unittest
from unittest import mock

from grn import notify

RECIPIENTS = 'first@example.invalid, second@example.invalid'
INQUIRY = ('RQ-TEST', 'Subject line', 'Body text', 'visitor@example.invalid',
           ('A Visitor', 'visitor@example.invalid', '', '', 'a real message'))


class RouteChoice(unittest.TestCase):
    def test_nothing_configured_means_no_route(self):
        with mock.patch.dict('os.environ', {'NOTIFY_EMAILS': RECIPIENTS}, clear=True):
            self.assertEqual(notify._route(), '')

    def test_a_resend_key_wins_over_smtp(self):
        env = {'RESEND_API_KEY': 'key', 'ZOHO_EMAIL': 'sender@example.invalid',
               'ZOHO_APP_PASSWORD': 'x'}
        with mock.patch.dict('os.environ', env, clear=True):
            self.assertEqual(notify._route(), 'resend')

    def test_the_zoho_mail_api_needs_all_three_values(self):
        env = {'ZOHO_MAIL_CLIENT_ID': 'id', 'ZOHO_MAIL_CLIENT_SECRET': 'secret'}
        with mock.patch.dict('os.environ', env, clear=True):
            self.assertEqual(notify._route(), '')
        env['ZOHO_MAIL_REFRESH_TOKEN'] = 'refresh'
        with mock.patch.dict('os.environ', env, clear=True):
            self.assertEqual(notify._route(), 'zoho-mail-api')

    def test_smtp_is_the_last_route_and_survives_for_paid_hosts(self):
        env = {'ZOHO_EMAIL': 'sender@example.invalid', 'ZOHO_APP_PASSWORD': 'x'}
        with mock.patch.dict('os.environ', env, clear=True):
            self.assertEqual(notify._route(), 'smtp')


class ResendRoute(unittest.TestCase):
    def test_the_message_goes_out_over_https_to_every_recipient(self):
        env = {'RESEND_API_KEY': 'key', 'ZOHO_EMAIL': 'sender@example.invalid',
               'NOTIFY_EMAILS': RECIPIENTS}
        calls = []

        def fake_post(url, payload, headers):
            calls.append((url, payload, headers))
            return {'id': 'abc'}

        with mock.patch.dict('os.environ', env, clear=True), \
                mock.patch.object(notify, '_post_json', fake_post):
            mailed = notify._deliver('inquiry', *INQUIRY)

        self.assertTrue(mailed)
        url, payload, headers = calls[0]
        self.assertEqual(url, 'https://api.resend.com/emails')
        self.assertEqual(payload['to'], ['first@example.invalid', 'second@example.invalid'])
        self.assertEqual(payload['from'], 'sender@example.invalid')
        self.assertEqual(payload['reply_to'], 'visitor@example.invalid')
        self.assertEqual(payload['subject'], 'Subject line')
        self.assertEqual(headers['Authorization'], 'Bearer key')

    def test_mail_from_can_override_the_sender(self):
        env = {'RESEND_API_KEY': 'key', 'NOTIFY_EMAILS': RECIPIENTS,
               'MAIL_FROM': 'noreply@example.invalid'}
        calls = []
        with mock.patch.dict('os.environ', env, clear=True), \
                mock.patch.object(notify, '_post_json',
                                  lambda url, payload, headers: calls.append(payload) or {'id': 'abc'}):
            notify._deliver('inquiry', *INQUIRY)
        self.assertEqual(calls[0]['from'], 'noreply@example.invalid')

    def test_a_refusal_is_logged_and_the_submission_still_stands(self):
        env = {'RESEND_API_KEY': 'key', 'ZOHO_EMAIL': 'sender@example.invalid'}
        with mock.patch.dict('os.environ', env, clear=True), \
                mock.patch.object(notify, '_post_json', lambda *a: {'error': 'bad key'}), \
                mock.patch('sys.stdout', new_callable=io.StringIO) as out:
            mailed = notify._deliver('inquiry', *INQUIRY)
        self.assertFalse(mailed)
        self.assertIn('mail failed via resend', out.getvalue())
        self.assertIn('bad key', out.getvalue())


class ZohoMailApiRoute(unittest.TestCase):
    def _env(self):
        return {'ZOHO_MAIL_CLIENT_ID': 'id', 'ZOHO_MAIL_CLIENT_SECRET': 'secret',
                'ZOHO_MAIL_REFRESH_TOKEN': 'refresh', 'ZOHO_EMAIL': 'sender@example.invalid',
                'NOTIFY_EMAILS': RECIPIENTS}

    def test_the_refresh_token_is_swapped_then_the_message_is_posted(self):
        calls = []

        def fake_request(url, data=None, headers=None, method='POST'):
            calls.append((url, data, headers, method))
            if 'oauth/v2/token' in url:
                return {'access_token': 'token-1'}
            if url.endswith('/api/accounts'):
                return {'data': [{'accountId': '778899'}]}
            return {'data': {'messageId': '1'}}

        with mock.patch.dict('os.environ', self._env(), clear=True), \
                mock.patch.object(notify, '_request', fake_request):
            mailed = notify._deliver('inquiry', *INQUIRY)

        self.assertTrue(mailed)
        token_call = calls[0]
        self.assertTrue(token_call[0].startswith('https://accounts.zoho.com/oauth/v2/token?'))
        self.assertIn('grant_type=refresh_token', token_call[0])
        self.assertIn('client_id=id', token_call[0])
        accounts_call = [c for c in calls if c[0] == 'https://mail.zoho.com/api/accounts'][0]
        self.assertEqual(accounts_call[3], 'GET')
        self.assertEqual(accounts_call[2]['Authorization'], 'Zoho-oauthtoken token-1')
        message_call = [c for c in calls if c[0].endswith('/accounts/778899/messages')][0]
        body = message_call[1].decode('utf-8')
        self.assertIn('fromAddress=sender%40example.invalid', body)
        self.assertIn('toAddress=first%40example.invalid%2Csecond%40example.invalid', body)
        self.assertIn('replyTo=visitor%40example.invalid', body)
        self.assertIn('mailFormat=plaintext', body)

    def test_a_refused_token_is_logged_not_raised(self):
        def fake_request(url, data=None, headers=None, method='POST'):
            return {'error': 'invalid_code'}

        with mock.patch.dict('os.environ', self._env(), clear=True), \
                mock.patch.object(notify, '_request', fake_request), \
                mock.patch('sys.stdout', new_callable=io.StringIO) as out:
            mailed = notify._deliver('inquiry', *INQUIRY)
        self.assertFalse(mailed)
        self.assertIn('mail failed via zoho-mail-api', out.getvalue())
        self.assertIn('invalid_code', out.getvalue())


class FailureLogging(unittest.TestCase):
    def test_a_blocked_smtp_send_says_why(self):
        env = {'ZOHO_EMAIL': 'sender@example.invalid', 'ZOHO_APP_PASSWORD': 'x'}
        broken = mock.Mock(side_effect=TimeoutError('timed out'))
        with mock.patch.dict('os.environ', env, clear=True), \
                mock.patch.object(notify, '_send', broken), \
                mock.patch('sys.stdout', new_callable=io.StringIO) as out:
            mailed = notify._deliver('inquiry', *INQUIRY)
        text = out.getvalue()
        self.assertFalse(mailed)
        self.assertIn('mail failed via smtp', text)
        self.assertIn('blocks outbound SMTP', text)

    def test_no_route_is_reported_once(self):
        with mock.patch.dict('os.environ', {}, clear=True), \
                mock.patch('sys.stdout', new_callable=io.StringIO) as out:
            mailed = notify._deliver('inquiry', *INQUIRY)
        self.assertFalse(mailed)
        self.assertIn('mail is not configured', out.getvalue())


class SpamGateStillWins(unittest.TestCase):
    def test_an_obvious_spam_submission_is_never_mailed(self):
        env = {'RESEND_API_KEY': 'key', 'NOTIFY_EMAILS': RECIPIENTS}
        with mock.patch.dict('os.environ', env, clear=True), \
                mock.patch.object(notify, '_post_json',
                                  mock.Mock(side_effect=AssertionError('must not send'))) as poster, \
                mock.patch('sys.stdout', new_callable=io.StringIO) as out:
            mailed = notify._deliver('inquiry', 'RQ-SPAM', 'S', 'B', 'bot@example.invalid',
                                     ('SEO Team', 'bot@example.invalid', '', 'seo',
                                      'cheap backlink seo package'))
        self.assertFalse(mailed)
        self.assertEqual(poster.call_count, 0)
        self.assertIn('looks like spam', out.getvalue())


class RequestHeaders(unittest.TestCase):
    """api.resend.com is behind Cloudflare, which 403s Python's default UA."""

    class _Response:
        def read(self):
            return b'{"id": "abc"}'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def test_every_call_carries_a_user_agent_that_is_not_python_urllib(self):
        seen = {}

        def fake_urlopen(request, timeout=None):
            seen['headers'] = {key.lower(): value for key, value in request.headers.items()}
            return self._Response()

        with mock.patch.object(notify.urllib.request, 'urlopen', fake_urlopen):
            notify._request('https://api.example.invalid/emails', b'{}',
                            {'Content-Type': 'application/json'})

        self.assertIn('user-agent', seen['headers'])
        self.assertNotIn('python-urllib', seen['headers']['user-agent'].lower())
        self.assertEqual(seen['headers']['accept'], 'application/json')

    def test_caller_headers_still_win(self):
        seen = {}

        def fake_urlopen(request, timeout=None):
            seen['headers'] = {key.lower(): value for key, value in request.headers.items()}
            return self._Response()

        with mock.patch.object(notify.urllib.request, 'urlopen', fake_urlopen):
            notify._request('https://api.example.invalid/emails', b'{}',
                            {'Authorization': 'Bearer key'})

        self.assertEqual(seen['headers']['authorization'], 'Bearer key')


if __name__ == '__main__':
    unittest.main()
