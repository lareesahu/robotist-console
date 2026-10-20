import json
import tempfile
import unittest
from pathlib import Path
from .app import create_app
from .local_config import local_options


class AdminAccessTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.options=local_options(self.tmp.name)
        self.options.update(TESTING=True,CATALOG_IMPORT_EXISTING=False)
        self.app=create_app(self.options)
        self.client=self.app.test_client()

    def tearDown(self):self.tmp.cleanup()

    def post(self,client,path,**values):
        client.get(path)
        with client.session_transaction() as s:values['csrf']=s['csrf']
        return client.post(path,data=values)

    def test_setup_login_logout_restart_and_private_pages(self):
        self.assertEqual(self.client.get('/manage/').status_code,302)
        self.assertEqual(self.client.get('/manage/catalog/api/products').status_code,401)
        self.assertEqual(self.client.get('/manage/login').location,'/manage/setup')
        self.assertEqual(self.post(self.client,'/manage/setup',password='short',confirm='short').status_code,400)
        password='local-test-only-password'
        self.assertEqual(self.post(self.client,'/manage/setup',password=password,confirm=password).location,'/manage/')
        self.assertIn('Manage Robotist.',self.client.get('/manage/').text)
        self.assertNotIn(password,Path(self.tmp.name,'admin-config.json').read_text())
        self.assertEqual(self.client.get('/manage/setup').status_code,302)
        self.post(self.client,'/grn/admin/logout')
        for path in ('/manage/','/manage/catalog/','/grn/admin','/grn/admin/team'):
            self.assertEqual(self.client.get(path).status_code,302)
        options=local_options(self.tmp.name)
        options.update(TESTING=True,CATALOG_IMPORT_EXISTING=False)
        restarted=create_app(options).test_client()
        self.assertEqual(self.post(restarted,'/manage/login',password='wrong-password').status_code,401)
        response=self.post(restarted,'/manage/login?next=//evil.invalid',password=password)
        self.assertEqual(response.location,'/manage/')
        self.assertEqual(restarted.get('/grn/admin/team').status_code,200)
        self.assertEqual(restarted.get('/manage/catalog/api/products').status_code,200)

    def test_setup_requires_loopback_and_csrf(self):
        self.assertEqual(self.client.post('/manage/setup',data={'password':'not-used'}).status_code,400)
        self.assertEqual(self.client.get('/manage/setup',environ_base={'REMOTE_ADDR':'192.168.1.5'}).status_code,403)
        self.assertEqual(self.client.get('/manage/setup',headers={'Host':'elsewhere.invalid'}).status_code,403)


if __name__=='__main__':unittest.main()
