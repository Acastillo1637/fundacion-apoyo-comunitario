"""Read-only production diagnostics. Never sends email, migrates or writes files."""
import json
import os
import socket
from pathlib import Path

from django.conf import settings
from django.core.checks import ERROR, WARNING, run_checks
from django.core.mail import get_connection
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


class Command(BaseCommand):
    help = 'Comprueba producción sin modificar datos ni enviar mensajes; --services abre conexiones.'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('--services', action='store_true')
        parser.add_argument('--strict', action='store_true', help='Considerar también avisos como bloqueos.')
        parser.add_argument('--frontend-dir', type=Path, default=settings.BASE_DIR.parent / 'frontend' / 'dist')

    def handle(self, *args, **options):
        results = []

        def record(name, ok, message, warning=False):
            results.append({'check':name, 'status': 'warning' if warning else 'ok' if ok else 'error', 'message':message})

        record('production_mode', not settings.DEBUG, 'Se requiere DJANGO_DEBUG=false para comprobar la configuración de producción.')
        for issue in run_checks(include_deployment_checks=True):
            if issue.level >= WARNING:
                record(issue.id, False, str(issue.msg), warning=issue.level < ERROR)
        frontend = options['frontend_dir'].resolve()
        record('frontend', (frontend / 'index.html').is_file() and any((frontend / 'assets').glob('*.js')),
               'Frontend compilado: se requieren index.html y assets; no usar Vite en producción.')
        static = Path(settings.STATIC_ROOT)
        record('static', (static / 'admin' / 'css' / 'base.css').is_file(),
               'Estáticos Django: ejecutar collectstatic antes de iniciar el servicio.')
        private = Path(settings.PRIVATE_DOCUMENT_ROOT)
        record('private_storage', private.is_dir() and os.access(private, os.R_OK | os.W_OK | os.X_OK),
               'El usuario del servicio debe acceder al directorio privado persistente; no se crean archivos durante esta prueba.')
        ca = settings.DATABASES['default'].get('OPTIONS', {}).get('sslrootcert')
        if ca:
            record('database_ca', Path(ca).is_file() and os.access(ca, os.R_OK), 'El certificado raíz PostgreSQL debe existir y ser legible en el servidor.')
        if options['services'] and not settings.DEBUG:
            try:
                if connection.settings_dict.get('OPTIONS', {}).get('sslmode') not in ['require','verify-ca','verify-full']:
                    raise ValueError()
                with connection.cursor() as cursor:
                    cursor.execute('SELECT 1')
                    assert cursor.fetchone()[0] == 1
                executor = MigrationExecutor(connection)
                pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
                record('database', True, 'Conexión PostgreSQL establecida; no se modificaron datos.')
                record('migrations', not pending, 'Hay migraciones pendientes.' if pending else 'Migraciones al día.')
            except Exception:
                record('database', False, 'No se pudo comprobar PostgreSQL y sus migraciones. Revisa conexión, TLS y permisos.')
            try:
                if settings.EMAIL_BACKEND != 'django.core.mail.backends.smtp.EmailBackend' or not settings.EMAIL_HOST or settings.EMAIL_USE_TLS == settings.EMAIL_USE_SSL:
                    raise ValueError()
                with get_connection(fail_silently=False) as smtp:
                    if smtp.connection is None:
                        raise ValueError()
                record('smtp', True, 'Conexión SMTP comprobada; autenticación según configuración. No se envió correo; falta comprobar entrega y DNS.')
            except Exception:
                record('smtp', False, 'No se pudo abrir SMTP seguro. Revisa host, puerto, cifrado y credenciales.')
            try:
                with socket.create_connection((settings.CLAMAV_HOST, settings.CLAMAV_PORT), timeout=5) as scanner:
                    scanner.settimeout(5)
                    scanner.sendall(b'zPING\0')
                    reply = scanner.recv(128).rstrip(b'\0\r\n')
                    if reply != b'PONG':
                        raise ValueError()
                record('antivirus', True, 'ClamAV respondió PONG. Verifica además sus firmas y una carga de prueba.')
            except Exception:
                record('antivirus', False, 'ClamAV no respondió correctamente. Las cargas permanecerán protegidas y fallarán si no puede analizarse el archivo.')
        else:
            record('services', True, 'Servicios externos sin comprobar: usa --services con el entorno real de producción.', warning=True)
        failed = any(row['status'] == 'error' or (options['strict'] and row['status'] == 'warning') for row in results)
        self.stdout.write(json.dumps({'ok':not failed, 'services_checked':bool(options['services'] and not settings.DEBUG),
                                     'checks':results}, ensure_ascii=False, indent=2))
        if failed:
            raise CommandError('La configuración todavía tiene bloqueos de producción; revisa el informe sin publicar secretos.')
