"""Private uploads; remote objects remain durable when a Render instance sleeps."""
import io
import re
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit
from flask import send_file


class Files:
    def __init__(self, directory, prefix, url=None, key=None):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.prefix, self.url, self.key = prefix, url, key
        if url:
            parsed = urlsplit(url)
            if parsed.scheme != 'https' or not parsed.hostname.endswith('.supabase.co') or parsed.path not in ('', '/') or parsed.query or parsed.username:
                raise ValueError('Use the HTTPS Supabase project URL')
            if not key:
                raise ValueError('Configure the server-only Supabase storage key')

    def __truediv__(self, name):
        if not re.fullmatch(r'[a-zA-Z0-9_-]+(?:\.[a-zA-Z0-9]+)?', str(name)):
            raise ValueError('Invalid private file name')
        return File(self, str(name))

    def request(self, name, data=None):
        endpoint = self.url.rstrip('/') + '/storage/v1/object/robotist-private/' + self.prefix + '/' + name
        headers = {'apikey': self.key}
        if not self.key.startswith('sb_secret_'):
            headers['Authorization'] = 'Bearer ' + self.key
        if data is not None:
            headers.update({'Content-Type':'application/octet-stream', 'x-upsert':'false'})
        request = urllib.request.Request(endpoint, data=data, headers=headers, method='POST' if data is not None else 'GET')
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                return response.read()
        except OSError:
            raise ValueError('File storage is unavailable. The change was not completed; please retry.') from None

    def response(self, name, **kwargs):
        return send_file(io.BytesIO((self/name).read_bytes()), **kwargs)


class File:
    def __init__(self, files, name):
        self.files, self.name = files, name

    def read_bytes(self):
        if self.files.url:
            return self.files.request(self.name)
        return (self.files.directory/self.name).read_bytes()

    def read_text(self, encoding='utf-8'):
        return self.read_bytes().decode(encoding)

    def write_bytes(self, data):
        if self.files.url:
            self.files.request(self.name, data)
        else:
            (self.files.directory/self.name).write_bytes(data)
        return len(data)

    def write_text(self, text, encoding='utf-8'):
        return self.write_bytes(text.encode(encoding))
