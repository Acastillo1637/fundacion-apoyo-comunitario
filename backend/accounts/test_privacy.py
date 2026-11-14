from unittest.mock import patch
from django.contrib.auth.models import Group, Permission
from django.test import Client, TestCase, override_settings
from activities.models import Notification, MatchingPolicy
from activities.test_participation import authenticate_operator
from volunteers.tests import make_profile
from .checks import production_readiness
from .models import PrivacyRequest, PrivacyRequestChange, User


class PrivacyTests(TestCase):
    def setUp(self):
        self.owner=make_profile('privacy-owner@example.org')
        self.other=make_profile('privacy-other@example.org')
        group,_=Group.objects.get_or_create(name='Administrador general')
        self.admins=[User.objects.create_user(f'privacy-admin-{index}@example.org') for index in range(2)]
        for user in self.admins:
            user.groups.add(group)
            user.user_permissions.add(Permission.objects.get(codename='manage_accounts'))
        inactive=User.objects.create_user('privacy-inactive@example.org',is_active=False);inactive.groups.add(group)
        self.client.force_login(self.owner.user)
        self.staff=Client();authenticate_operator(self.staff,self.admins[0])

    def create_request(self):
        response=self.client.post('/api/privacy/requests/',{'kind':'deletion','note':'Quisiera revisar la eliminación de mi cuenta de prueba.'},content_type='application/json')
        self.assertEqual(response.status_code,201,response.content)
        return response.json()

    def test_all_active_administrators_receive_notice_without_exposing_request_text(self):
        request=self.create_request()
        notifications=Notification.objects.filter(target='privacy-requests')
        self.assertEqual(set(notifications.values_list('user_id',flat=True)),{user.pk for user in self.admins})
        self.assertTrue(all('eliminación de mi cuenta' not in item.message for item in notifications))

    def test_users_only_see_their_requests_and_cannot_review(self):
        item=self.create_request()
        self.assertEqual(self.client.get('/api/privacy/requests/?scope=all').status_code,403)
        self.client.force_login(self.other.user)
        self.assertEqual(self.client.get('/api/privacy/requests/').json()['total'],0)
        self.assertEqual(self.client.post(f'/api/privacy/requests/{item["id"]}/review/',{'revision':0,'status':'answered','response':'Respuesta no autorizada'},content_type='application/json').status_code,403)

    def test_review_has_revision_history_and_does_not_delete_account(self):
        item=self.create_request()
        url=f'/api/privacy/requests/{item["id"]}/review/'
        values={'revision':0,'status':'answered','response':'Recibimos la solicitud; se evaluará conforme a la política aprobada.'}
        response=self.staff.post(url,values,content_type='application/json')
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(self.staff.post(url,values,content_type='application/json').status_code,409)
        self.assertTrue(User.objects.filter(pk=self.owner.user_id,is_active=True).exists())
        self.assertTrue(PrivacyRequestChange.objects.filter(request_id=item['id'],actor=self.admins[0]).exists())
        self.assertTrue(Notification.objects.filter(user=self.owner.user,target='privacy-requests').exists())

    def test_own_export_ignores_other_user_id_and_never_includes_password(self):
        response=self.client.get(f'/api/privacy/export/?user_id={self.other.user_id}')
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(response.json()['account']['email'],self.owner.user.email)
        self.assertNotContains(response,self.other.user.email)
        self.assertNotIn('password',response.content.decode())
        self.assertIn('no-store',response['Cache-Control'])

    def test_privacy_submission_requires_csrf_and_rejects_forged_owner(self):
        strict=Client(enforce_csrf_checks=True);strict.force_login(self.owner.user)
        self.assertEqual(strict.post('/api/privacy/requests/',{'kind':'access','note':'Solicito mis datos de cuenta.'},content_type='application/json').status_code,403)
        response=self.client.post('/api/privacy/requests/',{'kind':'access','note':'Solicito mis datos de cuenta.','owner_id':str(self.other.user_id)},content_type='application/json')
        self.assertEqual(response.status_code,400)

    def test_health_is_sanitized_and_method_limited(self):
        self.assertEqual(Client().get('/api/health/live/').json(),{'status':'ok'})
        self.assertEqual(Client().post('/api/health/live/').status_code,405)
        with patch('accounts.health.connection.cursor',side_effect=RuntimeError('password=private-test-value')):
            response=Client().get('/api/health/ready/')
        self.assertEqual(response.status_code,503)
        self.assertNotContains(response,'private-test-value',status_code=503)

    @override_settings(DEBUG=False,PUBLIC_APP_URL='http://localhost',ALLOWED_HOSTS=['*'],DATA_RETENTION_NOTICE='',EMAIL_HOST='',CLAMAV_HOST='')
    def test_production_checks_identify_external_configuration_gaps(self):
        identifiers={row.id for row in production_readiness(None)}
        self.assertTrue({'pro12.E001','pro12.E002','pro12.E003','pro12.E004'}.issubset(identifiers))
