"""Transactional local catalog storage, separate from leads and GRN data."""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from grn.database import connect


class Store:
    def __init__(self, path, database_url=None):
        self.database_url = database_url
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.database_url:
            return
        with self.connect() as db:
            db.executescript('''
              CREATE TABLE IF NOT EXISTS catalog_products (
                id TEXT PRIMARY KEY, slug TEXT UNIQUE NOT NULL, version INTEGER NOT NULL,
                document TEXT NOT NULL, published TEXT);
              CREATE TABLE IF NOT EXISTS catalog_events (
                id INTEGER PRIMARY KEY, product_id TEXT NOT NULL,
                occurred_at TEXT DEFAULT CURRENT_TIMESTAMP, action TEXT NOT NULL,
                version INTEGER NOT NULL);
            ''')

    @contextmanager
    def connect(self):
        db = connect(self.path, self.database_url)
        try:
            with db:
                yield db
        finally:
            db.close()

    def all(self):
        with self.connect() as db:
            return [json.loads(r['document']) for r in db.execute('SELECT document FROM catalog_products ORDER BY '+('sequence' if self.database_url else 'rowid')+' DESC')]

    def get(self, id):
        with self.connect() as db:
            r = db.execute('SELECT * FROM catalog_products WHERE id=?', (id,)).fetchone()
            if not r:
                raise ValueError('Robot not found')
            return json.loads(r['document'])

    def save(self, doc, expected, action, publish=False):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT version FROM catalog_products WHERE id=?', (doc['id'],)).fetchone()
            if (row['version'] if row else 0) != expected:
                raise ValueError('This robot changed in another window. Reload before saving.')
            doc['version'] = expected + 1
            body = json.dumps(doc, ensure_ascii=False)
            if row:
                db.execute('UPDATE catalog_products SET slug=?,version=?,document=? WHERE id=?',
                           (doc['slug'], doc['version'], body, doc['id']))
            else:
                db.execute('INSERT INTO catalog_products(id,slug,version,document) VALUES(?,?,?,?)',
                           (doc['id'], doc['slug'], doc['version'], body))
            if publish:
                db.execute('UPDATE catalog_products SET published=? WHERE id=?', (body, doc['id']))
            db.execute('INSERT INTO catalog_events(product_id,action,version) VALUES(?,?,?)', (doc['id'], action, doc['version']))
        return doc

    def published(self, slug=None):
        with self.connect() as db:
            rows = db.execute('SELECT published FROM catalog_products WHERE published IS NOT NULL').fetchall()
            docs = [json.loads(r[0]) for r in rows]
            return next((d for d in docs if d['slug'] == slug), None) if slug else docs

    def events(self, id):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT occurred_at,action,version FROM catalog_events WHERE product_id=? ORDER BY id DESC', (id,))]
