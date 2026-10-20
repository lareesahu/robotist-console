"""Plain customer copy and allowlisted video embeds; never accept embed HTML."""
import ipaddress
import re
from urllib.parse import urlsplit, parse_qs, urlencode


def plain_text(value):
    text = str(value or '')
    text = re.sub(r'```[^\n]*\n?|```', '', text)
    text = re.sub(r'!?(\[([^\]]+)\])\([^\n)]+\)', r'\2', text)
    text = re.sub(r'\*\*(.*?)\*\*|__(.*?)__', lambda m: m[1] or m[2] or '', text, flags=re.S)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = re.sub(r'(?m)^\s{0,3}(?:#{1,6}\s+|[-*+]\s+|>\s*)', '', text)
    return text.strip()


def video(value):
    if not isinstance(value, dict):
        raise ValueError('Each video needs a link and title')
    url, title = value.get('url', ''), value.get('title', '')
    nsfw = value.get('nsfw') is True
    if not isinstance(url, str) or not isinstance(title, str) or len(url)>2000 or len(title)>160:
        raise ValueError('Use a video link under 2,000 characters and title under 160 characters')
    url, title = url.strip(), plain_text(title)
    if not title:
        raise ValueError('Give each video a descriptive title')
    try:
        u = urlsplit(url)
        if u.scheme != 'https' or not u.hostname or u.username or u.password or u.port not in (None,443):
            raise ValueError()
        host = u.hostname.lower()
        if '.' not in host or host.endswith(('.local','.localhost','.internal')):
            raise ValueError()
        try:
            if not ipaddress.ip_address(host).is_global: raise ValueError('Private video address')
        except ValueError as exc:
            if str(exc)=='Private video address': raise
        parts = u.path.strip('/').split('/')
        ident = None
        if host in ('youtube.com','www.youtube.com','m.youtube.com','youtube-nocookie.com','www.youtube-nocookie.com','youtu.be'):
            ident = parts[0] if host=='youtu.be' else (parse_qs(u.query).get('v',[''])[0] if u.path=='/watch' else (parts[1] if len(parts)==2 and parts[0] in ('embed','shorts','live') else ''))
            if not re.fullmatch(r'[A-Za-z0-9_-]{11}',ident): raise ValueError()
            return dict(url='https://www.youtube.com/watch?v='+ident,title=title,kind='iframe',src='https://www.youtube-nocookie.com/embed/'+ident,nsfw=nsfw)
        if host in ('vimeo.com','www.vimeo.com','player.vimeo.com'):
            ident = parts[1] if parts[0]=='video' and len(parts)>=2 else parts[0]
            if not re.fullmatch(r'\d{1,12}',ident): raise ValueError()
            privacy = parse_qs(u.query).get('h',[''])[0] or (parts[1] if len(parts)==2 and parts[0]!='video' else '')
            if privacy and not re.fullmatch(r'[A-Za-z0-9]+',privacy): raise ValueError()
            src='https://player.vimeo.com/video/'+ident+(('?'+urlencode({'h':privacy})) if privacy else '')
            return dict(url=url,title=title,kind='iframe',src=src,nsfw=nsfw)
        if u.path.lower().endswith(('.mp4','.webm')):
            return dict(url=url,title=title,kind='video',src=url,nsfw=nsfw)
    except ValueError:
        pass
    raise ValueError('Use a YouTube, Vimeo or public HTTPS MP4/WebM link, not embed code')


def videos(values):
    if not isinstance(values,list) or len(values)>6:
        raise ValueError('Add up to six product videos')
    return [video(v) for v in values]
