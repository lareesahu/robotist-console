"""Persistent loopback-only setup. Secrets live outside the public source tree."""
import json
import secrets
from pathlib import Path


def local_options(data_dir):
    directory = Path(data_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'admin-config.json'
    if not path.exists():
        with path.open('x', encoding='utf-8') as handle:
            json.dump({'secret': secrets.token_urlsafe(48), 'password_hash': None}, handle)
    config = json.loads(path.read_text(encoding='utf-8'))
    return dict(DATA_DIR=str(directory), LOCAL_REVIEW=True, LOCAL_AUTO_LOGIN=False,
                SESSION_COOKIE_SECURE=False, SECRET_KEY=config['secret'],
                ADMIN_PASSWORD_HASH=config.get('password_hash') or 'setup-required',
                LOCAL_SETUP_PENDING=not config.get('password_hash'), LOCAL_CONFIG_PATH=str(path))


def save_password(app, password_hash):
    path = Path(app.config['LOCAL_CONFIG_PATH'])
    config = json.loads(path.read_text(encoding='utf-8'))
    if config.get('password_hash'):
        raise ValueError('Administrator access has already been configured. Sign in instead.')
    config['password_hash'] = password_hash
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(config), encoding='utf-8')
    temporary.replace(path)
    app.config.update(ADMIN_PASSWORD_HASH=password_hash, LOCAL_SETUP_PENDING=False)
