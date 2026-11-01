from allauth.account.models import EmailAddress
from allauth.mfa.totp.internal.auth import TOTP, format_hotp_value, generate_totp_secret, hotp_value, yield_hotp_counters_from_time
from allauth.mfa.recovery_codes.internal.auth import RecoveryCodes
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import Client, TestCase

from activities.test_participation import authenticate_operator
from volunteers.models import DocumentType, Skill
from volunteers.tests import make_profile
from .models import AuditEvent, User


class UnifiedLoginTests(TestCase):
    def setUp(self):
        call_command('setup_roles', verbosity=0)
        self.password = 'Long-test-password-52953!'
        self.user = User.objects.create_user('admin-unified@example.org', self.password)
        self.user.groups.add(Group.objects.get(name='Administrador general'))
        EmailAddress.objects.create(user=self.user, email=self.user.email, primary=True, verified=True)

    def login(self, **changes):
        return self.client.post('/api/login/', {'email': self.user.email, 'password': self.password, **changes}, content_type='application/json')

    def test_one_login_opens_admin_operations_and_catalogs(self):
        self.assertEqual(self.login().status_code, 200)
        for path in ['management/users/', 'management/catalogs/skills/', 'activities/operations/requests/', 'documents/review-queue/', 'workspace-summary/?portal=administration']:
            with self.subTest(path=path):
                self.assertEqual(self.client.get('/api/' + path).status_code, 200)

    def test_enrolled_totp_cannot_be_bypassed_and_works_inline(self):
        secret = generate_totp_secret()
        TOTP.activate(self.user, secret)
        response = self.login()
        self.assertEqual(response.status_code, 409)
        self.assertTrue(response.json()['mfa_required'])
        self.assertNotIn('_auth_user_id', self.client.session)
        code = format_hotp_value(hotp_value(secret, next(yield_hotp_counters_from_time())))
        self.assertEqual(self.login(code=code).status_code, 200)
        self.assertEqual(self.client.get('/api/management/users/').status_code, 200)
        self.client.logout()
        self.assertEqual(self.login(code=code).status_code, 400)

    def test_wrong_factor_does_not_start_session(self):
        TOTP.activate(self.user, generate_totp_secret())
        self.assertEqual(self.login(code='invalid').status_code, 400)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_recovery_code_works_once_inline(self):
        codes = RecoveryCodes.activate(self.user)
        code = codes.get_unused_codes()[0]
        self.assertEqual(self.login(code=code).status_code, 200)
        self.client.logout()
        self.assertEqual(self.login(code=code).status_code, 400)

    def test_enrolling_factor_invalidates_password_only_portal_authorization(self):
        self.login()
        TOTP.activate(self.user, generate_totp_secret())
        self.assertEqual(self.client.get('/api/management/users/').status_code, 403)


class WorkspaceTests(TestCase):
    def setUp(self):
        call_command('setup_roles', verbosity=0)
        self.user = User.objects.create_user('workspace@example.org')
        self.user.groups.add(Group.objects.get(name='Administrador general'))
        authenticate_operator(self.client, self.user)

    def test_admin_counts_real_accounts(self):
        response = self.client.get('/api/workspace-summary/?portal=administration')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['metrics'][0]['value'], 1)

    def test_volunteer_cannot_read_staff_summary_or_catalogs(self):
        profile = make_profile('workspace-volunteer@example.org')
        self.client.force_login(profile.user)
        for path in ['workspace-summary/?portal=administration', 'management/catalogs/skills/', 'operations/volunteers/']:
            self.assertEqual(self.client.get('/api/' + path).status_code, 403)
        self.assertEqual(self.client.get('/api/workspace-summary/?portal=volunteer').status_code, 200)

    def test_catalog_create_edit_deactivate_and_unique_name(self):
        document = DocumentType.objects.create(name='Certificado de ejemplo')
        data = {'name': 'Habilidad de ejemplo', 'description': 'Descripcion', 'is_active': True, 'required_documents': [document.pk]}
        response = self.client.post('/api/management/catalogs/skills/', data, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Skill.objects.get().required_documents.get(), document)
        self.assertEqual(self.client.post('/api/management/catalogs/skills/', data, content_type='application/json').status_code, 400)
        data.update(id=response.json()['id'], is_active=False)
        self.assertEqual(self.client.put('/api/management/catalogs/skills/', data, content_type='application/json').status_code, 200)
        self.assertFalse(Skill.objects.get().is_active)
        self.assertTrue(AuditEvent.objects.filter(action='catalog.updated').exists())

    def test_catalog_rejects_extra_fields_and_invalid_documents(self):
        data = {'name': 'Prueba', 'is_active': True, 'is_superuser': True}
        self.assertEqual(self.client.post('/api/management/catalogs/skills/', data, content_type='application/json').status_code, 400)
        data.pop('is_superuser')
        data['required_documents'] = [99999]
        self.assertEqual(self.client.post('/api/management/catalogs/skills/', data, content_type='application/json').status_code, 400)

    def test_restriction_requires_reason_and_updates_audit(self):
        profile = make_profile('restricted@example.org')
        data = {'id': profile.pk, 'restricted': True, 'reason': ''}
        self.assertEqual(self.client.post('/api/operations/volunteers/', data, content_type='application/json').status_code, 400)
        data['reason'] = 'Restriccion temporal de prueba'
        self.assertEqual(self.client.post('/api/operations/volunteers/', data, content_type='application/json').status_code, 200)
        profile.refresh_from_db()
        self.assertTrue(profile.is_restricted)
        self.assertTrue(AuditEvent.objects.filter(action='volunteer.restriction.updated').exists())

    def test_mutations_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        authenticate_operator(client, self.user)
        self.assertEqual(client.post('/api/management/catalogs/skills/', {}, content_type='application/json').status_code, 403)
        self.assertEqual(client.post('/api/activities/notifications/', {'read_all': True}, content_type='application/json').status_code, 403)

    def test_own_account_name_edit_updates_revision_without_access_changes(self):
        data = {'first_name': 'Nombre', 'last_name': 'Nuevo', 'revision': 0}
        response = self.client.patch('/api/account-profile/', data, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['management_revision'], 1)
        self.assertEqual(response.json()['roles'], ['Administrador general'])
        self.assertEqual(self.client.patch('/api/account-profile/', data, content_type='application/json').status_code, 409)
        data.update(revision=1, roles=['Voluntario'])
        self.assertEqual(self.client.patch('/api/account-profile/', data, content_type='application/json').status_code, 400)

    def test_catalog_and_restriction_malformed_input_returns_validation_error(self):
        for path, method, data in [('management/catalogs/skills/', 'put', {'id': 'invalid', 'name': 'Prueba', 'is_active': True}),
                                   ('management/catalogs/skills/', 'post', []),
                                   ('operations/volunteers/', 'post', {'id': 'invalid', 'restricted': True, 'reason': 'Motivo de prueba'})]:
            self.assertEqual(getattr(self.client, method)('/api/' + path, data, content_type='application/json').status_code, 400)
