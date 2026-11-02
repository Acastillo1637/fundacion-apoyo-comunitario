from io import StringIO
from pathlib import Path
import tempfile

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from activities.models import Event, Participation, ServiceRequest
from activities.participation import eligibility
from .models import AuditEvent, User, VolunteerProfile


@override_settings(DEBUG=True)
class CommunityDemoTests(TestCase):
    def setUp(self):
        call_command('setup_roles', stdout=StringIO())
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.override = override_settings(BASE_DIR=Path(self.directory.name) / 'backend')
        self.override.enable()
        self.addCleanup(self.override.disable)

    def seed(self, apply=False):
        call_command('seed_community_demo', apply=apply, stdout=StringIO())

    def test_preview_does_not_create_accounts_or_events(self):
        self.seed()
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(Event.objects.count(), 0)

    def test_seed_preserves_existing_user_and_is_repeat_safe(self):
        existing = User.objects.create_user('existing@example.org', 'Original-test-password-459!')
        original_password = existing.password
        with patch_no_mail():
            self.seed(apply=True)
        self.assertEqual(User.objects.count(), 23)
        self.assertEqual(VolunteerProfile.objects.count(), 18)
        self.assertEqual(Event.objects.count(), 6)
        self.assertEqual(ServiceRequest.objects.count(), 8)
        self.assertEqual(Event.objects.filter(status='open').count(), 4)
        existing.refresh_from_db()
        self.assertEqual(existing.password, original_password)
        self.assertFalse(existing.groups.exists())
        self.assertFalse(User.objects.filter(email__endswith='@demo.example.org', is_superuser=True).exists())
        self.assertEqual(VolunteerProfile.objects.filter(notice_version='community-demo-v1').count(), 18)
        for position in Event.objects.get(title='Recuperación de espacios verdes en el barrio').positions.all():
            self.assertLessEqual(position.participations.filter(status='confirmed', assignment='primary').count(), position.capacity)
        for participation in Participation.objects.filter(status__in=['confirmed', 'invited', 'waitlisted', 'applied']).select_related('profile__user', 'position__event'):
            self.assertEqual(eligibility(participation.profile, participation.position), [])
        receipts = list(Path(self.directory.name).glob('backups/*/access.json'))
        self.assertEqual(len(receipts), 1)
        self.seed(apply=True)
        self.assertEqual(User.objects.count(), 23)
        self.assertEqual(Event.objects.count(), 6)
        self.assertEqual(AuditEvent.objects.filter(action='demo.seed.completed').count(), 1)

    def test_email_collision_aborts_without_overwriting(self):
        existing = User.objects.create_user('camila.rojas@demo.example.org', first_name='Existing')
        with self.assertRaises(CommandError):
            self.seed(apply=True)
        existing.refresh_from_db()
        self.assertEqual(existing.first_name, 'Existing')
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(Event.objects.count(), 0)

    @override_settings(DEBUG=False)
    def test_production_refuses_demo_data(self):
        with self.assertRaises(CommandError):
            self.seed(apply=True)
        self.assertEqual(User.objects.count(), 0)


def patch_no_mail():
    from unittest.mock import patch
    return patch('django.core.mail.message.EmailMessage.send', side_effect=AssertionError('El seed no debe enviar correos'))
