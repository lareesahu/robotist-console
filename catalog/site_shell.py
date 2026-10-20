"""Reuse the established homepage navigation/footer without a second design."""
from functools import lru_cache
from pathlib import Path
from urllib.parse import urljoin
import re
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parent.parent

def _rules(css):
    css=re.sub(r'/\*.*?\*/','',css,flags=re.S)
    start=0
    while start<len(css):
        opening=css.find('{',start)
        if opening<0:return
        depth=1;end=opening+1;quote=None;escaped=False
        while end<len(css) and depth:
            char=css[end]
            if escaped:escaped=False
            elif char=='\\':escaped=True
            elif quote:
                if char==quote:quote=None
            elif char in ('"',"'"):quote=char
            elif char=='{':depth+=1
            elif char=='}':depth-=1
            end+=1
        yield css[start:opening].strip(),css[opening+1:end-1]
        start=end

def _shell_css(css):
    output=[]
    for selector,body in _rules(css):
        if selector.startswith('@media'):
            nested=_shell_css(body)
            if nested:output.append(selector+'{'+nested+'}')
        elif selector==':root':output.append('.robotist-shell,.has-site-shell{'+body+'}')
        elif not selector.startswith('@'):
            selectors=[s.strip() for s in selector.split(',') if re.search(r'\.(?:nav|footer)(?:[-\s.:#\[]|$)',s)]
            if selectors:output.append(','.join('.robotist-shell '+s for s in selectors)+'{'+body+'}')
    return '\n'.join(output)

@lru_cache(maxsize=4)
def _load(stamp,mobile_stamp):
    page=BeautifulSoup((ROOT/'index.html').read_text(encoding='utf-8'),'html.parser')
    fragments=[]
    for selector in ('nav.nav','footer.footer'):
        element=page.select_one(selector)
        if element is None:raise ValueError('Robotist homepage shared element missing: '+selector)
        for tag in element.select('[href],[src]'):
            for attr in ('href','src'):
                if tag.has_attr(attr):tag[attr]=urljoin('/',tag[attr])
            tag.attrs.pop('onclick',None)
        if selector=='nav.nav':
            element['aria-label']='Main navigation'
            element.select_one('.nav-logo')['aria-label']='Robotist home'
            links=element.select_one('.nav-links');links['id']='robotist-navigation-links'
            button=element.select_one('.nav-hamburger')
            button['type']='button';button['aria-expanded']='false';button['aria-controls']=links['id']
        fragments.append('<div class="robotist-shell">'+str(element)+'</div>')
    css='.robotist-shell{font-family:var(--font-body);line-height:1.5}.robotist-shell *{box-sizing:border-box;margin:0;padding:0}.robotist-shell nav{gap:0}.robotist-shell footer{display:block}.robotist-shell a{border-radius:0}.has-site-shell>main{padding-top:72px}\n'
    css+=_shell_css('\n'.join(tag.get_text() for tag in page.select('style')))
    css+=_shell_css((ROOT/'mobile-usability.css').read_text(encoding='utf-8'))
    return dict(robotist_navigation=fragments[0],robotist_footer=fragments[1]),css

def shared_elements():
    return _load((ROOT/'index.html').stat().st_mtime_ns,(ROOT/'mobile-usability.css').stat().st_mtime_ns)
