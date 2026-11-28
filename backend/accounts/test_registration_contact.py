import json

from django.test import TestCase

from .models import User, VolunteerProfile


class VolunteerRegistrationContactTests(TestCase):
    def setUp(self):
        self.data = {'email': 'registro-contacto@example.org', 'password': 'Long-example-password-998!',
                     'first_name': 'Ana', 'last_name': 'Pérez', 'adult': True, 'privacy': True,
                     'account_type': 'volunteer', 'whatsapp': True, 'phone': '912345678', 'commune': ' renca '}

    def register(self, data, **extra):
        return self.client.post('/api/register/', json.dumps(data), content_type='application/json', **extra)

    def test_registration_persists_contact_and_canonical_commune_and_allows_login(self):
        response = self.register(self.data)
        self.assertEqual(response.status_code, 201)
        profile = VolunteerProfile.objects.get(user__email=self.data['email'])
        self.assertEqual(profile.phone, '+56912345678')
        self.assertEqual(profile.commune, 'Renca')
        self.assertTrue(profile.user.is_active)
        self.assertIsNotNone(profile.whatsapp_opt_in_at)
        self.assertFalse(profile.user.is_staff)
        login = self.client.post('/api/login/', json.dumps({
            'email': self.data['email'], 'password': self.data['password']}), content_type='application/json')
        self.assertEqual(login.status_code, 200)

    def test_missing_blank_invented_or_overlong_contact_is_rejected_without_creating_account(self):
        for index, (field, value) in enumerate([('phone', None), ('phone', ''), ('phone', '   '),
                             ('phone', '+569123456789'), ('phone', 'abcdefghijk'),
                             ('phone', '+12125550199'), ('phone', '225551234'),
                             ('commune', None), ('commune', ''), ('commune', 'juanita'), ('commune', 'ren'), ('whatsapp', False), ('whatsapp', None)], 1):
            with self.subTest(field=field, value=value):
                data = {**self.data, field: value}
                if value is None:
                    del data[field]
                response = self.register(data, REMOTE_ADDR=f'192.0.2.{index}')
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())
                self.assertFalse(User.objects.filter(email=self.data['email']).exists())
