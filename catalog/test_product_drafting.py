import base64
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from bs4 import BeautifulSoup
from .content import video, plain_text
from .extraction import extract
from .test_integration import IntegratedCatalogTest


class ProductVideosTest(IntegratedCatalogTest):
    def test_video_publish_and_draft_isolation(self):
        self.ready()
        self.assertEqual(self.action('save',videos=[{'title':'Handling demonstration','url':'https://youtu.be/abcdefghijk'}]).status_code,200)
        self.action('preview');self.action('publish')
        path='/products/'+self.d['slug']+'.html'
        page=BeautifulSoup(self.app.test_client().get(path).text,'html.parser')
        frame=page.select_one('#product-videos iframe')
        self.assertEqual(frame['src'],'https://www.youtube-nocookie.com/embed/abcdefghijk')
        self.assertEqual(frame['title'],'Handling demonstration')
        self.assertEqual(self.action('save',videos=[]).status_code,200)
        self.assertIn('product-videos',self.app.test_client().get(path).text)
        self.assertNotIn('id="product-videos"',self.client.get('/manage/catalog/preview/'+self.d['id']).text)

    def test_autofill_preserves_edits_and_conflicts(self):
        self.action('save',fields={'name':{'value':'My title','reviewed':True}})
        candidates=[dict(key=k,value=v,source_id='test',locator='line 1',quote=v) for k,v in [('name','Suggested title'),('description','**Useful** introduction'),('spec:Payload','5 kg'),('spec:Payload','6 kg')]]
        with patch('catalog.service.extract',return_value=(candidates,'DeepSeek Flash')):
            self.assertEqual(self.action('extract',mode='ai').status_code,200)
            self.assertEqual(self.d['fields']['name']['value'],'My title')
            self.assertEqual(self.d['fields']['description']['value'],'Useful introduction')
            self.assertFalse(self.d['fields']['description']['reviewed'])
            self.assertNotIn('spec:Payload',self.d['fields'])
            self.assertEqual(sum(c['decision']=='pending' for c in self.d['candidates']),3)
            self.action('extract',mode='ai')
            self.assertEqual(len(self.d['candidates']),4)

    def test_plain_copy_across_public_views(self):
        self.ready()
        self.action('save',fields={'description':{'value':'**Useful** robot. <script>alert(1)</script>','reviewed':True}})
        self.action('preview');self.action('publish')
        for route in ['/','/products/'+self.d['slug']+'.html']:
            text=self.app.test_client().get(route).text
            self.assertNotIn('**Useful**',text)
            self.assertNotIn('<script>alert(1)</script>',text)
            if route!='/' : self.assertIn('Useful',text)


class ProviderAndMediaTest(unittest.TestCase):
    def test_video_validation(self):
        for url in ['javascript:alert(1)','https://youtube.com.evil.example/embed/abcdefghijk','http://vimeo.com/1234','https://127.0.0.1/a.mp4','<iframe src="https://youtube.com"></iframe>']:
            with self.assertRaises(ValueError):video({'url':url,'title':'Demo'})
        self.assertEqual(video({'url':'https://vimeo.com/123456/abcd1234','title':'Demo'})['src'],'https://player.vimeo.com/video/123456?h=abcd1234')
        self.assertEqual(video({'url':'https://cdn.example.com/demo.mp4','title':'Demo'})['kind'],'video')
        self.assertEqual(plain_text('**Text**\n- `Payload`: 5 kg'),'Text\nPayload: 5 kg')

    def test_deepseek_request_and_invalid_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory);p.joinpath('a').write_text('Payload: 5 kg',encoding='utf-8')
            response={'status':'completed','output':[{'content':[{'type':'output_text','text':json.dumps({'candidates':[{'key':'spec:Payload','value':'5 kg','source_id':'a','quote':'invented quote','locator':'line 1'}]})}]}]}
            class Reply:
                def __enter__(self):return self
                def __exit__(self,*args):pass
                def read(self):return json.dumps(response).encode()
            with patch.dict(os.environ,{'DEEPSEEK_API_KEY':'test-only'}),patch('catalog.extraction.urllib.request.urlopen',return_value=Reply()) as call:
                with self.assertRaisesRegex(ValueError,'quote was not found'):extract([{'id':'a','name':'source.txt','mime':'text/plain'}],p,'ai')
                req=call.call_args[0][0]
                self.assertEqual(req.full_url,'https://api.deepseek.com/responses')
                self.assertEqual(json.loads(req.data)['model'],'deepseek-v4-flash')


if __name__=='__main__':unittest.main()
