import re
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.contrib.auth.models import Group, Permission
from django.core import mail
from django.core.management import call_command
from django.db import close_old_connections, connection, connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from .models import AccountChange, AccountManagementGuard, AuditEvent, User, VolunteerProfile


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AccountManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('setup_roles', verbosity=0)
        cls.manager = User.objects.create_user('general@example.org', first_name='Administradora', last_name='General')
        cls.manager.groups.add(Group.objects.get(name='Administrador general'))
        cls.target = User.objects.create_user('voluntario@example.org', 'A-strong-example-password-592!', first_name='Persona', last_name='Prueba')
        cls.target.groups.add(Group.objects.get(name='Voluntario'))
        EmailAddress.objects.create(user=cls.target, email=cls.target.email, primary=True, verified=True)
        now = timezone.now()
        VolunteerProfile.objects.create(user=cls.target, adult_confirmed_at=now, privacy_accepted_at=now)

    def setUp(self):
        self.client.force_login(self.manager)
        self.mfa(self.client, self.manager)

    @staticmethod
    def mfa(client, user):
        session = client.session
        session['account_authentication_methods_user'] = str(user.pk)
        session['account_authentication_methods'] = [{'method': 'mfa', 'at': timezone.now().timestamp()}]
        session.save()

    def update(self, target=None, revision=0, client=None, **changes):
        return (client or self.client).patch(f'/api/management/users/{(target or self.target).pk}/', {
            'revision': revision, 'reason': 'Cambio administrativo de prueba.', **changes,
        }, content_type='application/json')

    def create(self, **changes):
        return self.client.post('/api/management/users/', {
            'email': 'invitado@example.org', 'first_name': 'Persona', 'last_name': 'Invitada',
            'roles': ['Voluntario'], 'reason': 'Alta autorizada para pruebas.', **changes,
        }, content_type='application/json')

    def test_list_search_filter_and_no_credentials(self):
        response = self.client.get('/api/management/users/?q=voluntario&active=true&role=Voluntario')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['total'], 1)
        row = response.json()['results'][0]
        self.assertEqual(row['email'], self.target.email)
        self.assertNotIn('password', row)
        self.assertNotIn('user_permissions', row)
        self.assertNotIn('session_version', row)

    def test_anonymous_volunteer_and_secretary_cannot_manage_accounts(self):
        self.assertEqual(Client().get('/api/management/users/').status_code, 403)
        for group in ['Voluntario', 'Secretaría']:
            self.target.groups.set([Group.objects.get(name=group)])
            client = Client()
            client.force_login(self.target)
            self.mfa(client, self.target)
            self.assertEqual(client.get('/api/management/users/').status_code, 403)
            self.assertEqual(self.update(client=client, is_active=False).status_code, 403)

    def test_manager_without_mfa_is_denied(self):
        session = self.client.session
        session['account_authentication_methods'] = []
        session.save()
        self.assertEqual(self.client.get('/api/management/users/').status_code, 403)

    def test_csrf_is_required_for_changes(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.manager)
        self.mfa(client, self.manager)
        self.assertEqual(self.update(client=client, is_active=False).status_code, 403)

    def test_identity_change_is_audited_without_duplicate_personal_values(self):
        response = self.update(first_name='Nombre corregido')
        self.assertEqual(response.status_code, 200)
        self.target.refresh_from_db()
        self.assertEqual(self.target.first_name, 'Nombre corregido')
        self.assertEqual(self.target.management_revision, 1)
        self.assertEqual(self.target.session_version, 0)
        change = AccountChange.objects.get(action='updated_by_admin')
        self.assertEqual(change.actor, self.manager)
        self.assertEqual(change.fields_changed, ['first_name'])
        self.assertNotIn('first_name', change.after_access)
        self.assertTrue(AuditEvent.objects.filter(action='account.updated_by_admin').exists())

    def test_roles_and_staff_are_derived_only_from_approved_roles(self):
        self.assertEqual(self.update(roles=['Administrador general']).status_code, 200)
        self.target.refresh_from_db()
        self.assertTrue(self.target.is_staff)
        self.assertFalse(self.target.is_superuser)
        self.assertTrue(self.target.has_perm('accounts.manage_accounts'))
        self.assertEqual(self.update(revision=1, roles=['Secretaría']).status_code, 200)
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_staff)

    def test_role_change_invalidates_existing_session(self):
        target_client = Client()
        target_client.force_login(self.target)
        self.assertEqual(target_client.get('/api/profile/').status_code, 200)
        self.assertEqual(self.update(roles=['Secretaría']).status_code, 200)
        self.assertEqual(target_client.get('/api/profile/').status_code, 403)

    def test_deactivation_then_reactivation_does_not_revive_old_session(self):
        client = Client()
        client.force_login(self.target)
        self.assertEqual(self.update(is_active=False).status_code, 200)
        self.assertEqual(client.get('/api/profile/').status_code, 403)
        self.assertEqual(self.update(revision=1, is_active=True).status_code, 200)
        self.assertEqual(client.get('/api/profile/').status_code, 403)

    def test_password_reset_does_not_overwrite_concurrent_deactivation(self):
        from .adapter import FoundationAccountAdapter
        stale_user = User.objects.get(pk=self.target.pk)
        self.assertEqual(self.update(is_active=False).status_code, 200)
        FoundationAccountAdapter().set_password(stale_user, 'New-test-password-that-stays-private-259!')
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_active)
        self.assertEqual(self.target.session_version, 1)

    def test_self_role_change_and_deactivation_are_denied(self):
        self.assertEqual(self.update(target=self.manager, roles=['Voluntario']).status_code, 403)
        self.assertEqual(self.update(target=self.manager, is_active=False).status_code, 403)
        self.manager.refresh_from_db()
        self.assertTrue(self.manager.is_active)
        self.assertTrue(self.manager.groups.filter(name='Administrador general').exists())

    def test_self_identity_change_is_allowed(self):
        self.assertEqual(self.update(target=self.manager, first_name='Nombre propio').status_code, 200)
        self.assertEqual(self.client.get('/api/management/users/').status_code, 200)

    def test_technical_accounts_and_direct_permissions_are_protected(self):
        technical = User.objects.create_superuser('tecnica@example.org', 'Another-long-example-password-888!')
        self.assertEqual(self.update(target=technical, is_active=False).status_code, 403)
        self.target.user_permissions.add(Permission.objects.get(codename='view_volunteerprofile'))
        self.assertEqual(self.update(first_name='No permitido').status_code, 403)

    def test_unknown_roles_privilege_flags_password_and_email_injection_are_rejected(self):
        for changes in [{'roles': ['Superusuario']}, {'roles': []}, {'roles': ['Voluntario', 'Voluntario']}, {'is_superuser': True}, {'is_staff': True}, {'password': 'not-accepted'}, {'email': 'otro@example.org'}, {'user_permissions': [1]}]:
            with self.subTest(changes=changes):
                self.assertEqual(self.update(**changes).status_code, 400)

    def test_last_active_administrator_is_protected(self):
        self.manager.groups.clear()
        self.manager.user_permissions.add(Permission.objects.get(codename='manage_accounts'))
        self.target.groups.set([Group.objects.get(name='Administrador general')])
        self.assertEqual(self.update(roles=['Voluntario']).status_code, 400)
        self.assertEqual(self.update(is_active=False).status_code, 400)

    def test_stale_revision_cannot_overwrite_new_changes(self):
        self.assertEqual(self.update(first_name='Nombre revisado').status_code, 200)
        self.assertEqual(self.update(is_active=False).status_code, 409)
        self.target.refresh_from_db()
        self.assertTrue(self.target.is_active)

    def test_profile_edit_invalidates_management_revision(self):
        client = Client()
        client.force_login(self.target)
        self.assertEqual(client.patch('/api/profile/', {'first_name': 'Nombre propio nuevo', 'last_name': 'Prueba', 'phone': '', 'commune': ''}, content_type='application/json').status_code, 200)
        self.assertEqual(self.update(first_name='Dato obsoleto').status_code, 409)

    def test_account_creation_uses_invitation_and_does_not_forge_consent(self):
        response = self.create()
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.json()['email_sent'])
        user = User.objects.get(email='invitado@example.org')
        self.assertFalse(user.has_usable_password())
        self.assertFalse(user.is_superuser)
        self.assertFalse(VolunteerProfile.objects.filter(user=user).exists())
        self.assertFalse(EmailAddress.objects.get(user=user).verified)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/accounts/password/reset/key/', mail.outbox[0].body)
        self.assertNotIn('/accounts/password/reset/key/', str(response.json()))

    def test_invited_recipient_can_establish_password_through_link(self):
        self.assertEqual(self.create().status_code, 201)
        link = re.search(r'https?://[^\s]+/accounts/password/reset/key/[^\s]+', mail.outbox[0].body).group(0)
        recipient = Client()
        response = recipient.get(link)
        self.assertEqual(response.status_code, 302)
        password = 'Recipient-chooses-a-strong-password-759!'
        self.assertEqual(recipient.post(response.url, {'password1': password, 'password2': password}).status_code, 302)
        self.assertTrue(User.objects.get(email='invitado@example.org').check_password(password))

    @override_settings(DEBUG=True, PUBLIC_APP_URL='http://127.0.0.1:5173')
    def test_invitation_link_uses_frontend_port(self):
        self.assertEqual(self.create().status_code, 201)
        self.assertIn('http://127.0.0.1:5173/accounts/password/reset/key/', mail.outbox[0].body)

    def test_creation_rejects_duplicate_email_case_insensitively(self):
        self.assertEqual(self.create(email=self.target.email.upper()).status_code, 400)

    def test_creation_does_not_accept_privilege_flags_or_password(self):
        for changes in [{'is_superuser': True}, {'password': 'not-accepted'}, {'is_staff': True}]:
            self.assertEqual(self.create(**changes).status_code, 400)
        self.assertFalse(User.objects.filter(email='invitado@example.org').exists())

    def test_mail_failure_keeps_account_for_retry(self):
        with patch('accounts.account_management.request_password_reset', side_effect=OSError('SMTP unavailable')):
            response = self.create()
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.json()['email_sent'])
        self.assertTrue(User.objects.filter(email='invitado@example.org').exists())
        self.assertTrue(AuditEvent.objects.filter(action='account.access_email_failed').exists())

    def test_creation_rejects_email_used_as_another_accounts_alias(self):
        EmailAddress.objects.create(user=self.target, email='alias@example.org', verified=True)
        self.assertEqual(self.create(email='alias@example.org').status_code, 400)
        self.assertFalse(User.objects.filter(email='alias@example.org').exists())

    def test_access_email_does_not_change_password_or_reveal_token(self):
        previous = self.target.password
        response = self.client.post(f'/api/management/users/{self.target.pk}/access-email/', {'reason': 'Recuperación solicitada por el titular.'}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.target.refresh_from_db()
        self.assertEqual(self.target.password, previous)
        self.assertNotIn('reset/key', str(response.json()))

    def test_delete_is_not_available(self):
        self.assertEqual(self.client.delete(f'/api/management/users/{self.target.pk}/').status_code, 405)

    def test_invited_volunteer_accepts_own_consent_before_profile_creation(self):
        self.create()
        user = User.objects.get(email='invitado@example.org')
        client = Client()
        client.force_login(user)
        body = {'adult': True, 'privacy': True, 'whatsapp': False}
        self.assertEqual(client.post('/api/profile/onboarding/', body, content_type='application/json').status_code, 403)
        EmailAddress.objects.filter(user=user).update(verified=True)
        self.assertEqual(client.post('/api/profile/onboarding/', {**body, 'adult': False}, content_type='application/json').status_code, 400)
        self.assertEqual(client.post('/api/profile/onboarding/', body, content_type='application/json').status_code, 201)
        self.assertEqual(client.post('/api/profile/onboarding/', body, content_type='application/json').status_code, 200)
        self.assertEqual(VolunteerProfile.objects.filter(user=user).count(), 1)
        self.assertEqual(client.get('/api/profile/').status_code, 200)


@skipUnless(connection.vendor == 'postgresql', 'Prueba real de bloqueo: requiere PostgreSQL.')
class ConcurrentAccountManagementTests(TransactionTestCase):
    def test_two_administrators_cannot_remove_each_other_simultaneously(self):
        call_command('setup_roles', verbosity=0)
        first = User.objects.create_user('primera@example.org')
        second = User.objects.create_user('segunda@example.org')
        role = Group.objects.get(name='Administrador general')
        first.groups.add(role)
        second.groups.add(role)
        AccountManagementGuard.objects.create(pk=1)
        barrier = Barrier(2)

        def demote(pair):
            actor_id, target_id = pair
            close_old_connections()
            try:
                actor = User.objects.get(pk=actor_id)
                client = Client()
                client.force_login(actor)
                AccountManagementTests.mfa(client, actor)
                barrier.wait(timeout=10)
                return client.patch(f'/api/management/users/{target_id}/', {
                    'revision': 0, 'roles': ['Voluntario'], 'reason': 'Reasignación administrativa de prueba.',
                }, content_type='application/json').status_code
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(demote, [(first.pk, second.pk), (second.pk, first.pk)]))
        self.assertEqual(sorted(results), [200, 403])
        self.assertEqual(User.objects.filter(is_active=True, groups__name='Administrador general').count(), 1)
