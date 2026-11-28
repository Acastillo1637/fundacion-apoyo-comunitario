import json
import os
import subprocess
import sys

from django.conf import settings
from django.test import Client, SimpleTestCase


class DevelopmentOriginTests(SimpleTestCase):
    def configured_origins(self, debug):
        env = {**os.environ, 'DJANGO_DEBUG': 'true' if debug else 'false',
               'DJANGO_CSRF_TRUSTED_ORIGINS': 'https://fundacion.example.test',
               'DJANGO_SECRET_KEY': 'isolated-settings-test-only-never-deploy-this-value-9284',
               'DATABASE_ENGINE': 'postgresql'}
        result = subprocess.run([sys.executable, '-c',
            'import json; from config.settings import CSRF_TRUSTED_ORIGINS; print(json.dumps(CSRF_TRUSTED_ORIGINS))'],
            cwd=settings.BASE_DIR, env=env, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)

    def test_development_accepts_both_local_vite_ports_with_valid_csrf(self):
        origins = self.configured_origins(True)
        for origin in ['http://127.0.0.1:5173', 'http://127.0.0.1:5174',
                       'http://localhost:5173', 'http://localhost:5174']:
            with self.subTest(origin=origin), self.settings(CSRF_TRUSTED_ORIGINS=origins):
                client = Client(enforce_csrf_checks=True)
                token = client.get('/api/session/').json()['csrf_token']
                response = client.post('/api/logout/', {}, content_type='application/json',
                    HTTP_ORIGIN=origin, HTTP_X_CSRFTOKEN=token)
                self.assertEqual(response.status_code, 200)

    def test_production_does_not_implicitly_trust_local_origins(self):
        self.assertEqual(self.configured_origins(False), ['https://fundacion.example.test'])

    def test_local_origin_still_requires_csrf_token_and_rejects_unknown_origins(self):
        with self.settings(CSRF_TRUSTED_ORIGINS=self.configured_origins(True)):
            client = Client(enforce_csrf_checks=True)
            token = client.get('/api/session/').json()['csrf_token']
            self.assertEqual(client.post('/api/logout/', {}, content_type='application/json',
                HTTP_ORIGIN='http://127.0.0.1:5174').status_code, 403)
            self.assertEqual(client.post('/api/logout/', {}, content_type='application/json',
                HTTP_ORIGIN='https://untrusted.example.test', HTTP_X_CSRFTOKEN=token).status_code, 403)
