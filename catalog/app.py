"""Robotist website and internal CMS share one origin and the GRN admin session."""
import argparse,json,mimetypes,os,secrets,sqlite3,time,urllib.error,urllib.request
from pathlib import Path
from urllib.parse import urlsplit
from functools import wraps
from flask import request,session,redirect,jsonify,abort,send_from_directory,Response,render_template,url_for
from werkzeug.security import generate_password_hash
from grn.app import create_app as create_grn_app
from .service import CatalogService,readiness
from .content import plain_text
from grn.database import connect
from .site import Site, analytics, consent
from .import_existing import import_catalog

ROOT=Path(__file__).resolve().parent.parent

# ── Blog: pre-rendered pages, generated on demand ────────────────────────────
# Published posts ship as blog/<slug>.html (built by tools/build_blog_static.py). The RankSpot
# webhook commits blog-posts.json directly, so a freshly published post may not have its page
# yet; render it here rather than sending a crawler to the JavaScript-only article route.
_blog_pages={}
_blog_module=None

def render_blog_page(slug):
    global _blog_module
    import importlib.util,logging
    try:
        posts_path=ROOT/'blog-posts.json'; template_path=ROOT/'blog-post.html'
        key=(posts_path.stat().st_mtime_ns,template_path.stat().st_mtime_ns)
        hit=_blog_pages.get(slug)
        if hit and hit[0]==key:return hit[1]
        posts=json.loads(posts_path.read_text(encoding='utf-8'))
        post=next((p for p in posts if p.get('slug')==slug and p.get('status')!='draft'),None)
        if not post:return None
        if _blog_module is None:
            spec=importlib.util.spec_from_file_location('build_blog_static',ROOT/'tools'/'build_blog_static.py')
            _blog_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(_blog_module)
        published=[p for p in posts if p.get('status')!='draft']
        page=_blog_module.build_page(template_path.read_text(encoding='utf-8'),post,published)
        _blog_pages[slug]=(key,page)
        return page
    except Exception:
        logging.getLogger(__name__).exception('blog page render failed: %s',slug)
        return None


# ── Blog manager (review drafts, then publish) ───────────────────────────────
# blog-posts.json is the single source the whole site reads, so a publish or
# unpublish from the Content Manager flips the status there and commits the file
# to the repository (like the RankSpot webhook does). On a deployed service
# GITHUB_TOKEN must be configured; a local review run writes the file in place.
BLOG_REPO='lareesahu/robotist-ecommerce'
BLOG_BRANCH='main'

def _blog_file(app):
    override=app.config.get('BLOG_JSON')
    return Path(override) if override else (ROOT/'blog-posts.json')

def _blog_posts(app):
    return json.loads(_blog_file(app).read_text(encoding='utf-8'))

def _blog_status_counts(posts):
    drafts=sum(1 for p in posts if p.get('status')=='draft')
    return drafts,len(posts)-drafts

def _blog_github(app,method,path,body=None):
    token=os.getenv('GITHUB_TOKEN','')
    if not token:raise RuntimeError('GITHUB_TOKEN is not configured on this service.')
    request_=urllib.request.Request('https://api.github.com'+path,method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json',
                 'User-Agent':'Robotist-Content-Manager/1.0','Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(request_,timeout=30) as response:
            return json.loads(response.read() or b'{}')
    except urllib.error.HTTPError as error:
        detail=error.read().decode(errors='replace')[:200]
        raise RuntimeError('GitHub refused the change (%s): %s' % (error.code,detail))
    except Exception as error:
        raise RuntimeError('GitHub was unreachable: %s' % error)

def _blog_commit(app,posts,message):
    """Persist blog-posts.json: commit through GitHub on a deployed service, write in place for local review."""
    import base64
    payload=json.dumps(posts,ensure_ascii=False,indent=2).replace('\n','\r\n')+'\r\n'
    # Local review always stays local, even when a token is in the environment:
    # tests and local runs must never write to the live repository.
    if app.config.get('LOCAL_REVIEW') or app.config.get('BLOG_LOCAL_WRITE'):
        with open(_blog_file(app),'w',encoding='utf-8',newline='') as handle:
            handle.write(payload)
        return 'file'
    if os.getenv('GITHUB_TOKEN',''):
        current=_blog_github(app,'GET','/repos/%s/contents/blog-posts.json?ref=%s' % (BLOG_REPO,BLOG_BRANCH))
        _blog_github(app,'PUT','/repos/%s/contents/blog-posts.json' % BLOG_REPO,{
            'message':message,'branch':BLOG_BRANCH,
            'content':base64.b64encode(payload.encode()).decode(),
            'sha':current.get('sha')})
        return 'github'
    raise RuntimeError('Publishing needs GITHUB_TOKEN on this service.')

def _blog_drop_page(app,slug):
    """A page committed for a post that has just been returned to draft must stop being served."""
    import base64
    page=ROOT/'blog'/(slug+'.html')
    if app.config.get('LOCAL_REVIEW') or app.config.get('BLOG_LOCAL_WRITE'):
        if page.is_file():page.unlink()
        return
    if os.getenv('GITHUB_TOKEN',''):
        path='/repos/%s/contents/blog/%s.html?ref=%s' % (BLOG_REPO,slug,BLOG_BRANCH)
        try:
            current=_blog_github(app,'GET',path)
        except RuntimeError:
            return
        _blog_github(app,'DELETE','/repos/%s/contents/blog/%s.html' % (BLOG_REPO,slug),
                     {'message':"blog: remove '%s.html' after unpublishing" % slug,'branch':BLOG_BRANCH,'sha':current.get('sha')})
        return
    if page.is_file():page.unlink()

def create_app(config=None):
    config=dict(config or {})
    config.setdefault('DEMO',False)
    config.setdefault('LOCAL_REVIEW',False)
    config.setdefault('LOCAL_AUTO_LOGIN',False)
    if os.getenv('ROBOTIST_TRUST_PROXY')=='1':
        # Render's static-site rewrite forwards to this service with its own
        # host. Accept only Robotist's public origins, never a forwarded header.
        config.setdefault('PUBLIC_ORIGINS',('https://www.robotist.com.au','https://robotist.com.au'))
    app=create_grn_app(config)
    if os.getenv('ROBOTIST_TRUST_PROXY')=='1':
        from werkzeug.middleware.proxy_fix import ProxyFix
        # Render terminates TLS and supplies the forwarding headers. Do not
        # trust forwarded host names or arbitrary numbers of proxy hops.
        app.wsgi_app=ProxyFix(app.wsgi_app,x_for=1,x_proto=1,x_host=0,x_port=0,x_prefix=0)
    app.json.sort_keys=False
    directory=Path(app.config['DATA_DIR'])/'catalog'
    service=CatalogService(directory,app.config['DATABASE_URL'],app.config['SUPABASE_URL'],app.config['SUPABASE_KEY'])
    app.extensions['catalog']=service
    site=Site(ROOT,service.store)
    from .commerce import register_commerce
    register_commerce(app,site)
    from .mailforward import register_mailforward
    register_mailforward(app)


    def catalogue_rows(documents=None):
        """Every robot the website actually shows, read from the rendered catalogue.

        The homepage merges the static catalogue with whatever the CMS has
        published, so parsing it keeps the assistant's knowledge identical to
        what a visitor can see. Nothing here is hand-maintained.

        Pass a dict as ``documents`` to collect the published document already
        fetched for each slug, so callers never query the store twice.
        """
        from bs4 import BeautifulSoup
        rows=[]
        seen=set()
        try:
            page=BeautifulSoup(site.homepage(),'html.parser')
        except Exception:
            return rows
        for card in page.select('.robot-card'):
            link=card.select_one('a[href*="products/"]')
            if not link:continue
            slug=Path(urlsplit(link['href']).path).stem
            if not slug or slug in seen:continue
            seen.add(slug)
            def text_of(selector):
                node=card.select_one(selector)
                return node.get_text(' ',strip=True) if node else ''
            image=card.select_one('img')
            category=(card.get('data-category') or '').split()[0]
            document=service.store.published(slug)
            if documents is not None and document:documents[slug]=document
            best=text_of('.robot-info-best').replace('Best for:','').strip()
            if document and not best:
                fields=document['fields']
                best=plain_text(fields.get('spec:Best for',{}).get('value','')) or plain_text(fields.get('spec:Best For',{}).get('value',''))
            cover=next((a for a in document['assets'] if a.get('area')=='cover'),None) if document else None
            rows.append({'slug':slug,
                         'name':text_of('.robot-info-name') or slug,
                         'category':category or text_of('.robot-cat-tag').lower(),
                         'price':text_of('.robot-info-price') or 'price on request',
                         'best':best,
                         'description':card.get('data-desc') or '',
                         'image':('/catalog/images/'+cover['id']) if cover else (image.get('src','') if image else ''),
                         'nsfw':bool(cover.get('nsfw')) if cover else False,
                         'url':'/products/'+slug+'.html'})
        return rows

    # Labels already printed on the line, or commercial noise the visitor asked
    # about anyway, so the digest stays short enough to read on every answer.
    REDUNDANT_SPECS={'model','brand','wdp (usd)','price','category','origin','availability','warranty','deployment','support','best for'}

    def robot_specs(slug,document):
        """Technical facts for one robot: published fields first, then its page.

        The assistant used to carry a hand-written specification block that went
        stale the moment the catalogue grew, so specs are read from the same two
        sources the product page itself is built from.
        """
        facts=[]
        if document:
            for key,field in (document.get('fields') or {}).items():
                if key.startswith('spec:') and isinstance(field,dict):
                    facts.append((key[5:],plain_text(field.get('value',''))))
        if not [f for f in facts if f[1]]:
            from bs4 import BeautifulSoup
            try:
                page=BeautifulSoup((ROOT/'products'/(slug+'.html')).read_text(encoding='utf-8'),'html.parser')
            except Exception:
                return []
            for item in page.select('.spec-item, .companion-spec'):
                label=item.select_one('.spec-label, .companion-spec-label')
                value=item.select_one('.spec-value, .companion-spec-value')
                if label and value:
                    facts.append((label.get_text(' ',strip=True),value.get_text(' ',strip=True)))
        specs=[]
        for label,value in facts:
            label,value=str(label or '').strip(),str(value or '').strip()
            if not label or not value or label.lower() in REDUNDANT_SPECS:continue
            specs.append(label+': '+value)
        return specs[:8]

    def catalogue_digest():
        """One cached block of catalogue facts for every assistant answer."""
        cached=app.extensions.get('catalogue_digest')
        if cached and time.time()-cached[0]<600:return cached[1]
        documents={}
        rows=catalogue_rows(documents)
        lines=[]
        for r in rows:
            facts=[r['name'], r['category'] or 'robot', r['price'] or 'price on request']
            if r['best']:facts.append('best for '+r['best'])
            lines.append('- '+' | '.join(facts)+f" | slug {r['slug']} | {r['url']}")
        # Specifications are an enhancement: an answer must never fail, or lose
        # the catalogue, because one page could not be read.
        try:
            detailed=[]
            for r,line in zip(rows,lines):
                specs=robot_specs(r['slug'],documents.get(r['slug']))
                if not specs:
                    described=(plain_text(r.get('description') or '') or '').strip()
                    if described:specs=['about: '+described[:200]]
                detailed.append(line+(' | '+' | '.join(specs) if specs else ''))
            lines=detailed
        except Exception:
            pass
        digest=('[ROBOTIST CATALOGUE - LIVE]\n'
                'Read from the robotist.com.au catalogue when this answer was generated. '
                'These are the only robots you may recommend, and the slug is what you put in a card or cart tag. '
                'Where a robot line continues with technical specifications (platform, degrees of freedom, payload, runtime, coverage), answer specification questions from them. '
                'Never invent a robot, a price or a specification; if something is not listed, say the Robotist team will confirm.\n'
                + ('\n'.join(lines) if lines else '- the catalogue is empty right now'))
        app.extensions['catalogue_digest']=(time.time(),digest)
        return digest

    @app.get('/api/catalogue')
    def api_catalogue():
        return jsonify(robots=catalogue_rows())

    @app.post('/api/assistant')
    def assistant():
        """One server-side DeepSeek call shared by every site chatbot.

        The key stays in the service environment, so no page ships a key the
        public can read. Input is clamped, the model is fixed and the route is
        rate limited per socket IP.
        """
        key=os.getenv('DEEPSEEK_API_KEY')
        if not key:return jsonify(error='The assistant is not connected yet.'),503
        limited=app.extensions['grn_services']['limited']
        if limited('assistant',40,600):return jsonify(error='Too many messages just now. Please try again in a few minutes.'),429
        if not request.is_json:return jsonify(error='JSON required'),415
        payload=request.get_json(silent=True) or {}
        messages=payload.get('messages')
        if not isinstance(messages,list) or not messages:return jsonify(error='messages required'),400
        clean=[]
        for item in messages[-24:]:
            if not isinstance(item,dict):continue
            role,content=item.get('role'),item.get('content')
            if role not in ('system','user','assistant') or not isinstance(content,str) or not content.strip():continue
            clean.append({'role':role,'content':content[:4000]})
        if not clean:return jsonify(error='messages required'),400
        # The published catalogue is authoritative over any list inside a page.
        clean.insert(0,{'role':'system','content':catalogue_digest()})
        try:
            budget=max(64,min(int(payload.get('max_tokens') or 800),1000))
            warmth=max(0.0,min(float(payload.get('temperature') or 0.6),1.0))
        except (TypeError,ValueError):
            budget,warmth=800,0.6
        body={'model':'deepseek-flash','messages':clean,'max_tokens':budget,'temperature':warmth,
              'thinking':{'type':'disabled'}}
        upstream_request=urllib.request.Request('https://api.deepseek.com/v1/chat/completions',
            data=json.dumps(body).encode(),
            headers={'Content-Type':'application/json','Authorization':'Bearer '+key},method='POST')
        try:
            with urllib.request.urlopen(upstream_request,timeout=60) as upstream:
                return Response(upstream.read(),status=upstream.status,mimetype='application/json')
        except urllib.error.HTTPError:
            return jsonify(error='The assistant is unavailable right now.'),502
        except Exception:
            return jsonify(error='The assistant is unavailable right now.'),504
    app.config['MAX_CONTENT_LENGTH']=12*1024*1024

    def limits():
        request.max_content_length=(12 if request.path.startswith('/manage/catalog') else 5)*1024*1024
        if app.config['LOCAL_REVIEW']:
            if request.host.split(':')[0] not in ('127.0.0.1','localhost') or request.remote_addr not in ('127.0.0.1','::1'):
                abort(403)
    app.before_request_funcs[None].insert(0,limits)

    def admin(fn):
        @wraps(fn)
        def wrapped(*args,**kwargs):
            if not session.get('admin'):
                if '/api/' in request.path:return jsonify(error='Sign in to manage Robotist content'),401
                return redirect(url_for('login', next=request.path))
            return fn(*args,**kwargs)
        return wrapped

    @app.after_request
    def catalog_headers(response):
        if request.path.startswith('/manage'):
            response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-src https://www.youtube-nocookie.com https://player.vimeo.com; media-src 'self' https:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
            response.headers['X-Robots-Tag']='noindex, nofollow'
        elif response.mimetype=='text/html' and not response.direct_passthrough and not response.headers.get('Content-Security-Policy') and not request.path.startswith('/proposals/'):
            # One injection point for every rendered page, so the catalogue, cart and
            # template pages all report to the same property. Pages carrying their own
            # Content-Security-Policy are left alone rather than silently broken.
            body=response.get_data(as_text=True)
            tagged=consent(analytics(body))
            if tagged!=body:response.set_data(tagged)
        return response

    @app.route('/manage')
    @app.route('/manage/')
    @admin
    def management():
        from contextlib import closing
        with closing(connect(Path(app.config['DATA_DIR'])/'grn.sqlite3',app.config['DATABASE_URL'])) as con:
            pending=con.execute("SELECT count(*) FROM applications WHERE status='pending'").fetchone()[0]
            members=con.execute('SELECT count(*),coalesce(sum(published),0) FROM profiles').fetchone()
            recent=con.execute("SELECT id,name,role,location,created_at FROM applications WHERE status='pending' ORDER BY created_at DESC LIMIT 4").fetchall()
            new_inquiries=con.execute("SELECT count(*) FROM inquiries WHERE status='new'").fetchone()[0]
        robots=service.store.all()
        published=service.store.published()
        try:
            blog_drafts,blog_published=_blog_status_counts(_blog_posts(app))
        except Exception:
            blog_drafts,blog_published=0,0
        return render_template('management.html',pending=pending,members=members,recent=recent,
                               robot_count=len(robots),published_count=len(published),new_inquiries=new_inquiries,
                               blog_drafts=blog_drafts,blog_published=blog_published)

    @app.route('/manage/catalog/')
    @admin
    def catalog_manager():
        return render_template('robots.html')

    @app.route('/manage/catalog/static/<name>')
    @admin
    def catalog_static(name):
        if name not in ('app.js','admin.css'):abort(404)
        return send_from_directory(ROOT/'catalog/static',name)

    @app.route('/manage/catalog/api/session')
    @admin
    def catalog_session():
        return jsonify(csrf=session['csrf'],ai_ready=bool(os.getenv('DEEPSEEK_API_KEY')),local=app.config['LOCAL_REVIEW'])

    @app.route('/manage/catalog/api/products',methods=['GET','POST'])
    @app.route('/manage/catalog/api/products/<ident>',methods=['GET'])
    @app.route('/manage/catalog/api/products/<ident>/<action>',methods=['POST'])
    @admin
    def catalog_api(ident=None,action=None):
        try:
            if request.method=='GET':
                if ident:
                    d=service.store.get(ident)
                    return jsonify(product=d,errors=readiness(d),events=service.store.events(ident))
                return jsonify(service.store.all())
            if not request.is_json:return jsonify(error='JSON required'),415
            payload=request.get_json()
            if not isinstance(payload,dict):raise ValueError('Object required')
            # Build all four public views before committing a publication. A malformed
            # template must never create a half-visible product.
            if action=='publish':
                d=service.store.get(ident)
                site.product(d)
                if not site.soup('index.html').select_one('#robotGrid .robot-card'):raise ValueError('Catalog template unavailable')
                if not site.soup('compare.html').select_one('.cmp'):raise ValueError('Comparison template unavailable')
                site.sitemap()
            d=service.perform(request.path.removeprefix('/manage/catalog'),payload)
            return jsonify(d)
        except sqlite3.IntegrityError:return jsonify(error='A robot with this name already has a product page. Choose a distinct robot name.'),409
        except (ValueError,KeyError,TypeError) as error:return jsonify(error=str(error)),400

    @app.route('/manage/catalog/preview/<ident>')
    @admin
    def catalog_preview(ident):
        d=service.store.get(ident)
        page=site.product(d)
        # The base resolves original product assets; fragment links must still
        # point into this preview rather than the /products/ directory.
        from bs4 import BeautifulSoup
        preview=BeautifulSoup(page,'html.parser')
        for link in preview.select('a[href^="#"]'):
            link['href']=request.path+link['href']
        page=str(preview)
        page=page.replace('<head>','<head><base href="/products/"><meta name="robots" content="noindex,nofollow">',1)
        return public_response(page,preview=True)

    # ── Blog manager: drafts to review, then publish ────────────────────────
    @app.route('/manage/blog/')
    @admin
    def blog_manager():
        return render_template('blog.html')

    @app.route('/manage/blog/static/<name>')
    @admin
    def blog_static(name):
        if name!='blog.js':abort(404)
        return send_from_directory(ROOT/'catalog/static',name)

    @app.route('/manage/blog/api/posts')
    @admin
    def blog_api_posts():
        posts=_blog_posts(app)
        drafts,published=_blog_status_counts(posts)
        return jsonify(posts=posts,drafts=drafts,published=published,csrf=session['csrf'],
                       github=bool(os.getenv('GITHUB_TOKEN')))

    @app.route('/manage/blog/api/posts/<slug>/<action>',methods=['POST'])
    @admin
    def blog_api_action(slug,action):
        if action not in ('publish','unpublish'):abort(404)
        posts=_blog_posts(app)
        post=next((p for p in posts if p.get('slug')==slug),None)
        if not post:return jsonify(error='That post is not in blog-posts.json.'),404
        post['status']='published' if action=='publish' else 'draft'
        post['dateModified']=time.strftime('%Y-%m-%d')
        verb='publish' if action=='publish' else 'return to draft'
        try:
            _blog_commit(app,posts,"blog: %s '%s' via Content Manager" % (verb,post.get('title','')))
            if action=='unpublish':_blog_drop_page(app,slug)
        except RuntimeError as error:
            return jsonify(error='Could not save the change: %s' % error),502
        drafts,published=_blog_status_counts(posts)
        return jsonify(slug=slug,status=post['status'],drafts=drafts,published=published)

    @app.route('/manage/blog/preview/<slug>')
    @admin
    def blog_preview(slug):
        global _blog_module
        posts=_blog_posts(app)
        post=next((p for p in posts if p.get('slug')==slug),None)
        if not post:abort(404)
        related=[p for p in posts if p.get('status')!='draft' and p.get('slug')!=slug]
        if _blog_module is None:
            import importlib.util
            spec=importlib.util.spec_from_file_location('build_blog_static',ROOT/'tools'/'build_blog_static.py')
            _blog_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(_blog_module)
        page=_blog_module.build_page((ROOT/'blog-post.html').read_text(encoding='utf-8'),post,related)
        page=page.replace('<head>','<head><meta name="robots" content="noindex,nofollow">',1)
        banner=('<div style="position:fixed;bottom:0;left:0;right:0;z-index:99999;background:#102a3c;color:white;'
                'padding:12px;text-align:center">Draft preview \u00b7 '
                '<a style="color:#a8dcef" href="/manage/blog/">Return to Blog Manager</a></div>')
        return page.replace('<body>','<body>'+banner,1)

    @app.route('/manage/catalog/sources/<aid>')
    @admin
    def catalog_source(aid):
        a=next((a for d in service.store.all() for a in d['assets'] if a['id']==aid),None)
        if not a:abort(404)
        return service.uploads.response(aid,mimetype=a['mime'],as_attachment=True,download_name=a['name'])

    @app.route('/catalog/images/<aid>')
    def catalog_image(aid):
        docs=service.store.published()
        if session.get('admin'):docs+=service.store.all()
        a=next((a for d in docs for a in d['assets'] if a['id']==aid and a['mime'].startswith('image/')),None)
        if not a:abort(404)
        return service.uploads.response(aid,mimetype=a['mime'])

    def public_response(page,preview=False):
        if not preview:
            page=site.with_cart(page,session.get('csrf',''),sum(session.get('inquiry_cart',{}).values()),app.extensions['commerce']['token'](),request.path)
        elif app.config['LOCAL_REVIEW']:
            page=page.replace('</head>','<script src="/catalog/review-guard.js"></script></head>',1)
        if preview:
            page=page.replace('<body>','<body><div style="position:fixed;bottom:0;left:0;right:0;z-index:99999;background:#102a3c;color:white;padding:12px;text-align:center">Unpublished preview · <a style="color:#a8dcef" href="/manage/catalog/">Return to Catalog Manager</a></div>',1)
        return page

    @app.route('/catalog/review-guard.js')
    def review_guard():
        return Response("document.addEventListener('submit',event=>{event.preventDefault();event.stopImmediatePropagation();let note=document.createElement('p');note.textContent='Inquiry delivery will be enabled after deployment. Your form has not been sent.';event.target.append(note)},true);",mimetype='text/javascript')

    @app.get('/assets/form-workflow.js')
    def inquiry_script():
        script=(ROOT/'assets/form-workflow.js').read_text(encoding='utf-8')
        script=script.replace('https://formspree.io/f/mnjevgjq','/inquiries')
        script=script.replace('if (response.ok) {', "if (response.ok) { window.location.assign('/inquiry/received'); return;")
        script=script.replace("! Your inquiry is on its way. We\\u2019ll reply within one business day.","! Your inquiry has been received by the Robotist team for review.")
        from grn import captcha
        script=script.replace("var RECAPTCHA_SITE_KEY = '';","var RECAPTCHA_SITE_KEY = '%s';"%captcha.site_key())
        return Response(script,mimetype='text/javascript')

    @app.get('/assets/manage.js')
    def manage_script():
        # Admin pages run under script-src 'self', so console behaviour lives in a file.
        return Response((ROOT/'assets/manage.js').read_text(encoding='utf-8'),mimetype='text/javascript')

    @app.route('/')
    @app.route('/index.html')
    def site_home():return public_response(site.homepage())

    @app.route('/compare.html')
    def site_compare():return public_response(site.comparison())

    @app.route('/sitemap.xml')
    def site_sitemap():return Response(site.sitemap(),mimetype='application/xml')

    @app.route('/brand-center')
    @app.route('/brand-center.html')
    def site_brand_center():
        path=ROOT/'brand-center.html'
        if not path.is_file():abort(404)
        return public_response(path.read_text(encoding='utf-8'))

    @app.route('/products/<slug>.html')
    def site_product(slug):
        d=service.store.published(slug)
        if d:return public_response(site.product(d))
        path=ROOT/'products'/(slug+'.html')
        if not path.is_file():abort(404)
        return public_response(path.read_text(encoding='utf-8'))

    # Proposal documents are client-facing: serve them byte-for-byte, with no site chrome.
    @app.route('/proposals/<path:name>')
    def proposal_file(name):
        path=Path('proposals')/name
        if any(part.startswith('.') or part=='..' for part in path.parts) or path.suffix.lower() not in ('.html','.css','.js','.png','.jpg','.jpeg','.webp','.svg','.woff2','.pdf'):
            abort(404)
        if not (ROOT/path).is_file():abort(404)
        return send_from_directory(ROOT/'proposals',name)

    FEEDBACK_LOG=ROOT/'data'/'proposal-feedback.jsonl'
    FEEDBACK_RATE={}

    @app.route('/api/proposal-feedback',methods=['POST','GET'])
    def proposal_feedback():
        if request.method=='GET':
            token=os.environ.get('PROPOSAL_FEEDBACK_TOKEN','')
            if not token or request.args.get('token')!=token:abort(404)
            since=int(request.args.get('since','0') or 0);items=[]
            if FEEDBACK_LOG.is_file():
                for line in FEEDBACK_LOG.read_text(encoding='utf-8').splitlines():
                    try:row=json.loads(line)
                    except ValueError:continue
                    if int(row.get('id',0))>since:items.append(row)
            return jsonify({'count':len(items),'items':items[-50:],'last':max([int(r['id']) for r in items],default=since)})
        ip=(request.headers.get('X-Forwarded-For') or request.remote_addr or '').split(',')[0].strip()
        now=time.time()
        if now-FEEDBACK_RATE.get(ip,0)<5:return jsonify({'ok':False,'error':'slow down'}),429
        FEEDBACK_RATE[ip]=now
        d=request.get_json(silent=True) or request.form.to_dict() or {}
        if not d:
            try:d=json.loads(request.get_data(as_text=True) or '{}')
            except ValueError:d={}
        name=str(d.get('name',''))[:120].strip();email=str(d.get('email',''))[:160].strip()
        if not name or '@' not in email:return jsonify({'ok':False,'error':'name and email are required'}),400
        rec={'id':int(now*1000),'at':str(d.get('at') or time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))[:40],'name':name,'email':email,'stance':str(d.get('stance',''))[:60].strip(),'notes':str(d.get('notes',''))[:4000].strip(),'page':str(d.get('page',''))[:200],'ip':ip,'ua':(request.headers.get('User-Agent') or '')[:200]}
        try:
            FEEDBACK_LOG.parent.mkdir(parents=True,exist_ok=True)
            with FEEDBACK_LOG.open('a',encoding='utf-8') as fh:fh.write(json.dumps(rec,ensure_ascii=False)+'\n')
        except OSError:pass
        return jsonify({'ok':True,'id':rec['id']})

    @app.route('/<path:filename>')
    def site_file(filename):
        path=Path(filename)
        if any(part.startswith('.') or part=='..' for part in path.parts) or path.parts[0] in ('catalog','grn','work','leads','webhook','node_modules','tests'):
            abort(404)
        if not path.suffix and (ROOT/path/'index.html').is_file():
            if not request.path.endswith('/'):return redirect(request.path+'/',code=308)
            return public_response((ROOT/path/'index.html').read_text(encoding='utf-8'))
        # Robot geometry under motion-library/robots is served as-is: URDF descriptions,
        # OBJ/MTL and Collada meshes, and the STL parts of the LimX humanoids.
        if path.suffix.lower() not in ('.html','.js','.css','.png','.jpg','.jpeg','.webp','.svg','.woff2','.woff','.ttf','.ico','.json','.txt','.mp4','.webm','.gif',
                                       '.urdf','.obj','.mtl','.dae','.stl','.glb','.gltf'):abort(404)
        if path.suffix=='.html' and (ROOT/path).is_file():return public_response((ROOT/path).read_text(encoding='utf-8'))
        if path.suffix=='.html' and len(path.parts)==2 and path.parts[0]=='blog':
            page=render_blog_page(path.stem)
            if page:return public_response(page)
            # Unknown slug or a draft: hand over to the dynamic article route (which never
            # renders drafts either).
            return redirect('/blog-post.html?slug='+path.stem,code=302)
        # Model files are plain text (OBJ, MTL, URDF, Collada) and compress about six
        # times. tools/deploy_to_site.sh leaves a .gz beside each one, so send the
        # compressed copy to any browser that accepts it and let it cache the result.
        if path.suffix.lower() in ('.obj','.mtl','.urdf','.dae','.json','.js','.css','.txt','.stl'):
            gz=ROOT/(filename+'.gz')
            if gz.is_file() and 'gzip' in (request.headers.get('Accept-Encoding') or '').lower():
                response=send_from_directory(ROOT,filename+'.gz',mimetype=mimetypes.guess_type(filename)[0] or 'application/octet-stream')
                response.headers['Content-Encoding']='gzip'
                response.headers['Vary']='Accept-Encoding'
                response.headers['Cache-Control']='public, max-age=604800'
                return response
        return send_from_directory(ROOT,filename)

    # A visitor who mistypes an address gets the public page, not the console's error screen,
    # which talked about saving an action and offered a link back into the admin console.
    # Console paths keep their own template; API paths keep their JSON envelope (design 7.4).
    @app.errorhandler(404)
    def public_not_found(error):
        if request.path.startswith(('/grn/api/','/manage/api/')):
            return jsonify({'error':{'code':'not_found','message':error.description or 'Request refused.','details':{}}}),404
        if request.path.startswith(('/grn/','/manage/','/catalog/','/work/')):
            return render_template('error.html',error=error),404
        page=ROOT/'404.html'
        if page.is_file():return public_response(page.read_text(encoding='utf-8')),404
        return error

    if app.config.get('CATALOG_IMPORT_EXISTING',True):
        import_catalog(ROOT,directory,service)
    return app


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--local',action='store_true')
    parser.add_argument('--data-dir',required=True)
    parser.add_argument('--port',type=int,default=8880)
    args=parser.parse_args()
    options={'DATA_DIR':args.data_dir}
    if args.local:
        from .local_config import local_options
        options=local_options(args.data_dir)
    create_app(options).run(host='127.0.0.1',port=args.port,debug=False)
