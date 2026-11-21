import importlib.util
import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command, CommandError
from django.test import SimpleTestCase, override_settings
from .checks import production_readiness

MODULE = 'accounts.management.commands.preflight_production'


class ProductionPreflightTests(SimpleTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.frontend = root / 'frontend'
        (self.frontend / 'assets').mkdir(parents=True)
        (self.frontend / 'assets' / 'app.js').write_text('test', encoding='utf-8')
        (self.frontend / 'index.html').write_text('test', encoding='utf-8')
        static = root / 'static'
        (static / 'admin' / 'css').mkdir(parents=True)
        (static / 'admin' / 'css' / 'base.css').write_text('test', encoding='utf-8')
        private = root / 'private'
        private.mkdir()
        self.configuration = override_settings(DEBUG=False, STATIC_ROOT=static, PRIVATE_DOCUMENT_ROOT=private,
            EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend', EMAIL_HOST='smtp.example.test', CLAMAV_HOST='scanner')
        self.configuration.enable()
        self.addCleanup(self.configuration.disable)

    @patch(MODULE + '.run_checks', return_value=[])
    @patch(MODULE + '.socket.create_connection')
    @patch(MODULE + '.get_connection')
    def test_default_checks_are_offline_and_do_not_claim_services_checked(self, smtp, scanner, checks):
        output = io.StringIO()
        call_command('preflight_production', frontend_dir=self.frontend, stdout=output)
        result = json.loads(output.getvalue())
        self.assertTrue(result['ok'])
        self.assertFalse(result['services_checked'])
        smtp.assert_not_called()
        scanner.assert_not_called()

    @patch(MODULE + '.run_checks', return_value=[])
    def test_missing_frontend_and_development_mode_are_blockers(self, checks):
        with override_settings(DEBUG=True), self.assertRaises(CommandError):
            call_command('preflight_production', frontend_dir=self.frontend / 'missing', stdout=io.StringIO())

    @override_settings(EMAIL_USE_TLS=False, EMAIL_USE_SSL=False)
    @patch(MODULE + '.run_checks', return_value=[])
    @patch(MODULE + '.socket.create_connection')
    @patch(MODULE + '.get_connection')
    def test_invalid_email_encryption_never_attempts_smtp_authentication(self, smtp, scanner, checks):
        with self.assertRaises(CommandError):
            call_command('preflight_production', frontend_dir=self.frontend, services=True, stdout=io.StringIO())
        smtp.assert_not_called()

    @patch(MODULE + '.run_checks', return_value=[])
    @patch(MODULE + '.MigrationExecutor')
    @patch(MODULE + '.connection')
    @patch(MODULE + '.socket.create_connection')
    @patch(MODULE + '.get_connection')
    def test_services_check_connections_without_email_or_database_writes(self, smtp, scanner, db, executor, checks):
        db.settings_dict = {'OPTIONS': {'sslmode':'verify-full'}}
        cursor = db.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (1,)
        executor.return_value.migration_plan.return_value = []
        scanner.return_value.__enter__.return_value.recv.return_value = b'PONG\0'
        output = io.StringIO()
        call_command('preflight_production', frontend_dir=self.frontend, services=True, stdout=output)
        result = json.loads(output.getvalue())
        self.assertTrue(result['ok'])
        self.assertTrue(result['services_checked'])
        cursor.execute.assert_called_once_with('SELECT 1')
        smtp.return_value.__enter__.return_value.send_messages.assert_not_called()

    @patch(MODULE + '.run_checks', return_value=[])
    @patch(MODULE + '.MigrationExecutor')
    @patch(MODULE + '.connection')
    @patch(MODULE + '.socket.create_connection', side_effect=OSError('PRIVATE-CREDENTIAL'))
    @patch(MODULE + '.get_connection', side_effect=OSError('PRIVATE-CREDENTIAL'))
    def test_service_errors_are_sanitized_and_pending_migrations_block(self, smtp, scanner, db, executor, checks):
        db.settings_dict = {'OPTIONS': {'sslmode':'verify-full'}}
        db.cursor.return_value.__enter__.return_value.fetchone.return_value = (1,)
        executor.return_value.migration_plan.return_value = [object()]
        output = io.StringIO()
        with self.assertRaises(CommandError):
            call_command('preflight_production', frontend_dir=self.frontend, services=True, stdout=output)
        self.assertNotIn('PRIVATE-CREDENTIAL', output.getvalue())
        errors = {row['check'] for row in json.loads(output.getvalue())['checks'] if row['status'] == 'error'}
        self.assertTrue({'smtp', 'antivirus', 'migrations'}.issubset(errors))


class ReleaseAllowlistTests(SimpleTestCase):
    def test_package_excludes_secrets_and_private_data(self):
        spec = importlib.util.spec_from_file_location('build_release', settings.BASE_DIR.parent / 'scripts' / 'build-release.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for filename in ['.env.shared', 'backend/.env', 'backend/backend.env', 'config/backend.env.private', 'backend/private_media/user.pdf',
                         'backups/data.json', 'backend/key.pem', 'backend/dev.sqlite3', '.git/config']:
            self.assertFalse(module.allowed(filename), filename)
        for filename in ['.env.example', 'backend/config/settings.py', 'deploy/nginx.conf.example', 'README.md']:
            self.assertTrue(module.allowed(filename), filename)

    def test_production_env_parser_never_evaluates_shell_content(self):
        spec = importlib.util.spec_from_file_location('production_manage', settings.BASE_DIR.parent / 'scripts' / 'production-manage.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'private.env'
            path.write_text('DJANGO_DEBUG=false\nDJANGO_SECRET_KEY="$(never-execute)"\n', encoding='utf-8')
            path.chmod(0o600)
            self.assertEqual(module.read_env(path)['DJANGO_SECRET_KEY'], '$(never-execute)')
            for text in ['PYTHONPATH=unexpected\n', 'DJANGO_DEBUG=false\nDJANGO_DEBUG=true\n', 'DJANGO_SECRET_KEY="unfinished\n']:
                path.write_text(text, encoding='utf-8')
                with self.assertRaises(ValueError):
                    module.read_env(path)


@override_settings(DEBUG=False, PUBLIC_APP_URL='https://volunteer.example.test',
    ALLOWED_HOSTS=['volunteer.example.test'], DATA_RETENTION_NOTICE='Texto institucional ficticio de prueba.',
    EMAIL_HOST='smtp.example.test', EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
    DEFAULT_FROM_EMAIL='Fundación de prueba <no-reply@example.test>', EMAIL_USE_TLS=True,
    EMAIL_USE_SSL=False, CLAMAV_HOST='scanner')
class ProductionConfigurationTests(SimpleTestCase):
    def identifiers(self):
        return {issue.id for issue in production_readiness(None)}

    def test_display_name_sender_is_valid_but_example_sender_is_blocked(self):
        self.assertNotIn('pro12.E006', self.identifiers())
        with override_settings(DEFAULT_FROM_EMAIL='no-reply@localhost'):
            self.assertIn('pro12.E006', self.identifiers())

    def test_smtp_requires_exactly_one_encryption_mode(self):
        for tls, ssl, valid in [(True,False,True),(False,True,True),(False,False,False),(True,True,False)]:
            with override_settings(EMAIL_USE_TLS=tls, EMAIL_USE_SSL=ssl):
                self.assertEqual('pro12.E007' not in self.identifiers(), valid)

    def test_public_origin_cannot_include_credentials_or_a_path(self):
        for url in ['https://user:password@volunteer.example.test','https://volunteer.example.test/private',
                    'https://volunteer.example.test/?secret=test']:
            with override_settings(PUBLIC_APP_URL=url):
                self.assertIn('pro12.E008', self.identifiers())

    def test_relative_private_directory_is_not_a_production_destination(self):
        with override_settings(PRIVATE_DOCUMENT_ROOT=Path('relative-private')):
            self.assertIn('pro12.E009', self.identifiers())
