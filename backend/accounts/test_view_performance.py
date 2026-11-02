from django.contrib.auth.models import Group
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from activities.models import EventPosition, Participation
from activities.test_participation import authenticate_operator, event_fixture
from volunteers.tests import make_profile
from .models import User


class ViewPerformanceTests(TestCase):
    def setUp(self):
        call_command('setup_roles', verbosity=0)
        self.user = User.objects.create_user('performance-admin@example.org')
        self.user.groups.add(Group.objects.get(name='Administrador general'))
        authenticate_operator(self.client, self.user)

    def measure(self, path):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get('/api/' + path)
            self.assertEqual(response.status_code, 200)
        return len(queries), response.json()

    def test_user_list_query_count_does_not_grow_per_account(self):
        single, _ = self.measure('management/users/')
        for index in range(8):
            make_profile(f'performance-user-{index}@example.org')
        several, _ = self.measure('management/users/')
        self.assertEqual(single, several)

    def test_event_list_query_count_does_not_grow_per_event(self):
        event_fixture()
        single, _ = self.measure('activities/operations/events/')
        for _ in range(4):
            event_fixture()
        several, result = self.measure('activities/operations/events/')
        self.assertEqual(single, several)
        self.assertEqual(len(result['results']), 5)

    def test_dashboard_counts_capacity_once_with_multiple_participants(self):
        event, position = event_fixture()
        EventPosition.objects.create(event=event, name='Otra función', capacity=4)
        for index, assignment in enumerate(['primary', 'backup']):
            profile = make_profile(f'performance-participant-{index}@example.org')
            Participation.objects.create(event=event, position=position, profile=profile,
                                         status='confirmed', assignment=assignment)
        _, result = self.measure('workspace-summary/?portal=operations')
        row = result['events'][0]
        self.assertEqual((row['capacity'], row['confirmed'], row['backups']), (5, 1, 1))

    def test_role_changes_invalidate_instance_prefetch(self):
        from .portals import is_volunteer
        self.assertFalse(is_volunteer(self.user))
        self.user.groups.add(Group.objects.get(name='Voluntario'))
        self.assertTrue(is_volunteer(self.user))
