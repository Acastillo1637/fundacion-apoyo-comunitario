from datetime import datetime, time, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from activities.models import Notification
from activities.participation import eligibility
from activities.test_participation import authenticate_operator, available, event_fixture
from volunteers.tests import make_profile
from .models import AccountChange, User


class RestrictionTests(TestCase):
    def setUp(self):
        call_command('setup_roles', verbosity=0)
        self.operator = User.objects.create_user('restriction-operator@example.org')
        self.operator.groups.add(Group.objects.get(name='Secretaría'))
        self.profile = make_profile('restriction-volunteer@example.org')
        authenticate_operator(self.client, self.operator)

    def update(self, **changes):
        return self.client.post('/api/operations/volunteers/', {'id': self.profile.pk, 'restricted': True,
            'reason': 'Restricción temporal de prueba.', 'revision': 0, **changes}, content_type='application/json')

    def test_restriction_covers_end_of_selected_day_in_santiago(self):
        until = timezone.localdate() + timedelta(days=3)
        self.assertEqual(self.update(until=str(until)).status_code, 200)
        self.profile.refresh_from_db()
        expected = datetime.combine(until, time.max, tzinfo=ZoneInfo('America/Santiago'))
        self.assertEqual(self.profile.restriction_expires_at, expected)
        self.assertTrue(self.profile.participation_restricted)
        self.assertEqual(self.profile.restriction_revision, 1)

    def test_expiration_unblocks_candidates_and_directory_filter_without_deleting_history(self):
        self.update(until=str(timezone.localdate()))
        self.profile.refresh_from_db()
        event, position = event_fixture()
        available(self.profile, event)
        self.assertIn('Participación no habilitada', eligibility(self.profile, position))
        after = self.profile.restriction_expires_at + timedelta(seconds=1)
        with patch('django.utils.timezone.now', return_value=after):
            self.assertFalse(self.profile.participation_restricted)
            self.assertNotIn('Participación no habilitada', eligibility(self.profile, position))
            self.assertEqual(self.client.get('/api/operations/volunteers/?restricted=true').json()['total'], 0)
            self.assertEqual(self.client.get('/api/operations/volunteers/?restricted=false').json()['total'], 1)
        self.assertTrue(self.profile.is_restricted)
        self.assertEqual(AccountChange.objects.filter(action='participation_restriction').count(), 1)

    def test_indefinite_restriction_and_manual_removal_require_fresh_revision(self):
        self.assertEqual(self.update().status_code, 200)
        self.assertEqual(self.update(restricted=False).status_code, 409)
        self.assertEqual(self.update(restricted=False, revision=1).status_code, 200)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.participation_restricted)
        self.assertIsNone(self.profile.restriction_expires_at)
        self.assertEqual(self.profile.restriction_revision, 2)
        self.assertEqual(AccountChange.objects.filter(action='participation_restriction').count(), 2)

    def test_cannot_set_past_expiry_or_expiry_while_removing(self):
        self.assertEqual(self.update(until=str(timezone.localdate() - timedelta(days=1))).status_code, 400)
        self.assertEqual(self.update(restricted=False, until=str(timezone.localdate())).status_code, 400)
        self.assertFalse(AccountChange.objects.exists())

    def test_revision_conflict_does_not_duplicate_audit_or_notification(self):
        self.update()
        self.assertEqual(self.update(until=str(timezone.localdate())).status_code, 409)
        self.assertEqual(AccountChange.objects.count(), 1)
        self.assertEqual(Notification.objects.filter(user=self.profile.user).count(), 1)

    def test_audit_retains_actor_date_reason_and_expiry(self):
        self.update(until=str(timezone.localdate() + timedelta(days=3)))
        change = AccountChange.objects.get()
        self.assertEqual(change.actor, self.operator)
        self.assertIsNotNone(change.after_access['restriction_expires_at'])
        self.assertFalse(change.before_access['participation_restricted'])
        data = self.client.get(f'/api/operations/volunteers/{self.profile.pk}/').json()
        self.assertIn('actor__first_name', data['restriction_history'][0])
        self.assertIsNotNone(data['restriction_expires_at'])

    def test_own_status_is_visible_only_to_the_volunteer(self):
        self.update()
        self.assertEqual(self.client.get('/api/activities/participation-status/').status_code, 403)
        self.client.force_login(self.profile.user)
        result = self.client.get('/api/activities/participation-status/').json()
        self.assertTrue(result['restricted'])
        self.assertIn('temporal', result['reason'])
        self.assertEqual(self.update(restricted=False, revision=1).status_code, 403)

    def test_expired_own_status_does_not_expose_outdated_reason(self):
        self.update(until=str(timezone.localdate()))
        self.profile.refresh_from_db()
        self.client.force_login(self.profile.user)
        with patch('django.utils.timezone.now', return_value=self.profile.restriction_expires_at + timedelta(seconds=1)):
            result = self.client.get('/api/activities/participation-status/').json()
        self.assertEqual(result, {'restricted': False, 'reason': '', 'expires_at': None})
