"""One-time, non-destructive SQLite -> empty PostgreSQL data import."""
import hashlib
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from django.apps import apps
from django.conf import settings
from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.core.management.color import no_style
from django.db import connections, transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone


APP_ORDER = ['accounts', 'volunteers', 'documents', 'activities', 'account', 'mfa', 'admin']
EXCLUDED = {'accounts.RateBucket', 'accounts.AccountManagementGuard'}


def serialized(models, alias):
    rows = (row for model in models for row in model._base_manager.using(alias).order_by('pk'))
    return serializers.serialize('json', rows, use_natural_foreign_keys=True, use_natural_primary_keys=False)


def digest(payload):
    records = json.loads(payload)
    for record in records:
        model = apps.get_model(record['model'])
        for field in model._meta.local_many_to_many:
            if field.name in record['fields']:
                record['fields'][field.name].sort(key=lambda value: json.dumps(value, sort_keys=True))
    return hashlib.sha256(json.dumps(records, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


class Command(BaseCommand):
    help = 'Importa una instantanea local a PostgreSQL vacio; sin --apply solo comprueba.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        target = connections['default']
        if target.vendor != 'postgresql':
            raise CommandError('Este comando requiere la conexion PostgreSQL compartida.')
        source_path = settings.BASE_DIR / 'dev.sqlite3'
        if not source_path.is_file():
            raise CommandError('No existe la base local dev.sqlite3.')
        models = [model for app in APP_ORDER for model in apps.get_app_config(app).get_models()
                  if model._meta.label not in EXCLUDED]
        target.ensure_connection()
        executor = MigrationExecutor(target)
        if executor.migration_plan(executor.loader.graph.leaf_nodes()):
            raise CommandError('Aplica primero las migraciones pendientes en Supabase.')
        if any(model._base_manager.using('default').exists() for model in models):
            raise CommandError('Destino con datos: se cancela para no sobrescribir ni duplicar registros.')
        backup_dir = settings.BASE_DIR.parent / 'backups' / f"local-to-shared-{timezone.now():%Y%m%dT%H%M%S}-{uuid4().hex[:8]}"
        backup_dir.mkdir(parents=True)
        snapshot = backup_dir / 'source.sqlite3'
        # SQLite's backup API captures a consistent snapshot, including WAL commits.
        with sqlite3.connect(source_path.as_uri() + '?mode=ro', uri=True) as source:
            with sqlite3.connect(snapshot) as destination:
                source.backup(destination)
        config = dict(connections.databases['default'])
        config.update(ENGINE='django.db.backends.sqlite3', NAME=snapshot.as_uri() + '?mode=ro',
                      USER='', PASSWORD='', HOST='', PORT='', OPTIONS={'uri': True}, CONN_MAX_AGE=0)
        connections.databases['local_snapshot'] = config
        alias = 'local_snapshot'
        try:
            pending = MigrationExecutor(connections[alias])
            if pending.migration_plan(pending.loader.graph.leaf_nodes()):
                raise CommandError('La base local tiene migraciones pendientes. No se importo nada.')
            if apps.get_model('mfa', 'Authenticator').objects.using(alias).exists():
                raise CommandError('Hay factores MFA: prepara primero su migracion de claves. Destino sin cambios.')
            if apps.get_model('documents', 'VolunteerDocument').objects.using(alias).exists():
                raise CommandError('Hay documentos privados: prepara tambien el traslado de archivos. Destino sin cambios.')
            payload = serialized(models, alias)
            (backup_dir / 'application-data.json').write_text(payload, encoding='utf-8')
            source_counts = {model._meta.label: model._base_manager.using(alias).count() for model in models}
            Group = apps.get_model('auth', 'Group')
            Permission = apps.get_model('auth', 'Permission')
            groups = [{'name': group.name, 'permissions': [list(permission.natural_key()) for permission in group.permissions.all()]}
                      for group in Group.objects.using(alias).order_by('name')]
            (backup_dir / 'groups.json').write_text(json.dumps(groups, ensure_ascii=True), encoding='utf-8')
            manifest = {'counts': source_counts, 'data_sha256': digest(payload), 'status': 'prepared'}
            manifest_path = backup_dir / 'manifest.json'
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
            for label, count in source_counts.items():
                if count:
                    self.stdout.write(f'{label}: {count}')
            self.stdout.write(f'Respaldo privado: {backup_dir}')
            if not options['apply']:
                self.stdout.write('Comprobacion completada. Sin escrituras en Supabase. Usa --apply para importar.')
                return
            with transaction.atomic():
                # Block concurrent writes until emptiness checks and verification finish.
                lock_models = [*models, Group, Group.permissions.through]
                lock_models += [field.remote_field.through for model in models for field in model._meta.local_many_to_many]
                tables = sorted({target.ops.quote_name(model._meta.db_table) for model in lock_models})
                with target.cursor() as cursor:
                    cursor.execute("SET LOCAL lock_timeout = '10s'")
                    cursor.execute('LOCK TABLE ' + ', '.join(tables) + ' IN SHARE ROW EXCLUSIVE MODE')
                if any(model._base_manager.using('default').exists() for model in models):
                    raise CommandError('El destino cambio durante la preparacion. Importacion cancelada.')
                # Permissions are resolved by their natural names, never SQLite IDs.
                for entry in groups:
                    group, _ = Group.objects.using('default').get_or_create(name=entry['name'])
                    permissions = [Permission.objects.db_manager('default').get_by_natural_key(*key) for key in entry['permissions']]
                    group.permissions.set(permissions)
                deferred = []
                with target.constraint_checks_disabled():
                    for item in serializers.deserialize('json', payload, using='default', handle_forward_references=True):
                        item.save(using='default')
                        if item.deferred_fields:
                            deferred.append(item)
                    for item in deferred:
                        item.save_deferred_fields(using='default')
                    target.check_constraints()
                with target.cursor() as cursor:
                    for statement in target.ops.sequence_reset_sql(no_style(), [*models, Group]):
                        cursor.execute(statement)
                if source_counts != {model._meta.label: model._base_manager.using('default').count() for model in models}:
                    raise CommandError('No coinciden los conteos. Se revierte la importacion.')
                if digest(serialized(models, 'default')) != manifest['data_sha256']:
                    raise CommandError('No coincide el contenido. Se revierte la importacion.')
            manifest['status'] = 'imported_and_verified'
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
            self.stdout.write(self.style.SUCCESS('Importacion confirmada. Conteos y contenido verificados; SQLite original intacto.'))
        finally:
            connections[alias].close()
