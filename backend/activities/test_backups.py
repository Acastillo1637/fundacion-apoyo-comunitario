from datetime import timedelta

from django.contrib.auth.models import Permission
from django.test import Client, TestCase
from django.utils import timezone

from accounts.models import User
from volunteers.tests import make_profile
from .models import EventPosition, Notification, Participation
from .participation import eligibility
from .test_participation import authenticate_operator, available, event_fixture


class BackupTests(TestCase):
    def setUp(self):
        self.profile = make_profile('backup@example.org')
        self.other = make_profile('primary@example.org')
        self.operator = User.objects.create_user('backup-operator@example.org')
        self.operator.user_permissions.add(Permission.objects.get(codename='manage_operations'))
        self.event, self.position = event_fixture()
        available(self.profile, self.event)
        available(self.other, self.event)
        self.staff = Client()
        authenticate_operator(self.staff, self.operator)
        self.client.force_login(self.profile.user)

    def invite(self, assignment='backup'):
        return self.staff.post(f'/api/activities/operations/events/{self.event.pk}/participants/',
            {'position_id': self.position.pk, 'profile_id': self.profile.pk, 'assignment': assignment}, content_type='application/json')

    def decide(self, item, action, staff=False):
        return (self.staff if staff else self.client).post(f'/api/activities/participations/{item.pk}/decision/',
            {'revision': item.revision, 'action': action}, content_type='application/json')

    def accepted_backup(self):
        self.assertEqual(self.invite().status_code, 201)
        item = Participation.objects.get(profile=self.profile)
        self.assertEqual(self.decide(item, 'accept').status_code, 200)
        item.refresh_from_db()
        return item

    def test_backup_acceptance_does_not_consume_primary_capacity(self):
        Participation.objects.create(event=self.event, position=self.position, profile=self.other, status='confirmed')
        item = self.accepted_backup()
        self.assertEqual(item.assignment, 'backup')
        self.assertEqual(item.status, 'confirmed')
        own = self.client.get('/api/activities/participations/').json()['results'][0]
        self.assertNotIn('address', own)
        result = self.staff.get(f'/api/activities/operations/events/{self.event.pk}/participants/').json()
        self.assertEqual(result['stats']['confirmed'], 1)
        self.assertEqual(result['stats']['backups'], 1)
        self.assertEqual(result['stats']['vacancies'], [])

    def test_volunteer_cannot_choose_assignment_or_activate_backup(self):
        response = self.client.post('/api/activities/participations/', {'position_id': self.position.pk, 'assignment': 'backup'}, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        item = self.accepted_backup()
        self.assertEqual(self.decide(item, 'activate-backup').status_code, 403)

    def test_activation_is_a_new_invitation_and_requires_owner_acceptance(self):
        item = self.accepted_backup()
        response = self.decide(item, 'activate-backup', staff=True)
        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.assertEqual((item.assignment, item.status), ('primary', 'invited'))
        self.assertEqual(Participation.objects.filter(status='confirmed', assignment='primary').count(), 0)
        self.assertEqual(self.decide(item, 'confirm', staff=True).status_code, 400)
        self.assertEqual(self.decide(item, 'accept').json()['status'], 'confirmed')
        self.assertTrue(Notification.objects.filter(user=self.profile.user, message__contains='invitación como titular').exists())

    def test_full_function_blocks_activation_without_changing_backup(self):
        item = self.accepted_backup()
        Participation.objects.create(event=self.event, position=self.position, profile=self.other, status='confirmed')
        self.assertEqual(self.decide(item, 'activate-backup', staff=True).status_code, 409)
        item.refresh_from_db()
        self.assertEqual((item.assignment, item.status), ('backup', 'confirmed'))

    def test_cancellation_exposes_vacancy_without_automatic_activation(self):
        item = self.accepted_backup()
        primary = Participation.objects.create(event=self.event, position=self.position, profile=self.other, status='confirmed')
        notices = Notification.objects.filter(user=self.profile.user).count()
        self.assertEqual(self.decide(primary, 'cancel', staff=True).status_code, 200)
        item.refresh_from_db()
        self.assertEqual((item.assignment, item.status), ('backup', 'confirmed'))
        self.assertEqual(Notification.objects.filter(user=self.profile.user).count(), notices)
        result = self.staff.get(f'/api/activities/operations/events/{self.event.pk}/participants/?assignment=backup&status=confirmed').json()
        self.assertEqual(result['total'], 1)
        self.assertTrue(result['results'][0]['eligible'])
        self.assertEqual(result['stats']['vacancies'][0]['available'], 1)

    def test_backup_must_accept_before_activation(self):
        self.invite()
        item = Participation.objects.get()
        self.assertEqual(self.decide(item, 'activate-backup', staff=True).status_code, 400)

    def test_activation_and_final_acceptance_recheck_restrictions(self):
        item = self.accepted_backup()
        self.profile.is_restricted = True
        self.profile.save(update_fields=['is_restricted'])
        self.assertEqual(self.decide(item, 'activate-backup', staff=True).status_code, 400)
        self.profile.is_restricted = False
        self.profile.save(update_fields=['is_restricted'])
        self.assertEqual(self.decide(item, 'activate-backup', staff=True).status_code, 200)
        item.refresh_from_db()
        self.profile.availability_slots.all().delete()
        self.assertEqual(self.decide(item, 'accept').status_code, 400)
        item.refresh_from_db()
        self.assertEqual(item.status, 'invited')

    def test_proposing_applicant_as_backup_requires_new_consent(self):
        item = Participation.objects.create(event=self.event, position=self.position, profile=self.profile, status='applied')
        self.assertEqual(self.decide(item, 'invite-backup', staff=True).status_code, 200)
        item.refresh_from_db()
        self.assertEqual((item.assignment, item.status), ('backup', 'invited'))
        self.assertEqual(self.decide(item, 'accept').json()['status'], 'confirmed')

    def test_backup_does_not_generate_attendance_or_hours(self):
        item = self.accepted_backup()
        self.event.starts_at = timezone.now() - timedelta(hours=3)
        self.event.ends_at = timezone.now() - timedelta(hours=1)
        self.event.save(update_fields=['starts_at', 'ends_at'])
        self.assertEqual(self.decide(item, 'present', staff=True).status_code, 400)

    def test_capacity_is_rechecked_when_activated_backup_accepts(self):
        item = self.accepted_backup()
        self.decide(item, 'activate-backup', staff=True)
        item.refresh_from_db()
        Participation.objects.create(event=self.event, position=self.position, profile=self.other, status='confirmed')
        self.assertEqual(self.decide(item, 'accept').json()['status'], 'waitlisted')
        self.assertEqual(Participation.objects.filter(status='confirmed', assignment='primary').count(), 1)

    def test_backup_does_not_block_another_primary_but_activation_checks_conflict(self):
        item = self.accepted_backup()
        event, position = event_fixture()
        self.assertEqual(eligibility(self.profile, position), [])
        Participation.objects.create(event=event, position=position, profile=self.profile, status='confirmed')
        self.assertEqual(self.decide(item, 'activate-backup', staff=True).status_code, 400)

    def test_activation_is_scoped_to_the_backups_function(self):
        second = EventPosition.objects.create(event=self.event, name='Otra función', capacity=1)
        item = self.accepted_backup()
        Participation.objects.create(event=self.event, position=second, profile=self.other, status='confirmed')
        self.assertEqual(self.decide(item, 'activate-backup', staff=True).status_code, 200)

    def test_invalid_filters_and_assignment_are_rejected(self):
        self.assertEqual(self.invite('superuser').status_code, 400)
        self.assertEqual(self.staff.get(f'/api/activities/operations/events/{self.event.pk}/participants/?assignment=invalid').status_code, 400)

    def test_renewed_backup_invitation_preserves_assignment_and_revision_guard(self):
        item = self.accepted_backup()
        self.assertEqual(self.decide(item, 'activate-backup', staff=True).status_code, 200)
        self.assertEqual(self.decide(item, 'activate-backup', staff=True).status_code, 409)
