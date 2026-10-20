"""Database connections for local development and the hosted PostgreSQL service."""
import re
import sqlite3


class Record(dict):
    def __getitem__(self, key):
        return list(self.values())[key] if isinstance(key, int) else super().__getitem__(key)


class Result:
    def __init__(self, cursor):
        self.cursor = cursor
        self.rowcount = cursor.rowcount

    def fetchone(self):
        row = self.cursor.fetchone()
        return Record(row) if row is not None else None

    def fetchall(self):
        return [Record(row) for row in self.cursor.fetchall()]

    def __iter__(self):
        return iter(self.fetchall())


class PostgresConnection:
    """Adapt only the parameter and transaction conventions used by this app."""
    def __init__(self, url):
        import psycopg
        from psycopg.rows import dict_row
        self.connection = psycopg.connect(url, row_factory=dict_row, connect_timeout=15,
                                         sslmode='require', prepare_threshold=None)

    def execute(self, statement, values=()):
        import psycopg
        statement = statement.replace('CURRENT_TIMESTAMP', 'CURRENT_TIMESTAMP::text')
        statement = statement.replace(' LIKE ', ' ILIKE ')
        normalize = lambda value: int(value) if isinstance(value, bool) else value
        values = {k: normalize(v) for k, v in values.items()} if isinstance(values, dict) else tuple(normalize(v) for v in values)
        # Shared transaction lock replaces SQLite's writer lock. Small admin and
        # submission workloads require correctness over parallel write throughput.
        if statement == 'BEGIN IMMEDIATE':
            statement = 'SELECT pg_advisory_xact_lock(726268191)'
        if statement.startswith('INSERT OR IGNORE INTO'):
            statement = statement.replace('INSERT OR IGNORE INTO', 'INSERT INTO', 1) + ' ON CONFLICT DO NOTHING'
        if isinstance(values, dict):
            statement = re.sub(r'(?<!:):([a-z_]+)', r'%(\1)s', statement)
        else:
            statement = statement.replace('?', '%s')
        try:
            return Result(self.connection.execute(statement, values or None))
        except psycopg.IntegrityError as error:
            raise sqlite3.IntegrityError('Database constraint rejected the change') from error

    def commit(self):
        self.connection.commit()

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, kind, value, traceback):
        if kind:
            self.connection.rollback()
        else:
            self.connection.commit()


def connect(path, url=None):
    if url:
        return PostgresConnection(url)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys=ON')
    return connection
