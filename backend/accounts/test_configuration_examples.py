import importlib.util
from pathlib import Path
import re

from django.conf import settings
from django.test import SimpleTestCase

ROOT = settings.BASE_DIR.parent


def template(path):
    pairs = [line.split('=', 1) for line in path.read_text(encoding='utf-8').splitlines()
             if line.strip() and not line.lstrip().startswith('#')]
    keys = [key.strip() for key, _ in pairs]
    if len(set(keys)) != len(keys):
        raise AssertionError('La plantilla contiene claves duplicadas.')
    return {key.strip(): value.strip() for key, value in pairs}


class ConfigurationExamplesTests(SimpleTestCase):
    def test_production_template_matches_the_production_reader_without_secrets(self):
        spec = importlib.util.spec_from_file_location('production_manage', ROOT / 'scripts/production-manage.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        values = template(ROOT / '.env.example')
        self.assertEqual(set(values), module.NAMES)
        self.assertEqual(values['DJANGO_DEBUG'], 'false')
        self.assertEqual(values['POSTGRES_SSLMODE'], 'verify-full')
        for name in ['DJANGO_SECRET_KEY', 'POSTGRES_PASSWORD', 'EMAIL_HOST_PASSWORD', 'GEOAPIFY_API_KEY']:
            self.assertEqual(values[name], '')

    def test_shared_template_matches_the_shared_reader_without_secrets(self):
        text = (ROOT / 'scripts/load-shared-env.ps1').read_text(encoding='utf-8')
        declaration = re.search(r'\$allowedNames\s*=\s*@\(([^)]+)\)', text).group(1)
        supported = set(re.findall(r"'([A-Z_]+)'", declaration))
        values = template(ROOT / 'config/shared-database.env.example')
        self.assertEqual(set(values), supported)
        self.assertEqual(values['POSTGRES_PORT'], '6543')
        for name in ['DJANGO_SECRET_KEY', 'POSTGRES_PASSWORD', 'GEOAPIFY_API_KEY']:
            self.assertEqual(values[name], '')
