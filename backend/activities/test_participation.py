import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth.models import Permission
from django.db import connection, connections
from django.test import Client, TestCase, TransactionTestCase
from django.utils import timezone

from accounts.models import User
from volunteers.models import AvailabilitySlot, DocumentType, Skill, VolunteerSkill, UnavailableDate
from volunteers.tests import make_profile
from documents.models import VolunteerDocument
from .models import Event, EventPosition, Notification, Participation, ServiceRequest


def event_fixture():
    start = (timezone.localtime() + timedelta(days=14)).replace(hour=10, minute=0, second=0, microsecond=0)
    source = ServiceRequest.objects.create(submission_id=uuid.uuid4(), requester_type='person', contact_name='Contacto', email='contact@example.org', phone='+56912345678',
        description='Solicitud comunitaria de prueba', quantity=1, starts_at=start, ends_at=start + timedelta(hours=2), address='Direccion privada', commune='Santiago', privacy_accepted_at=timezone.now(), status='approved', email_verified_at=timezone.now())
    event = Event.objects.create(request=source, title='Actividad de prueba', public_description='Descripcion publica de prueba', starts_at=start, ends_at=source.ends_at, address=source.address, commune=source.commune, status='open')
    position = EventPosition.objects.create(event=event, name='Apoyo', capacity=1)
    return event, position


def available(profile, event):
    start, end = timezone.localtime(event.starts_at), timezone.localtime(event.ends_at)
    AvailabilitySlot.objects.create(profile=profile, weekday=start.weekday(), start_time=start.time(), end_time=end.time())


def authenticate_operator(client, user):
    client.force_login(user)
    session = client.session
    session['account_authentication_methods_user'] = str(user.pk)
    session['account_authentication_methods'] = [{'method': 'password', 'at': timezone.now().timestamp()}]
    session.save()


class ParticipationTests(TestCase):
    def setUp(self):
        self.profile = make_profile('volunteer@example.org')
        self.other = make_profile('other@example.org')
        self.operator = User.objects.create_user('operator@example.org')
        self.operator.user_permissions.add(Permission.objects.get(codename='manage_operations'))
        self.event, self.position = event_fixture()
        available(self.profile, self.event)
        available(self.other, self.event)
        self.client.force_login(self.profile.user)
        self.staff = Client()
        authenticate_operator(self.staff, self.operator)

    def apply(self, client=None, **changes):
        return (client or self.client).post('/api/activities/participations/', {'position_id': self.position.pk, **changes}, content_type='application/json')

    def invite(self, profile=None):
        return self.staff.post(f'/api/activities/operations/events/{self.event.pk}/participants/', {'position_id': self.position.pk, 'profile_id': (profile or self.profile).pk}, content_type='application/json')

    def decision(self, item, action, client=None, revision=None):
        return (client or self.client).post(f'/api/activities/participations/{item.pk}/decision/', {'revision': item.revision if revision is None else revision, 'action': action}, content_type='application/json')

    def test_apply_owns_profile_and_creates_notification(self):
        self.assertEqual(self.apply().status_code, 201)
        item = Participation.objects.get()
        self.assertEqual(item.profile, self.profile)
        self.assertEqual(item.status, 'applied')
        self.assertTrue(Notification.objects.filter(user=self.profile.user).exists())
        self.assertEqual(self.apply().status_code, 409)

    def test_cannot_forge_profile_status_or_attendance(self):
        for changes in [{'profile_id': self.other.pk}, {'status': 'confirmed'}, {'attendance': 'present'}]:
            self.assertEqual(self.apply(**changes).status_code, 400)
        self.assertFalse(Participation.objects.exists())

    def test_invitation_expiry_and_cross_owner_decision(self):
        self.assertEqual(self.invite().status_code, 201)
        item = Participation.objects.get()
        self.assertLessEqual(item.expires_at, timezone.now() + timedelta(hours=48))
        self.client.force_login(self.other.user)
        self.assertEqual(self.decision(item, 'accept').status_code, 404)
        self.client.force_login(self.profile.user)
        item.expires_at = timezone.now() - timedelta(seconds=1)
        item.save(update_fields=['expires_at'])
        self.assertEqual(self.decision(item, 'accept').status_code, 400)
        self.assertEqual(self.client.get('/api/activities/participations/').json()['results'][0]['status'], 'expired')

    def test_invitation_confirmation_and_waitlist_capacity(self):
        self.invite()
        self.invite(self.other)
        first = Participation.objects.get(profile=self.profile)
        second = Participation.objects.get(profile=self.other)
        self.assertEqual(self.decision(first, 'accept').json()['status'], 'confirmed')
        self.client.force_login(self.other.user)
        self.assertEqual(self.decision(second, 'accept').json()['status'], 'waitlisted')
        self.assertEqual(Participation.objects.filter(status='confirmed').count(), 1)

    def test_staff_can_renew_expired_invitation_without_duplicate(self):
        self.invite()
        item = Participation.objects.get()
        item.expires_at = timezone.now() - timedelta(minutes=1)
        item.save(update_fields=['expires_at'])
        self.assertEqual(self.invite().status_code, 201)
        self.assertEqual(Participation.objects.count(), 1)
        item.refresh_from_db()
        self.assertGreater(item.expires_at, timezone.now())
        self.assertEqual(item.revision, 1)

    def test_reject_invitation_and_withdraw_application(self):
        self.invite()
        item = Participation.objects.get()
        self.assertEqual(self.decision(item, 'decline').json()['status'], 'declined')
        item.delete()
        self.apply()
        item = Participation.objects.get()
        self.assertEqual(self.decision(item, 'withdraw').json()['status'], 'cancelled')

    def test_withdraw_frees_capacity_and_manual_waitlist_confirmation(self):
        first = Participation.objects.create(event=self.event, position=self.position, profile=self.profile, status='confirmed')
        second = Participation.objects.create(event=self.event, position=self.position, profile=self.other, status='waitlisted')
        self.assertEqual(self.decision(first, 'withdraw').status_code, 200)
        self.assertEqual(self.decision(second, 'confirm', self.staff).json()['status'], 'confirmed')

    def test_volunteer_cannot_confirm_or_access_operator_resources(self):
        self.apply()
        item = Participation.objects.get()
        self.assertEqual(self.decision(item, 'confirm').status_code, 403)
        self.assertEqual(self.client.get(f'/api/activities/operations/events/{self.event.pk}/participants/').status_code, 403)
        self.assertEqual(self.client.get(f'/api/activities/operations/events/{self.event.pk}/positions/{self.position.pk}/candidates/').status_code, 403)

    def test_unavailability_and_restrictions_block_participation(self):
        UnavailableDate.objects.create(profile=self.profile, date=timezone.localtime(self.event.starts_at).date())
        self.assertEqual(self.apply().status_code, 400)
        self.profile.unavailable_dates.all().delete()
        self.profile.is_restricted = True
        self.profile.save(update_fields=['is_restricted'])
        self.assertEqual(self.apply().status_code, 400)
        self.assertEqual(self.invite().status_code, 400)

    def test_skill_and_latest_document_required_through_event_date(self):
        skill = Skill.objects.create(name='Especialidad')
        document_type = DocumentType.objects.create(name='Certificado')
        skill.required_documents.add(document_type)
        self.position.required_skills.add(skill)
        self.assertEqual(self.apply().status_code, 400)
        VolunteerSkill.objects.create(profile=self.profile, skill=skill)
        self.assertEqual(self.apply().status_code, 400)
        document = VolunteerDocument.objects.create(profile=self.profile, document_type=document_type, version=1, storage_key='not-a-real-file', size=100, mime_type='application/pdf', checksum='x', scan_status='clean', status='validated', expires_on=timezone.localdate() + timedelta(days=1))
        self.assertEqual(self.apply().status_code, 400)
        document.expires_on = timezone.localdate() + timedelta(days=30)
        document.save(update_fields=['expires_on'])
        self.assertEqual(self.apply().status_code, 201)

    def test_rechecks_eligibility_on_acceptance(self):
        self.invite()
        item = Participation.objects.get()
        self.profile.availability_slots.all().delete()
        self.assertEqual(self.decision(item, 'accept').status_code, 400)
        item.refresh_from_db()
        self.assertEqual(item.status, 'invited')

    def test_conflicting_confirmed_activity_blocks_acceptance(self):
        self.invite()
        item = Participation.objects.get()
        event, position = event_fixture()
        Participation.objects.create(profile=self.profile, event=event, position=position, status='confirmed')
        self.assertEqual(self.decision(item, 'accept').status_code, 400)

    def test_revision_prevents_repeated_decision(self):
        self.invite()
        item = Participation.objects.get()
        self.assertEqual(self.decision(item, 'accept').status_code, 200)
        self.assertEqual(self.decision(item, 'decline', revision=0).status_code, 409)

    def test_attendance_only_staff_after_event_starts(self):
        item = Participation.objects.create(event=self.event, position=self.position, profile=self.profile, status='confirmed')
        self.assertEqual(self.decision(item, 'present', self.staff).status_code, 400)
        self.event.starts_at = timezone.now() - timedelta(hours=3)
        self.event.ends_at = timezone.now() - timedelta(hours=1)
        self.event.save(update_fields=['starts_at', 'ends_at'])
        self.assertEqual(self.decision(item, 'present').status_code, 403)
        self.assertEqual(self.decision(item, 'present', self.staff).json()['attendance'], 'present')

    def test_private_address_only_confirmed_and_own_participations(self):
        self.apply()
        item = Participation.objects.get()
        self.assertNotIn('address', self.client.get('/api/activities/participations/').json()['results'][0])
        self.decision(item, 'confirm', self.staff)
        self.assertEqual(self.client.get('/api/activities/participations/').json()['results'][0]['address'], self.event.address)
        self.client.force_login(self.other.user)
        self.assertEqual(self.client.get('/api/activities/participations/').json()['total'], 0)

    def test_notifications_read_only_own_messages(self):
        Notification.objects.create(user=self.profile.user, message='Mensaje propio')
        Notification.objects.create(user=self.other.user, message='Mensaje ajeno')
        response = self.client.post('/api/activities/notifications/', {'read_all': True}, content_type='application/json')
        self.assertEqual(response.json()['unread'], 0)
        self.assertEqual(len(response.json()['results']), 1)
        self.assertIsNone(Notification.objects.get(user=self.other.user).read_at)

    def test_whatsapp_link_only_with_consent(self):
        self.assertNotIn('whatsapp_url', self.invite().json())
        self.profile.phone = '+56 9 1234 5678'
        self.profile.whatsapp_opt_in_at = timezone.now()
        self.profile.save(update_fields=['phone', 'whatsapp_opt_in_at'])
        response = self.staff.get(f'/api/activities/operations/events/{self.event.pk}/participants/')
        self.assertTrue(response.json()['results'][0]['whatsapp_url'].startswith('https://wa.me/56912345678?'))

    def test_event_cancellation_notifies_and_cancels_participants(self):
        self.apply()
        response = self.staff.post(f'/api/activities/operations/events/{self.event.pk}/transition/', {'revision': 0, 'status': 'cancelled', 'reason': 'Motivo de prueba'}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Participation.objects.get().status, 'cancelled')
        self.assertTrue(Notification.objects.filter(message__startswith='Actividad cancelada').exists())


@skipUnless(connection.vendor == 'postgresql', 'Requiere bloqueos de PostgreSQL')
class CapacityConcurrencyTests(TransactionTestCase):
    def test_two_acceptances_for_one_remaining_slot(self):
        event, position = event_fixture()
        profiles = [make_profile(f'concurrent{number}@example.org') for number in range(2)]
        for profile in profiles:
            available(profile, event)
        items = [Participation.objects.create(event=event, position=position, profile=profile, status='invited', expires_at=timezone.now() + timedelta(hours=48)) for profile in profiles]
        barrier = Barrier(2)

        def worker(item):
            try:
                client = Client()
                client.force_login(item.profile.user)
                barrier.wait(timeout=15)
                response = client.post(f'/api/activities/participations/{item.pk}/decision/', {'revision': 0, 'action': 'accept'}, content_type='application/json')
                return response.status_code, response.json().get('status')
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(worker, items))
        self.assertEqual(sorted(results), [(200, 'confirmed'), (200, 'waitlisted')])
        self.assertEqual(Participation.objects.filter(status='confirmed').count(), 1)
