"""Chatbot keys belong to the service, never to the browser.

These tests fail if a page ever ships a key or a direct provider URL again, and
they pin the assistant endpoint's refusals and clamps.
"""
import json, os, re, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from .app import create_app

KEY = 'sk-49c14c16ee84428da4bd99c58264bed0'
PAGES = ['/', '/robotmaxx-chat.html', '/eden-chat.html', '/eden-chat/', '/eden-chat-v2.html']


class FakeUpstream:
    def __init__(self, payload, status=200):
        self.payload, self.status = payload, status

    def read(self):
        return json.dumps(self.payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class AssistantTest(unittest.TestCase):
    def build(self, directory, **env):
        patcher = patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        return create_app(dict(TESTING=True, SECRET_KEY='test', ADMIN_PASSWORD_HASH='unused',
                               DATA_DIR=directory, CATALOG_IMPORT_EXISTING=False))

    def test_no_public_page_ships_a_key_or_calls_the_provider_directly(self):
        with tempfile.TemporaryDirectory() as directory:
            client = self.build(directory, DEEPSEEK_API_KEY=KEY).test_client()
            for page in PAGES:
                body = client.get(page).get_data(as_text=True)
                self.assertNotIn(KEY, body, page + ' ships the key')
                self.assertIsNone(re.search(r"sk-[A-Za-z0-9]{16,}", body), page + ' ships a key-looking string')
                self.assertNotIn('api.deepseek.com', body, page + ' calls the provider from the browser')
            for page in PAGES[1:]:
                self.assertIn('/api/assistant', client.get(page).get_data(as_text=True), page + ' does not use the server endpoint')

    def test_without_a_configured_key_the_endpoint_says_so(self):
        with tempfile.TemporaryDirectory() as directory:
            client = self.build(directory).test_client()
            os.environ.pop('DEEPSEEK_API_KEY', None)
            response = client.post('/api/assistant', json={'messages': [{'role': 'user', 'content': 'hi'}]})
            self.assertEqual(response.status_code, 503)

    def test_endpoint_forwards_clamped_input_and_returns_the_upstream_body(self):
        with tempfile.TemporaryDirectory() as directory:
            client = self.build(directory, DEEPSEEK_API_KEY=KEY).test_client()
            seen = {}

            def fake(request, timeout=None):
                seen['url'], seen['body'] = request.full_url, json.loads(request.data)
                seen['auth'] = request.headers.get('Authorization')
                return FakeUpstream({'choices': [{'message': {'content': 'hello'}}]})

            with patch('catalog.app.urllib.request.urlopen', fake):
                response = client.post('/api/assistant', json={
                    'model': 'deepseek-v4-pro',
                    'max_tokens': 99999,
                    'temperature': 4,
                    'messages': [{'role': 'user', 'content': 'hi'}, {'role': 'system', 'content': ''}]})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()['choices'][0]['message']['content'], 'hello')
            self.assertEqual(seen['url'], 'https://api.deepseek.com/v1/chat/completions')
            self.assertEqual(seen['auth'], 'Bearer ' + KEY)
            self.assertEqual(seen['body']['model'], 'deepseek-flash', 'the client must not choose the model')
            self.assertEqual(seen['body']['max_tokens'], 1000, 'the token budget must be clamped')
            self.assertEqual(seen['body']['temperature'], 1.0, 'temperature must be clamped')
            self.assertEqual(seen['body']['thinking'], {'type': 'disabled'})
            roles = [m['role'] for m in seen['body']['messages']]
            self.assertEqual(roles[0], 'system', 'the live catalogue is sent as the first system message')
            self.assertIn('ROBOTIST CATALOGUE', seen['body']['messages'][0]['content'])
            self.assertEqual(roles[1:], ['user'], 'blank messages are dropped and order is preserved')

    def test_the_assistant_is_told_the_specifications_the_site_publishes(self):
        with tempfile.TemporaryDirectory() as directory:
            client = self.build(directory, DEEPSEEK_API_KEY=KEY).test_client()
            seen = {}

            def fake(request, timeout=None):
                seen['body'] = json.loads(request.data)
                return FakeUpstream({'choices': [{'message': {'content': 'ok'}}]})

            with patch('catalog.app.urllib.request.urlopen', fake):
                response = client.post('/api/assistant', json={'messages': [{'role': 'user', 'content': 'specs?'}]})
            self.assertEqual(response.status_code, 200)
            digest = seen['body']['messages'][0]['content']
            self.assertIn('slug pndbotics-adam', digest)
            self.assertIn('Degrees of Freedom', digest, 'a published specification must reach the assistant')

    def test_a_rough_published_document_cannot_take_the_assistant_down(self):
        """A published document must reach the assistant, whatever shape it is in."""
        with tempfile.TemporaryDirectory() as directory:
            app = self.build(directory, DEEPSEEK_API_KEY=KEY)
            store = app.extensions['catalog'].store
            page = (Path(__file__).resolve().parent.parent / 'index.html').read_text(encoding='utf-8')
            seen = {}

            def published(slug=None):
                fields = {'name': {'value': 'ADAM SP'},
                          'category': {'value': 'Humanoid'},
                          'description': {'value': 'Full-size humanoid research platform'},
                          'spec:Platform': {'value': 'Full-size humanoid'},
                          'spec:Payload': {'value': ' 45 kg '}}
                document = {'id': 'x', 'slug': slug or 'pndbotics-adam', 'version': 1, 'state': 'published',
                            'notes': '', 'fields': fields, 'assets': [], 'candidates': []}
                return document if slug else [document]

            def fake(request, timeout=None):
                seen['body'] = json.loads(request.data)
                return FakeUpstream({'choices': [{'message': {'content': 'ok'}}]})

            with patch.object(store, 'published', published):
                with patch('catalog.site.Site.homepage', return_value=page):
                    with patch('catalog.app.urllib.request.urlopen', fake):
                        response = app.test_client().post('/api/assistant', json={'messages': [{'role': 'user', 'content': 'hi'}]})
            self.assertEqual(response.status_code, 200)
            digest = seen['body']['messages'][0]['content']
            self.assertIn('Platform: Full-size humanoid', digest, 'a published specification must reach the assistant')
            self.assertIn('Payload: 45 kg', digest, 'published values must be trimmed, not dropped')

    def test_endpoint_refuses_shapes_it_cannot_serve(self):
        with tempfile.TemporaryDirectory() as directory:
            client = self.build(directory, DEEPSEEK_API_KEY=KEY).test_client()
            self.assertEqual(client.post('/api/assistant', data='not json', content_type='text/plain').status_code, 415)
            self.assertEqual(client.post('/api/assistant', json={'messages': []}).status_code, 400)
            self.assertEqual(client.post('/api/assistant', json={'messages': 'hi'}).status_code, 400)
            self.assertEqual(client.post('/api/assistant', json={'messages': [{'role': 'tool', 'content': 'x'}]}).status_code, 400)
            foreign = client.post('/api/assistant', json={'messages': [{'role': 'user', 'content': 'hi'}]},
                                  headers={'Origin': 'https://evil.invalid'})
            self.assertEqual(foreign.status_code, 403, 'foreign origins must be refused')

    def test_other_posts_still_need_the_session_token(self):
        with tempfile.TemporaryDirectory() as directory:
            client = self.build(directory, DEEPSEEK_API_KEY=KEY).test_client()
            without = client.post('/cart/add', data={'slug': 'fourier-gr-3'},
                                  base_url='https://www.robotist.com.au',
                                  headers={'Origin': 'https://www.robotist.com.au'})
            self.assertEqual(without.status_code, 400, 'exempting the assistant must not exempt other posts')

    def test_the_endpoint_is_rate_limited(self):
        with tempfile.TemporaryDirectory() as directory:
            client = self.build(directory, DEEPSEEK_API_KEY=KEY).test_client()
            with patch('catalog.app.urllib.request.urlopen', lambda request, timeout=None: FakeUpstream({'choices': []})):
                codes = [client.post('/api/assistant', json={'messages': [{'role': 'user', 'content': 'hi'}]}).status_code
                         for _ in range(41)]
            self.assertEqual(codes[-1], 429, 'the 41st call in the window must be refused')
            self.assertIn(200, codes)

    def test_the_assistant_knowledge_matches_the_visible_catalogue(self):
        """ /api/catalogue is what the assistant is told about and what the page renders. """
        with tempfile.TemporaryDirectory() as directory:
            client = self.build(directory, DEEPSEEK_API_KEY=KEY).test_client()
            rows = client.get('/api/catalogue').get_json()['robots']
            self.assertTrue(rows, 'the catalogue endpoint returned nothing')
            page = client.get('/').get_data(as_text=True)
            for robot in rows:
                self.assertIn(robot['slug'] + '.html', page, robot['slug'] + ' is offered but not shown on the homepage')
                self.assertTrue(robot['name'], robot['slug'] + ' has no name')
                self.assertTrue(robot['slug'] and robot['slug'].islower(), 'slugs are what the model echoes back')
            self.assertGreaterEqual(len(rows), 20, 'the catalogue is suspiciously small')

    def test_every_catalogue_card_shares_one_geometry(self):
        """The rendered catalogue keeps one card size per breakpoint, no stray rows."""
        with tempfile.TemporaryDirectory() as directory:
            client = self.build(directory, DEEPSEEK_API_KEY=KEY).test_client()
            page = client.get('/').get_data(as_text=True)
            self.assertIn('id="robotGrid"', page)
            for stale in ('catalogueFeatured', 'catalogueMid', 'robot-card featured', 'robot-card mid', 'robot-card small'):
                self.assertNotIn(stale, page, stale + ' came back')


if __name__ == '__main__':
    unittest.main()
