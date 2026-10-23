"""Inquiry cart and private request inbox; no checkout, charges or auto-mail."""
import json
import re
import secrets
from urllib.parse import urljoin
from flask import request, session, redirect, url_for, render_template, abort, jsonify, flash


def register_commerce(app, site):
    services=app.extensions['grn_services']
    db,admin,limited,audit=(services[k] for k in ('db','admin_required','limited','audit'))
    if not app.config['DATABASE_URL']:
        with app.app_context():
            db().executescript('''CREATE TABLE IF NOT EXISTS inquiries (
              id TEXT PRIMARY KEY, submission_token TEXT NOT NULL UNIQUE,
              name TEXT NOT NULL,email TEXT NOT NULL,company TEXT NOT NULL DEFAULT '',
              location TEXT NOT NULL DEFAULT '',phone TEXT NOT NULL DEFAULT '',
              message TEXT NOT NULL,interest TEXT NOT NULL DEFAULT '',
              items TEXT NOT NULL,source TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'new',
              notes TEXT NOT NULL DEFAULT '',version INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE INDEX IF NOT EXISTS inquiry_status ON inquiries(status,created_at);''')
            if 'details' not in {row[1] for row in db().execute('PRAGMA table_info(inquiries)')}:
                db().execute("ALTER TABLE inquiries ADD COLUMN details TEXT NOT NULL DEFAULT '{}'")
            db().commit()

    def product(slug):
        if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',slug) or len(slug)>80:return None
        document=site.store.published(slug)
        if document:
            value=lambda key:document['fields'].get(key,{}).get('value','')
            cover=next((a for a in document['assets'] if a['area']=='cover'),None)
            return dict(slug=slug,name=value('name'),price=value('price') or 'Price on request',image='/catalog/images/'+cover['id'] if cover else '',url='/products/'+slug+'.html',nsfw=bool(cover and cover.get('nsfw')))
        path=site.root/'products'/(slug+'.html')
        if not path.is_file():return None
        page=site.soup(path.relative_to(site.root))
        name=page.select_one('.product-name,.companion-title')
        if not name:return None
        photo=page.select_one('.product-hero-image img,.companion-visual img')
        price=page.select_one('.companion-price-value')
        return dict(slug=slug,name=name.get_text(' ',strip=True),price=price.get_text(' ',strip=True) if price else 'Quote on request',image=urljoin('/products/',photo.get('src','')) if photo else '',url='/products/'+slug+'.html',nsfw=False)

    def cart_items():
        result=[]
        for slug,quantity in session.get('inquiry_cart',{}).items():
            item=product(slug)
            if item:result.append(dict(item,quantity=quantity))
        return result

    def token():
        if 'inquiry_token' not in session or session.pop('inquiry_token_consumed',False):session['inquiry_token']=secrets.token_urlsafe(24)
        return session['inquiry_token']

    def field(name,maximum,required=False):
        value=request.form.get(name,'').strip()
        if len(value)>maximum or (required and not value):raise ValueError(f'Please enter {name.replace("_"," ")} (up to {maximum} characters).')
        return value

    @app.context_processor
    def cart_context():return dict(cart_count=sum(session.get('inquiry_cart',{}).values()))

    @app.get('/cart')
    def cart():return render_template('cart.html',items=cart_items(),values={},errors=[],submission_token=token())

    @app.post('/cart/add')
    def cart_add():
        slug=field('slug',80,True)
        if not product(slug):abort(404)
        items=dict(session.get('inquiry_cart',{}))
        if slug not in items and len(items)>=20:abort(400,'A request can include up to 20 different robots.')
        items[slug]=min(items.get(slug,0)+1,99)
        session['inquiry_cart']=items
        return redirect(url_for('cart'),code=303)

    @app.post('/cart/update')
    def cart_update():
        items=dict(session.get('inquiry_cart',{}))
        if request.form.get('remove'):
            items.pop(request.form['remove'],None)
        else:
            for slug in items:
                try:quantity=int(request.form.get('quantity_'+slug,items[slug]))
                except ValueError:abort(400,'Quantities must be whole numbers between 1 and 99.')
                if not 1<=quantity<=99:abort(400,'Quantities must be whole numbers between 1 and 99.')
                items[slug]=quantity
        session['inquiry_cart']=items
        return redirect(url_for('cart'),code=303)

    def persist(items,source):
        if limited('inquiry',12,3600):abort(429,'Too many inquiries. Please try again later.')
        if request.form.get('_gotcha') or request.form.get('company_url'):raise ValueError('Unable to accept this inquiry.')
        # Human check: skipped unless GRN_RECAPTCHA_SITE_KEY/SECRET are configured.
        from grn.captcha import verify as verify_captcha
        human,reason=verify_captcha(request.form.get('g-recaptcha-response',''),request.remote_addr or '')
        if not human:
            print('[captcha] inquiry refused: %s'%reason)
            raise ValueError('The captcha check did not pass. Please try again.')
        name,email=field('customer_name' if source=='requirements' else 'name',120,True),field('email',254,True)
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):raise ValueError('Enter a valid email address.')
        message='Deployment requirements submitted below.' if source=='requirements' else field('message',5000,True)
        details={}
        if source=='requirements':
            allowed=site.requirement_fields()
            for key in allowed:
                values=[value.strip() for value in request.form.getlist(key) if value.strip()]
                if any(len(value)>5000 for value in values):raise ValueError('A requirements answer is too long.')
                if values:details[key]=values
            if len(json.dumps(details))>50000:raise ValueError('The requirements submission is too long.')
            field('country',200,True)
        submission=request.form.get('submission_token','')
        if not submission or submission!=session.get('inquiry_token'):raise ValueError('This inquiry form expired. Reload the page before submitting.')
        prior=db().execute('SELECT id FROM inquiries WHERE submission_token=?',(submission,)).fetchone()
        if prior:return prior['id']
        company,location,phone,interest=field('company',160),field('location',200),field('phone',80),field('interest',200)
        ident='RQ-'+secrets.token_hex(5).upper()
        with db() as con:
            con.execute('BEGIN IMMEDIATE')
            prior=con.execute('SELECT id FROM inquiries WHERE submission_token=?',(submission,)).fetchone()
            if prior:return prior['id']
            con.execute('INSERT INTO inquiries(id,submission_token,name,email,company,location,phone,message,interest,items,source) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                        (ident,submission,name,email,company,location,phone,message,interest,json.dumps(items),source))
            con.execute('UPDATE inquiries SET details=? WHERE id=?',(json.dumps(details),ident))
            audit(ident,'Inquiry received: '+source)
        try:
            from grn.notify import notify_inquiry
            notify_inquiry(dict(id=ident,name=name,email=email,company=company,location=location,phone=phone,interest=interest,message=message,source=source,items=items,details=details))
        except Exception as error:
            print('[notify] inquiry %s: %s' % (ident,error))
        return ident

    @app.post('/cart/submit')
    def cart_submit():
        items=cart_items()
        try:
            prior=db().execute('SELECT id FROM inquiries WHERE submission_token=?',(request.form.get('submission_token',''),)).fetchone()
            if prior and request.form.get('submission_token')==session.get('inquiry_token'):
                ident=prior['id']
            else:
                if not items:raise ValueError('Add at least one robot to your inquiry cart.')
                ident=persist(items,'cart')
            session['inquiry_receipt']=ident
            session['inquiry_cart']={}
            session['inquiry_token_consumed']=True
            # Retain the token until the next page render so a repeated POST is idempotent.
            return redirect(url_for('inquiry_received'),code=303)
        except ValueError as error:
            return render_template('cart.html',items=items,values=request.form,errors=[str(error)],submission_token=token()),400

    @app.get('/inquiry/received')
    def inquiry_received():
        ident=session.get('inquiry_receipt')
        if not ident:return redirect(url_for('cart'))
        return render_template('inquiry-received.html',reference=ident)

    @app.get('/inquiry/token')
    def inquiry_token():
        """Issue the session token a form needs before it posts to /inquiries.

        Static pages cannot carry a token injected at render time, so the form
        asks for one first. The cookie from this response is what makes the
        later POST check out.
        """
        return jsonify(ok=True, token=token())

    @app.post('/inquiries')
    def contact_submit():
        try:
            ident=persist([],'requirements' if request.form.get('form_kind')=='requirements' else 'contact')
            session['inquiry_receipt']=ident
            session['inquiry_token_consumed']=True
            if request.accept_mimetypes.best=='application/json':return jsonify(ok=True,reference=ident),201
            return redirect(url_for('inquiry_received'),code=303)
        except ValueError as error:
            if request.accept_mimetypes.best=='application/json':return jsonify(error=str(error)),400
            abort(400,str(error))

    @app.get('/manage/inquiries')
    @admin
    def inquiries():
        status=request.args.get('status','new')
        if status not in ('all','new','reviewing','quoted','closed'):abort(400)
        search=request.args.get('q','')[:160]
        rows=db().execute("SELECT * FROM inquiries WHERE (?='all' OR status=?) AND (name LIKE ? OR email LIKE ? OR id LIKE ?) ORDER BY created_at DESC",(status,status,*(['%'+search+'%']*3))).fetchall()
        counts={r['status']:r['n'] for r in db().execute('SELECT status,count(*) n FROM inquiries GROUP BY status')}
        from grn.screening import screen
        screening={r['id']:screen(dict(r)) for r in rows}
        return render_template('inquiries.html',inquiries=rows,status=status,q=search,counts=counts,screening=screening)

    @app.route('/manage/inquiries/<ident>',methods=['GET','POST'])
    @admin
    def inquiry_detail(ident):
        row=db().execute('SELECT * FROM inquiries WHERE id=?',(ident,)).fetchone()
        if not row:abort(404)
        if request.method=='POST':
            status=field('status',20,True)
            if status not in ('new','reviewing','quoted','closed'):abort(400)
            with db() as con:
                updated=con.execute('UPDATE inquiries SET status=?,notes=?,version=version+1,updated_at=CURRENT_TIMESTAMP WHERE id=? AND version=?',(status,field('notes',6000),ident,request.form.get('version')))
                if updated.rowcount!=1:abort(409,'This inquiry changed in another window. Reload before saving.')
                audit(ident,'Inquiry marked '+status)
            flash('Inquiry updated. No message was sent to the customer.')
            return redirect(url_for('inquiry_detail',ident=ident),code=303)
        history=db().execute('SELECT * FROM audit WHERE object_id=? ORDER BY id DESC',(ident,)).fetchall()
        labels=site.requirement_fields() if row['source']=='requirements' else {}
        details={labels.get(key,key):value for key,value in json.loads(row['details']).items()}
        from grn.screening import screen
        screening=screen(dict(row))
        return render_template('inquiry-detail.html',inquiry=row,items=json.loads(row['items']),details=details,history=history,screening=screening)

    def console_post():
        """Guard for console writes that destroy or change records."""
        if request.form.get('csrf')!=session.get('csrf'):abort(400,'Reload the console and try again.')

    def status_back(default='new'):
        wanted=request.form.get('status','')
        return wanted if wanted in ('all','new','reviewing','quoted','closed') else default

    def delete_inquiries(identifiers):
        """Delete the named inquiries and their history, leaving one audit line per reference.

        Spam is most of what arrives, so the console must be able to clear it. The
        deletion itself is audited — who removed which reference, and when — while
        the customer's own answers stop existing.
        """
        removed=[]
        with db() as con:
            con.execute('BEGIN IMMEDIATE')
            for ident in identifiers:
                row=con.execute('SELECT id,name,email FROM inquiries WHERE id=?',(ident,)).fetchone()
                if not row:continue
                con.execute('DELETE FROM inquiries WHERE id=?',(ident,))
                con.execute('DELETE FROM audit WHERE object_id=?',(ident,))
                audit(ident,'Inquiry deleted: %s <%s>'%(row['name'],row['email']))
                removed.append(ident)
        return removed

    @app.post('/manage/inquiries/delete')
    @admin
    def inquiries_delete_selected():
        console_post()
        identifiers=[value.strip() for value in request.form.getlist('id') if value.strip()][:500]
        if not identifiers:
            flash('Nothing was selected, so nothing was deleted.')
            return redirect(url_for('inquiries',status=status_back('all')),code=303)
        removed=delete_inquiries(identifiers)
        flash('%d %s deleted.'%(len(removed),'inquiry' if len(removed)==1 else 'inquiries'))
        return redirect(url_for('inquiries',status=status_back('all')),code=303)

    @app.post('/manage/inquiries/<ident>/delete')
    @admin
    def inquiry_delete(ident):
        console_post()
        removed=delete_inquiries([ident])
        flash('%s deleted.'%ident if removed else '%s was already gone.'%ident)
        return redirect(url_for('inquiries',status=status_back('all')),code=303)

    app.extensions['commerce']=dict(product=product,token=token)
