"""Render published catalog snapshots into Robotist's existing public pages."""
import json,re
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urlsplit
import copy
from .content import plain_text, videos


# Google Analytics 4 for robotist.com.au. The property and its web stream exist, but
# the tag was missing from the rebuilt site, so it is injected into every HTML
# response here instead of being pasted into 70 files.
ANALYTICS_ID='G-WCTLN70HXT'

# One answer per visitor, stored in this cookie and read before analytics may write
# anything of its own. Everything except the essential session cookie waits for it.
CONSENT_COOKIE='robotist_consent'
CONSENT_SECONDS=6*30*24*60*60

ANALYTICS_TAG=r"""<script async src="https://www.googletagmanager.com/gtag/js?id=__GA_ID__"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}
(function(){
  var COOKIE='__CONSENT_COOKIE__',MAX_AGE=__CONSENT_SECONDS__;
  function read(){
    var jar=document.cookie?document.cookie.split('; '):[];
    for(var i=0;i<jar.length;i++){var part=jar[i].split('=');if(part[0]===COOKIE)return decodeURIComponent(part.slice(1).join('='));}
    return '';
  }
  function write(v){
    var d=new Date();d.setTime(d.getTime()+MAX_AGE*1000);
    document.cookie=COOKIE+'='+v+';expires='+d.toUTCString()+';path=/;SameSite=Lax'+(location.protocol==='https:'?';Secure':'');
  }
  // Analytics storage stays denied until the visitor accepts, so an unanswered or
  // rejected visit leaves no analytics cookie behind. Accepting flips it in place.
  gtag('consent','default',{ad_storage:'denied',ad_user_data:'denied',ad_personalization:'denied',
                            analytics_storage:(read()==='granted'?'granted':'denied'),wait_for_update:500});
  window.robotistConsent={
    cookie:COOKIE,
    choice:read,
    set:function(value){
      var granted=value==='granted'?'granted':'denied';
      write(granted);
      gtag('consent','update',{analytics_storage:granted});
      try{window.dispatchEvent(new CustomEvent('robotist:consent',{detail:granted}));}catch(e){}
      return granted;
    },
    clear:function(){
      document.cookie=COOKIE+'=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/';
      gtag('consent','update',{analytics_storage:'denied'});
      // Withdrawing the choice also removes what it allowed, so a visitor who
      // clears it is back to the state a first-time visitor is in.
      var host=location.hostname.replace(/^www\./,'');
      var names=document.cookie.split('; ').map(function(part){return part.split('=')[0];});
      for(var i=0;i<names.length;i++){
        if(names[i].indexOf('_ga')!==0)continue;
        [';path=/',';path=/;domain='+location.hostname,';path=/;domain=.'+host,';path=/;domain='+host].forEach(function(scope){
          document.cookie=names[i]+'=;expires=Thu, 01 Jan 1970 00:00:00 GMT'+scope;
        });
      }
      try{window.dispatchEvent(new CustomEvent('robotist:consent',{detail:'cleared'}));}catch(e){}
    }
  };
  gtag('js',new Date());
  gtag('config','__GA_ID__');
  // Action tracking. Delegated listeners so cards, product pages and forms added
  // by the CMS all report without touching each page. Beacon transport keeps the
  // events alive when a form posts and navigates away.
  function send(n,p){if(typeof gtag!=='function')return;var q={transport_type:'beacon'};
    if(p)for(var k in p)q[k]=p[k];gtag('event',n,q);}
  function text(el){return el?(el.textContent||'').replace(/\s+/g,' ').trim().slice(0,80):'';}
  document.addEventListener('submit',function(e){var f=e.target;
    if(!f||!f.tagName||f.tagName.toLowerCase()!=='form')return;
    var action=(f.getAttribute('action')||'');
    if(f.classList&&f.classList.contains('add-to-cart')){
      var slug=f.querySelector('input[name=slug]'),card=f.closest('.robot-card,.product-hero-content,.companion-content');
      send('add_to_cart',{item_id:slug?slug.value:'',item_name:text(card&&card.querySelector('.robot-info-name,.product-name,.companion-title'))});return;}
    if(action.indexOf('cart_submit')>-1){send('generate_lead',{form_id:'inquiry_cart'});return;}
    if(action.indexOf('/inquiries')>-1||f.classList.contains('inquiry-form')||f.id==='requirements-form'||f.id==='grn-application')
      {send('generate_lead',{form_id:f.id||f.className||'inquiry',page_path:location.pathname});}},true);
  document.addEventListener('click',function(e){var t=e.target;if(!t||!t.closest)return;
    if(t.closest('.chatbot-btn,.chatbot-launcher,.chat-launcher')){send('chat_open',{});return;}
    var a=t.closest('a[href]');if(!a)return;var h=a.getAttribute('href')||'';
    if(h.indexOf('tel:')===0){send('contact_click',{method:'phone'});return;}
    if(h.indexOf('mailto:')===0){send('contact_click',{method:'email'});return;}
    if(/wa\.me|whatsapp/i.test(h)){send('contact_click',{method:'whatsapp'});return;}
    if(/^https?:/i.test(h)&&a.hostname&&a.hostname!==location.hostname)
      {send('outbound_click',{link_url:h.slice(0,200),link_domain:a.hostname});}},true);
})();
</script>"""
ANALYTICS_TAG=(ANALYTICS_TAG.replace('__GA_ID__',ANALYTICS_ID)
                           .replace('__CONSENT_COOKIE__',CONSENT_COOKIE)
                           .replace('__CONSENT_SECONDS__',str(CONSENT_SECONDS)))

# The choice itself. Injected at the same single point as the analytics tag so no
# page can drift out of step, and it removes itself once an answer is stored.
CONSENT_BANNER=r"""<style>
.robotist-consent{position:fixed;left:20px;bottom:20px;z-index:9998;max-width:min(420px,calc(100vw - 40px));
  background:#060D18;border:1px solid #142035;border-radius:14px;padding:16px 18px;
  box-shadow:0 18px 40px rgba(3,8,16,.55);color:#F0F4F8;
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;font-size:13px;line-height:1.55;text-align:left}
.robotist-consent[hidden]{display:none}
.robotist-consent .robotist-consent-head{display:block;margin-bottom:6px;color:#4AA8C8;font-size:11px;letter-spacing:.14em;text-transform:uppercase}
.robotist-consent p{margin:0 0 12px}
.robotist-consent a{color:#A8DCEF;text-decoration:underline;text-underline-offset:2px}
.robotist-consent-actions{display:flex;gap:8px;flex-wrap:wrap}
.robotist-consent button{font:inherit;font-weight:600;cursor:pointer;border-radius:999px;padding:9px 18px;min-height:40px;
  border:1px solid #4AA8C8;background:#4AA8C8;color:#030810}
.robotist-consent button.robotist-consent-reject{background:transparent;border-color:#26364a;color:#F0F4F8;font-weight:500}
.robotist-consent button:focus-visible{outline:2px solid #A8DCEF;outline-offset:2px}
@media(max-width:520px){.robotist-consent{left:12px;right:12px;bottom:12px;max-width:none}}
a.robotist-cookie-settings{color:#8A9BB0;font-size:12px;line-height:1.4;text-decoration:none;border-bottom:1px solid rgba(138,155,176,.35);padding-bottom:1px}
a.robotist-cookie-settings:hover{color:#A8DCEF;border-bottom-color:currentColor}
a.robotist-cookie-settings:focus-visible{outline:2px solid #A8DCEF;outline-offset:3px}
</style>
<div class="robotist-consent" id="robotist-consent" role="dialog" aria-labelledby="robotist-consent-title" hidden>
  <span class="robotist-consent-head" id="robotist-consent-title">Cookies</span>
  <p>We use essential cookies to run this site. Analytics cookies stay off until you accept them. <a href="/cookies.html">Cookie policy</a></p>
  <div class="robotist-consent-actions">
    <button type="button" data-consent="granted">Accept analytics</button>
    <button type="button" class="robotist-consent-reject" data-consent="denied">Reject</button>
  </div>
</div>
<script>
(function(){
  var box=document.getElementById('robotist-consent'),api=window.robotistConsent;
  if(!box)return;
  if(!api){box.remove();return;}
  if(api.choice()){box.remove();return;}
  box.hidden=false;
  box.addEventListener('click',function(event){
    var button=event.target&&event.target.closest?event.target.closest('[data-consent]'):null;
    if(!button)return;
    api.set(button.getAttribute('data-consent'));
    box.remove();
  });
})();
</script>"""

# Robotist headings are bold: the H1 and every heading below it, on every page. This is a
# brand rule, so it is injected at the same single point as the analytics tag and the banner
# instead of being repeated in 25 page stylesheets that a future generator could contradict.
# `!important` is what makes it stick: the pages dress their headings with classes
# (.hero-h1, .section-title) and some set the weight inline, and both outrank a bare
# element selector. Nothing in the pages declares a heading weight as `!important`.
HEADING_WEIGHT=r"""<style>
h1,h2,h3,h4,h5,h6{font-weight:700 !important}
</style>"""

# The footer stays the way each page already renders it; the policy link is added to
# the one row every page shares, so the choice can be revisited after the banner is gone.
COOKIE_SETTINGS_LINK='<a class="robotist-cookie-settings" href="/cookies.html">Cookie settings</a>'
FOOTER_BOTTOM=re.compile(r'(<div class="footer-bottom">\s*<span class="footer-copy">.*?</span>)',re.S)


def analytics(markup):
    """Add the GA tag to an HTML document once. Returns the markup unchanged when it is
    not HTML, already tagged, or has no head to attach to."""
    if 'googletagmanager.com/gtag/js' in markup or '</head>' not in markup:return markup
    return markup.replace('</head>',ANALYTICS_TAG+'</head>',1)


def consent(markup):
    """Offer the cookie choice, keep the policy reachable after it is made, and hold the
    heading weight the brand sets.

    One injection point for every HTML response, so the banner, the analytics defaults,
    the footer link and the heading rule can never drift page by page.
    """
    if '</body>' not in markup:return markup
    if 'class="robotist-cookie-settings"' not in markup:
        markup=FOOTER_BOTTOM.sub(lambda match:match.group(1)+COOKIE_SETTINGS_LINK,markup,count=1)
    if HEADING_WEIGHT not in markup and '</head>' in markup:
        markup=markup.replace('</head>',HEADING_WEIGHT+'</head>',1)
    if 'id="robotist-consent"' in markup:return markup
    index=markup.lower().rfind('</body>')
    return markup[:index]+CONSENT_BANNER+markup[index:]


class Site:
    def __init__(self,root,store):
        self.root=Path(root)
        self.store=store

    def soup(self,relative):
        return BeautifulSoup((self.root/relative).read_text(encoding='utf-8'),'html.parser')

    def requirement_fields(self):
        labels={}
        for el in self.soup('requirements.html').select('#requirements-form [name]'):
            name=el['name']
            if name.startswith('_') or name in labels:continue
            group=el.find_parent(class_='req-field')
            label=group.select_one('.req-label') if group else None
            labels[name]=label.get_text(' ',strip=True).rstrip(' *') if label else name.replace('_',' ').capitalize()
        labels['contact_person']='Contact person and title'
        return labels

    # One brand icon set for every public page, resolved here so no page carries
    # its own copy. Eden keeps the pre-15-September mark until its identity is
    # decided, so it is served from /eden/ instead of the Robotist file.
    # ?v= is the icon set's version. Browsers keep favicons in their own cache and
    # can show a stale mark for a URL they have seen before, so bump this string in
    # both here and grn/templates/base.html whenever the brand icon changes.
    ICON_LINKS=(
        {'rel':'icon','href':'/favicon.svg?v=20260915c','type':'image/svg+xml'},
        {'rel':'icon','href':'/favicon-32.png?v=20260915c','sizes':'32x32','type':'image/png'},
        {'rel':'icon','href':'/favicon.ico?v=20260915c','sizes':'any'},
        {'rel':'apple-touch-icon','href':'/apple-touch-icon.png?v=20260915c','sizes':'180x180'},
    )
    ICON_SELECTOR='link[rel="icon"],link[rel="shortcut icon"],link[rel="apple-touch-icon"],link[rel="apple-touch-icon-precomposed"],link[rel="mask-icon"]'

    @staticmethod
    def is_eden(path):
        route=urlsplit(path).path.lower()
        name=Path(route).name
        return (route.startswith('/eden/') or name.startswith(('eden','old-eden'))
                or Path(route).parent.name.startswith(('eden','old-eden')))

    def with_brand_icons(self,page,path):
        if not page.head:return page
        prefix='/eden' if self.is_eden(path) else ''
        for link in list(page.select(self.ICON_SELECTOR)):link.decompose()
        for spec in self.ICON_LINKS:
            tag=page.new_tag('link')
            for key,value in spec.items():tag[key]=prefix+value if key=='href' else value
            page.head.append(tag)
        return page

    def veil_markup(self,page,label='18+',hint='Tap to reveal',hide='Hide again'):
        veil=page.new_tag('button',attrs={'type':'button','class':'nsfw-veil','aria-label':'Reveal sensitive content'})
        for cls,text in [('nsfw-veil-label',label),('nsfw-veil-hint',hint),('nsfw-veil-hide',hide)]:
            span=page.new_tag('span',attrs={'class':cls});span.string=text;veil.append(span)
        return veil

    def veil(self,page,media,host,nsfw):
        """Blur one sensitive image or video and reveal it on click, as the Eden stage does."""
        if not nsfw or media is None or host is None:return False
        host['class']=[c for c in host.get('class',[]) if c!='nsfw-host']+['nsfw-host']
        media['class']=[c for c in media.get('class',[]) if c!='nsfw-blur']+['nsfw-blur']
        host.append(self.veil_markup(page))
        return True

    def veil_assets(self,page):
        """Only a page that carries a veiled asset loads the veil stylesheet and script."""
        if page.head and not page.head.select_one('link[href="/assets/nsfw-veil.css"]'):
            page.head.append(page.new_tag('link',rel='stylesheet',href='/assets/nsfw-veil.css'))
        if page.body and not page.body.select_one('script[src="/assets/nsfw-veil.js"]'):
            page.body.append(page.new_tag('script',src='/assets/nsfw-veil.js',defer=''))

    def with_cart(self,markup,csrf,count,submission_token,path):
        page=BeautifulSoup(markup,'html.parser')
        if not page.head or not page.body:return markup
        page=self.with_brand_icons(page,path)
        page.head.append(page.new_tag('link',rel='stylesheet',href='/grn/assets/cart.css'))
        link=page.new_tag('a',href='/cart',attrs={'class':'inquiry-cart-link'})
        link.string=f'Inquiry cart ({count})'
        page.body.append(link)
        def add_form(slug,name):
            form=page.new_tag('form',method='post',action='/cart/add',attrs={'class':'add-to-cart'})
            for key,value in [('csrf',csrf),('slug',slug)]:form.append(page.new_tag('input',type='hidden',attrs={'name':key,'value':value}))
            button=page.new_tag('button',type='submit',attrs={'aria-label':'Add '+name+' to inquiry cart'})
            button.string='Add to inquiry cart +';form.append(button)
            return form
        for card in page.select('.robot-card'):
            product_link=card.select_one('a[href*="products/"]')
            if not product_link:continue
            slug=Path(urlsplit(product_link['href']).path).stem
            name=card.select_one('.robot-info-name')
            info=card.select_one('.robot-info')
            if info and name:info.append(add_form(slug,name.get_text(' ',strip=True)))
        name=page.select_one('.product-name,.companion-title')
        if name and path.startswith('/products/'):
            slug=Path(path).stem
            target=page.select_one('.product-hero-content,.companion-content') or name.parent
            target.append(add_form(slug,name.get_text(' ',strip=True)))
        for form in page.select('#inquiry-form,#inquiry-modal form,#requirements-form'):
            form['method']='post';form['action']='/inquiries'
            for key,value in [('csrf',csrf),('submission_token',submission_token)]:
                form.append(page.new_tag('input',type='hidden',attrs={'name':key,'value':value}))
            if form.get('id')=='requirements-form':
                form.append(page.new_tag('input',type='hidden',attrs={'name':'form_kind','value':'requirements'}))
        for script in page.select('script:not([src])'):
            if script.string and 'https://formspree.io/f/mnjevgjq' in script.string:
                script.string=script.string.replace('https://formspree.io/f/mnjevgjq','/inquiries').replace('if (response.ok) {', "if (response.ok) { window.location.assign('/inquiry/received'); return;")
        return str(page)

    def product(self,doc):
        compact=doc.get('template')=='compact'
        own=self.root/'products'/f'{doc["slug"]}.html'
        # Imported pages retain their exact shell; new pages use the matching existing family.
        page=self.soup(own.relative_to(self.root) if own.exists() else ('products/adam-u.html' if compact else 'products/fourier-gr-3.html'))
        actual=bool(page.select_one('.companion-title'))
        if actual!=compact:page=self.soup('products/adam-u.html' if compact else 'products/fourier-gr-3.html')
        v=lambda k:plain_text(doc['fields'].get(k,{}).get('value',''))
        def put(selector,text):
            node=page.select_one(selector)
            if node:node.clear();node.append(text)
        put('title',v('name')+' — Robotist')
        for m in page.select('meta[name="description"],meta[property="og:description"]'):m['content']=v('description')
        for m in page.select('meta[property="og:title"]'):m['content']=v('name')+' — Robotist'
        canonical='https://www.robotist.com.au/products/'+doc['slug']+'.html'
        for m in page.select('link[rel="canonical"]'):m['href']=canonical
        for m in page.select('meta[property="og:url"]'):m['content']=canonical
        put('.companion-title' if compact else '.product-name',v('name'))
        put('.companion-kicker' if compact else '.product-category',v('category'))
        put('.companion-description' if compact else '.product-desc',v('description'))
        put('.companion-price-value',v('price'))
        cover=next((a for a in doc['assets'] if a['area']=='cover'),None)
        veiled=False
        if cover:
            image=page.select_one('.companion-visual img' if compact else '.product-hero-image img')
            if image:
                image['src']='/catalog/images/'+cover['id'];image['alt']=cover['alt']
                veiled=self.veil(page,image,image.find_parent('div',class_='companion-visual') or image.find_parent('div',class_='product-hero-image'),cover.get('nsfw'))
            # A sensitive cover is never handed to a link preview.
            for m in page.select('meta[property="og:image"]'):
                if cover.get('nsfw'):m.decompose()
                else:m['content']='https://www.robotist.com.au/catalog/images/'+cover['id']
        grid=page.select_one('.companion-specs' if compact else '.specs-grid')
        if grid:
            grid.clear()
            prefix='companion-' if compact else ''
            facts={'Model':v('name'),'Price':v('price'),'Category':v('category')}
            facts.update({plain_text(k[5:]):plain_text(f['value']) for k,f in doc['fields'].items() if k.startswith('spec:')})
            for key,value in facts.items():
                if not value:continue
                item=page.new_tag('div',attrs={'class':'companion-spec' if compact else 'spec-item'})
                for cl,txt in [(prefix+'spec-label',key),(prefix+'spec-value',value)]:
                    span=page.new_tag('span',attrs={'class':cl});span.string=txt;item.append(span)
                grid.append(item)
        if not compact:
            highlights=page.select_one('.product-highlights');highlights.clear()
            for line in v('highlights').splitlines():
                if line.strip():
                    pill=page.new_tag('span',attrs={'class':'highlight-pill'});pill.string=line;highlights.append(pill)
            strengths=page.select_one('.strengths-grid')
            if strengths:
                section=strengths.find_parent('section')
                title=section.select_one('.section-title')
                if title:title.string=v('why_title') or 'Why this robot'
                strengths.clear()
                if not v('strengths').strip():
                    section.decompose()
                    strengths=None
                for line in v('strengths').splitlines():
                    if not line.strip():continue
                    title,_,body=line.partition('|')
                    card=page.new_tag('div',attrs={'class':'strength-card'})
                    for cl,txt in [('strength-name',title),('strength-desc',body)]:
                        el=page.new_tag('div',attrs={'class':cl});el.string=txt.strip();card.append(el)
                    if strengths is not None: strengths.append(card)
            put('.inquiry-card h3','Interested in '+v('name')+'?')
        product_videos=videos(doc.get('videos',[]))
        if product_videos:
            section=page.new_tag('section',attrs={'class':'companion-section' if compact else 'section','id':'product-videos','aria-label':'Product videos'})
            heading=page.new_tag('h2',attrs={'class':'section-title'});heading['style']='font-weight:600;letter-spacing:-.02em';heading.string='See it in action';section.append(heading)
            for item in product_videos:
                figure=page.new_tag('figure',attrs={'style':'margin:24px 0;max-width:960px'})
                media=page.new_tag(item['kind'],src=item['src'])
                media['style']='display:block;width:100%;aspect-ratio:16/9;border:0;background:#030810'
                if item['kind']=='iframe':
                    media['title']=item['title'];media['loading']='lazy';media['allow']='fullscreen; picture-in-picture';media['allowfullscreen']='';media['referrerpolicy']='strict-origin-when-cross-origin'
                else:
                    media['controls']='';media['preload']='none';media['playsinline']='';media['aria-label']=item['title']
                if item.get('nsfw'):
                    host=page.new_tag('div',attrs={'class':'nsfw-host nsfw-media'})
                    media['class']=(media.get('class',[])+['nsfw-blur'])
                    host.append(media);host.append(self.veil_markup(page))
                    figure.append(host);veiled=True
                else:
                    figure.append(media)
                caption=page.new_tag('figcaption');caption.string=item['title'];figure.append(caption)
                fallback=page.new_tag('a',href=item['url'],target='_blank',rel='noopener noreferrer');fallback['style']='display:inline-block;min-height:44px;padding:10px 0;color:#A8DCEF;text-decoration:underline';fallback.string='Open video';figure.append(fallback)
                section.append(figure)
            anchor=page.select_one('#specs') or page.select_one('.companion-hero') or page.select_one('.product-hero')
            if anchor:anchor.insert_after(section)
        # Preserve inquiry form and public navigation; add the founder's extra product images.
        extras=[a for a in doc['assets'] if a['area']=='gallery']
        if extras:
            section=page.new_tag('section',attrs={'class':'companion-section' if compact else 'section'})
            h=page.new_tag('h2');h.string='Robot images';section.append(h)
            for a in extras:
                image=page.new_tag('img',src='/catalog/images/'+a['id'],alt=a['alt'],loading='lazy')
                image['style']='max-width:100%;max-height:600px;object-fit:contain'
                if a.get('nsfw'):
                    host=page.new_tag('span',attrs={'class':'nsfw-host nsfw-inline'})
                    image['class']=['nsfw-blur'];host.append(image);host.append(self.veil_markup(page))
                    section.append(host);veiled=True
                else:
                    section.append(image)
            anchor=page.select_one('#specs')
            if anchor:anchor.insert_after(section)
        if veiled:self.veil_assets(page)
        return str(page)

    FEATURED_LIMIT=6

    def card_for(self, page, doc):
        """The catalogue card for one published robot: the page's own, or a copy of the exemplar."""
        href='products/'+doc['slug']+'.html'
        card=next((a.find_parent(class_='robot-card') for a in page.select('.robot-card a[href]') if a['href'].lstrip('/')==href),None)
        created=card is None
        if created:
            exemplar=page.select_one('#robotGrid .robot-card')
            if exemplar is None:raise ValueError('The catalogue grid has no card to copy for a new robot.')
            card=copy.copy(exemplar);exemplar.parent.append(card)
        return card,created

    def fill_card(self, page, card, doc, created):
        """Everything a card says: its facts, where it links, and its cover with any veil."""
        href='products/'+doc['slug']+'.html'
        v=lambda k:plain_text(doc['fields'].get(k,{}).get('value',''))
        card['data-category']=v('category').lower()
        # New cards should not depend on a scroll observer being reinitialised.
        card['class']=[c for c in card.get('class',[]) if c!='reveal']
        for a in card.select('a[href]'):
            if 'products/' in a['href']:a['href']=href
        for selector,value in [('.robot-info-name',v('name')),('.robot-info-price',v('price')),('.robot-cat-tag',v('category')),('.robot-info-best',v('spec:Best for'))]:
            # An empty CMS field must not blank copy the page already carries; only
            # a card the CMS just created starts empty.
            if not value and not created:continue
            for el in card.select(selector):el.clear();el.append(value)
        # The card carries its description as data, never as a hover layer: the
        # ItemList JSON-LD and the assistant's catalogue read it from here.
        if v('description') or created:card['data-desc']=v('description')
        cover=next((a for a in doc['assets'] if a['area']=='cover'),None)
        if cover is None:return False
        veiled=False
        for image in card.select('img'):
            image['src']='/catalog/images/'+cover['id'];image['alt']=cover['alt']
            if self.veil(page,image,image.find_parent('div',class_='robot-card-img-wrap'),cover.get('nsfw')):veiled=True
        return veiled

    def featured(self, doc):
        """True when the admin flagged this robot for the homepage band."""
        return plain_text(doc['fields'].get('featured',{}).get('value','')).strip().lower() in ('yes','true','1','on')

    def featured_band(self, page, featured):
        """The Featured band above the catalogue. Nothing flagged means no band on the page."""
        grid=page.select_one('#featuredGrid')
        if grid is None:return False
        band=grid.find_parent('section') or grid
        if not featured:
            band.decompose();return False
        exemplar=page.select_one('#robotGrid .robot-card')
        if exemplar is None:return False
        veiled=False
        for doc in featured[:self.FEATURED_LIMIT]:
            card=copy.copy(exemplar)
            for badge in card.select('.robot-featured-badge'):badge.decompose()
            grid.append(card)
            if self.fill_card(page,card,doc,True):veiled=True
        band.attrs.pop('hidden',None)
        return veiled

    def homepage(self):
        page=self.soup('index.html')
        veiled=False
        featured=[]
        for doc in self.store.published():
            card,created=self.card_for(page,doc)
            if self.fill_card(page,card,doc,created):veiled=True
            if self.featured(doc):featured.append(doc)
        if veiled:self.veil_assets(page)
        if self.featured_band(page,featured):veiled=True
        self.sync_catalogue_count(page)
        return str(page)

    NUMBER_WORDS={1:'One',2:'Two',3:'Three',4:'Four',5:'Five',6:'Six',7:'Seven',8:'Eight',9:'Nine',10:'Ten',
                  11:'Eleven',12:'Twelve',13:'Thirteen',14:'Fourteen',15:'Fifteen',16:'Sixteen',17:'Seventeen',
                  18:'Eighteen',19:'Nineteen',20:'Twenty',21:'Twenty-one',22:'Twenty-two',23:'Twenty-three',
                  24:'Twenty-four',25:'Twenty-five',26:'Twenty-six',27:'Twenty-seven',28:'Twenty-eight',
                  29:'Twenty-nine',30:'Thirty'}

    def card_facts(self,card):
        """What one catalogue card says: the headline count and the ItemList read from here."""
        text=lambda selector:(card.select_one(selector).get_text(' ',strip=True) if card.select_one(selector) else '')
        link=card.select_one('a[href*="products/"]')
        slug=Path(urlsplit(link['href']).path).stem if link else ''
        return {'name':text('.robot-info-name'),
                'category':text('.robot-cat-tag'),
                'price':text('.robot-info-price'),
                'description':card.get('data-desc') or '',
                'url':'https://www.robotist.com.au/products/'+slug+'.html' if slug else ''}

    def sync_catalogue_count(self,page):
        """The published count is the number of cards; the copy and the ItemList follow it."""
        cards=page.select('#robotGrid .robot-card')
        facts=[f for f in (self.card_facts(card) for card in cards) if f['name']]
        word=self.NUMBER_WORDS.get(len(facts))
        title=page.select_one('.catalogue-title')
        if word and title:
            for node in title.find_all(string=True):
                if 'machines' in node:node.replace_with(re.sub(r'^[^ ]+',word,node))
        for script in page.select('script[type="application/ld+json"]'):
            content=script.string or ''
            if '"ItemList"' not in content:continue
            try:data=json.loads(content)
            except ValueError:continue
            categories={f['category'].lower() for f in facts if f['category']}
            data['numberOfItems']=len(facts)
            data['description']=f"{len(facts)} commercial robots across {len(categories) or 5} categories available for purchase or rental worldwide"
            data['itemListElement']=[{'@type':'ListItem','position':index,'name':f['name'],
                                      'url':f['url'] or 'https://www.robotist.com.au/#catalogue',
                                      'description':(f['description'] or f['category'] or f['name'])}
                                     for index,f in enumerate(facts,1)]
            # A product description must never be able to close this script tag.
            script.string=(json.dumps(data,indent=2,ensure_ascii=False)
                           .replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026'))
        return page

    def comparison(self):
        """The comparison list is one row per machine; a published document either fills its
        existing row or joins a New arrivals group at the end of the list."""
        page=self.soup('compare.html');container=page.select_one('.cmp')
        if container is None:raise ValueError('Comparison list unavailable')
        v_of=[]
        for doc in self.store.published():
            href='products/'+doc['slug']+'.html'
            for row in list(container.select('a.cmp-row[href]')):
                if row.get('href','').lstrip('/')==href:row.decompose()
            v=lambda k:plain_text(doc['fields'].get(k,{}).get('value',''))
            name=v('name') or doc['slug']
            row=page.new_tag('a',attrs={'class':'cmp-row','href':href})
            media=page.new_tag('span',attrs={'class':'c-media'})
            cover=next((a for a in doc['assets'] if a['area']=='cover'),None)
            if cover:
                media.append(page.new_tag('img',attrs={'loading':'lazy','src':'/catalog/images/'+cover['id'],
                                                       'alt':name}))
            row.append(media)
            identity=page.new_tag('span',attrs={'class':'c-name'})
            leaf=page.new_tag('span',attrs={'class':'n'});leaf.string=name;identity.append(leaf)
            pill=page.new_tag('span',attrs={'class':'t'});pill.string=v('category') or 'Robot'
            identity.append(pill);row.append(identity)
            figures=[('c-dof',v('spec:Degrees of Freedom') or v('spec:DOF') or '—'),
                     ('c-cap',v('spec:Speed') or v('spec:Payload') or '—'),
                     ('c-use',v('spec:Best for') or '—'),
                     ('c-price',v('price') or '—')]
            for index,(css,value) in enumerate(figures):
                cell=page.new_tag('span',attrs={'class':css})
                if index==0:
                    inner=page.new_tag('span',attrs={'class':'v blank' if value=='—' else 'v'})
                    inner.string=value;cell.append(inner)
                else:cell.string=value
                row.append(cell)
            action=page.new_tag('span',attrs={'class':'c-go'});action.string='View'
            row.append(action)
            v_of.append(row)
        if v_of:
            group=page.new_tag('div',attrs={'class':'cmp-group'})
            label=page.new_tag('span');label.string='New arrivals'
            note=page.new_tag('em');note.string='%d %s added from the catalogue' % (len(v_of),'machine' if len(v_of)==1 else 'machines')
            group.append(label);group.append(note)
            container.append(group)
            for row in v_of:container.append(row)
        return str(page)

    def sitemap(self):
        import json
        import xml.etree.ElementTree as ET
        ns='http://www.sitemaps.org/schemas/sitemap/0.9'
        ET.register_namespace('',ns)
        root=ET.fromstring((self.root/'sitemap.xml').read_text(encoding='utf-8'))
        present={x.text for x in root.iter('{'+ns+'}loc')}
        for doc in self.store.published():
            url='https://www.robotist.com.au/products/'+doc['slug']+'.html'
            if url not in present:ET.SubElement(ET.SubElement(root,'{'+ns+'}url'),'{'+ns+'}loc').text=url
        posts_json=self.root/'blog-posts.json'
        if posts_json.is_file():
            try:entries=json.loads(posts_json.read_text(encoding='utf-8'))
            except Exception:entries=[]
            for post in entries:
                if post.get('status')=='draft' or not post.get('slug'):continue
                url='https://www.robotist.com.au/blog/'+post['slug']+'.html'
                if url not in present:ET.SubElement(ET.SubElement(root,'{'+ns+'}url'),'{'+ns+'}loc').text=url
        return ET.tostring(root,encoding='unicode')
