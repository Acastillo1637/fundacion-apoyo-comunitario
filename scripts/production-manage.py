"""Run an explicit Django command with a private production env file, without a shell."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
NAMES = frozenset('''FOUNDATION_NAME DJANGO_SECRET_KEY DJANGO_DEBUG DJANGO_ALLOWED_HOSTS
DJANGO_CSRF_TRUSTED_ORIGINS PUBLIC_APP_URL DATABASE_ENGINE POSTGRES_DB POSTGRES_USER
POSTGRES_PASSWORD POSTGRES_HOST POSTGRES_PORT POSTGRES_SSLMODE POSTGRES_SSLROOTCERT
DJANGO_TRUST_PROXY DATA_RETENTION_NOTICE MAP_TILE_URL GEOCODING_URL GEOCODING_USER_AGENT
GEOAPIFY_API_KEY EMAIL_BACKEND EMAIL_HOST EMAIL_PORT EMAIL_HOST_USER EMAIL_HOST_PASSWORD
EMAIL_USE_TLS EMAIL_USE_SSL DEFAULT_FROM_EMAIL CLAMAV_HOST CLAMAV_PORT PRIVATE_DOCUMENT_ROOT'''.split())


def read_env(path):
    if os.name != 'nt' and path.stat().st_mode & 0o077:
        raise ValueError('El archivo de secretos debe tener permisos 600 o más restrictivos.')
    values = {}
    for number, line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        name, separator, value = line.partition('=')
        name, value = name.strip(), value.strip()
        if not separator or not re.fullmatch('[A-Z][A-Z0-9_]*', name) or name not in NAMES or name in values:
            raise ValueError(f'Línea {number} inválida o duplicada; no se ejecutó ningún comando.')
        if value.startswith(('"', "'")):
            if len(value) < 2 or value[-1] != value[0]:
                raise ValueError(f'Comillas sin cerrar en línea {number}.')
            value = value[1:-1]
        values[name] = value
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        values = read_env(args.env_file)
    except (OSError, ValueError):
        parser.error('No se pudo leer una configuración privada válida. Revisa formato, nombres, duplicados y permisos 600.')
    if values.get('DJANGO_DEBUG', '').lower() != 'false' or values.get('DATABASE_ENGINE') != 'postgresql':
        parser.error('La configuración debe declarar DJANGO_DEBUG=false y DATABASE_ENGINE=postgresql.')
    if not args.command:
        parser.error('Indica el comando Django que deseas ejecutar. No se realizan acciones implícitas.')
    return subprocess.call([sys.executable, str(ROOT/'backend'/'manage.py'), *args.command],
                           cwd=ROOT, env=dict(os.environ, **values))


if __name__ == '__main__':
    raise SystemExit(main())
