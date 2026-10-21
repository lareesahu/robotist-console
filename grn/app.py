"""Same-origin GRN service. Run python -m grn.app --demo for loopback review."""
import argparse
import hmac
import io
import os
import re
import secrets
import sqlite3
import time
import uuid
from datetime import timedelta, date
from contextlib import closing
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, abort, flash, g, redirect, render_template, request, send_from_directory, session, url_for
from PIL import Image, UnidentifiedImageError
from .database import connect
from .files import Files
from .profile_fields import (LANGUAGE_MAX, LEVELS, language_rows, languages_json, languages_of, parse_languages,
                             parse_skills, public_scope, skills_field, skills_json, skills_of, with_public_fields)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.exceptions import BadRequest

ROOT = Path(__file__).resolve().parent.parent
ROLES = ('Robotics engineering', 'Software & secondary development', 'Systems integration', 'Deployment & commissioning', 'Service & technical support', 'Other technical expertise')


def create_app(config=None):
    app = Flask(__name__, static_url_path='/grn/assets')
    from catalog.site_shell import shared_elements
    app.context_processor(lambda: shared_elements()[0])

    @app.get('/grn/site-shell.css')
    def site_shell_styles():
        from flask import Response
        return Response(shared_elements()[1],mimetype='text/css')
    app.config.update(SECRET_KEY=os.getenv('GRN_SECRET_KEY'), ADMIN_PASSWORD_HASH=os.getenv('GRN_ADMIN_PASSWORD_HASH'),
                      DATABASE_URL=os.getenv('ROBOTIST_DATABASE_URL'), SUPABASE_URL=os.getenv('ROBOTIST_SUPABASE_URL'), SUPABASE_KEY=os.getenv('ROBOTIST_SUPABASE_KEY'), DATA_DIR=os.getenv('GRN_DATA_DIR'), ROBOTS_CMS_URL=os.getenv('GRN_ROBOTS_CMS_URL', ''), DEMO=False, MAX_CONTENT_LENGTH=5 * 1024 * 1024,
                      SESSION_COOKIE_NAME='robotist_grn', SESSION_COOKIE_HTTPONLY=True,
                      SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=True,
                      PERMANENT_SESSION_LIFETIME=timedelta(hours=8))
    if config:
        app.config.update(config)
    if app.config['DATABASE_URL'] and not (app.config['SUPABASE_URL'] and app.config['SUPABASE_KEY']):
        raise RuntimeError('Hosted database mode also requires durable Supabase file storage.')
    if not app.config['SECRET_KEY'] or not app.config['ADMIN_PASSWORD_HASH'] or not app.config['DATA_DIR']:
        raise RuntimeError('Set GRN_SECRET_KEY, GRN_ADMIN_PASSWORD_HASH and GRN_DATA_DIR before starting GRN.')
    data_dir = Path(app.config['DATA_DIR']).resolve()
    if data_dir == ROOT or ROOT in data_dir.parents:
        raise RuntimeError('GRN_DATA_DIR must be outside the repository/static publish tree.')
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / 'photos').mkdir(exist_ok=True)
    db_path = data_dir / 'grn.sqlite3'
    photos = Files(data_dir/'photos', 'photos', app.config['SUPABASE_URL'], app.config['SUPABASE_KEY'])
    if not app.config['DATABASE_URL']:
        with closing(sqlite3.connect(db_path)) as con:
            con.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS applications (
              id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE COLLATE NOCASE,
              location TEXT NOT NULL, organization TEXT NOT NULL, role TEXT NOT NULL, website TEXT NOT NULL,
              experience TEXT NOT NULL, motivation TEXT NOT NULL, consent INTEGER NOT NULL,
              public_consent INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
              notes TEXT NOT NULL DEFAULT '', version INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS profiles (
              id TEXT PRIMARY KEY, application_id TEXT UNIQUE REFERENCES applications(id), name TEXT NOT NULL,
              title TEXT NOT NULL DEFAULT '', location TEXT NOT NULL DEFAULT '', bio TEXT NOT NULL DEFAULT '',
              website TEXT NOT NULL DEFAULT '', photo TEXT NOT NULL DEFAULT '', consent INTEGER NOT NULL DEFAULT 0,
              published INTEGER NOT NULL DEFAULT 0, sort_order INTEGER NOT NULL DEFAULT 0,
              skills TEXT NOT NULL DEFAULT '[]', languages TEXT NOT NULL DEFAULT '[]',
              consent_scope TEXT NOT NULL DEFAULT '',
              version INTEGER NOT NULL DEFAULT 1, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS audit (
              id INTEGER PRIMARY KEY, object_id TEXT NOT NULL, action TEXT NOT NULL,
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS rate_limits (key TEXT NOT NULL, at REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS rate_key ON rate_limits(key, at);
            ''')
            columns = {row[1] for row in con.execute('PRAGMA table_info(profiles)')}
            for name in ('academic_background', 'credentials'):
                if name not in columns:
                    con.execute(f"ALTER TABLE profiles ADD COLUMN {name} TEXT NOT NULL DEFAULT ''")
            for name, definition in {'skills':"TEXT NOT NULL DEFAULT '[]'",'languages':"TEXT NOT NULL DEFAULT '[]'",'consent_scope':"TEXT NOT NULL DEFAULT ''",'consent_proposals':'INTEGER NOT NULL DEFAULT 0','consent_materials':'INTEGER NOT NULL DEFAULT 0','consent_reference':"TEXT NOT NULL DEFAULT ''",'consent_date':"TEXT NOT NULL DEFAULT ''",'agreement_status':"TEXT NOT NULL DEFAULT 'not_started'",'agreement_reference':"TEXT NOT NULL DEFAULT ''"}.items():
                if name not in columns:
                    con.execute(f'ALTER TABLE profiles ADD COLUMN {name} {definition}')
            application_columns = {row[1] for row in con.execute('PRAGMA table_info(applications)')}
            for name in ('service_regions', 'availability'):
                if name not in application_columns:
                    con.execute(f"ALTER TABLE applications ADD COLUMN {name} TEXT NOT NULL DEFAULT ''")
            con.commit()

    if app.config['DATABASE_URL']:
        # Fail closed: new code must never serve against a schema missing these columns.
        try:
            with closing(connect(db_path, app.config['DATABASE_URL'])) as check:
                check.execute('SELECT skills, languages, consent_scope FROM profiles LIMIT 1').fetchone()
        except Exception as error:
            raise RuntimeError('GRN database is missing the profile skills/languages/consent_scope columns. '
                               'Apply grn/migrations/2026-10-21-profile-skills-languages.sql before deploying.') from error

    def db():
        if 'db' not in g:
            g.db = connect(db_path, app.config['DATABASE_URL'])
        return g.db

    @app.teardown_appcontext
    def close_db(_error):
        con = g.pop('db', None)
        if con:
            con.close()

    def audit(object_id, action):
        db().execute('INSERT INTO audit(object_id, action) VALUES (?, ?)', (object_id, action))

    def limited(kind, limit, seconds):
        # Trust socket IP only; configure edge rate limiting when behind a proxy.
        key = kind + ':' + request.remote_addr
        now = time.time()
        with db() as con:
            con.execute('BEGIN IMMEDIATE')
            con.execute('DELETE FROM rate_limits WHERE at < ?', (now - 3600,))
            count = con.execute('SELECT count(*) FROM rate_limits WHERE key=? AND at>?', (key, now - seconds)).fetchone()[0]
            if count >= limit:
                return True
            con.execute('INSERT INTO rate_limits VALUES (?, ?)', (key, now))
        return False

    # The public assistant has no session to bind a token to. It is the only
    # POST allowed without a CSRF token, it still refuses foreign origins, and
    # the route rate-limits by socket IP and keeps the API key server side.
    PUBLIC_POST_PATHS = ('/api/assistant','/api/proposal-feedback')

    @app.before_request
    def protect():
        if request.method == 'POST':
            origin = request.headers.get('Origin')
            allowed_origins = {request.host_url.rstrip('/'), *app.config.get('PUBLIC_ORIGINS', ())}
            if origin and origin not in allowed_origins:
                abort(403, 'Cross-origin submissions are not accepted.')
            if request.path not in PUBLIC_POST_PATHS:
                token = (request.headers.get('X-Catalog-CSRF', '') or request.form.get('csrf', '')) if request.path.startswith(('/manage/catalog/','/manage/blog/')) else request.form.get('csrf', '')
                if not token or not hmac.compare_digest(token, session.get('csrf', '')):
                    abort(400, 'This form expired. Reload the page and try again.')
        if 'csrf' not in session:
            session['csrf'] = secrets.token_urlsafe(32)

    @app.after_request
    def headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        if request.path.startswith('/grn'):
            response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
            if request.path.startswith('/grn/admin') and session.get('admin'):
                response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'none'; style-src 'self'; img-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
            if request.endpoint == 'landing':
                response.headers['Content-Security-Policy'] = "default-src 'self'; script-src https://assets.calendly.com 'self'; style-src 'self' 'unsafe-inline' https://assets.calendly.com; frame-src https://calendly.com https://*.calendly.com; connect-src https://calendly.com https://*.calendly.com; img-src 'self' data:; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
        return response

    @app.context_processor
    def context():
        return dict(csrf=session.get('csrf'), demo=app.config['DEMO'], roles=ROLES,
                    local_review=app.config.get('LOCAL_REVIEW',False),
                    admin_page=request.path.startswith('/manage') or request.path.startswith('/grn/admin'),
                    robots_url=url_for('catalog_manager') if 'catalog_manager' in app.view_functions else app.config['ROBOTS_CMS_URL'],
                    blog_url=url_for('blog_manager') if 'blog_manager' in app.view_functions else '',
                    cms_url=url_for('management') if 'management' in app.view_functions else url_for('content_home'))

    def admin_required(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not session.get('admin'):
                return redirect(url_for('login', next=request.path))
            return fn(*args, **kwargs)
        return wrapped

    def field(name, maximum=200, required=False):
        value = request.form.get(name, '').strip()
        if len(value) > maximum or (required and not value):
            raise ValueError(f'{name.replace("_", " ").capitalize()} is required and must be at most {maximum} characters.' if required else f'{name.capitalize()} must be at most {maximum} characters.')
        return value

    def website():
        value = field('website', 500)
        if value:
            parsed = urlsplit(value)
            if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError('Website must be a complete https:// address without credentials.')
        return value

    def record(table, ident):
        row = db().execute(f'SELECT * FROM {table} WHERE id=?', (ident,)).fetchone()
        if row is None:
            abort(404)
        return row

    def public_profiles():
        return [with_public_fields(row) for row in db().execute("SELECT p.* FROM profiles p LEFT JOIN applications a ON a.id=p.application_id WHERE p.published=1 AND p.consent=1 AND (p.application_id IS NULL OR a.status='approved') ORDER BY p.sort_order, p.name").fetchall()]

    @app.route('/grn/', methods=['GET','POST'])
    def landing():
        if request.method=='POST':return apply()
        return render_template('landing.html', profiles=public_profiles(),errors=[],values={},submitted=request.args.get('submitted')=='1' and session.get('receipt'))

    @app.route('/grn/apply', methods=['GET', 'POST'])
    def apply():
        if request.method=='GET':return redirect(url_for('landing')+'#application')
        errors = []
        if request.method == 'POST':
            if limited('apply', 12, 3600):
                abort(429, 'Too many submissions. Please try again in an hour.')
            try:
                if request.form.get('company_url'):
                    raise ValueError('Unable to accept this submission.')
                values = {k: field(k, n, True) for k, n in [('name', 120), ('email', 254), ('location', 160), ('role', 80), ('experience', 3000), ('motivation', 2000)]}
                if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', values['email']):
                    raise ValueError('Enter a valid email address.')
                if values['role'] not in ROLES:
                    raise ValueError('Choose an area of contribution.')
                if request.form.get('consent') != 'yes':
                    raise ValueError('Please agree to application review and follow-up.')
                values.update(id=str(uuid.uuid4()), organization=field('organization', 160), website=website(), consent=1, service_regions=field('service_regions', 500), availability=field('availability', 500),
                              public_consent=int(request.form.get('public_consent') == 'yes'))
                inserted = False
                try:
                    with db() as con:
                        con.execute('INSERT INTO applications(id,name,email,location,organization,role,website,experience,motivation,consent,public_consent,service_regions,availability) VALUES (:id,:name,:email,:location,:organization,:role,:website,:experience,:motivation,:consent,:public_consent,:service_regions,:availability)', values)
                        audit(values['id'], 'Application submitted')
                        inserted = True
                except sqlite3.IntegrityError:
                    # Same receipt for repeat requests prevents email enumeration.
                    pass
                if inserted:
                    try:
                        from .notify import notify_application
                        notify_application(values)
                    except Exception as error:
                        print('[notify] application %s: %s' % (values['id'], error))
                session['receipt'] = True
                return redirect(url_for('landing',submitted='1')+'#application', code=303)
            except ValueError as error:
                errors.append(str(error))
        return render_template('landing.html', profiles=public_profiles(),errors=errors,values=request.form,submitted=False),400

    @app.route('/grn/received')
    def received():
        if not session.get('receipt'):
            return redirect(url_for('apply'))
        return render_template('received.html')

    @app.route('/grn/admin/login', methods=['GET', 'POST'])
    @app.route('/manage/login', methods=['GET', 'POST'])
    def login():
        if app.config.get('LOCAL_SETUP_PENDING'):
            return redirect(url_for('setup'))
        error = None
        if request.method == 'POST':
            if limited('login', 5, 900):
                abort(429, 'Too many sign-in attempts. Try again in 15 minutes.')
            if check_password_hash(app.config['ADMIN_PASSWORD_HASH'], request.form.get('password', '')):
                session.clear()
                session.update(admin=True, csrf=secrets.token_urlsafe(32))
                session.permanent = True
                target=request.args.get('next','')
                if not (target.startswith('/manage/') or target.startswith('/grn/admin')) or urlsplit(target).netloc or '\\' in target:
                    target=url_for('management') if 'management' in app.view_functions else url_for('content_home')
                return redirect(target, code=303)
            error = 'Incorrect password.'
        return render_template('login.html', error=error), 401 if error else 200

    @app.route('/manage/setup', methods=['GET','POST'])
    def setup():
        if not app.config.get('LOCAL_REVIEW') or not app.config.get('LOCAL_SETUP_PENDING'):
            return redirect(url_for('login'))
        if request.remote_addr not in ('127.0.0.1','::1') or request.host.split(':')[0] not in ('127.0.0.1','localhost'):
            abort(403)
        error=None
        if request.method=='POST':
            password=request.form.get('password','')
            if len(password)<12 or len(password)>128:
                error='Use a password between 12 and 128 characters.'
            elif password!=request.form.get('confirm',''):
                error='The passwords do not match.'
            else:
                from catalog.local_config import save_password
                save_password(app,generate_password_hash(password))
                session.clear()
                session.update(admin=True,csrf=secrets.token_urlsafe(32))
                session.permanent=True
                return redirect(url_for('management'),code=303)
        return render_template('setup.html',error=error),400 if error else 200

    @app.post('/grn/admin/logout')
    def logout():
        session.clear()
        return redirect(url_for('landing'), code=303)

    @app.route('/grn/admin')
    @admin_required
    def dashboard():
        status = request.args.get('status', 'pending')
        if status not in ('pending', 'approved', 'declined', 'all'):
            abort(400)
        q = request.args.get('q', '')[:160]
        rows = db().execute('SELECT * FROM applications WHERE (?=\'all\' OR status=?) AND (name LIKE ? OR email LIKE ?) ORDER BY created_at DESC', (status, status, '%' + q + '%', '%' + q + '%')).fetchall()
        counts = {r['status']: r['n'] for r in db().execute('SELECT status,count(*) n FROM applications GROUP BY status')}
        return render_template('dashboard.html', applications=rows, counts=counts, status=status, q=q)

    @app.route('/grn/admin/content')
    @admin_required
    def content_home():
        return render_template('content.html', robots_url=url_for('catalog_manager') if 'catalog_manager' in app.view_functions else app.config['ROBOTS_CMS_URL'])

    @app.route('/grn/admin/applications/<ident>', methods=['GET', 'POST'])
    @admin_required
    def review(ident):
        row = record('applications', ident)
        if request.method == 'POST':
            target = request.form.get('status')
            if target not in ('pending', 'approved', 'declined'):
                abort(400)
            notes = field('notes', 4000)
            with db() as con:
                result = con.execute('UPDATE applications SET status=?,notes=?,version=version+1,updated_at=CURRENT_TIMESTAMP WHERE id=? AND version=?', (target, notes, ident, request.form.get('version')))
                if result.rowcount != 1:
                    abort(409, 'Another reviewer changed this application. Reload before saving.')
                if target != 'approved':
                    con.execute('UPDATE profiles SET published=0,version=version+1 WHERE application_id=?', (ident,))
                else:
                    con.execute('INSERT OR IGNORE INTO profiles(id,application_id,name,location,consent) VALUES (?,?,?,?,?)', (str(uuid.uuid4()), ident, row['name'], row['location'], 0))
                audit(ident, f'Review saved: {target}')
            flash('Review saved. No email was sent. Public profiles are managed separately.')
            return redirect(url_for('review', ident=ident), code=303)
        profile = db().execute('SELECT id FROM profiles WHERE application_id=?', (ident,)).fetchone()
        history = db().execute('SELECT * FROM audit WHERE object_id=? ORDER BY id DESC', (ident,)).fetchall()
        return render_template('review.html', application=row, profile=profile, history=history)

    @app.route('/grn/admin/team', methods=['GET', 'POST'])
    @admin_required
    def team():
        if request.method == 'POST':
            name = field('name', 120, True)
            ident = str(uuid.uuid4())
            with db() as con:
                con.execute('INSERT INTO profiles(id,name) VALUES (?,?)', (ident, name))
                audit(ident, 'Team profile draft created by administrator')
            return redirect(url_for('profile', ident=ident), code=303)
        return render_template('team.html', profiles=[with_public_fields(row) for row in db().execute('SELECT * FROM profiles ORDER BY sort_order,name').fetchall()])

    @app.route('/grn/admin/team/<ident>', methods=['GET', 'POST'])
    @admin_required
    def profile(ident):
        row = record('profiles', ident)
        application = record('applications', row['application_id']) if row['application_id'] else None
        errors = []
        skill_text = skills_field(row)
        lang_rows = language_rows(row)
        if request.method == 'POST':
            try:
                values = dict(name=field('name', 120, True), title=field('title', 120, True), location=field('location', 160, True),
                              bio=field('bio', 1200, True), academic_background=field('academic_background', 2000), credentials=field('credentials', 2000), website=website(), photo=row['photo'],
                              consent=int(request.form.get('consent') == 'yes'), published=int(request.form.get('published') == 'yes'))
                values['sort_order'] = int(request.form.get('sort_order', '0'))
                values.update(consent_proposals=int(request.form.get('consent_proposals')=='yes'),consent_materials=int(request.form.get('consent_materials')=='yes'),consent_reference=field('consent_reference',1000),consent_date=field('consent_date',10),agreement_status=field('agreement_status',30) or 'not_started',agreement_reference=field('agreement_reference',1000))
                if values['agreement_status'] not in ('not_started','sent','signed','ended'):
                    raise ValueError('Choose a valid agreement status.')
                if values['agreement_status']=='signed' and not values['agreement_reference']:
                    raise ValueError('Record the signed agreement reference before marking it signed.')
                if values['consent'] or values['consent_proposals'] or values['consent_materials']:
                    if not values['consent_reference'] or not values['consent_date']:
                        raise ValueError('Record the approval date and evidence reference for the approved profile and channels.')
                    try:
                        approved_on=date.fromisoformat(values['consent_date'])
                    except ValueError:
                        raise ValueError('Enter a valid approval date.')
                    if approved_on>date.today():
                        raise ValueError('Approval date cannot be in the future.')
                if not -999 <= values['sort_order'] <= 999:
                    raise ValueError('Display order must be between -999 and 999.')
                skills = parse_skills(request.form.get('skills'))
                languages = parse_languages([request.form.get(f'language_name_{index}', '') for index in range(1, LANGUAGE_MAX + 1)],
                                            [request.form.get(f'language_level_{index}', '') for index in range(1, LANGUAGE_MAX + 1)])
                if values['published'] and (not values['consent'] or (application and application['status'] != 'approved')):
                    raise ValueError('Publication requires approval and permission to show this profile publicly.')
                upload = request.files.get('photo')
                photo_bytes = None
                if upload and upload.filename:
                    try:
                        with Image.open(upload.stream) as img:
                            if img.format not in ('JPEG', 'PNG', 'WEBP') or img.width * img.height > 20_000_000:
                                raise ValueError('Use a JPEG, PNG or WebP photo up to 20 megapixels.')
                            img.load()
                            img = img.convert('RGB')
                            img.thumbnail((1200, 1200))
                            output = io.BytesIO()
                            img.save(output, format='JPEG', quality=88)
                            photo_bytes = output.getvalue()
                    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
                        raise ValueError('This file is not a supported image.')
                    values['photo'] = uuid.uuid4().hex + '.jpg'
                values.update(id=ident, version=request.form.get('version'), skills=skills_json(skills),
                              languages=languages_json(languages))
                values['consent_scope'] = public_scope(values, skills, languages)
                with db() as con:
                    con.execute('BEGIN IMMEDIATE')
                    stored = con.execute('SELECT published,consent_scope,consent_reference,skills,languages FROM profiles WHERE id=?', (ident,)).fetchone()
                    if stored is None:
                        abort(404)
                    if values['published'] and values['consent_scope'] != (stored['consent_scope'] or '') \
                            and values['consent_reference'] == (stored['consent_reference'] or ''):
                        raise ValueError('This changes what is shown publicly. Record the new approval evidence reference for this change, or unpublish the profile.')
                    if application and values['published']:
                        current = con.execute('SELECT status,public_consent FROM applications WHERE id=?', (row['application_id'],)).fetchone()
                        if current['status'] != 'approved':
                            abort(409, 'Application approval changed. Reload before publishing.')
                    result = con.execute('UPDATE profiles SET name=:name,title=:title,location=:location,bio=:bio,academic_background=:academic_background,credentials=:credentials,website=:website,photo=:photo,consent=:consent,published=:published,sort_order=:sort_order,skills=:skills,languages=:languages,version=version+1,updated_at=CURRENT_TIMESTAMP WHERE id=:id AND version=:version', values)
                    if result.rowcount != 1:
                        abort(409, 'Another reviewer changed this profile. Reload before saving.')
                    con.execute('UPDATE profiles SET consent_proposals=:consent_proposals,consent_materials=:consent_materials,consent_reference=:consent_reference,consent_date=:consent_date,agreement_status=:agreement_status,agreement_reference=:agreement_reference WHERE id=:id',values)
                    if values['published']:
                        con.execute('UPDATE profiles SET consent_scope=? WHERE id=?', (values['consent_scope'], ident))
                    if (stored['skills'] or '') != values['skills'] or (stored['languages'] or '') != values['languages']:
                        before = ', '.join(skills_of(stored)) or 'none'
                        after = ', '.join(skills) or 'none'
                        before_lang = '; '.join(f"{item['name']} ({item['level']})" for item in languages_of(stored)) or 'none'
                        after_lang = '; '.join(f"{item['name']} ({item['level']})" for item in languages) or 'none'
                        audit(ident, ('Skills: ' + before + ' -> ' + after + '; languages: ' + before_lang + ' -> ' + after_lang)[:600])
                    if photo_bytes:
                        (photos / values['photo']).write_bytes(photo_bytes)
                    audit(ident, 'Public profile saved' if values['published'] else 'Private draft saved / unpublished')
                    audit(ident, 'Profile permissions: website='+str(bool(values['consent']))+', proposals='+str(bool(values['consent_proposals']))+', capability materials='+str(bool(values['consent_materials']))+'; approval date='+values['consent_date']+'; evidence='+values['consent_reference']+'; agreement='+values['agreement_status']+'; agreement reference='+values['agreement_reference'])
                flash('Profile saved.' if not values['published'] else 'Profile is now visible on the local GRN page.' if app.config['DEMO'] else 'Profile published.')
                return redirect(url_for('profile', ident=ident), code=303)
            except ValueError as error:
                errors.append(str(error))
                skill_text = request.form.get('skills', '')
                lang_rows = [(request.form.get(f'language_name_{index}', ''), request.form.get(f'language_level_{index}', ''))
                             for index in range(1, LANGUAGE_MAX + 1)]
        values = dict(row)
        if errors:
            values.update({k: request.form.get(k, '') for k in ('name', 'title', 'location', 'bio', 'academic_background', 'credentials', 'website', 'sort_order')})
            values.update(consent=request.form.get('consent') == 'yes', published=request.form.get('published') == 'yes')
            values.update({k:request.form.get(k,'') for k in ('consent_reference','consent_date','agreement_status','agreement_reference')})
            values.update({k:request.form.get(k)=='yes' for k in ('consent_proposals','consent_materials')})
        history=db().execute('SELECT * FROM audit WHERE object_id=? ORDER BY id DESC',(ident,)).fetchall()
        return render_template('profile.html', profile=values, application=application, errors=errors, history=history,
                               skill_text=skill_text, lang_rows=lang_rows, levels=LEVELS), 400 if errors else 200

    @app.route('/grn/photos/<filename>')
    def photo(filename):
        row = db().execute("SELECT p.* FROM profiles p LEFT JOIN applications a ON a.id=p.application_id WHERE photo=? AND (p.application_id IS NULL OR a.status='approved')", (filename,)).fetchone()
        if not row or (not session.get('admin') and not (row['published'] and row['consent'])):
            abort(404)
        return photos.response(filename, mimetype='image/jpeg')

    @app.route('/grn/health')
    def health():
        db().execute('SELECT 1').fetchone()
        return {'service': 'robotist-grn', 'status': 'ok'}

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(409)
    @app.errorhandler(413)
    @app.errorhandler(429)
    def error_page(error):
        return render_template('error.html', error=error), error.code

    @app.errorhandler(ValueError)
    def validation_error(error):
        return error_page(BadRequest(str(error)))

    if app.config['DEMO']:
        @app.route('/')
        def home():
            return send_from_directory(ROOT, 'index.html')

        @app.route('/<path:filename>')
        def site_preview(filename):
            # Tracked public assets only; never serve repository internals or databases.
            path = Path(filename)
            if '..' in path.parts or any(p.startswith('.') for p in path.parts) or path.suffix.lower() not in ('.html', '.css', '.js', '.png', '.jpg', '.jpeg', '.webp', '.svg', '.woff2', '.ico') or path.parts[0] in ('grn', 'node_modules', 'work', 'leads', 'webhook', 'tests'):
                abort(404)
            return send_from_directory(ROOT, filename)
    app.extensions['grn_services'] = dict(db=db, admin_required=admin_required, limited=limited, audit=audit)
    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--port', type=int, default=5187)
    args = parser.parse_args()
    options = None
    if args.demo:
        options = dict(DEMO=True, SECRET_KEY=secrets.token_hex(32), ADMIN_PASSWORD_HASH=generate_password_hash('robotist-local-review'),
                       DATA_DIR=os.getenv('GRN_DATA_DIR', str(ROOT.parent / 'grn-review-data')), SESSION_COOKIE_SECURE=False)
    create_app(options).run(host='127.0.0.1', port=args.port, debug=False)
