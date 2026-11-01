import json
import re
from allauth.account.models import EmailAddress
from django.contrib.auth.models import Permission
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from .models import User, VolunteerProfile


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AccountTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ana@example.org', 'A-strong-example-password-592!', first_name='Ana')
        VolunteerProfile.objects.create(user=self.user, adult_confirmed_at=timezone.now(), privacy_accepted_at=timezone.now())

    def post(self, endpoint, data, client=None):
        return (client or self.client).post(endpoint, json.dumps(data), content_type='application/json')

    def test_registration_never_grants_privileges(self):
        response = self.post('/api/register/', {'email': 'nuevo@example.org', 'password': 'Long-example-password-998!', 'first_name': 'Nueva', 'last_name': 'Persona', 'adult': True, 'privacy': True, 'is_superuser': True, 'is_staff': True})
        self.assertEqual(response.status_code, 202)
        user = User.objects.get(email='nuevo@example.org')
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(VolunteerProfile.objects.filter(user=user).exists())
        self.assertEqual(len(mail.outbox), 1)

    def test_registration_requires_adult_and_privacy(self):
        response = self.post('/api/register/', {'email': 'nuevo@example.org', 'password': 'Long-example-password-998!', 'first_name': 'Nueva', 'last_name': 'Persona', 'adult': False, 'privacy': True})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(email='nuevo@example.org').exists())

    def test_unverified_email_cannot_login(self):
        response = self.post('/api/login/', {'email': self.user.email, 'password': 'A-strong-example-password-592!'})
        self.assertEqual(response.status_code, 400)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_verified_login_and_logout(self):
        EmailAddress.objects.create(user=self.user, email=self.user.email, verified=True, primary=True)
        response = self.post('/api/login/', {'email': self.user.email.upper(), 'password': 'A-strong-example-password-592!'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/api/profile/').status_code, 200)
        self.post('/api/logout/', {})
        self.assertEqual(self.client.get('/api/profile/').status_code, 403)

    def test_anonymous_login_requires_csrf(self):
        response = self.post('/api/login/', {}, Client(enforce_csrf_checks=True))
        self.assertEqual(response.status_code, 403)

    def test_only_own_profile_can_be_modified(self):
        other = User.objects.create_user('otro@example.org', 'Other-long-password-349!', first_name='Otro')
        self.client.force_login(self.user)
        response = self.client.patch('/api/profile/', json.dumps({'first_name': 'Ana nueva', 'last_name': 'Pérez', 'phone': '+56 9 1234 5678', 'commune': 'Maipú'}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        other.refresh_from_db()
        self.assertEqual(other.first_name, 'Otro')
        response = self.client.patch('/api/profile/', json.dumps({'id': str(other.pk), 'is_staff': True}), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)

    def test_volunteer_cannot_read_operations(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/api/operations/').status_code, 403)

    def test_operations_requires_permission_and_mfa(self):
        self.user.user_permissions.add(Permission.objects.get(codename='view_volunteerprofile'))
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/api/operations/').status_code, 403)
        session = self.client.session
        session['account_authentication_methods'] = [{'method': 'mfa', 'at': timezone.now().timestamp()}]
        session['account_authentication_methods_user'] = str(self.user.pk)
        session.save()
        self.assertEqual(self.client.get('/api/operations/').status_code, 200)

    def test_staff_cannot_bypass_mfa_via_json_login(self):
        self.user.is_staff = True
        self.user.save()
        EmailAddress.objects.create(user=self.user, email=self.user.email, verified=True, primary=True)
        response = self.post('/api/login/', {'email': self.user.email, 'password': 'A-strong-example-password-592!'})
        self.assertEqual(response.status_code, 409)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_login_is_rate_limited(self):
        for _ in range(10):
            self.post('/api/login/', {})
        self.assertEqual(self.post('/api/login/', {}).status_code, 429)

    def test_allauth_registration_cannot_bypass_consent(self):
        response = self.client.get('/accounts/signup/')
        self.assertContains(response, 'registro', status_code=200)

    def test_email_confirmation_link_verifies_account(self):
        self.post('/api/register/', {'email': 'verify@example.org', 'password': 'Long-example-password-998!', 'first_name': 'Ana', 'last_name': 'Prueba', 'adult': True, 'privacy': True})
        link = re.search(r'https?://[^\s]+/accounts/confirm-email/[^\s]+', mail.outbox[0].body).group(0)
        response = self.client.get(link)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(EmailAddress.objects.get(email='verify@example.org').verified)
        self.client.post(link)
        self.assertTrue(EmailAddress.objects.get(email='verify@example.org').verified)

    def test_password_recovery_sends_email(self):
        EmailAddress.objects.create(user=self.user, email=self.user.email, verified=True, primary=True)
        response = self.client.post('/accounts/password/reset/', {'email': self.user.email})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)

    def test_stale_mfa_for_another_user_is_rejected(self):
        self.user.user_permissions.add(Permission.objects.get(codename='view_volunteerprofile'))
        self.client.force_login(self.user)
        session = self.client.session
        session['account_authentication_methods'] = [{'method': 'mfa', 'at': timezone.now().timestamp()}]
        session['account_authentication_methods_user'] = 'another-user'
        session.save()
        self.assertEqual(self.client.get('/api/operations/').status_code, 403)
