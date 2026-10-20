import os,tempfile,unittest
from unittest.mock import patch
from .app import create_app

class ProductionProxyTest(unittest.TestCase):
    def test_https_forms_work_behind_render_without_trusting_forwarded_host(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,{'ROBOTIST_TRUST_PROXY':'1'}):
            app=create_app(dict(TESTING=True,SECRET_KEY='test',ADMIN_PASSWORD_HASH='unused',DATA_DIR=directory,CATALOG_IMPORT_EXISTING=False))
            client=app.test_client()
            headers={'X-Forwarded-Proto':'https','X-Forwarded-For':'198.51.100.23','X-Forwarded-Host':'evil.invalid'}
            response=client.get('/cart',base_url='http://robotist.example',headers=headers)
            self.assertIn('Secure',response.headers['Set-Cookie'])
            with client.session_transaction(base_url='https://robotist.example') as s:csrf=s['csrf']
            response=client.post('/cart/add',data={'csrf':csrf,'slug':'fourier-gr-3'},base_url='https://robotist.example',headers={**headers,'Origin':'https://robotist.example'})
            self.assertEqual(response.status_code,303)
            routed=client.post('/cart/add',data={'csrf':csrf,'slug':'fourier-gr-3'},base_url='https://robotist.example',headers={**headers,'Origin':'https://www.robotist.com.au'})
            self.assertEqual(routed.status_code,303)
            missing_token=client.post('/cart/add',data={'slug':'fourier-gr-3'},base_url='https://robotist.example',headers={**headers,'Origin':'https://www.robotist.com.au'})
            self.assertEqual(missing_token.status_code,400)
            self.assertEqual(client.post('/cart/add',data={'csrf':csrf,'slug':'fourier-gr-3'},base_url='https://robotist.example',headers={**headers,'Origin':'https://evil.invalid'}).status_code,403)
            self.assertEqual(client.get('/manage/',base_url='https://robotist.example',headers=headers).status_code,302)
            setup=client.get('/manage/setup',base_url='https://robotist.example',headers=headers)
            self.assertEqual(setup.status_code,302)
            self.assertIn('/login',setup.location)

if __name__=='__main__':unittest.main()
