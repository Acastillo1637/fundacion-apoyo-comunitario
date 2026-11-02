from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import User
from .models import Notification
from .participation import notifications


class NotificationPerformanceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('notifications-performance@example.org')

    def get_notifications(self):
        request = APIRequestFactory().get('/api/activities/notifications/')
        force_authenticate(request, user=self.user)
        with self.assertNumQueries(1):
            return notifications(request).data

    def test_empty_notifications_need_one_query(self):
        self.assertEqual(self.get_notifications(), {'unread': 0, 'results': []})

    def test_unread_total_includes_older_rows_outside_latest_thirty(self):
        Notification.objects.bulk_create([Notification(user=self.user, message=f'Anterior {index}') for index in range(7)])
        Notification.objects.bulk_create([Notification(user=self.user, message=f'Reciente {index}', read_at=timezone.now()) for index in range(30)])
        other = User.objects.create_user('notifications-other@example.org')
        Notification.objects.create(user=other, message='Privado de otra persona')
        result = self.get_notifications()
        self.assertEqual(result['unread'], 7)
        self.assertEqual(len(result['results']), 30)
        self.assertTrue(all(item['read_at'] for item in result['results']))
        self.assertTrue(all('unread_total' not in item for item in result['results']))
