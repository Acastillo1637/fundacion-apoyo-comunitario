import json

from django.test import SimpleTestCase, TestCase
from django.contrib.auth.models import Group
from django.utils import timezone

from .communes import COMMUNES
from .serializers import ProfileSerializer
from .models import User, VolunteerProfile


class CommuneValidationTests(SimpleTestCase):
    def test_catalogue_and_normalization(self):
        self.assertEqual(len(COMMUNES), 346)
        self.assertEqual(len(set(COMMUNES)), 346)
        for supplied, expected in [('renca', 'Renca'), (' MAIPU ', 'Maipú'), ('nunoa', 'Ñuñoa')]:
            serializer = ProfileSerializer(data={'first_name': 'Ana', 'last_name': 'Pérez',
                                                'phone': '+56912345678', 'commune': supplied})
            self.assertTrue(serializer.is_valid(), serializer.errors)
            self.assertEqual(serializer.validated_data['commune'], expected)


class ProfileRequiredDataTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('comunas@example.org', 'Example-password-2359!', first_name='Ana')
        self.user.groups.add(Group.objects.get_or_create(name='Voluntario')[0])
        VolunteerProfile.objects.create(user=self.user, adult_confirmed_at=timezone.now(), privacy_accepted_at=timezone.now())

    def test_invalid_or_missing_profile_fields_do_not_save(self):
        self.client.force_login(self.user)
        original_name = self.user.first_name
        base = {'first_name': 'Cambio', 'last_name': 'Pérez', 'phone': '+56912345678', 'commune': 'Renca'}
        for field, value in [('commune', 'juanita'), ('commune', 'ren'), ('commune', ''),
                             ('commune', '   '), ('phone', ''), ('first_name', ''), ('last_name', '')]:
            with self.subTest(field=field, value=value):
                response = self.client.patch('/api/profile/', json.dumps({**base, field: value}), content_type='application/json')
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())
                self.user.refresh_from_db()
                self.assertEqual(self.user.first_name, original_name)

    def test_commune_catalogue_is_public_for_registration(self):
        public = self.client.get('/api/communes/')
        self.assertEqual(public.status_code, 200)
        self.assertEqual(set(public.json()), {'communes'})
        self.assertEqual(len(public.json()['communes']), 346)
        self.client.force_login(self.user)
        response = self.client.get('/api/communes/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Renca', response.json()['communes'])
