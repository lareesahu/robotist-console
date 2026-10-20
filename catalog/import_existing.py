"""Optional read-only import from the verified static catalog into review drafts.

Existing slugs are skipped. No imported field is considered founder-reviewed.
"""
import argparse
import hashlib
import html
import io
import json
import re
import uuid
from pathlib import Path
from PIL import Image
from .storage import Store
from grn.files import Files
from .service import KEYS, CATEGORIES


def plain(s):
    return html.unescape(re.sub(r'<[^>]+>','',s)).strip()


def import_catalog(source, data_dir, service=None):
    source, data_dir = Path(source).resolve(), Path(data_dir).resolve()
    if data_dir == source or source in data_dir.parents:
        raise ValueError('Keep private data outside the static site source')
    store = service.store if service else Store(data_dir/'catalog.sqlite3')
    uploads=service.uploads if service else Files(data_dir/'uploads', 'catalog')
    existing={d['slug'] for d in store.all()}
    result=[]
    for page in sorted((source/'products').glob('*.html')):
        if page.stem in existing:
            continue
        raw=page.read_text(encoding='utf-8')
        def cls(name):
            found=re.search(r'<[^>]+class="'+re.escape(name)+r'"[^>]*>(.*?)</[^>]+>',raw,re.S)
            return plain(found.group(1)) if found else ''
        compact='companion-title' in raw
        name=cls('companion-title' if compact else 'product-name')
        if not name:
            result.append({'page':page.name,'skipped':'No standard product-name element'})
            continue
        category=cls('companion-kicker' if compact else 'product-category')
        normal=next((c for c in CATEGORIES if c.lower() in category.lower()),'')
        prefix='companion-' if compact else ''
        pairs=[(plain(k),plain(v)) for k,v in re.findall(r'<span class="'+prefix+r'spec-label">(.*?)</span>\s*<span class="'+prefix+r'spec-value">(.*?)</span>',raw,re.S)]
        values={k:'' for k in KEYS}
        values.update(name=name,category=normal,description=cls('companion-description' if compact else 'product-desc'))
        for k,v in pairs:
            if re.fullmatch(r'[\w ()/°%.-]{1,70}',k): values['spec:'+k]=v
        values['price']=next((v for k,v in pairs if 'USD' in k or 'Price' in k),'')
        highlights=re.findall(r'<span class="highlight-pill">(.*?)</span>',raw,re.S)
        values['highlights']='\n'.join(plain(x) for x in highlights)
        why=re.search(r'<div class="section-eyebrow">Why This Robot</div>\s*<h2[^>]*>(.*?)</h2>',raw,re.S)
        values['why_title']=plain(why.group(1)) if why else ''
        strengths=re.findall(r'<div class="strength-name">(.*?)</div>\s*<div class="strength-desc">(.*?)</div>',raw,re.S)
        values['strengths']='\n'.join(plain(k)+' | '+plain(v) for k,v in strengths)
        aid=uuid.uuid4().hex
        evidence='Source: '+page.as_posix()+'\nSHA256: '+hashlib.sha256(page.read_bytes()).hexdigest()+'\n\n'+'\n'.join(k+': '+v for k,v in values.items())
        (uploads/aid).write_text(evidence,encoding='utf-8')
        assets=[{'id':aid,'name':page.name+'.source.txt','mime':'text/plain','area':'documents','size':len(evidence.encode()),'alt':'','nsfw':False}]
        match=re.search(r'<div class="'+('companion-visual' if compact else 'product-hero-image')+r'">\s*<img src="([^"]+)"',raw)
        if match:
            image=(page.parent/match.group(1)).resolve()
            if source in image.parents and image.is_file():
                with Image.open(image) as im:
                    im.thumbnail((1600,1600))
                    buf=io.BytesIO(); im.convert('RGBA').save(buf,format='PNG')
                iid=uuid.uuid4().hex; (uploads/iid).write_bytes(buf.getvalue())
                assets.append({'id':iid,'name':image.name,'mime':'image/png','area':'cover','size':len(buf.getvalue()),'alt':name,'nsfw':False})
        fields={k:{'value':v,'reviewed':False,'source':'Existing site copy — unverified',
                   'evidence':{'source_id':aid,'locator':'Imported field '+k,'quote':v or 'Not supplied'}} for k,v in values.items()}
        d={'id':uuid.uuid4().hex,'slug':page.stem,'template':'compact' if compact else 'standard','version':0,'state':'draft','fields':fields,'assets':assets,'candidates':[]}
        store.save(d,0,'Imported existing static page as unreviewed draft')
        result.append({'page':page.name,'id':d['id'],'fields':len(fields),'cover':len(assets)>1})
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--source',required=True)
    p.add_argument('--data-dir',required=True)
    args=p.parse_args()
    print(json.dumps(import_catalog(args.source,args.data_dir),indent=2))
