import base64,tempfile,unittest,io
from pathlib import Path
from PIL import Image
from bs4 import BeautifulSoup
from .app import create_app


class IntegratedCatalogTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        import shutil
        shutil.copy(Path(__file__).resolve().parent.parent/'blog-posts.json',Path(self.tmp.name)/'blog-posts.json')
        self.app=create_app(dict(TESTING=True,DATA_DIR=self.tmp.name,BLOG_JSON=str(Path(self.tmp.name)/'blog-posts.json'),SECRET_KEY='test-only',ADMIN_PASSWORD_HASH='unused',SESSION_COOKIE_SECURE=False,CATALOG_IMPORT_EXISTING=False,LOCAL_REVIEW=True,LOCAL_AUTO_LOGIN=False))
        self.client=self.app.test_client()
        with self.client.session_transaction() as s:s['admin']=True;s['csrf']='test-csrf'
        self.headers={'X-Catalog-CSRF':'test-csrf'}
        self.d=self.client.post('/manage/catalog/api/products',json={},headers=self.headers).get_json()

    def tearDown(self):self.tmp.cleanup()

    def action(self,action,**data):
        response=self.client.post('/manage/catalog/api/products/'+self.d['id']+'/'+action,json=dict(version=self.d['version'],**data),headers=self.headers)
        if response.status_code==200:self.d=response.get_json()
        return response

    def ready(self):
        image=io.BytesIO();Image.new('RGB',(64,64),'blue').save(image,format='PNG')
        self.assertEqual(self.action('upload',area='cover',name='robot.png',data=base64.b64encode(image.getvalue()).decode()).status_code,200)
        self.action('save',fields={k:{'value':v,'reviewed':True} for k,v in {'name':'Integration Test Robot','category':'Humanoid','description':'Synthetic test robot only.','price':'Price on request','spec:Payload':'5 kg'}.items()},alts={a['id']:'Synthetic test robot' for a in self.d['assets']})

    def test_upload_first_and_two_collections(self):
        page=self.client.get('/manage/catalog/').text
        self.assertIn('Add robot',page);self.assertNotIn('id="slug"',page)
        home=self.client.get('/manage/').text
        self.assertIn('Robots for sale',home);self.assertIn('Team Members',home)
        self.assertEqual(self.client.get('/grn/admin/team').status_code,200)

    def test_publication_updates_actual_site_routes_atomically(self):
        self.ready()
        visitor=self.app.test_client()
        aid=self.d['assets'][0]['id']
        self.assertEqual(visitor.get('/catalog/images/'+aid).status_code,404)
        self.assertEqual(self.action('publish').status_code,400)
        self.assertEqual(self.action('preview').status_code,200)
        self.assertEqual(self.d['slug'],'integration-test-robot')
        preview=self.client.get('/manage/catalog/preview/'+self.d['id']).text
        self.assertIn('/manage/catalog/preview/'+self.d['id']+'#specs',preview)
        self.assertEqual(self.action('publish').status_code,200)
        path='/products/integration-test-robot.html'
        self.assertIn('5 kg',visitor.get(path).text)
        self.assertIn('integration-test-robot.html',visitor.get('/').text)
        self.assertIn('integration-test-robot.html',visitor.get('/compare.html').text)
        self.assertIn('integration-test-robot.html',visitor.get('/sitemap.xml').text)
        response=visitor.get('/catalog/images/'+aid)
        self.assertEqual(response.status_code,200)
        response.close()
        self.action('save',fields={'name':{'value':'Private edited title','reviewed':False}})
        self.assertNotIn('Private edited title',visitor.get(path).text)
        self.assertIn('Integration Test Robot',visitor.get(path).text)
        self.assertEqual(visitor.get('/manage/catalog/').status_code,302)
        self.assertEqual(visitor.get('/manage/catalog/api/products').status_code,401)

    def test_blog_pages_are_crawlable_and_drafts_stay_out(self):
        import json
        visitor=self.app.test_client()
        posts=json.loads((Path(__file__).resolve().parent.parent/'blog-posts.json').read_text(encoding='utf-8'))
        published=[p for p in posts if p.get('status')!='draft']
        drafts=[p for p in posts if p.get('status')=='draft']
        sitemap=visitor.get('/sitemap.xml').text
        for post in published:self.assertIn('/blog/'+post['slug']+'.html',sitemap)
        for post in drafts:self.assertNotIn('/blog/'+post['slug']+'.html',sitemap)
        first=published[0]['slug']
        page=visitor.get('/blog/'+first+'.html')
        self.assertEqual(page.status_code,200)
        self.assertIn('application/ld+json',page.text)
        missing=visitor.get('/blog/not-a-real-post.html')
        self.assertEqual(missing.status_code,302)
        self.assertIn('/blog-post.html?slug=not-a-real-post',missing.headers['Location'])
        # A published post whose committed page is missing must still serve a pre-rendered page
        # (this is the RankSpot-webhook publish path).
        page_path=Path(__file__).resolve().parent.parent/'blog'/(first+'.html')
        moved=page_path.with_name(first+'.html.bak')
        page_path.rename(moved)
        try:
            generated=visitor.get('/blog/'+first+'.html')
            self.assertEqual(generated.status_code,200)
            self.assertIn('application/ld+json',generated.text)
            self.assertIn('Generated page',generated.text)
            headline=published[0]['title']
            self.assertIn(headline,generated.text)
        finally:
            moved.rename(page_path)

    def test_auth_csrf_and_private_source(self):
        self.action('upload',area='documents',name='source.txt',data=base64.b64encode(b'Payload: 5 kg').decode())
        aid=self.d['assets'][0]['id']
        visitor=self.app.test_client()
        self.assertEqual(visitor.get('/manage/catalog/sources/'+aid).status_code,302)
        self.assertEqual(visitor.get('/catalog/service.py').status_code,404)
        self.assertEqual(visitor.get('/catalog/images/'+aid).status_code,404)
        self.assertEqual(self.client.post('/manage/catalog/api/products',json={}).status_code,400)
        self.assertEqual(self.client.post('/manage/catalog/api/products',json={},headers={**self.headers,'Origin':'https://elsewhere.invalid'}).status_code,403)
        response=self.client.get('/manage/catalog/sources/'+aid)
        self.assertIn('attachment',response.headers['Content-Disposition'])
        response.close()

    def test_imported_publication_replaces_existing_card_and_rows(self):
        self.ready()
        service=self.app.extensions['catalog']
        self.d['slug']='fourier-gr-3';self.d['auto_slug']=False
        self.d=service.store.save(self.d,self.d['version'],'Test existing route')
        self.action('preview');self.assertEqual(self.action('publish').status_code,200)
        from bs4 import BeautifulSoup
        page=BeautifulSoup(self.client.get('/compare.html').text,'html.parser')
        rows={id(a) for a in page.select('a.cmp-row[href="products/fourier-gr-3.html"]')}
        self.assertEqual(len(rows),1)
        self.assertIn('Integration Test Robot',self.client.get('/products/fourier-gr-3.html').text)


    def test_sensitive_asset_is_blurred_on_every_public_surface_until_revealed(self):
        image=io.BytesIO();Image.new('RGB',(64,64),'blue').save(image,format='PNG')
        raw=base64.b64encode(image.getvalue()).decode()
        self.assertEqual(self.action('upload',area='cover',name='robot.png',data=raw).status_code,200)
        self.assertEqual(self.action('upload',area='gallery',name='extra.png',data=raw).status_code,200)
        # Nothing is sensitive until the editor says so.
        self.assertFalse(any(a['nsfw'] for a in self.d['assets']))
        fields={'name':'Sensitive Test Robot','category':'Humanoid','description':'Synthetic test robot only.','price':'Price on request'}
        reviewed={k:{'value':v,'reviewed':True} for k,v in fields.items()}
        alts={a['id']:'Synthetic test robot' for a in self.d['assets']}
        self.action('save',fields=reviewed,alts=alts,nsfw={a['id']:True for a in self.d['assets']})
        self.assertTrue(all(a['nsfw'] for a in self.d['assets']))
        self.assertEqual(self.action('preview').status_code,200)
        self.assertEqual(self.action('publish').status_code,200)
        path='/products/sensitive-test-robot.html'
        visitor=self.app.test_client()
        veils=lambda markup:len(BeautifulSoup(markup,'html.parser').select('.nsfw-host'))
        page=visitor.get(path).text
        self.assertEqual(veils(page),2)
        self.assertIn('nsfw-blur',page)
        self.assertIn('/assets/nsfw-veil.css',page)
        self.assertIn('/assets/nsfw-veil.js',page)
        self.assertNotIn('og:image',page)
        self.assertEqual(veils(visitor.get('/').text),1)
        with visitor.session_transaction() as s:s['inquiry_cart']={'sensitive-test-robot':1}
        cart=visitor.get('/cart').text
        self.assertEqual(veils(cart),1)
        self.assertIn('nsfw-blur',cart)
        self.assertIn('/assets/nsfw-veil.css',cart)
        rows={r['slug']:r for r in visitor.get('/api/catalogue').get_json()['robots']}
        self.assertIs(rows['sensitive-test-robot']['nsfw'],True)
        self.assertIs(rows['fourier-gr-3']['nsfw'],False)
        # A product without the flag ships no veil at all.
        self.assertEqual(veils(visitor.get('/products/fourier-gr-3.html').text),0)
        # Clearing the toggle and publishing again removes the blur everywhere.
        self.action('save',fields=reviewed,alts=alts,nsfw={a['id']:False for a in self.d['assets']})
        self.assertFalse(any(a['nsfw'] for a in self.d['assets']))
        self.assertEqual(self.action('preview').status_code,200)
        self.assertEqual(self.action('publish').status_code,200)
        self.assertEqual(veils(visitor.get(path).text),0)
        self.assertEqual(veils(visitor.get('/').text),0)
        self.assertEqual(veils(visitor.get('/cart').text),0)
        rows={r['slug']:r for r in visitor.get('/api/catalogue').get_json()['robots']}
        self.assertIs(rows['sensitive-test-robot']['nsfw'],False)
        # The other product page family carries the same veil.
        self.action('save',fields=reviewed,alts=alts,nsfw={a['id']:True for a in self.d['assets']},template='compact')
        self.assertEqual(self.action('preview').status_code,200)
        self.assertEqual(self.action('publish').status_code,200)
        self.assertEqual(veils(visitor.get(path).text),2)
        self.assertEqual(veils(visitor.get('/').text),1)

    def test_each_video_carries_its_own_flag_and_only_a_boolean_marks_it(self):
        self.action('upload',area='documents',name='notes.txt',data=base64.b64encode(b'Payload: 5 kg').decode())
        self.assertIs(self.d['assets'][0]['nsfw'],False)
        self.action('save',videos=[{'title':'Sensitive walkthrough','url':'https://www.youtube.com/watch?v=dQw4w9WgXcQ','nsfw':True},
                                   {'title':'Open walkthrough','url':'https://www.youtube.com/watch?v=dQw4w9WgXcQ'}])
        self.assertEqual([v['nsfw'] for v in self.d['videos']],[True,False])
        self.action('save',videos=[{'title':'Sensitive walkthrough','url':'https://www.youtube.com/watch?v=dQw4w9WgXcQ','nsfw':'yes'}])
        self.assertIs(self.d['videos'][0]['nsfw'],False)
        self.assertEqual(self.action('save',nsfw={'robot-cover':'yes'}).status_code,400)


    def test_the_homepage_featured_band_follows_the_admin_flag(self):
        """The band is a toggle: flagged robots appear above the catalogue, cleared ones remove it."""
        self.ready()
        self.assertEqual(self.action('save',fields={'featured':{'value':'yes','reviewed':True}}).status_code,200)
        self.assertEqual(self.action('preview').status_code,200)
        self.assertEqual(self.action('publish').status_code,200)
        visitor=self.app.test_client()
        home=BeautifulSoup(visitor.get('/').text,'html.parser')
        band=home.select_one('#featured')
        self.assertIsNotNone(band,'the featured band should be on the page once a robot is flagged')
        self.assertFalse(band.has_attr('hidden'))
        grid=home.select_one('#featuredGrid')
        self.assertIn('integration-test-robot.html',str(grid))
        self.assertIn('Integration Test Robot',grid.get_text(' ',strip=True))
        # The catalogue grid still carries the published robot as it always did.
        self.assertIn('integration-test-robot.html',str(home.select_one('#robotGrid')))
        # Clearing the flag removes the band rather than leaving an empty one.
        self.assertEqual(self.action('save',fields={'featured':{'value':'','reviewed':True}}).status_code,200)
        self.assertEqual(self.action('preview').status_code,200)
        self.assertEqual(self.action('publish').status_code,200)
        cleared=BeautifulSoup(visitor.get('/').text,'html.parser')
        self.assertIsNone(cleared.select_one('#featured'))


    def test_blog_manager_reviews_and_flips_status(self):
        """The manager lists every post, previews a draft with noindex, and publish/unpublish round-trips."""
        import json
        source=json.loads((Path(__file__).resolve().parent.parent/'blog-posts.json').read_text(encoding='utf-8'))
        expected_drafts=sum(1 for p in source if p.get('status')=='draft')
        visitor=self.app.test_client()
        self.assertEqual(visitor.get('/manage/blog/').status_code,302)
        self.assertEqual(visitor.get('/manage/blog/api/posts').status_code,401)
        data=self.client.get('/manage/blog/api/posts').get_json()
        self.assertEqual(data['drafts'],expected_drafts)
        self.assertEqual(data['published'],len(source)-expected_drafts)
        self.assertTrue(data['csrf'])
        draft=next(p for p in data['posts'] if p.get('status')=='draft')
        preview=self.client.get('/manage/blog/preview/'+draft['slug'])
        self.assertEqual(preview.status_code,200)
        self.assertIn('noindex',preview.text)
        self.assertIn('Return to Blog Manager',preview.text)
        self.assertIn('/blog/'+draft['slug']+'.html',preview.text)
        published=self.client.post('/manage/blog/api/posts/'+draft['slug']+'/publish',headers=self.headers,json={})
        self.assertEqual(published.status_code,200)
        self.assertEqual(published.get_json()['status'],'published')
        on_disk=json.loads((Path(self.tmp.name)/'blog-posts.json').read_text(encoding='utf-8'))
        self.assertEqual(next(p for p in on_disk if p['slug']==draft['slug'])['status'],'published')
        back=self.client.post('/manage/blog/api/posts/'+draft['slug']+'/unpublish',headers=self.headers,json={})
        self.assertEqual(back.status_code,200)
        self.assertEqual(back.get_json()['drafts'],expected_drafts)
        self.assertIn('Blog posts',self.client.get('/manage/').text)
        self.assertEqual(self.client.post('/manage/blog/api/posts/'+draft['slug']+'/bogus',headers=self.headers,json={}).status_code,404)
        self.assertEqual(self.client.post('/manage/blog/api/posts/not-a-post/publish',headers=self.headers,json={}).status_code,404)


if __name__=='__main__':unittest.main(verbosity=2)
