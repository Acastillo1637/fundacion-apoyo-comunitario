"""Linux-only syntax check using disposable certificates, never production keys."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

if sys.platform == 'win32':
    raise SystemExit('La comprobación Nginx se ejecuta en Linux mediante GitHub Actions.')
if not shutil.which('nginx') or not shutil.which('openssl'):
    raise SystemExit('Se requieren nginx y openssl instalados para comprobar la plantilla.')
root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='fundacion-nginx-') as directory:
    folder = Path(directory)
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
        '-subj', '/CN=voluntariado.example.org', '-keyout', str(folder/'privkey.pem'),
        '-out', str(folder/'fullchain.pem')], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    template = (root/'deploy'/'nginx.conf.example').read_text(encoding='utf-8')
    template = template.replace('/etc/letsencrypt/live/voluntariado.example.org/', str(folder)+'/')
    template = template.replace('/var/log/nginx/fundacion-access.log', str(folder/'access.log'))
    config = folder/'nginx.conf'
    config.write_text(f'error_log stderr;\npid {folder}/nginx.pid;\nevents {{}}\nhttp {{\n{template}\n}}\n', encoding='utf-8')
    subprocess.run(['nginx', '-e', 'stderr', '-t', '-p', str(folder), '-c', str(config)], check=True)
    print('Plantilla Nginx válida; certificado ficticio eliminado al finalizar.')
