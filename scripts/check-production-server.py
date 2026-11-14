"""Linux CI smoke check of the locked WSGI server; never uses the shared .env."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

if sys.platform == 'win32':
    raise SystemExit('Run the Gunicorn smoke check on Linux, as in GitHub Actions.')
if os.environ.get('DJANGO_DEBUG') != 'true':
    raise SystemExit('This isolated smoke check requires the CI development environment.')
with socket.socket() as available:
    available.bind(('127.0.0.1', 0))
    port = available.getsockname()[1]
process = subprocess.Popen([sys.executable, '-m', 'gunicorn', 'config.wsgi:application',
    '--bind', f'127.0.0.1:{port}', '--workers', '1', '--threads', '2'],
    cwd=Path(__file__).resolve().parents[1] / 'backend', stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(60):
        if process.poll() is not None:
            raise RuntimeError('Gunicorn exited before the health check.')
        try:
            with urlopen(f'http://127.0.0.1:{port}/api/health/live/', timeout=1) as response:
                if response.status == 200:
                    print('Locked Gunicorn WSGI health check passed.')
                    break
        except OSError:
            time.sleep(0.2)
    else:
        raise RuntimeError('Gunicorn did not become ready.')
finally:
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
