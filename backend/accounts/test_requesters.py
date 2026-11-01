import uuid
from datetime import timedelta

from allauth.account.models import EmailAddress
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from activities.models import RequestTransition, ServiceRequest
from .models import RequesterProfile, User, VolunteerProfile
from .views import user_data


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class RequesterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        cls.user = User.objects.create_user('entity@example.org', first_name='Ana', last_name='Perez')
        cls.user.groups.add(Group.objects.get(name='Solicitante'))
        EmailAddress.objects.create(user=cls.user, email=cls.user.email, verified=True, primary=True)
        cls.profile = RequesterProfile.objects.create(user=cls.user, requester_type='company', organization='Empresa de prueba', phone='+56912345678', adult_confirmed_at=timezone.now(), privacy_accepted_at=timezone.now(), representative_confirmed_at=timezone.now())

    def setUp(self):
        self.client.force_login(self.user)

    def registration(self, **changes):
        return {'email': 'new@example.org', 'first_name': 'Nueva', 'last_name': 'Persona',
                'password': 'Very-long-example-password-329!', 'account_type': 'requester',
                'requester_type': 'company', 'organization': 'Entidad', 'phone': '+56912345678',
                'adult': True, 'privacy': True, 'authorized_representative': True, **changes}

    def payload(self, **changes):
        return {'submission_id': str(uuid.uuid4()), 'description': 'Necesitamos apoyo para una jornada comunitaria.',
                'quantity': 3, 'date': str(timezone.localdate() + timedelta(days=30)),
                'start_time': '10:00', 'end_time': '12:00', 'address': 'Lugar de prueba 123',
                'commune': 'Santiago', 'skills': [], 'privacy': True, **changes}

    def post(self, data):
        return self.client.post('/api/requester/requests/', data, content_type='application/json')

    def test_entity_registration_creates_only_requester_profile(self):
        self.client.logout()
        response = self.client.post('/api/register/', self.registration(), content_type='application/json')
        self.assertEqual(response.status_code, 202)
        user = User.objects.get(email='new@example.org')
        self.assertEqual(list(user.groups.values_list('name', flat=True)), ['Solicitante'])
        self.assertFalse(VolunteerProfile.objects.filter(user=user).exists())
        self.assertIsNotNone(user.requester_profile.representative_confirmed_at)

    def test_entity_registration_requires_authorization_and_name(self):
        for changes in [{'authorized_representative': False}, {'organization': ''}]:
            with self.subTest(changes=changes):
                response = self.client.post('/api/register/', self.registration(**changes), content_type='application/json')
                self.assertEqual(response.status_code, 400)

    def test_self_registration_cannot_choose_staff_role(self):
        response = self.client.post('/api/register/', self.registration(account_type='administration'), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(email='new@example.org').exists())

    def test_person_and_institution_profiles(self):
        for kind in ['person', 'institution']:
            response = self.client.post('/api/register/', self.registration(email=f'{kind}@example.org', requester_type=kind), content_type='application/json')
            self.assertEqual(response.status_code, 202)
            profile = RequesterProfile.objects.get(user__email=f'{kind}@example.org')
            self.assertEqual(profile.organization, '' if kind == 'person' else 'Entidad')

    def test_spaces_follow_roles_not_accidental_profile_records(self):
        now = timezone.now()
        VolunteerProfile.objects.create(user=self.user, adult_confirmed_at=now, privacy_accepted_at=now)
        self.assertEqual(user_data(self.user)['available_portals'], ['requester'])
        self.user.groups.add(Group.objects.get(name='Voluntario'))
        self.assertEqual(user_data(self.user)['available_portals'], ['volunteer', 'requester'])
        staff = User.objects.create_user('staff@example.org')
        staff.groups.add(Group.objects.get(name='Administrador general'))
        self.assertEqual(user_data(staff)['available_portals'], ['administration', 'operations'])
        secretary = User.objects.create_user('secretary@example.org')
        secretary.groups.add(Group.objects.get(name='Secretaría'))
        self.assertEqual(user_data(secretary)['available_portals'], ['operations'])

    def test_requester_cannot_use_volunteer_or_administrative_endpoints(self):
        for path in ['profile/', 'volunteer/qualifications/', 'volunteer/availability/', 'documents/', 'management/users/', 'activities/operations/requests/']:
            with self.subTest(path=path):
                self.assertEqual(self.client.get('/api/' + path).status_code, 403)
        self.assertEqual(self.client.post('/api/profile/onboarding/', {}, content_type='application/json').status_code, 403)

    def test_verified_owner_submits_without_another_email_and_retry_is_idempotent(self):
        payload = self.payload()
        self.assertEqual(self.post(payload).status_code, 201)
        self.assertEqual(self.post(payload).status_code, 200)
        item = ServiceRequest.objects.get()
        self.assertEqual(item.requester, self.profile)
        self.assertEqual(item.organization, self.profile.organization)
        self.assertEqual(item.email, self.user.email)
        self.assertIsNotNone(item.email_verified_at)
        self.assertEqual(item.status, 'pending')

    def test_cannot_override_owner_contact_or_status(self):
        for field, value in [('requester', self.profile.pk), ('status', 'approved'), ('email', 'other@example.org'), ('organization', 'Other')]:
            with self.subTest(field=field):
                self.assertEqual(self.post(self.payload(**{field: value})).status_code, 400)
        self.assertFalse(ServiceRequest.objects.exists())

    def test_no_email_based_claiming_or_cross_owner_access(self):
        self.post(self.payload())
        item = ServiceRequest.objects.get()
        item.requester = None
        item.save(update_fields=['requester'])
        self.assertEqual(self.client.get('/api/requester/requests/').json()['count'], 0)
        self.assertEqual(self.client.get(f'/api/requester/requests/{item.pk}/').status_code, 404)
        self.assertEqual(self.post(self.payload(submission_id=str(item.submission_id))).status_code, 409)
        other = User.objects.create_user('other-requester@example.org')
        other.groups.add(Group.objects.get(name='Solicitante'))
        EmailAddress.objects.create(user=other, email=other.email, verified=True)
        self.client.force_login(other)
        self.assertEqual(self.client.get(f'/api/requester/requests/{item.pk}/').status_code, 404)
        item.requester = self.profile
        item.save(update_fields=['requester'])
        self.assertEqual(self.client.get(f'/api/requester/requests/{item.pk}/').status_code, 404)

    def test_history_does_not_expose_internal_notes_or_staff(self):
        self.post(self.payload())
        item = ServiceRequest.objects.get()
        RequestTransition.objects.create(request=item, actor=self.user, from_status='pending', to_status='in_review', reason='Confidential internal reason')
        data = self.client.get(f'/api/requester/requests/{item.pk}/').json()
        self.assertEqual(set(data['history'][0]), {'status', 'at'})
        self.assertNotIn('Confidential', str(data))

    def test_profile_revision_and_representation_validation(self):
        data = {'first_name': 'Ana', 'last_name': 'Nueva', 'requester_type': 'institution',
                'organization': 'Institucion', 'phone': '+56912345678', 'commune': 'Santiago',
                'revision': 0, 'adult': True, 'privacy': True, 'authorized_representative': False}
        self.assertEqual(self.client.put('/api/requester/profile/', data, content_type='application/json').status_code, 400)
        data['authorized_representative'] = True
        self.assertEqual(self.client.put('/api/requester/profile/', data, content_type='application/json').status_code, 200)
        self.assertEqual(self.client.put('/api/requester/profile/', data, content_type='application/json').status_code, 409)
        self.user.refresh_from_db()
        self.assertEqual(self.user.last_name, 'Nueva')
        self.assertEqual(self.user.management_revision, 1)

    def test_unverified_requester_cannot_submit_or_onboard(self):
        EmailAddress.objects.filter(user=self.user).update(verified=False)
        self.assertEqual(self.post(self.payload()).status_code, 403)
        self.assertEqual(self.client.get('/api/requester/profile/').status_code, 403)

    def test_invited_requester_can_complete_own_profile(self):
        self.profile.delete()
        data = {'first_name': 'Ana', 'last_name': 'Perez', 'requester_type': 'person', 'phone': '+56912345678',
                'commune': '', 'revision': 0, 'adult': True, 'privacy': True}
        self.assertIsNone(self.client.get('/api/requester/profile/').json()['profile'])
        self.assertEqual(self.client.put('/api/requester/profile/', data, content_type='application/json').status_code, 200)
        self.assertTrue(RequesterProfile.objects.filter(user=self.user).exists())
