"""Build an uploadable ZIP from tracked application files, never local secrets/data."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def safe_file(path):
    parts = Path(path).parts
    if any(part in {'.git', '.venv', 'node_modules', '__pycache__', 'private_media', 'backups'} for part in parts):
        return False
    name = parts[-1]
    if name.startswith('.env') or name.endswith('.env') or ('.env.' in name and not name.endswith('.env.example')) or name.endswith(('.sqlite3', '.pyc', '.pem', '.key', '.log')):
        return False
    return True


def allowed(path):
    if str(path).replace('\\', '/') == '.env.example':
        return True
    if not safe_file(path):
        return False
    parts = Path(path).parts
    return parts[0] in {'backend', 'deploy', 'scripts', 'docs', 'config'} or str(path) == 'README.md'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'backups' / 'releases')
    args = parser.parse_args()
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT).strip():
        parser.error('Guarda los cambios en un commit antes de crear un paquete identificable.')
    subprocess.run([sys.executable, str(ROOT / 'scripts' / 'check-docs.py')], cwd=ROOT, check=True)
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    subprocess.run(['npm.cmd' if os.name == 'nt' else 'npm', 'run', 'build'], cwd=ROOT / 'frontend', check=True)
    # Collect only static assets with an isolated development environment; no DB access.
    env = dict(os.environ, DJANGO_DEBUG='true', DATABASE_ENGINE='sqlite', DJANGO_SECRET_KEY=secrets.token_urlsafe(64))
    subprocess.run([sys.executable, str(ROOT / 'backend' / 'manage.py'), 'collectstatic', '--noinput'], env=env, cwd=ROOT, check=True)
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    files = [ROOT / name for name in tracked if name and allowed(name)]
    for folder in [ROOT / 'frontend' / 'dist', ROOT / 'backend' / 'staticfiles']:
        files.extend(path for path in folder.rglob('*') if path.is_file() and safe_file(path.relative_to(ROOT)))
    manifest = {'commit':commit, 'files':[]}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    archive = args.output_dir / f'fundacion-{commit[:12]}.zip'
    # Exclusive creation prevents silently replacing a previously validated release.
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as package:
        for path in sorted(set(files)):
            if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
                raise ValueError('El paquete rechaza enlaces y archivos fuera del proyecto.')
            name = path.relative_to(ROOT).as_posix()
            data = path.read_bytes()
            package.writestr(name, data)
            manifest['files'].append({'path':name, 'bytes':len(data), 'sha256':hashlib.sha256(data).hexdigest()})
        package.writestr('RELEASE_MANIFEST.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(f'{checksum}  {archive.name}\n', encoding='utf-8')
    print(f'Paquete generado: {archive}')
    print('No incluye .env.shared, base de datos, documentos privados, dependencias instaladas ni credenciales.')


if __name__ == '__main__':
    main()
