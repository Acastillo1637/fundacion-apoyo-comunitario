from datetime import timedelta
import json
import re
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from allauth.account.models import EmailAddress
from allauth.mfa.models import Authenticator
from allauth.mfa.totp.internal.auth import format_hotp_value, hotp_value, yield_hotp_counters_from_time
from django.core import mail
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from .models import AuditEvent, PendingEmailChange, User


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', PUBLIC_APP_URL='http://testserver')
class AccountSecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.counter=123456789
        frozen=patch('allauth.mfa.totp.internal.auth.yield_hotp_counters_from_time',side_effect=lambda:iter([self.counter]))
        frozen.start();self.addCleanup(frozen.stop)
        self.password='Strong-current-password-for-tests-729!'
        self.user=User.objects.create_user('secure-owner@example.org',self.password)
        self.other=User.objects.create_user('secure-other@example.org',self.password)
        EmailAddress.objects.create(user=self.user,email=self.user.email,verified=True,primary=True)
        self.client.force_login(self.user)

    def action(self,action,**values):
        return self.client.post('/api/security/action/',{'action':action,'current_password':self.password,**values},content_type='application/json')

    def setup_totp(self):
        response=self.action('totp_setup')
        self.assertEqual(response.status_code,200,response.content)
        return response.json()['secret']

    def code(self,secret,offset=0):
        counter=self.counter+offset
        return format_hotp_value(hotp_value(secret,counter))

    def activate(self):
        secret=self.setup_totp()
        response=self.action('totp_activate',code=self.code(secret))
        self.assertEqual(response.status_code,200,response.content)
        return secret

    def test_state_contains_no_secrets_and_is_never_cached(self):
        self.activate()
        response=self.client.get('/api/security/')
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json()['totp_enabled'])
        self.assertIn('no-store',response['Cache-Control'])
        self.assertNotIn('secret',response.json())
        self.assertNotIn('codes',response.json())
        self.assertFalse(self.other.authenticator_set.exists())

    def test_password_change_requires_current_password_and_validation_and_revokes_other_sessions(self):
        other_session=Client();other_session.force_login(self.user)
        self.assertEqual(self.action('password',current_password='wrong',new_password='New-long-password-for-tests-932!').status_code,400)
        self.assertEqual(self.action('password',new_password='123').status_code,400)
        response=self.action('password',new_password='New-long-password-for-tests-932!')
        self.assertEqual(response.status_code,200,response.content)
        self.user.refresh_from_db();self.assertTrue(self.user.check_password('New-long-password-for-tests-932!'))
        self.assertEqual(self.client.get('/api/security/').status_code,200)
        self.assertEqual(other_session.get('/api/security/').status_code,403)

    def test_security_requires_authentication_csrf_and_rejects_forged_owner(self):
        self.assertEqual(Client().get('/api/security/').status_code,403)
        strict=Client(enforce_csrf_checks=True);strict.force_login(self.user)
        self.assertEqual(strict.post('/api/security/action/',{'action':'totp_setup','current_password':self.password},content_type='application/json').status_code,403)
        self.assertEqual(self.action('totp_setup',user_id=str(self.other.pk)).status_code,400)
        self.assertFalse(self.other.authenticator_set.exists())

    def test_setup_requires_verified_mailbox_but_normal_login_does_not(self):
        EmailAddress.objects.filter(user=self.user).update(verified=False)
        self.assertEqual(self.action('totp_setup').status_code,400)
        response=Client().post('/api/login/',{'email':self.user.email,'password':self.password},content_type='application/json')
        self.assertEqual(response.status_code,200)

    def test_totp_setup_activation_disable_and_existing_factor_encryption(self):
        secret=self.setup_totp()
        pending=self.client.session['security_totp_setup']
        self.assertNotEqual(pending['secret'],secret)
        self.assertEqual(self.action('totp_activate',code='wrong').status_code,400)
        self.assertEqual(self.action('totp_activate',code=self.code(secret)).status_code,200)
        factor=self.user.authenticator_set.get(type='totp')
        self.assertTrue(factor.data['secret'].startswith('fac1:'))
        self.assertNotIn('security_totp_setup',self.client.session)
        self.assertEqual(self.action('totp_disable').status_code,400)
        self.assertEqual(self.action('totp_disable',mfa_code=self.code(secret)).status_code,200)
        self.assertFalse(self.user.authenticator_set.exists())
        self.assertTrue(AuditEvent.objects.filter(action='security.totp_disable').exists())

    def test_pending_totp_is_expiring_and_cancellable(self):
        secret=self.setup_totp()
        session=self.client.session;value=session['security_totp_setup'];value['expires']=0;session['security_totp_setup']=value;session.save()
        self.assertEqual(self.action('totp_activate',code=self.code(secret)).status_code,400)
        self.setup_totp()
        self.assertEqual(self.action('totp_cancel').status_code,200)
        self.assertNotIn('security_totp_setup',self.client.session)
        self.assertFalse(self.user.authenticator_set.exists())

    def test_recovery_codes_only_shown_after_reauthentication_once_and_old_codes_invalidated(self):
        secret=self.activate()
        self.assertEqual(self.action('recovery_view').status_code,400)
        response=self.action('recovery_view',mfa_code=self.code(secret))
        self.assertEqual(response.status_code,200,response.content)
        codes=response.json()['codes'];self.assertGreater(len(codes),1)
        self.assertEqual(self.action('recovery_view',mfa_code=codes[0]).status_code,400)
        response=self.action('recovery_generate',mfa_code=codes[1])
        self.assertEqual(response.status_code,200,response.content)
        self.assertNotEqual(codes,response.json()['codes'])
        self.assertEqual(self.action('totp_disable',mfa_code=codes[2]).status_code,400)

    def email_token(self,email):
        response=self.action('email_request',new_email=email)
        self.assertEqual(response.status_code,200,response.content)
        self.assertNotIn('token',response.json())
        url=re.search(r'http://[^\s]+/seguridad/verificar-correo\?[^\s]+',mail.outbox[-1].body).group(0)
        return parse_qs(urlsplit(url).query)['token'][0]

    def test_email_change_proves_target_mailbox_is_own_only_single_use_and_preserves_accounts(self):
        token=self.email_token('secure-new@example.org')
        self.user.refresh_from_db();self.assertEqual(self.user.email,'secure-owner@example.org')
        intruder=Client();intruder.force_login(self.other)
        self.assertEqual(intruder.post('/api/security/action/',{'action':'email_confirm','current_password':self.password,'token':token},content_type='application/json').status_code,400)
        self.assertEqual(self.action('email_confirm',token=token+'x').status_code,400)
        self.assertEqual(self.action('email_confirm',token=token).status_code,200)
        self.user.refresh_from_db();self.assertEqual(self.user.email,'secure-new@example.org')
        self.assertTrue(EmailAddress.objects.get(user=self.user,email=self.user.email).verified)
        self.assertEqual(self.action('email_confirm',token=token).status_code,400)
        self.other.refresh_from_db();self.assertEqual(self.other.email,'secure-other@example.org')

    def test_email_request_rejects_duplicates_and_failed_delivery_does_not_change_account(self):
        self.assertEqual(self.action('email_request',new_email=self.other.email).status_code,400)
        with patch('accounts.account_security.send_mail',side_effect=OSError('test')):
            self.assertEqual(self.action('email_request',new_email='unreachable@example.org').status_code,503)
        self.assertFalse(PendingEmailChange.objects.filter(user=self.user).exists())
        self.user.refresh_from_db();self.assertEqual(self.user.email,'secure-owner@example.org')

    def test_expired_or_superseded_email_link_cannot_change_account(self):
        old=self.email_token('first@example.org')
        current=self.email_token('second@example.org')
        self.assertEqual(self.action('email_confirm',token=old).status_code,400)
        PendingEmailChange.objects.filter(user=self.user).update(created_at=timezone.now()-timedelta(hours=1))
        self.assertEqual(self.action('email_confirm',token=current).status_code,400)

    def test_logout_really_invalidates_session(self):
        self.assertEqual(self.client.post('/api/logout/',{},content_type='application/json').status_code,200)
        self.assertEqual(self.client.get('/api/security/').status_code,403)

    def test_legacy_totp_secret_is_compatible(self):
        from .mfa_adapter import FoundationMFAAdapter
        adapter=FoundationMFAAdapter()
        self.assertEqual(adapter.decrypt('OLDSECRET'), 'OLDSECRET')
        self.assertEqual(adapter.decrypt(adapter.encrypt('NEWSECRET')), 'NEWSECRET')

    def test_legacy_security_forms_redirect_and_cannot_bypass_sensitive_checks(self):
        for path in ['2fa/','email/','password/change/','password/set/','2fa/totp/activate/',
                     '2fa/totp/deactivate/','2fa/recovery-codes/','2fa/recovery-codes/generate/','2fa/recovery-codes/download/']:
            with self.subTest(path=path):
                response=self.client.get('/accounts/'+path)
                self.assertEqual(response.status_code,302)
                self.assertEqual(response.url,'/seguridad')
                self.assertEqual(self.client.post('/accounts/'+path,{}).status_code,405)
        self.assertFalse(self.user.authenticator_set.exists())

    def test_email_link_survives_normal_logout_login_but_requires_same_account_credentials(self):
        token=self.email_token('new-after-login@example.org')
        self.client.logout()
        self.client.post('/api/login/',{'email':self.user.email,'password':self.password},content_type='application/json')
        response=self.action('email_confirm',token=token)
        self.assertEqual(response.status_code,200,response.content)
