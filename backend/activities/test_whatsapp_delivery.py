from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth.models import Permission
from django.db import connection, connections
from django.test import Client, TestCase, TransactionTestCase
from django.utils import timezone

from accounts.models import AuditEvent, User
from volunteers.tests import make_profile
from .contacts import delivery_data, load_delivery
from .models import ContactChange, ContactInvitation, Participation
from .test_participation import authenticate_operator, available, event_fixture


class WhatsappDeliveryTests(TestCase):
    def setUp(self):
        self.profile = make_profile('delivery-volunteer@example.org')
        self.profile.phone = '+56900000000'
        self.profile.whatsapp_opt_in_at = timezone.now()
        self.profile.save()
        self.event, self.position = event_fixture()
        available(self.profile, self.event)
        self.operator = User.objects.create_user('delivery-operator@example.org', first_name='Secretaría', last_name='Prueba')
        self.operator.user_permissions.add(Permission.objects.get(codename='manage_operations'))
        authenticate_operator(self.client, self.operator)
        self.url = f'/api/activities/operations/events/{self.event.pk}/contacts/'

    def create(self):
        response = self.client.post(self.url, {'profile_id':self.profile.pk, 'position_id':self.position.pk}, content_type='application/json')
        self.assertIn(response.status_code, [200,201], response.content)
        return response.json()

    def action(self, item, action, **extra):
        return self.client.post(f'/api/activities/operations/contacts/{item["id"]}/action/',
            {'action':action, 'revision':item['revision'], **extra}, content_type='application/json')

    def test_repeat_open_and_reload_keep_pending_delivery_and_one_contact(self):
        item = self.create()
        for _ in range(3):
            self.assertEqual(self.create()['id'], item['id'])
            response = self.action(item, 'start')
            self.assertEqual(response.status_code, 200, response.content)
            item = response.json()
            self.assertEqual(item['status'], 'contact_started')
            self.assertFalse(item['delivery']['send_confirmed'])
            self.assertTrue(item['delivery']['can_confirm_send'])
        self.assertEqual(ContactInvitation.objects.count(), 1)
        self.assertEqual(ContactChange.objects.filter(action='start').count(), 3)
        self.assertFalse(ContactChange.objects.filter(action='sent').exists())
        self.assertFalse(Participation.objects.exists())
        reloaded = self.client.get(self.url).json()['results'][0]
        self.assertEqual(reloaded['delivery'], item['delivery'])
        candidates = self.client.get(f'/api/activities/operations/events/{self.event.pk}/positions/{self.position.pk}/candidates/').json()
        self.assertEqual(candidates['results'][0]['contact']['delivery'], item['delivery'])

    def test_manual_send_is_separate_and_reopening_never_downgrades_it(self):
        item = self.action(self.create(), 'start').json()
        response = self.action(item, 'sent')
        self.assertEqual(response.status_code, 200, response.content)
        item = response.json()
        self.assertEqual(item['status'], 'sent')
        self.assertTrue(item['delivery']['send_confirmed'])
        self.assertFalse(item['delivery']['can_confirm_send'])
        sent = item['delivery']['sent']
        self.assertEqual(sent['actor_id'], str(self.operator.pk))
        self.assertIsNotNone(sent['at'])
        for _ in range(22):
            item = self.action(item, 'start').json()
        self.assertEqual(item['status'], 'sent')
        self.assertEqual(item['delivery']['sent'], sent)
        self.assertEqual(self.client.get(self.url).json()['results'][0]['delivery']['sent'], sent)
        self.assertEqual(self.action(item, 'sent').status_code, 409)
        self.assertEqual(ContactChange.objects.filter(action='sent').count(), 1)
        self.assertFalse(Participation.objects.exists())
        self.assertFalse(ContactChange.objects.filter(action='accepted').exists())

    def test_opening_and_manual_confirmation_record_different_responsible_users(self):
        item = self.action(self.create(), 'start').json()
        second = User.objects.create_user('second-secretary@example.org', first_name='Otra', last_name='Secretaría')
        second.user_permissions.add(Permission.objects.get(codename='manage_operations'))
        authenticate_operator(self.client, second)
        item = self.action(item, 'sent').json()
        self.assertEqual(item['delivery']['opened']['actor_id'], str(self.operator.pk))
        self.assertEqual(item['delivery']['sent']['actor_id'], str(second.pk))
        self.assertEqual(AuditEvent.objects.get(action='contact.sent').actor_id, second.pk)

    def test_new_round_clears_delivery_state_without_erasing_audit(self):
        item = self.action(self.create(), 'start').json()
        item = self.action(item, 'sent').json()
        item = self.action(item, 'cancelled', note='Cancelación ficticia de prueba').json()
        item = self.action(item, 'reopen', note='Nueva ronda ficticia de prueba').json()
        self.assertIsNone(item['delivery']['opened'])
        self.assertIsNone(item['delivery']['sent'])
        self.assertFalse(item['delivery']['can_confirm_send'])
        self.assertEqual(self.action(item, 'sent').status_code, 400)
        self.assertEqual(ContactChange.objects.filter(action='sent').count(), 1)

    def test_send_confirmation_does_not_overwrite_an_already_recorded_acceptance(self):
        item = self.action(self.create(), 'start').json()
        item = self.action(item, 'accepted', note='Respuesta aceptada ficticia de prueba').json()
        item = self.action(item, 'sent').json()
        self.assertEqual(item['status'], 'accepted')
        self.assertTrue(item['delivery']['send_confirmed'])
        self.assertFalse(Participation.objects.exists())

    def test_permissions_and_client_cannot_forge_a_responsible_user(self):
        item = self.create()
        self.assertEqual(self.action(item, 'start', actor_id=str(self.operator.pk)).status_code, 400)
        self.client.force_login(self.profile.user)
        self.assertEqual(self.action(item, 'start').status_code, 403)
        self.assertEqual(self.action(item, 'sent').status_code, 403)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_delivery_history_is_batched_without_per_contact_queries(self):
        item = self.action(self.create(), 'start').json()
        contacts = list(ContactInvitation.objects.all())
        with self.assertNumQueries(1):
            load_delivery(contacts)
        with self.assertNumQueries(0):
            self.assertEqual(delivery_data(contacts[0])['opened']['actor_id'], str(self.operator.pk))


@skipUnless(connection.vendor == 'postgresql', 'Requiere bloqueos reales PostgreSQL.')
class ConcurrentWhatsappContactTests(TransactionTestCase):
    def test_two_concurrent_open_requests_share_one_followup_record(self):
        profile = make_profile('concurrent-wa@example.org')
        event, position = event_fixture()
        available(profile, event)
        operator = User.objects.create_user('concurrent-wa-secretary@example.org')
        operator.user_permissions.add(Permission.objects.get(codename='manage_operations'))
        barrier = Barrier(2)
        def worker(_):
            try:
                client = Client()
                authenticate_operator(client, User.objects.get(pk=operator.pk))
                barrier.wait(timeout=10)
                return client.post(f'/api/activities/operations/events/{event.pk}/contacts/',
                    {'profile_id':profile.pk,'position_id':position.pk}, content_type='application/json').status_code
            finally:
                connections['default'].close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(worker, range(2)))
        self.assertEqual(sorted(results), [200,201])
        self.assertEqual(ContactInvitation.objects.count(), 1)
        self.assertEqual(ContactChange.objects.filter(action='created').count(), 1)
