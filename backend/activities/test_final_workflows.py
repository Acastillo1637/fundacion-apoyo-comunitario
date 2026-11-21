from datetime import timedelta

from django.contrib.auth.models import Permission
from django.test import Client, TestCase
from django.utils import timezone

from accounts.models import User
from .models import Event, Notification
from .test_participation import authenticate_operator, event_fixture


class NotificationArchiveTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('archive@example.org')
        self.other = User.objects.create_user('archive-other@example.org')
        self.client.force_login(self.user)
        Notification.objects.bulk_create([Notification(user=self.user, message=f'Aviso {i}') for i in range(65)])
        self.foreign = Notification.objects.create(user=self.other, message='Aviso ajeno')

    def test_all_pages_retain_global_unread_and_never_include_foreign_records(self):
        ids = set()
        for page, count in [(1,30),(2,30),(3,5),(4,0)]:
            result = self.client.get(f'/api/activities/notifications/?page={page}').json()
            self.assertEqual((result['total'], result['unread']), (65,65))
            self.assertEqual(len(result['results']), count)
            found = {row['id'] for row in result['results']}
            self.assertFalse(found & ids)
            self.assertNotIn(self.foreign.pk, found)
            ids |= found
        self.assertEqual(len(ids), 65)

    def test_individual_read_is_owned_and_unread_filter_remains_consistent(self):
        own = self.user.notifications.first()
        url = '/api/activities/notifications/?unread_only=1'
        response = self.client.post(url, {'read_id': self.foreign.pk}, content_type='application/json')
        self.assertEqual(response.status_code, 404)
        result = self.client.post(url, {'read_id': own.pk}, content_type='application/json').json()
        self.assertEqual((result['unread'],result['total']), (64,64))
        self.assertNotIn(own.pk, [row['id'] for row in result['results']])
        own.refresh_from_db()
        self.assertIsNotNone(own.read_at)
        result = self.client.post(url, {'read_all': True}, content_type='application/json').json()
        self.assertEqual((result['unread'],result['total']), (0,0))
        self.foreign.refresh_from_db()
        self.assertIsNone(self.foreign.read_at)

    def test_invalid_pages_filters_and_mutations_are_rejected(self):
        for query in ['page=0','page=-1','page=no','page=100001','unread_only=all']:
            self.assertEqual(self.client.get('/api/activities/notifications/?'+query).status_code, 400)
        for body in [{}, {'read_all':False}, {'read_id':-1}, {'read_all':True,'read_id':1}, {'user_id':str(self.other.pk)}]:
            self.assertEqual(self.client.post('/api/activities/notifications/', body, content_type='application/json').status_code, 400)
        self.client.logout()
        self.assertEqual(self.client.get('/api/activities/notifications/').status_code, 403)


class OperationalSearchTests(TestCase):
    def setUp(self):
        self.operator = User.objects.create_user('search-operator@example.org')
        self.operator.user_permissions.add(Permission.objects.get(codename='manage_operations'))
        authenticate_operator(self.client, self.operator)
        self.event, _ = event_fixture()
        self.event.title = 'Encuentro del barrio'
        self.event.commune = 'Maipú'
        self.event.save()
        self.past, _ = event_fixture()
        self.past.title = 'Archivo de actividades'
        self.past.status = 'finished'
        self.past.starts_at = timezone.now()-timedelta(days=2)
        self.past.ends_at = self.past.starts_at+timedelta(hours=2)
        self.past.save()

    def test_event_filters_are_applied_before_pagination_for_compact_and_full_lists(self):
        for compact in ['0','1']:
            result = self.client.get(f'/api/activities/operations/events/?compact={compact}&q=Maipú&status=open&period=upcoming').json()
            self.assertEqual(result['total'], 1)
            self.assertEqual(result['results'][0]['id'], str(self.event.pk))
        result = self.client.get('/api/activities/operations/events/?period=past').json()
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['results'][0]['id'], str(self.past.pk))

    def test_request_search_by_contact_and_commune_and_invalid_filters(self):
        self.event.request.contact_name = 'Contacto especial'
        self.event.request.save()
        result = self.client.get('/api/activities/operations/requests/?q=especial&status=approved').json()
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['results'][0]['id'], str(self.event.request_id))
        for resource in ['events','requests']:
            for query in ['status=invalid','period=invalid','q='+'x'*121]:
                self.assertEqual(self.client.get(f'/api/activities/operations/{resource}/?{query}').status_code, 400)
            self.assertEqual(self.client.get(f'/api/activities/operations/{resource}/',{'q':"' OR 1=1;--"}).json()['total'], 0)

    def test_filters_do_not_bypass_operator_permissions(self):
        self.client.force_login(User.objects.create_user('not-an-operator@example.org'))
        for resource in ['events','requests']:
            self.assertEqual(self.client.get(f'/api/activities/operations/{resource}/?q=Maipú').status_code, 403)
