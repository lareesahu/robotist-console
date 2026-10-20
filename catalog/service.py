import base64, binascii, io, os, re, secrets, sqlite3, uuid, html
from pathlib import Path
from PIL import Image
from .storage import Store
from grn.files import Files
from .extraction import extract
from .content import videos, plain_text
KEYS = ['name','category','description','price','highlights','why_title','strengths','featured']
CATEGORIES = ['Humanoid','Quadruped','Cleaning','Industrial','Companion']
MAX_FILE = 8 * 1024 * 1024
esc = lambda value: html.escape(str(value), quote=True)


def valid_key(key):
    return key in KEYS or bool(re.fullmatch(r'spec:[\w ()/°%.-]{1,70}', key))


def readiness(doc):
    errors = []
    for key in ['name','category','description']:
        if not doc['fields'].get(key,{}).get('value','').strip():
            errors.append(key + ' is required')
    if doc['fields'].get('category',{}).get('value') not in CATEGORIES:
        errors.append('Choose a catalog category')
    if not any(a['area']=='cover' for a in doc['assets']):
        errors.append('Upload a cover image')
    if any(a['area']!='documents' and not a['alt'].strip() for a in doc['assets']):
        errors.append('Describe each image for accessibility')
    if any(f['value'].strip() and not f.get('reviewed') for f in doc['fields'].values()):
        errors.append('Review every populated field')
    if any(c['decision']=='pending' for c in doc['candidates']):
        errors.append('Accept or dismiss every extraction candidate')
    return errors



class CatalogService:
    def __init__(self, directory, database_url=None, supabase_url=None, supabase_key=None):
        self.directory=Path(directory)
        self.uploads=Files(self.directory/"uploads", "catalog", supabase_url, supabase_key)
        self.store=Store(self.directory/"catalog.sqlite3", database_url)

    def perform(self,path,payload):
        store,uploads=self.store,self.uploads
        if path == '/api/products':
            slug = 'robot-' + uuid.uuid4().hex[:12]
            if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',slug) or len(slug)>80:
                raise ValueError('Use a short lowercase URL slug with hyphens')
            doc = {'id':uuid.uuid4().hex,'slug':slug,'auto_slug':True,'notes':'','version':0,'state':'draft','fields':{k:{'value':'','reviewed':False,'source':'Founder entry'} for k in KEYS},'assets':[],'candidates':[]}
            return store.save(doc,0,'Created draft')
        parts = path.split('/')
        if len(parts)!=5 or parts[1:3]!=['api','products']:
            raise ValueError('Unknown action')
        doc = store.get(parts[3])
        expected = payload.get('version')
        if expected != doc['version']:
            raise ValueError('This robot changed in another window. Reload before saving.')
        action = parts[4]
        if action == 'save':
            notes=payload.get('notes',doc.get('notes',''))
            if not isinstance(notes,str) or len(notes)>12000:
                raise ValueError('Initial notes must be under 12,000 characters')
            if notes!=doc.get('notes','') and notes.strip():
                aid=uuid.uuid4().hex
                raw=notes.encode('utf-8')
                (uploads/aid).write_bytes(raw)
                doc['assets'].append({'id':aid,'name':'Founder notes.txt','mime':'text/plain','area':'documents','size':len(raw),'alt':'','nsfw':False})
            doc['notes']=notes
            template=payload.get('template',doc.get('template','standard'))
            if template not in ['standard','compact']:
                raise ValueError('Unknown product page layout')
            doc['template']=template
            if 'videos' in payload:
                doc['videos']=videos(payload['videos'])
            fields = payload.get('fields',{})
            if not isinstance(fields,dict) or len(fields)>70:
                raise ValueError('Invalid fields')
            for k,f in fields.items():
                if not valid_key(k) or not isinstance(f,dict) or not isinstance(f.get('value'),str) or len(f['value'])>6000:
                    raise ValueError('Invalid field')
                old = doc['fields'].get(k,{})
                doc['fields'][k] = {'value':f['value'].strip(),'reviewed':f.get('reviewed') is True,
                    'source':old.get('source','Founder entry'), 'evidence':old.get('evidence'),
                    'founder_edited':old.get('founder_edited',False) or old.get('value')!=f['value'].strip()}
            flags = payload.get('nsfw',{})
            if not isinstance(flags,dict) or len(flags)>40 or any(not isinstance(v,bool) for v in flags.values()):
                raise ValueError('Invalid NSFW selection')
            for a in doc['assets']:
                alt = payload.get('alts',{}).get(a['id'],a['alt'])
                if not isinstance(alt,str) or len(alt)>500:
                    raise ValueError('Invalid image description')
                a['alt']=alt
                if a['id'] in flags:
                    a['nsfw']=flags[a['id']]
        elif action == 'upload':
            area = payload.get('area')
            if area not in ['cover','gallery','documents']:
                raise ValueError('Unknown upload area')
            if len(doc['assets']) >= 16:
                raise ValueError('Maximum 16 source files per robot')
            raw = base64.b64decode(payload.get('data',''),validate=True)
            if not raw or len(raw)>MAX_FILE or sum(a['size'] for a in doc['assets'])+len(raw)>32*1024*1024:
                raise ValueError('8 MB per file and 32 MB per robot maximum')
            name = str(payload.get('name','source')).replace('\\','/').split('/')[-1][:150]
            mime = payload.get('mime')
            if area in ['cover','gallery']:
                try:
                    with Image.open(io.BytesIO(raw)) as im:
                        if im.width*im.height>30_000_000 or im.format not in ['PNG','JPEG','WEBP']:
                            raise ValueError('Use PNG, JPEG or WebP under 30 megapixels')
                        im.load()
                        out=io.BytesIO()
                        im.convert('RGB' if im.mode=='RGB' else 'RGBA').save(out,format='PNG')
                        raw=out.getvalue()
                    if len(raw)>MAX_FILE:
                        raise ValueError('Decoded image exceeds 8 MB')
                    mime='image/png'
                except (OSError,Image.DecompressionBombError) as exc:
                    raise ValueError('The file is not a valid image') from exc
            elif name.lower().endswith('.pdf') and raw.startswith(b'%PDF-'):
                mime='application/pdf'
            elif name.lower().endswith(('.txt','.md','.csv')):
                raw.decode('utf-8')
                mime='text/plain'
            else:
                raise ValueError('Supporting documents: PDF or UTF-8 TXT, MD, CSV')
            aid=uuid.uuid4().hex
            (uploads/aid).write_bytes(raw)
            if area=='cover':
                for old in doc['assets']:
                    if old['area']=='cover':
                        old['area']='gallery'
            doc['assets'].append({'id':aid,'name':name,'mime':mime,'area':area,'size':len(raw),'alt':'','nsfw':False})
        elif action == 'extract':
            candidates,provider=extract(doc['assets'],uploads,payload.get('mode'))
            if len(candidates)>100:
                raise ValueError('Too many candidates; use a smaller source document')
            for c in candidates:
                if not valid_key(c['key']) or len(c['value'])>6000:
                    raise ValueError('Unrecognized extraction field')
            fresh=[]
            for c in candidates:
                c=dict(c, value=plain_text(c['value']),id=uuid.uuid4().hex,decision='pending',provider=provider)
                if any(all(old.get(k)==c.get(k) for k in ('key','value','source_id','quote')) for old in doc['candidates']+fresh):
                    continue
                fresh.append(c)
            for c in fresh:
                competing=[x for x in fresh+doc['candidates'] if x['key']==c['key'] and x['decision']=='pending']
                if payload.get('mode')=='ai' and not doc['fields'].get(c['key'],{}).get('value','').strip() and len({x['value'] for x in competing})==1:
                    doc['fields'][c['key']]={'value':c['value'],'reviewed':False,'source':provider,'evidence':{k:c[k] for k in ('source_id','locator','quote')}}
                    c['decision']='accepted'
            doc['candidates'] += fresh
        elif action == 'decide':
            candidate=next((c for c in doc['candidates'] if c['id']==payload.get('candidate')),None)
            decision=payload.get('decision')
            if not candidate or decision not in ['accepted','dismissed'] or candidate['decision']!='pending':
                raise ValueError('Invalid candidate decision')
            candidate['decision']=decision
            if decision=='accepted':
                doc['fields'][candidate['key']]={'value':candidate['value'],'reviewed':False,
                    'source':candidate['provider'],'evidence':{k:candidate[k] for k in ['source_id','locator','quote']}}
        elif action == 'remove-asset':
            aid=payload.get('asset')
            if any(c['source_id']==aid for c in doc['candidates']) or any((f.get('evidence') or {}).get('source_id')==aid for f in doc['fields'].values()):
                raise ValueError('This source supports extraction history and must be retained')
            doc['assets']=[a for a in doc['assets'] if a['id']!=aid]
        elif action in ['preview','publish']:
            errors=readiness(doc)
            if errors:
                raise ValueError('; '.join(errors))
            if action=='publish' and doc['state']!='preview':
                raise ValueError('Prepare and inspect a preview before publishing locally')
            if action=='preview' and doc.get('auto_slug'):
                doc['slug']=re.sub(r'[^a-z0-9]+','-',doc['fields']['name']['value'].lower()).strip('-')[:80] or doc['slug']
            if action=='publish':
                doc['auto_slug']=False
            doc['state']='published' if action=='publish' else 'preview'
        else:
            raise ValueError('Unknown action')
        if action not in ['preview','publish']:
            doc['state']='draft'
        return store.save(doc,expected,action,publish=action=='publish')
