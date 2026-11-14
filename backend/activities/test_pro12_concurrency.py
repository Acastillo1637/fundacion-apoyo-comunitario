from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.db import connection, connections
from django.test import Client, TransactionTestCase
from django.utils import timezone

from accounts.models import User
from volunteers.tests import make_profile
from .models import ContactInvitation, GeocodingGate, MatchingPolicy, Participation
from .test_participation import authenticate_operator, available, event_fixture


@skipUnless(connection.vendor=='postgresql','Requiere bloqueos PostgreSQL reales')
class Pro12ConcurrencyTests(TransactionTestCase):
    def test_two_manual_confirmations_cannot_take_the_same_last_seat(self):
        event,position=event_fixture()
        operator=User.objects.create_user('manual-concurrency@example.org')
        operator.user_permissions.add(Permission.objects.get(codename='manage_operations'))
        contacts=[]
        for index in range(2):
            profile=make_profile(f'manual-concurrency-{index}@example.org');available(profile,event)
            contacts.append(ContactInvitation.objects.create(event=event,position=position,profile=profile,status='accepted',expires_at=timezone.now()+timedelta(hours=48)))
        barrier=Barrier(2)
        def worker(contact):
            try:
                client=Client();authenticate_operator(client,operator)
                barrier.wait(timeout=10)
                response=client.post(f'/api/activities/operations/contacts/{contact.pk}/action/',{'action':'confirm','revision':0,'note':'Aceptación manual ficticia para probar concurrencia'},content_type='application/json')
                return response.status_code
            finally:
                connections['default'].close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(worker,contacts))
        self.assertEqual(results,[200,200])
        self.assertEqual(Participation.objects.filter(event=event,status='confirmed').count(),1)
        self.assertEqual(Participation.objects.filter(event=event,status='waitlisted').count(),1)

    def test_geocoding_gate_is_shared_across_simultaneous_users(self):
        MatchingPolicy.objects.update_or_create(pk=1,defaults={'geocoding_enabled':True,'geocoding_policy_accepted_at':timezone.now()})
        GeocodingGate.objects.update_or_create(pk=1,defaults={'next_request_at':timezone.now()-timedelta(seconds=5)})
        profiles=[make_profile(f'geocoding-concurrency-{index}@example.org') for index in range(2)]
        barrier=Barrier(2)
        def worker(profile):
            try:
                client=Client();client.force_login(profile.user)
                barrier.wait(timeout=10)
                return client.post('/api/maps/search/',{'query':f'Lugar público de prueba {profile.pk}'},content_type='application/json').status_code
            finally:
                connections['default'].close()
        with patch('accounts.geography.urlopen') as upstream:
            upstream.return_value.__enter__.return_value.read.return_value=b'[]'
            with ThreadPoolExecutor(max_workers=2) as pool:
                results=list(pool.map(worker,profiles))
        self.assertEqual(sorted(results),[200,429])
        self.assertEqual(upstream.call_count,1)
