import json
import re
from allauth.account.models import EmailAddress
from django.contrib.auth.models import Group, Permission
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.utils import timezone
from .models import User, VolunteerProfile


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AccountTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ana@example.org', 'A-strong-example-password-592!', first_name='Ana')
        self.user.groups.add(Group.objects.get_or_create(name='Voluntario')[0])
        VolunteerProfile.objects.create(user=self.user, adult_confirmed_at=timezone.now(), privacy_accepted_at=timezone.now())

    def post(self, endpoint, data, client=None):
        if endpoint == '/api/register/':
            data = {'phone': '+56912345678', 'commune': 'Renca', 'whatsapp': True, **data}
        return (client or self.client).post(endpoint, json.dumps(data), content_type='application/json')

    def test_registration_never_grants_privileges(self):
        response = self.post('/api/register/', {'email': 'nuevo@example.org', 'password': 'Long-example-password-998!', 'first_name': 'Nueva', 'last_name': 'Persona', 'adult': True, 'privacy': True, 'is_superuser': True, 'is_staff': True})
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email='nuevo@example.org')
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(VolunteerProfile.objects.filter(user=user).exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_registration_requires_adult_and_privacy(self):
        response = self.post('/api/register/', {'email': 'nuevo@example.org', 'password': 'Long-example-password-998!', 'first_name': 'Nueva', 'last_name': 'Persona', 'adult': False, 'privacy': True})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(email='nuevo@example.org').exists())

    def test_unverified_email_can_login_without_changing_verification(self):
        response = self.post('/api/login/', {'email': self.user.email, 'password': 'A-strong-example-password-592!'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('_auth_user_id', self.client.session)

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
        response = self.client.patch('/api/profile/', json.dumps({'first_name': 'Ana nueva', 'last_name': 'Pérez', 'phone': '+56912345678', 'commune': 'Maipú'}), content_type='application/json')
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

    def test_staff_without_enrolled_factor_uses_unified_login(self):
        self.user.is_staff = True
        self.user.save()
        EmailAddress.objects.create(user=self.user, email=self.user.email, verified=True, primary=True)
        response = self.post('/api/login/', {'email': self.user.email, 'password': 'A-strong-example-password-592!'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('_auth_user_id', self.client.session)

    def test_login_is_rate_limited(self):
        for _ in range(10):
            self.post('/api/login/', {})
        self.assertEqual(self.post('/api/login/', {}).status_code, 429)

    def test_allauth_registration_cannot_bypass_consent(self):
        response = self.client.get('/accounts/signup/')
        self.assertContains(response, 'registro', status_code=200)

    def test_registration_allows_immediate_login_without_mail_or_confirmation_token(self):
        from allauth.account.models import EmailConfirmation
        payload = {'email': 'verify@example.org', 'password': 'Long-example-password-998!', 'first_name': 'Ana', 'last_name': 'Prueba', 'adult': True, 'privacy': True}
        response = self.post('/api/register/', payload)
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email=payload['email'])
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password(payload['password']))
        self.assertNotEqual(user.password, payload['password'])
        self.assertFalse(EmailAddress.objects.get(user=user).verified)
        self.assertEqual(EmailConfirmation.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(self.post('/api/login/', {'email':user.email,'password':payload['password']}).status_code, 200)
        self.assertEqual(self.client.get('/api/profile/').status_code, 200)
        self.assertEqual(self.client.get('/api/management/users/').status_code, 403)
        self.assertEqual(len(mail.outbox), 0)

    def test_duplicate_email_does_not_replace_password_or_roles(self):
        response = self.post('/api/register/', {'email': self.user.email.upper(), 'password': 'Long-example-password-998!', 'first_name': 'Otra', 'last_name': 'Persona', 'adult': True, 'privacy': True})
        self.assertEqual(response.status_code, 409)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('A-strong-example-password-592!'))
        self.assertEqual(len(mail.outbox), 0)

    def test_weak_password_and_disabled_account_still_rejected(self):
        payload = {'email':'weak@example.org','password':'123456','first_name':'Ana','last_name':'Prueba','adult':True,'privacy':True}
        self.assertEqual(self.post('/api/register/',payload).status_code,400)
        self.user.is_active=False; self.user.save(update_fields=['is_active'])
        self.assertEqual(self.post('/api/login/',{'email':self.user.email,'password':'A-strong-example-password-592!'}).status_code,400)

    def test_password_reset_never_targets_another_accounts_secondary_alias(self):
        other=User.objects.create_user('other-owner@example.org','Other-long-password-943!')
        EmailAddress.objects.create(user=other,email=self.user.email,verified=True)
        self.client.post('/accounts/password/reset/',{'email':self.user.email})
        self.assertEqual(len(mail.outbox),1)
        from allauth.account.utils import user_pk_to_url_str
        self.assertIn('/'+user_pk_to_url_str(self.user)+'-',mail.outbox[0].body)
        self.assertNotIn('/'+user_pk_to_url_str(other)+'-',mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to,[self.user.email])

    def test_password_recovery_sends_email(self):
        EmailAddress.objects.create(user=self.user, email=self.user.email, verified=True, primary=True)
        response = self.client.post('/accounts/password/reset/', {'email': self.user.email})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)

    def test_full_password_recovery_changes_password_and_rejects_reused_link(self):
        EmailAddress.objects.create(user=self.user, email=self.user.email, verified=False, primary=True)
        previous_session=Client()
        self.assertEqual(self.post('/api/login/',{'email':self.user.email,'password':'A-strong-example-password-592!'},previous_session).status_code,200)
        self.client.post('/accounts/password/reset/', {'email': self.user.email})
        link = re.search(r'https?://[^\s]+/accounts/password/reset/key/[^\s]+', mail.outbox[0].body).group(0)
        response = self.client.get(link)
        self.assertEqual(response.status_code, 302)
        form_url = response.url
        self.assertContains(self.client.get(form_url), 'Elige una nueva contraseña')
        password = 'Another-strong-example-password-739!'
        response = self.client.post(form_url, {'password1': password, 'password2': password}, follow=True)
        self.assertContains(response, 'Contraseña actualizada')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(password))
        self.assertFalse(self.user.check_password('A-strong-example-password-592!'))
        self.assertEqual(self.post('/api/login/', {'email': self.user.email, 'password': password}).status_code, 200)
        self.assertContains(Client().get(link), 'El enlace no es válido')
        self.assertEqual(previous_session.get('/api/profile/').status_code,403)

    @override_settings(DEBUG=True, EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend')
    def test_console_recovery_page_explains_where_to_find_link(self):
        response = self.client.get('/accounts/password/reset/done/')
        self.assertContains(response, 'terminal de Django')
        self.assertContains(response, 'no enviamos mensajes')
        self.assertNotContains(response, 'Le hemos enviado')

    @override_settings(DEBUG=False, SECURE_SSL_REDIRECT=False)
    def test_production_recovery_page_does_not_show_local_instructions(self):
        response = self.client.get('/accounts/password/reset/done/')
        self.assertNotContains(response, 'terminal de Django')
        self.assertContains(response, 'Si el correo corresponde')

    def test_stale_mfa_for_another_user_is_rejected(self):
        self.user.user_permissions.add(Permission.objects.get(codename='view_volunteerprofile'))
        self.client.force_login(self.user)
        session = self.client.session
        session['account_authentication_methods'] = [{'method': 'mfa', 'at': timezone.now().timestamp()}]
        session['account_authentication_methods_user'] = 'another-user'
        session.save()
        self.assertEqual(self.client.get('/api/operations/').status_code, 403)

    @override_settings(CSRF_TRUSTED_ORIGINS=['http://127.0.0.1:5173', 'http://localhost:5173'])
    def test_local_frontend_origin_can_submit_with_valid_csrf(self):
        for origin in ['http://127.0.0.1:5173', 'http://localhost:5173']:
            with self.subTest(origin=origin):
                client = Client(enforce_csrf_checks=True)
                token = client.get('/api/session/').json()['csrf_token']
                response = client.post('/api/register/', '{}', content_type='application/json',
                                       HTTP_ORIGIN=origin, HTTP_X_CSRFTOKEN=token)
                # La petición alcanza el validador del registro; los datos vacíos son inválidos.
                self.assertEqual(response.status_code, 400)
                self.assertIn('email', response.json())

    @override_settings(CSRF_TRUSTED_ORIGINS=['http://127.0.0.1:5173'])
    def test_trusted_origin_still_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.get('/api/session/')
        response = client.post('/api/register/', '{}', content_type='application/json',
                               HTTP_ORIGIN='http://127.0.0.1:5173')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['code'], 'csrf_failed')

    @override_settings(CSRF_TRUSTED_ORIGINS=['http://127.0.0.1:5173'])
    def test_other_origin_is_rejected_even_with_valid_token(self):
        client = Client(enforce_csrf_checks=True)
        token = client.get('/api/session/').json()['csrf_token']
        response = client.post('/api/register/', '{}', content_type='application/json',
                               HTTP_ORIGIN='https://otro-sitio.example', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['code'], 'csrf_failed')
