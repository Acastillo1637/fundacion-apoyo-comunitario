"""Own-account operations; authentication and factors remain Django/allauth."""
import base64
from datetime import timedelta
from urllib.parse import urlencode
from uuid import uuid4

from allauth.account.internal.flows.login import record_authentication
from allauth.account.models import EmailAddress
from allauth.mfa.adapter import get_adapter
from allauth.mfa.base.internal.flows import post_authentication
from allauth.mfa.models import Authenticator
from allauth.mfa.internal.flows.add import validate_can_add_authenticator
from allauth.mfa.recovery_codes.internal.auth import RecoveryCodes
from allauth.mfa.recovery_codes.internal.flows import generate_recovery_codes, view_recovery_codes
from allauth.mfa.totp.forms import ActivateTOTPForm, DeactivateTOTPForm
from allauth.mfa.totp.internal.auth import SECRET_SESSION_KEY, TOTP
from allauth.mfa.totp.internal.flows import activate_totp, deactivate_totp
from django.conf import settings
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core import signing
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.views.decorators.cache import never_cache
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.response import Response

from volunteers.serializers import StrictSerializer
from .models import AuditEvent, PendingEmailChange, User
from .views import limited, user_data


class MailUnavailable(APIException):
    status_code = 503
    default_detail = 'No se pudo enviar el enlace. El correo de tu cuenta no cambió. Intenta más tarde.'


class EmailTokenGenerator(PasswordResetTokenGenerator):
    key_salt = 'foundation.account.email-change.v1'

    def _make_hash_value(self, user, timestamp):
        # A fresh login must not invalidate an email link. Password, address,
        # access changes and expiry still invalidate it.
        return f'{user.pk}:{user.password}:{user.email}:{user.session_version}:{timestamp}'


class ActionSerializer(StrictSerializer):
    action = serializers.ChoiceField(choices=['password', 'email_request', 'email_confirm', 'totp_setup',
        'totp_activate', 'totp_disable', 'recovery_view', 'recovery_generate', 'totp_cancel'])
    current_password = serializers.CharField(max_length=256, required=False, write_only=True, trim_whitespace=False)
    mfa_code = serializers.CharField(max_length=20, required=False, allow_blank=True, write_only=True)
    new_password = serializers.CharField(max_length=256, required=False, write_only=True, trim_whitespace=False)
    new_email = serializers.EmailField(required=False)
    code = serializers.CharField(max_length=20, required=False, write_only=True)
    token = serializers.CharField(max_length=1500, required=False, write_only=True)


def email_verified(user):
    return EmailAddress.objects.filter(user=user, email__iexact=user.email, verified=True).exists()


def state(user):
    authenticators = list(user.authenticator_set.all())
    recovery = next((item for item in authenticators if item.type == 'recovery_codes'), None)
    pending = PendingEmailChange.objects.filter(user=user, created_at__gt=timezone.now()-timedelta(minutes=30)).first()
    return {'email': user.email, 'email_verified': email_verified(user),
        'totp_enabled': any(item.type == 'totp' for item in authenticators),
        'mfa_enabled': bool(authenticators),
        'recovery_remaining': len(RecoveryCodes(recovery).get_unused_codes()) if recovery else 0,
        'pending_email': pending.email if pending else None}


def reauthenticate(request, user, values):
    if not user.check_password(values.get('current_password', '')):
        raise ValidationError('La contraseña actual no es correcta.')
    factors = list(user.authenticator_set.select_for_update())
    if factors:
        code = values.get('mfa_code', '')
        totp = next((factor for factor in factors if factor.type == 'totp'), None)
        recovery = next((factor for factor in factors if factor.type == 'recovery_codes'), None)
        factor = totp if totp and TOTP(totp).validate_code(code) else None
        if not factor and recovery and RecoveryCodes(recovery).validate_code(code):
            factor = recovery
        if not factor:
            raise ValidationError('Ingresa un código 2FA válido que no hayas utilizado, o un código de recuperación.')
        post_authentication(request._request, factor, reauthenticated=True)
    record_authentication(request._request, user, method='password', reauthenticated=True)


def keep_current_session(request, user):
    user.session_version += 1
    user.save(update_fields=['session_version'])
    request.session['account_session_version'] = user.session_version
    request.session.cycle_key()


@never_cache
@api_view(['GET'])
def status(request):
    return Response(state(request.user))


@never_cache
@api_view(['POST'])
def action(request):
    serializer = ActionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    values = serializer.validated_data
    kind = values['action']
    if limited(request._request, 'security-account', 20, identity=str(request.user.pk)) or limited(request._request, 'security-network', 40):
        raise ValidationError('Demasiados intentos de seguridad. Espera antes de continuar.')
    try:
        with transaction.atomic():
            user = User.objects.select_for_update().filter(pk=request.user.pk, is_active=True).first()
            if not user:
                raise PermissionDenied('La cuenta ya no está activa.')
            request.user = user
            if kind == 'totp_cancel':
                request.session.pop('security_totp_setup', None)
                request.session.pop(SECRET_SESSION_KEY, None)
                return Response({'detail': 'Configuración pendiente descartada.'})
            reauthenticate(request, user, values)
            result = {}
            if kind == 'password':
                password = values.get('new_password', '')
                try:
                    validate_password(password, user)
                except DjangoValidationError as exc:
                    raise ValidationError({'new_password': exc.messages})
                if user.check_password(password):
                    raise ValidationError('Elige una contraseña diferente de la actual.')
                user.set_password(password)
                user.save(update_fields=['password'])
                keep_current_session(request, user)
                update_session_auth_hash(request._request, user)
                PendingEmailChange.objects.filter(user=user).delete()
                request.session.pop('security_totp_setup', None)
                result['detail'] = 'Contraseña actualizada. Las otras sesiones se cerrarán.'
            elif kind == 'email_request':
                email = values.get('new_email', '').lower()
                if not email:
                    raise ValidationError('Indica el nuevo correo o el correo actual para comprobarlo.')
                if User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists() or EmailAddress.objects.filter(email__iexact=email).exclude(user=user).exists():
                    raise ValidationError('Ese correo no está disponible para esta cuenta.')
                pending, _ = PendingEmailChange.objects.update_or_create(user=user,
                    defaults={'email': email, 'nonce': uuid4(), 'created_at': timezone.now()})
                token = signing.dumps({'user': str(user.pk), 'nonce': str(pending.nonce),
                    'proof': EmailTokenGenerator().make_token(user)}, salt='foundation-email-change')
                url = settings.PUBLIC_APP_URL + '/seguridad/verificar-correo?' + urlencode({'token': token})
                try:
                    sent = send_mail(f'{settings.FOUNDATION_NAME}: confirma tu correo de cuenta',
                        f'Se solicitó comprobar este correo para tu cuenta. Abre el enlace en la plataforma, inicia sesión y confirma con tu contraseña y 2FA si corresponde.\n{url}\n'
                        'Vence en 30 minutos. Si no lo solicitaste, no confirmes. Tu correo no cambia al abrir el enlace.',
                        settings.DEFAULT_FROM_EMAIL, [email])
                    if sent != 1:
                        raise RuntimeError()
                except Exception as exc:
                    raise MailUnavailable() from exc
                result['detail'] = 'Enlace solicitado. El correo no cambiará hasta que lo confirmes. En desarrollo con correo de consola, revisa la terminal de Django.' if settings.DEBUG and 'console' in settings.EMAIL_BACKEND else 'Enviamos el enlace al correo indicado. Confírmalo para completar la operación.'
            elif kind == 'email_confirm':
                try:
                    token = signing.loads(values.get('token', ''), salt='foundation-email-change', max_age=1800)
                    pending = PendingEmailChange.objects.select_for_update().get(user=user, nonce=token['nonce'], created_at__gt=timezone.now()-timedelta(minutes=30))
                    if token['user'] != str(user.pk) or not EmailTokenGenerator().check_token(user, token['proof']):
                        raise ValueError()
                except (signing.BadSignature, KeyError, ValueError, PendingEmailChange.DoesNotExist):
                    raise ValidationError('El enlace no es válido, ya fue utilizado o venció. Solicita uno nuevo.')
                email = pending.email
                if User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists() or EmailAddress.objects.filter(email__iexact=email).exclude(user=user).exists():
                    raise ValidationError('Ese correo ya no está disponible.')
                EmailAddress.objects.filter(user=user).update(primary=False)
                EmailAddress.objects.update_or_create(user=user, email=email, defaults={'primary': True, 'verified': True})
                user.email = email
                user.management_revision += 1
                user.save(update_fields=['email', 'management_revision'])
                pending.delete()
                keep_current_session(request, user)
                request.session.pop('security_totp_setup', None)
                result.update(detail='Correo confirmado. Las otras sesiones se cerrarán.', user=user_data(user))
            elif kind == 'totp_setup':
                if user.authenticator_set.filter(type='totp').exists():
                    raise ValidationError('Ya tienes una aplicación de autenticación configurada.')
                if not email_verified(user):
                    raise ValidationError('Para proteger la recuperación, comprueba tu correo antes de activar 2FA. El registro y acceso normales no requieren esta comprobación.')
                try:
                    validate_can_add_authenticator(user)
                except DjangoValidationError as exc:
                    raise ValidationError(exc.messages)
                form = ActivateTOTPForm(user=user)
                secret = form.secret
                request.session.pop(SECRET_SESSION_KEY, None)
                request.session['security_totp_setup'] = {'user': str(user.pk), 'version': user.session_version,
                    'secret': get_adapter().encrypt(secret), 'expires': (timezone.now()+timedelta(minutes=5)).timestamp()}
                uri = get_adapter().build_totp_url(user, secret)
                svg = get_adapter().build_totp_svg(uri)
                result.update(secret=secret, qr='data:image/svg+xml;base64,'+base64.b64encode(svg.encode()).decode(),
                    detail='Escanea el QR en tu aplicación y confirma un código. La configuración vence en cinco minutos.')
            elif kind == 'totp_activate':
                pending = request.session.get('security_totp_setup', {})
                if pending.get('user') != str(user.pk) or pending.get('version') != user.session_version or pending.get('expires', 0) <= timezone.now().timestamp():
                    request.session.pop('security_totp_setup', None)
                    raise ValidationError('La configuración venció. Genera un nuevo QR.')
                if user.authenticator_set.filter(type='totp').exists():
                    raise ValidationError('La autenticación ya está activada.')
                request.session[SECRET_SESSION_KEY] = get_adapter().decrypt(pending['secret'])
                try:
                    form = ActivateTOTPForm(data={'code': values.get('code', '')}, user=user)
                    if not form.is_valid():
                        raise ValidationError({'code': list(form.errors.values())})
                    authenticator, _ = activate_totp(request._request, form)
                    post_authentication(request._request, authenticator, reauthenticated=True)
                finally:
                    request.session.pop(SECRET_SESSION_KEY, None)
                request.session.pop('security_totp_setup', None)
                keep_current_session(request, user)
                result['detail'] = '2FA activado. Guarda tus códigos de recuperación desde la opción correspondiente.'
            elif kind == 'totp_disable':
                authenticator = user.authenticator_set.filter(type='totp').first()
                if not authenticator:
                    raise ValidationError('No tienes una aplicación 2FA activa.')
                form = DeactivateTOTPForm(data={}, authenticator=authenticator)
                if not form.is_valid():
                    raise ValidationError({'detail': list(form.errors.values())})
                deactivate_totp(request._request, authenticator)
                keep_current_session(request, user)
                result['detail'] = '2FA desactivado y códigos asociados retirados. Las otras sesiones se cerrarán.'
            elif kind in ['recovery_view', 'recovery_generate']:
                if not user.authenticator_set.exclude(type='recovery_codes').exists():
                    raise ValidationError('Activa 2FA antes de gestionar códigos de recuperación.')
                if kind == 'recovery_generate':
                    generate_recovery_codes(request._request)
                codes, can_view = view_recovery_codes(request._request)
                if not codes or not can_view:
                    raise ValidationError('Estos códigos ya fueron mostrados. Genera nuevos para reemplazarlos.')
                result.update(codes=codes.get_unused_codes(), detail='Guárdalos en un lugar seguro. Cada código sirve una vez y esta lista solo se muestra una vez.')
            AuditEvent.objects.create(actor=user, action=f'security.{kind}', resource=f'user:{user.pk}')
            result['state'] = state(user)
            return Response(result)
    except IntegrityError:
        raise ValidationError('La información cambió o el correo no está disponible. Recarga y revisa tu cuenta.')
