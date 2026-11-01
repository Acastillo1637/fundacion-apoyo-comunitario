from concurrent.futures import ThreadPoolExecutor
from datetime import time
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.db import IntegrityError, close_old_connections, connection, connections, transaction
from django.test import Client, TestCase, TransactionTestCase
from django.test import override_settings
from django.utils import timezone

from accounts.models import AuditEvent, User, VolunteerProfile
from .models import AvailabilitySlot, DocumentType, Profession, Skill, UnavailableDate, VolunteerProfession, VolunteerSkill


def make_profile(email):
    user = User.objects.create_user(email=email, first_name='Persona de prueba')
    user.groups.add(Group.objects.get_or_create(name='Voluntario')[0])
    now = timezone.now()
    return VolunteerProfile.objects.create(user=user, adult_confirmed_at=now, privacy_accepted_at=now)


class VolunteerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.profile = make_profile('voluntario@example.org')
        cls.other = make_profile('otro@example.org')
        cls.skill = Skill.objects.create(name='Primeros auxilios')
        cls.inactive_skill = Skill.objects.create(name='Habilidad retirada', is_active=False)
        cls.profession = Profession.objects.create(name='Enfermería')
        cls.document = DocumentType.objects.create(name='Respaldo profesional')
        cls.profession.required_documents.add(cls.document)

    def setUp(self):
        self.client.force_login(self.profile.user)

    def put(self, path, data, client=None):
        return (client or self.client).put(f'/api/volunteer/{path}/', data, content_type='application/json')

    def qualifications(self, **overrides):
        return {'revision': 0, 'skills': [self.skill.pk], 'professions': [self.profession.pk], **overrides}

    def availability(self, **overrides):
        return {
            'revision': 0,
            'slots': [{'weekday': 0, 'start_time': '18:00', 'end_time': '22:00'}],
            'unavailable_dates': ['2027-01-04'],
            **overrides,
        }

    def test_resources_require_authentication(self):
        self.client.logout()
        for resource in ['catalogs', 'qualifications', 'availability']:
            with self.subTest(resource=resource):
                self.assertEqual(self.client.get(f'/api/volunteer/{resource}/').status_code, 403)

    def test_no_profile_returns_not_found_without_creating_one(self):
        user = User.objects.create_user('administrador@example.org')
        user.groups.add(Group.objects.get_or_create(name='Voluntario')[0])
        self.client.force_login(user)
        self.assertEqual(self.client.get('/api/volunteer/qualifications/').status_code, 404)
        self.assertFalse(VolunteerProfile.objects.filter(user=user).exists())

    def test_catalog_includes_active_entries_and_document_requirements(self):
        data = self.client.get('/api/volunteer/catalogs/').json()
        self.assertEqual([item['id'] for item in data['skills']], [self.skill.pk])
        self.assertEqual(data['professions'][0]['required_documents'][0]['id'], self.document.pk)

    def test_selected_inactive_entry_remains_visible(self):
        VolunteerSkill.objects.create(profile=self.profile, skill=self.inactive_skill)
        data = self.client.get('/api/volunteer/catalogs/').json()
        self.assertIn(self.inactive_skill.pk, [item['id'] for item in data['skills']])

    def test_qualifications_are_saved_as_declared_and_audited(self):
        response = self.put('qualifications', self.qualifications())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'declared')
        self.assertEqual(response.json()['revision'], 1)
        self.assertTrue(VolunteerProfession.objects.filter(profile=self.profile, profession=self.profession).exists())
        self.assertTrue(AuditEvent.objects.filter(actor=self.profile.user, action='qualifications.updated', resource=f'profile:{self.profile.pk}').exists())

    def test_qualifications_cannot_update_other_users_or_validation(self):
        for field, value in [('profile', self.other.pk), ('user', str(self.other.user_id)), ('status', 'validated'), ('verified', True)]:
            with self.subTest(field=field):
                self.assertEqual(self.put('qualifications', self.qualifications(**{field: value})).status_code, 400)
        self.assertEqual(VolunteerSkill.objects.count(), 0)

    def test_unknown_or_duplicate_catalog_choices_are_rejected(self):
        for ids in [[999999], [self.skill.pk, self.skill.pk]]:
            with self.subTest(ids=ids):
                self.assertEqual(self.put('qualifications', self.qualifications(skills=ids)).status_code, 400)
        self.assertEqual(VolunteerSkill.objects.count(), 0)

    def test_cannot_add_inactive_entry(self):
        response = self.put('qualifications', self.qualifications(skills=[self.inactive_skill.pk]))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(VolunteerSkill.objects.count(), 0)

    def test_inactive_entry_can_be_retained_or_removed(self):
        VolunteerSkill.objects.create(profile=self.profile, skill=self.inactive_skill)
        response = self.put('qualifications', self.qualifications(skills=[self.inactive_skill.pk]))
        self.assertEqual(response.status_code, 200)
        response = self.put('qualifications', self.qualifications(revision=1, skills=[], professions=[]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.profile.declared_skills.count(), 0)
        self.assertEqual(self.put('qualifications', self.qualifications(revision=2, skills=[self.inactive_skill.pk])).status_code, 400)

    def test_stale_qualifications_cannot_overwrite_newer_data(self):
        self.put('qualifications', self.qualifications())
        response = self.put('qualifications', self.qualifications(skills=[], professions=[]))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.profile.declared_skills.count(), 1)

    def test_bad_profession_does_not_partially_save_skills(self):
        response = self.put('qualifications', self.qualifications(professions=[999999]))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.profile.declared_skills.count(), 0)

    def test_availability_round_trip_and_timezone(self):
        response = self.put('availability', self.availability())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['slots'], self.availability()['slots'])
        self.assertEqual(response.json()['unavailable_dates'], ['2027-01-04'])
        self.assertEqual(response.json()['timezone'], 'America/Santiago')
        self.assertEqual(self.client.get('/api/volunteer/availability/').json()['revision'], 1)

    def test_overlap_duplicate_reversed_and_zero_length_slots_are_rejected(self):
        for slots in [
            [{'weekday': 0, 'start_time': '18:00', 'end_time': '22:00'}, {'weekday': 0, 'start_time': '21:00', 'end_time': '23:00'}],
            [{'weekday': 0, 'start_time': '18:00', 'end_time': '22:00'}] * 2,
            [{'weekday': 0, 'start_time': '22:00', 'end_time': '18:00'}],
            [{'weekday': 0, 'start_time': '18:00', 'end_time': '18:00'}],
        ]:
            with self.subTest(slots=slots):
                self.assertEqual(self.put('availability', self.availability(slots=slots)).status_code, 400)
        self.assertEqual(AvailabilitySlot.objects.count(), 0)

    def test_adjacent_slots_and_same_time_on_different_days_are_allowed(self):
        slots = [
            {'weekday': 0, 'start_time': '09:00', 'end_time': '12:00'},
            {'weekday': 0, 'start_time': '12:00', 'end_time': '14:00'},
            {'weekday': 1, 'start_time': '09:00', 'end_time': '12:00'},
        ]
        self.assertEqual(self.put('availability', self.availability(slots=slots)).status_code, 200)

    def test_invalid_days_times_and_injected_owner_are_rejected(self):
        for slot in [
            {'weekday': -1, 'start_time': '09:00', 'end_time': '12:00'},
            {'weekday': 7, 'start_time': '09:00', 'end_time': '12:00'},
            {'weekday': 0, 'start_time': '25:00', 'end_time': '26:00'},
            {'weekday': 0, 'start_time': '09:00:15', 'end_time': '12:00'},
            {'weekday': 0, 'start_time': '09:00', 'end_time': '12:00', 'profile': self.other.pk},
        ]:
            with self.subTest(slot=slot):
                self.assertEqual(self.put('availability', self.availability(slots=[slot])).status_code, 400)

    def test_dates_must_be_valid_and_unique(self):
        for dates in [['2027-02-30'], ['2027-01-04', '2027-01-04']]:
            self.assertEqual(self.put('availability', self.availability(unavailable_dates=dates)).status_code, 400)

    def test_limits_prevent_oversized_schedules_and_qualifications(self):
        self.assertEqual(self.put('availability', self.availability(slots=self.availability()['slots'] * 43)).status_code, 400)
        self.assertEqual(self.put('availability', self.availability(unavailable_dates=['2027-01-01'] * 61)).status_code, 400)
        self.assertEqual(self.put('qualifications', self.qualifications(skills=[self.skill.pk] * 51)).status_code, 400)

    def test_availability_changes_affect_only_own_profile(self):
        AvailabilitySlot.objects.create(profile=self.other, weekday=1, start_time=time(9), end_time=time(12))
        self.assertEqual(self.put('availability', self.availability()).status_code, 200)
        self.assertEqual(self.other.availability_slots.count(), 1)
        self.assertEqual(self.put('availability', self.availability(profile=self.other.pk, revision=1)).status_code, 400)

    def test_stale_schedule_cannot_overwrite_and_empty_schedule_can_be_saved(self):
        self.put('availability', self.availability())
        self.assertEqual(self.put('availability', self.availability(slots=[])).status_code, 409)
        self.assertEqual(self.profile.availability_slots.count(), 1)
        self.assertEqual(self.put('availability', self.availability(revision=1, slots=[], unavailable_dates=[])).status_code, 200)
        self.assertEqual(self.profile.availability_slots.count(), 0)
        self.assertEqual(self.profile.unavailable_dates.count(), 0)

    def test_invalid_schedule_does_not_erase_existing_data(self):
        self.put('availability', self.availability())
        self.assertEqual(self.put('availability', self.availability(revision=1, unavailable_dates=['invalid'])).status_code, 400)
        self.assertEqual(self.profile.availability_slots.count(), 1)
        self.assertEqual(self.profile.unavailable_dates.count(), 1)

    def test_mutations_require_csrf_even_for_authenticated_users(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.profile.user)
        for path, data in [('qualifications', self.qualifications()), ('availability', self.availability())]:
            with self.subTest(path=path):
                self.assertEqual(self.put(path, data, client).status_code, 403)

    def test_catalogs_are_read_only_through_volunteer_api(self):
        self.assertEqual(self.client.post('/api/volunteer/catalogs/', {'name': 'Nueva'}).status_code, 405)
        self.assertEqual(self.client.get('/admin/volunteers/skill/add/').status_code, 403)

    def test_catalog_admin_requires_model_permission_and_mfa(self):
        self.profile.user.is_staff = True
        self.profile.user.save()
        self.profile.user.user_permissions.add(Permission.objects.get(codename='add_skill'))
        self.assertEqual(self.client.get('/admin/volunteers/skill/add/').status_code, 403)
        session = self.client.session
        session['account_authentication_methods_user'] = str(self.profile.user_id)
        session['account_authentication_methods'] = [{'method': 'mfa', 'at': timezone.now().timestamp()}]
        session.save()
        response = self.client.post('/admin/volunteers/skill/add/', {'name': 'Conducción', 'description': 'Apoyo logístico', 'is_active': 'on', '_save': 'Guardar'})
        self.assertEqual(response.status_code, 302)
        skill = Skill.objects.get(name='Conducción')
        self.assertTrue(AuditEvent.objects.filter(actor=self.profile.user, action='catalog.created', resource=f'volunteers.skill:{skill.pk}').exists())
        self.assertEqual(self.client.get('/admin/volunteers/profession/add/').status_code, 403)

    def test_role_setup_is_idempotent_and_does_not_grant_catalog_edits_to_volunteers(self):
        call_command('setup_roles', verbosity=0)
        call_command('setup_roles', verbosity=0)
        self.assertEqual(Group.objects.get(name='Voluntario').permissions.count(), 0)
        self.assertTrue(Group.objects.get(name='Administrador general').permissions.filter(codename='change_skill').exists())
        self.assertFalse(Group.objects.get(name='Secretaría').permissions.filter(codename='change_skill').exists())

    @override_settings(DEBUG=True)
    def test_seed_is_repeatable_and_preserves_catalog_edits(self):
        self.skill.name = 'PRIMEROS AUXILIOS'
        self.skill.is_active = False
        self.skill.save()
        call_command('seed_catalogs', verbosity=0)
        before = (Skill.objects.count(), Profession.objects.count(), DocumentType.objects.count())
        call_command('seed_catalogs', verbosity=0)
        self.assertEqual(before, (Skill.objects.count(), Profession.objects.count(), DocumentType.objects.count()))
        self.skill.refresh_from_db()
        self.assertFalse(self.skill.is_active)
        self.assertEqual(self.skill.name, 'PRIMEROS AUXILIOS')

    @override_settings(DEBUG=False)
    def test_seed_refuses_production(self):
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            call_command('seed_catalogs', verbosity=0)

    def test_database_rejects_case_insensitive_duplicate_catalog_names(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Skill.objects.create(name=self.skill.name.upper())

    def test_database_rejects_invalid_duration_and_duplicate_exceptions(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            AvailabilitySlot.objects.create(profile=self.profile, weekday=0, start_time=time(18), end_time=time(9))
        UnavailableDate.objects.create(profile=self.profile, date='2027-01-04')
        with self.assertRaises(IntegrityError), transaction.atomic():
            UnavailableDate.objects.create(profile=self.profile, date='2027-01-04')


@skipUnless(connection.vendor == 'postgresql', 'Prueba de bloqueo real: requiere PostgreSQL.')
class ConcurrentAvailabilityTests(TransactionTestCase):
    def test_two_updates_from_same_revision_cannot_overwrite_each_other(self):
        profile = make_profile('concurrencia@example.org')
        barrier = Barrier(2)

        def update(start):
            close_old_connections()
            try:
                client = Client()
                client.force_login(User.objects.get(pk=profile.user_id))
                barrier.wait(timeout=10)
                return client.put('/api/volunteer/availability/', {
                    'revision': 0,
                    'slots': [{'weekday': 0, 'start_time': start, 'end_time': '18:00'}],
                    'unavailable_dates': [],
                }, content_type='application/json').status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(update, ['09:00', '10:00']))
        self.assertEqual(sorted(responses), [200, 409])
        profile.refresh_from_db()
        self.assertEqual(profile.availability_revision, 1)
        self.assertEqual(profile.availability_slots.count(), 1)
