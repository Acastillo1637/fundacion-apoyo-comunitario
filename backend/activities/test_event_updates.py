from datetime import timedelta
from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.contrib.auth.models import Group, Permission
from django.test import Client, TestCase
from django.utils import timezone

from accounts.models import AuditEvent, RequesterProfile, User
from volunteers.tests import make_profile
from .models import EventChange, Notification, Participation
from .test_participation import authenticate_operator, event_fixture


class PublishedInformationTests(TestCase):
    def setUp(self):
        self.event, self.position = event_fixture()
        self.profile = make_profile('event-update-volunteer@example.org')
        self.operator = User.objects.create_user('event-update-operator@example.org', first_name='Coordinacion')
        self.operator.user_permissions.add(Permission.objects.get(codename='manage_operations'))
        self.participation = Participation.objects.create(event=self.event, position=self.position, profile=self.profile, status='confirmed')
        self.staff = Client()
        authenticate_operator(self.staff, self.operator)
        self.path = f'/api/activities/operations/events/{self.event.pk}/'

    def update(self, **changes):
        return self.staff.patch(self.path, {'revision': 0, 'reason': 'Corrección informativa de prueba.',
            'title': 'Título actualizado de la actividad', **changes}, content_type='application/json')

    def test_public_update_preserves_schedule_positions_and_participants(self):
        start, end, address = self.event.starts_at, self.event.ends_at, self.event.address
        response = self.update()
        self.assertEqual(response.status_code, 200)
        self.event.refresh_from_db()
        self.participation.refresh_from_db()
        self.assertEqual((self.event.starts_at, self.event.ends_at, self.event.address), (start, end, address))
        self.assertEqual(self.event.positions.get().pk, self.position.pk)
        self.assertEqual(self.participation.status, 'confirmed')
        self.assertEqual(self.event.revision, 1)
        self.assertTrue(AuditEvent.objects.filter(action='event.information.updated').exists())

    def test_title_change_has_private_audit_and_notifies_participant_once(self):
        old_title = self.event.title
        self.update()
        change = EventChange.objects.get()
        self.assertEqual(change.actor, self.operator)
        self.assertEqual(change.before_public, {'title': old_title})
        self.assertEqual(change.after_public['title'], 'Título actualizado de la actividad')
        notice = Notification.objects.get()
        self.assertEqual(notice.user_id, self.profile.user_id)
        self.assertEqual(notice.target, 'participations')
        self.assertNotIn('Corrección informativa', notice.message)
        self.assertEqual(self.update().status_code, 409)
        self.assertEqual(Notification.objects.count(), 1)

    def test_private_only_update_does_not_notify_or_duplicate_private_notes(self):
        response = self.update(title=self.event.title, internal_notes='Nota privada reservada')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Notification.objects.exists())
        change = EventChange.objects.get()
        self.assertEqual(change.fields_changed, ['internal_notes'])
        self.assertEqual(change.before_public, {})
        self.assertEqual(change.after_public, {})

    def test_rejects_logistic_and_authority_field_injection(self):
        for field, value in [('address', 'Otra dirección'), ('date', '2030-01-01'), ('positions', []), ('status', 'finished'), ('request_id', 'unknown')]:
            with self.subTest(field=field):
                self.assertEqual(self.update(**{field: value}).status_code, 400)
        self.assertFalse(EventChange.objects.exists())

    def test_requires_real_change_reason_and_editable_fields(self):
        self.assertEqual(self.update(reason='').status_code, 400)
        self.assertEqual(self.update(title=self.event.title).status_code, 400)
        self.assertEqual(self.staff.patch(self.path, {'revision': 0, 'reason': 'Motivo sin cambios'}, content_type='application/json').status_code, 400)
        self.assertFalse(Notification.objects.exists())

    def test_volunteer_and_anonymous_cannot_edit(self):
        self.client.force_login(self.profile.user)
        for client in [self.client, Client()]:
            self.assertEqual(client.patch(self.path, {'revision': 0, 'reason': 'Motivo de prueba', 'title': 'Nuevo título'}, content_type='application/json').status_code, 403)

    def test_started_or_terminal_events_are_protected(self):
        for status in ['draft', 'finished', 'cancelled']:
            self.event.status = status
            self.event.save(update_fields=['status'])
            self.assertEqual(self.update().status_code, 400)
        self.event.status = 'open'
        self.event.starts_at = timezone.now() - timedelta(hours=2)
        self.event.ends_at = timezone.now() + timedelta(hours=2)
        self.event.save(update_fields=['status', 'starts_at', 'ends_at'])
        self.assertEqual(self.update().status_code, 400)

    def test_all_active_assignments_notified_but_cancelled_people_excluded(self):
        for index, status in enumerate(['applied', 'invited', 'waitlisted', 'confirmed', 'declined', 'cancelled', 'rejected']):
            profile = make_profile(f'event-update-{index}@example.org')
            Participation.objects.create(event=self.event, position=self.position, profile=profile,
                status=status, assignment='backup' if status == 'confirmed' else 'primary',
                expires_at=timezone.now() + timedelta(hours=1) if status == 'invited' else None)
        self.update()
        self.assertEqual(Notification.objects.count(), 5)

    def test_new_description_is_visible_to_owner_and_public_without_private_audit(self):
        description = 'Información pública corregida para la comunidad.'
        self.update(public_description=description, internal_notes='Nota que no debe publicarse')
        self.client.force_login(self.profile.user)
        own = self.client.get('/api/activities/participations/').json()['results'][0]
        self.assertEqual(own['public_description'], description)
        public = Client().get('/api/activities/public-events/').json()['results'][0]
        self.assertEqual(public['public_description'], description)
        self.assertNotIn('changes', public)
        self.assertNotIn('internal_notes', public)
        self.assertNotIn('Nota que no debe', str(public))

    def test_requester_receives_notice_and_sees_related_event_update(self):
        user = User.objects.create_user('event-update-requester@example.org')
        user.groups.add(Group.objects.get_or_create(name='Solicitante')[0])
        EmailAddress.objects.create(user=user, email=user.email, verified=True)
        owner = RequesterProfile.objects.create(user=user, requester_type='person', phone='+56912345678',
            adult_confirmed_at=timezone.now(), privacy_accepted_at=timezone.now())
        source = self.event.request
        source.requester = owner
        source.save(update_fields=['requester'])
        self.update()
        self.assertEqual(Notification.objects.get(user=user).target, 'my-requests')
        self.client.force_login(user)
        event = self.client.get('/api/requester/requests/').json()['results'][0]['events'][0]
        self.assertEqual(event['title'], 'Título actualizado de la actividad')
        self.assertNotIn('internal_notes', event)

    def test_failed_notification_rolls_back_edit_and_audit(self):
        with patch('activities.services.Notification.objects.bulk_create', side_effect=RuntimeError('notification failure')):
            with self.assertRaises(RuntimeError):
                self.update()
        self.event.refresh_from_db()
        self.assertEqual(self.event.revision, 0)
        self.assertFalse(EventChange.objects.exists())

    def test_patch_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        authenticate_operator(client, self.operator)
        self.assertEqual(client.patch(self.path, {'revision': 0, 'reason': 'Prueba CSRF', 'title': 'Título de prueba'}, content_type='application/json').status_code, 403)

    def test_expired_invitations_are_not_notified(self):
        profile = make_profile('event-update-expired@example.org')
        Participation.objects.create(event=self.event, position=self.position, profile=profile, status='invited', expires_at=timezone.now() - timedelta(minutes=1))
        self.update()
        self.assertFalse(Notification.objects.filter(user=profile.user).exists())

    def test_requester_and_participant_same_account_receives_one_notice(self):
        owner = RequesterProfile.objects.create(user=self.profile.user, requester_type='person', phone='+56912345678', adult_confirmed_at=timezone.now(), privacy_accepted_at=timezone.now())
        source = self.event.request
        source.requester = owner
        source.save(update_fields=['requester'])
        self.update()
        self.assertEqual(Notification.objects.filter(user=self.profile.user).count(), 1)
