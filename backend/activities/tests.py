import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth.models import Permission
from django.core import mail, signing
from django.db import close_old_connections, connection
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from accounts.models import AuditEvent
from volunteers.models import DocumentType, Skill
from volunteers.tests import make_profile
from .models import Event, EventPosition, EventTransition, ServiceRequest


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', PUBLIC_APP_URL='https://fundacion.example')
class ActivityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.profile = make_profile('operaciones@example.org')
        cls.volunteer = make_profile('participante@example.org')
        cls.skill = Skill.objects.create(name='Apoyo comunitario')
        cls.document_type = DocumentType.objects.create(name='Certificado de prueba')
        cls.profile.user.user_permissions.add(Permission.objects.get(codename='manage_operations'))

    def setUp(self):
        self.client.force_login(self.profile.user)
        self.mfa(self.client, self.profile)
        self.public = Client()

    @staticmethod
    def mfa(client, profile):
        session = client.session
        session['account_authentication_methods_user'] = str(profile.user_id)
        session['account_authentication_methods'] = [{'method': 'mfa', 'at': timezone.now().timestamp()}]
        session.save()

    def request_payload(self, **overrides):
        return {
            'submission_id': str(uuid.uuid4()), 'requester_type': 'institution',
            'contact_name': 'Contacto de prueba', 'organization': 'Organización ficticia',
            'email': 'solicitante@example.org', 'phone': '+56 9 1234 5678',
            'description': 'Necesitamos apoyo comunitario para una actividad de prueba.',
            'quantity': 5, 'date': str(timezone.localdate() + timedelta(days=14)),
            'start_time': '10:00', 'end_time': '14:00', 'address': 'Dirección privada de prueba 123',
            'commune': 'Maipú', 'observations': 'Observación privada',
            'skills': [self.skill.pk], 'privacy': True, 'website': '', **overrides,
        }

    def event_payload(self, **overrides):
        return {
            'title': 'Actividad de apoyo comunitario', 'public_description': 'Actividad abierta para colaborar con la comunidad.',
            'date': str(timezone.localdate() + timedelta(days=14)), 'start_time': '10:00', 'end_time': '14:00',
            'address': 'Dirección privada del evento 456', 'commune': 'Maipú', 'internal_notes': 'Información solo para coordinación',
            'positions': [{'name': 'Primeros auxilios', 'capacity': 2, 'required_skills': [self.skill.pk], 'required_documents': [self.document_type.pk]},
                          {'name': 'Apoyo general', 'capacity': 3, 'required_skills': [], 'required_documents': []}],
            **overrides,
        }

    def submit(self, data=None, client=None):
        return (client or self.public).post('/api/activities/requests/', data or self.request_payload(), content_type='application/json')

    def make_request(self, verified=True):
        response = self.submit()
        self.assertEqual(response.status_code, 202)
        item = ServiceRequest.objects.latest('created_at')
        if verified:
            item.email_verified_at = timezone.now()
            item.save(update_fields=['email_verified_at'])
        return item

    def transition_request(self, item, status, revision=None, reason=''):
        return self.client.post(f'/api/activities/operations/requests/{item.pk}/transition/',
                                {'revision': item.revision if revision is None else revision, 'status': status, 'reason': reason}, content_type='application/json')

    def approve(self, item):
        self.assertEqual(self.transition_request(item, 'in_review').status_code, 200)
        item.refresh_from_db()
        self.assertEqual(self.transition_request(item, 'approved').status_code, 200)
        item.refresh_from_db()

    def create_event(self, item=None, payload=None):
        if item is None:
            item = self.make_request()
            self.approve(item)
        return self.client.post(f'/api/activities/operations/requests/{item.pk}/events/', payload or self.event_payload(), content_type='application/json')

    def transition_event(self, item, status, revision=None, reason=''):
        return self.client.post(f'/api/activities/operations/events/{item.pk}/transition/',
                                {'revision': item.revision if revision is None else revision, 'status': status, 'reason': reason}, content_type='application/json')

    def test_public_submission_saves_private_request_and_sends_confirmation(self):
        response = self.submit()
        self.assertEqual(response.status_code, 202)
        item = ServiceRequest.objects.get()
        self.assertEqual(item.status, 'pending')
        self.assertIsNone(item.email_verified_at)
        self.assertIsNotNone(item.privacy_accepted_at)
        self.assertEqual(item.skills.get(), self.skill)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/#confirm-request=', mail.outbox[0].body)
        self.assertNotIn(item.email, str(response.json()))

    def test_same_submission_key_does_not_duplicate_request_or_email(self):
        data = self.request_payload()
        self.assertEqual(self.submit(data).status_code, 202)
        self.assertEqual(self.submit(data).status_code, 202)
        self.assertEqual(ServiceRequest.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_honeypot_does_not_store_or_send_email(self):
        self.assertEqual(self.submit(self.request_payload(website='spam')).status_code, 202)
        self.assertFalse(ServiceRequest.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_invalid_and_privileged_request_fields_are_rejected(self):
        for index, changes in enumerate([{'privacy': False}, {'organization': ''}, {'quantity': 0}, {'status': 'approved'}, {'email_verified_at': str(timezone.now())}, {'skills': [999999]}, {'end_time': '09:00'}, {'date': '2000-01-01'}], start=1):
            with self.subTest(changes=changes):
                self.assertEqual(self.submit(self.request_payload(**changes), client=Client(REMOTE_ADDR=f'192.0.2.{index}')).status_code, 400)
        self.assertFalse(ServiceRequest.objects.exists())

    def test_public_request_is_rate_limited(self):
        for _ in range(5):
            self.submit(self.request_payload(privacy=False))
        self.assertEqual(self.submit().status_code, 429)

    def test_anonymous_submission_requires_csrf(self):
        self.assertEqual(self.submit(client=Client(enforce_csrf_checks=True)).status_code, 403)

    @override_settings(CSRF_TRUSTED_ORIGINS=['http://127.0.0.1:5173'])
    def test_public_form_accepts_valid_csrf_from_frontend(self):
        client = Client(enforce_csrf_checks=True)
        token = client.get('/api/session/').json()['csrf_token']
        response = client.post('/api/activities/requests/', self.request_payload(), content_type='application/json', HTTP_X_CSRFTOKEN=token, HTTP_ORIGIN='http://127.0.0.1:5173')
        self.assertEqual(response.status_code, 202)

    def test_verification_does_not_approve_request_and_is_idempotent(self):
        self.submit()
        token = re.search(r'#confirm-request=([^\s]+)', mail.outbox[0].body).group(1)
        response = self.public.post('/api/activities/request-verification/', {'token': token}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        item = ServiceRequest.objects.get()
        self.assertIsNotNone(item.email_verified_at)
        self.assertEqual(item.status, 'pending')
        self.public.post('/api/activities/request-verification/', {'token': token}, content_type='application/json')
        self.assertEqual(AuditEvent.objects.filter(action='request.email_verified').count(), 1)

    def test_invalid_and_expired_verification_fail(self):
        self.assertEqual(self.public.post('/api/activities/request-verification/', {'token': 'fake'}, content_type='application/json').status_code, 400)
        self.submit()
        token = re.search(r'#confirm-request=([^\s]+)', mail.outbox[0].body).group(1)
        with patch('django.core.signing.time.time', return_value=timezone.now().timestamp() + 49 * 3600):
            self.assertEqual(self.public.post('/api/activities/request-verification/', {'token': token}, content_type='application/json').status_code, 400)

    def test_verification_requires_csrf(self):
        self.assertEqual(Client(enforce_csrf_checks=True).post('/api/activities/request-verification/', {'token': 'fake'}, content_type='application/json').status_code, 403)

    def test_operations_require_permission_and_mfa(self):
        item = self.make_request()
        self.assertEqual(self.public.get('/api/activities/operations/requests/').status_code, 403)
        client = Client()
        client.force_login(self.volunteer.user)
        self.mfa(client, self.volunteer)
        self.assertEqual(client.get(f'/api/activities/operations/requests/{item.pk}/').status_code, 403)
        session = self.client.session
        session['account_authentication_methods'] = []
        session.save()
        self.assertEqual(self.client.get('/api/activities/operations/requests/').status_code, 403)

    def test_unverified_request_cannot_be_approved(self):
        item = self.make_request(verified=False)
        self.transition_request(item, 'in_review')
        item.refresh_from_db()
        self.assertEqual(self.transition_request(item, 'approved').status_code, 400)
        item.refresh_from_db()
        self.assertEqual(item.status, 'in_review')

    def test_workflow_rejection_requires_reason_and_terminal_state_is_immutable(self):
        item = self.make_request()
        self.assertEqual(self.transition_request(item, 'approved').status_code, 400)
        self.transition_request(item, 'in_review')
        item.refresh_from_db()
        self.assertEqual(self.transition_request(item, 'rejected').status_code, 400)
        self.assertEqual(self.transition_request(item, 'rejected', reason='Fuera del alcance de la fundación.').status_code, 200)
        item.refresh_from_db()
        self.assertEqual(self.transition_request(item, 'approved').status_code, 400)

    def test_stale_revision_does_not_overwrite_request(self):
        item = self.make_request()
        self.transition_request(item, 'in_review')
        self.assertEqual(self.transition_request(item, 'approved').status_code, 409)

    def test_only_approved_requests_can_generate_events(self):
        item = self.make_request()
        self.assertEqual(self.create_event(item).status_code, 400)
        self.assertFalse(Event.objects.exists())

    def test_one_request_can_generate_several_draft_events(self):
        item = self.make_request()
        self.approve(item)
        for _ in range(2):
            response = self.create_event(item)
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.json()['status'], 'draft')
            self.assertEqual(response.json()['capacity'], 5)
        self.assertEqual(item.events.count(), 2)
        self.assertEqual(EventPosition.objects.count(), 4)

    def test_capacity_duplicates_and_injected_state_are_rejected(self):
        item = self.make_request()
        self.approve(item)
        positions = self.event_payload()['positions']
        for changes in [
            {'positions': []}, {'positions': positions * 2},
            {'positions': [{**positions[0], 'capacity': 501}]}, {'status': 'open'},
            {'positions': [{**positions[0], 'required_documents': [999999]}]},
        ]:
            self.assertEqual(self.create_event(item, self.event_payload(**changes)).status_code, 400)
        self.assertFalse(Event.objects.exists())

    def test_public_events_exclude_drafts_and_private_fields(self):
        response = self.create_event()
        item = Event.objects.get(pk=response.json()['id'])
        self.assertEqual(self.public.get('/api/activities/public-events/').json()['total'], 0)
        self.assertEqual(self.transition_event(item, 'open').status_code, 200)
        data = self.public.get('/api/activities/public-events/').json()
        self.assertEqual(data['total'], 1)
        public_event = data['results'][0]
        for key in ['address', 'internal_notes', 'request_id', 'email', 'phone', 'contact_name']:
            self.assertNotIn(key, public_event)
        self.assertNotIn('Dirección privada', str(data))
        self.assertNotIn('solo para coordinación', str(data))

    def test_open_event_cannot_be_edited_without_communication_workflow(self):
        item = Event.objects.get(pk=self.create_event().json()['id'])
        self.transition_event(item, 'open')
        item.refresh_from_db()
        response = self.client.put(f'/api/activities/operations/events/{item.pk}/', self.event_payload(revision=item.revision), content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_draft_edit_increments_revision_and_preserves_request(self):
        item = Event.objects.get(pk=self.create_event().json()['id'])
        response = self.client.put(f'/api/activities/operations/events/{item.pk}/', self.event_payload(revision=0, title='Título revisado'), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['revision'], 1)
        self.assertEqual(item.positions.count(), 2)
        self.assertEqual(self.client.put(f'/api/activities/operations/events/{item.pk}/', self.event_payload(revision=0), content_type='application/json').status_code, 409)

    def test_cancellation_requires_reason_and_removes_public_event(self):
        item = Event.objects.get(pk=self.create_event().json()['id'])
        self.transition_event(item, 'open')
        item.refresh_from_db()
        self.assertEqual(self.transition_event(item, 'cancelled').status_code, 400)
        self.assertEqual(self.transition_event(item, 'cancelled', reason='No se realizará la actividad.').status_code, 200)
        self.assertEqual(self.public.get('/api/activities/public-events/').json()['total'], 0)
        self.assertEqual(EventTransition.objects.filter(event=item).count(), 2)

    def test_event_cannot_finish_before_end_or_reopen_after_finished(self):
        item = Event.objects.get(pk=self.create_event().json()['id'])
        self.transition_event(item, 'open')
        item.refresh_from_db()
        self.assertEqual(self.transition_event(item, 'finished').status_code, 400)
        Event.objects.filter(pk=item.pk).update(starts_at=timezone.now() - timedelta(hours=2), ends_at=timezone.now() - timedelta(hours=1))
        self.assertEqual(self.transition_event(item, 'finished').status_code, 200)
        item.refresh_from_db()
        self.assertEqual(self.transition_event(item, 'open').status_code, 400)

    def test_inactive_requirements_prevent_publication(self):
        item = Event.objects.get(pk=self.create_event().json()['id'])
        self.skill.is_active = False
        self.skill.save()
        self.assertEqual(self.transition_event(item, 'open').status_code, 400)

    def test_private_detail_and_transition_require_csrf(self):
        item = self.make_request()
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.profile.user)
        self.mfa(client, self.profile)
        self.assertEqual(client.post(f'/api/activities/operations/requests/{item.pk}/transition/', {'status': 'in_review', 'revision': 0}, content_type='application/json').status_code, 403)

    def test_public_options_do_not_expose_document_or_contact_data(self):
        data = self.public.get('/api/activities/public-options/').json()
        self.assertEqual([skill['id'] for skill in data['skills']], [self.skill.pk])
        self.assertNotIn('documents', data)
        self.assertNotIn('email', data)

    def test_email_failure_can_be_retried_without_duplicate_request(self):
        payload = self.request_payload()
        with patch('activities.services.send_mail', side_effect=OSError('SMTP unavailable')):
            self.assertEqual(self.submit(payload).status_code, 503)
        self.assertEqual(ServiceRequest.objects.count(), 1)
        self.assertEqual(self.submit(payload).status_code, 202)
        self.assertEqual(ServiceRequest.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_complete_request_verification_approval_and_publication(self):
        self.assertEqual(self.submit().status_code, 202)
        token = re.search(r'#confirm-request=([^\s]+)', mail.outbox[0].body).group(1)
        self.assertEqual(self.public.post('/api/activities/request-verification/', {'token': token}, content_type='application/json').status_code, 200)
        item = ServiceRequest.objects.get()
        self.approve(item)
        created = self.create_event(item)
        self.assertEqual(created.status_code, 201)
        event = Event.objects.get(pk=created.json()['id'])
        self.assertEqual(self.transition_event(event, 'open').status_code, 200)
        public = self.public.get('/api/activities/public-events/').json()
        self.assertEqual(public['results'][0]['id'], str(event.pk))
        self.assertEqual(item.transitions.count(), 2)
        self.assertTrue(AuditEvent.objects.filter(action='event.open').exists())

    def test_bad_verification_shapes_return_client_error(self):
        for body in [[], {'token': 'fake', 'status': 'approved'}, {'token': signing.dumps({'id': 'bad', 'nonce': 'bad'}, salt='service-request-email')}]:
            self.assertEqual(self.public.post('/api/activities/request-verification/', body, content_type='application/json').status_code, 400)

    def test_oversized_requirement_lists_fail_without_saving(self):
        self.assertEqual(self.submit(self.request_payload(skills=[self.skill.pk] * 31)).status_code, 400)
        self.assertFalse(ServiceRequest.objects.exists())

    def test_ambiguous_chile_schedule_is_rejected(self):
        from .serializers import LocalScheduleSerializer
        zone = ZoneInfo('America/Santiago')
        start = timezone.localdate() + timedelta(days=1)
        candidate = None
        for offset in range(400):
            date = start + timedelta(days=offset)
            for hour in [0, 23]:
                naive = datetime.combine(date, datetime.min.time()).replace(hour=hour, minute=15)
                if naive.replace(tzinfo=zone, fold=0).utcoffset() != naive.replace(tzinfo=zone, fold=1).utcoffset():
                    candidate = (date, hour)
                    break
            if candidate:
                break
        self.assertIsNotNone(candidate)
        serializer = LocalScheduleSerializer(data={'date': str(candidate[0]), 'start_time': f'{candidate[1]:02d}:15', 'end_time': f'{candidate[1]:02d}:45'})
        self.assertFalse(serializer.is_valid())

    def test_skill_document_requirements_are_inherited_and_checked_before_publication(self):
        self.skill.required_documents.add(self.document_type)
        item = Event.objects.get(pk=self.create_event().json()['id'])
        private = self.client.get(f'/api/activities/operations/events/{item.pk}/').json()
        self.assertEqual(private['positions'][0]['inherited_documents'][0]['id'], self.document_type.pk)
        self.document_type.is_active = False
        self.document_type.save()
        self.assertEqual(self.transition_event(item, 'open').status_code, 400)


@skipUnless(connection.vendor == 'postgresql', 'Prueba de concurrencia real: requiere PostgreSQL.')
class ConcurrentEventTests(TransactionTestCase):
    def test_two_publications_from_same_revision_produce_one_transition(self):
        profile = make_profile('publicacion@example.org')
        profile.user.user_permissions.add(Permission.objects.get(codename='manage_operations'))
        now = timezone.now()
        source = ServiceRequest.objects.create(
            submission_id=uuid.uuid4(), requester_type='person', contact_name='Contacto de prueba',
            email='contacto@example.org', phone='+56912345678', description='Solicitud ficticia de apoyo.',
            quantity=1, starts_at=now + timedelta(days=2), ends_at=now + timedelta(days=2, hours=2),
            address='Dirección privada', commune='Maipú', privacy_accepted_at=now,
            email_verified_at=now, status='approved',
        )
        event = Event.objects.create(request=source, title='Publicación concurrente', public_description='Actividad de prueba.', starts_at=source.starts_at, ends_at=source.ends_at, address=source.address, commune=source.commune)
        EventPosition.objects.create(event=event, name='Apoyo general', capacity=1)
        barrier = Barrier(2)

        def publish(_):
            close_old_connections()
            try:
                from accounts.models import User
                client = Client()
                client.force_login(User.objects.get(pk=profile.user_id))
                ActivityTests.mfa(client, profile)
                barrier.wait(timeout=10)
                return client.post(f'/api/activities/operations/events/{event.pk}/transition/', {'revision': 0, 'status': 'open', 'reason': ''}, content_type='application/json').status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(publish, [0, 1]))
        self.assertEqual(sorted(responses), [200, 409])
        self.assertEqual(EventTransition.objects.filter(event=event).count(), 1)
