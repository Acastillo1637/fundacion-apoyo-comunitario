import hashlib
import json
from datetime import timedelta

from allauth.account.models import EmailAddress
from allauth.account.internal.flows.login import record_authentication
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.models import Group
from django.db import IntegrityError, connection, transaction
from django.core.cache import cache
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import AuditEvent, RateBucket, RequesterProfile, VolunteerProfile
from .portals import is_volunteer, portal_access
from .serializers import ProfileSerializer, RegistrationSerializer


def csrf_failure(request, reason=''):
    if request.path.startswith('/api/'):
        return JsonResponse({
            'detail': 'No se pudo validar la seguridad de la sesión. Recarga la página y vuelve a intentarlo.',
            'code': 'csrf_failed',
        }, status=403)
    from django.views.csrf import csrf_failure as default_failure
    return default_failure(request, reason=reason)


def user_data(user):
    from .portals import role_names
    return {'id': str(user.pk), 'email': user.email, 'first_name': user.first_name,
            'last_name': user.last_name, 'roles': role_names(user),
            'can_manage_volunteers': user.has_perm('accounts.view_volunteerprofile'),
            'can_review_documents': user.has_perm('documents.review_volunteerdocument'),
            'can_manage_activities': user.has_perm('activities.manage_operations'),
            'can_manage_users': user.has_perm('accounts.manage_accounts'),
            'has_volunteer_profile': VolunteerProfile.objects.filter(user=user).exists(),
            'has_requester_profile': RequesterProfile.objects.filter(user=user).exists(),
            'available_portals': portal_access(user),
            'management_revision': user.management_revision,
            'can_manage_catalogs': user.is_staff and any(
                user.has_perm(f'volunteers.change_{model}')
                for model in ['skill', 'profession', 'documenttype']
            )}


def limited(request, scope, limit, identity=None):
    # Claves sin datos de contacto/IP en claro; no se confía en X-Forwarded-For.
    now = timezone.now()
    window = int(now.timestamp()) // 900
    raw = f'{scope}:{identity if identity is not None else request.META.get("REMOTE_ADDR", "")}:{window}'
    key = hashlib.sha256(raw.encode()).hexdigest()
    # One atomic upsert, preserving a shared counter across workers/devices.
    # Both supported databases implement ON CONFLICT ... RETURNING.
    table = connection.ops.quote_name(RateBucket._meta.db_table)
    expires = connection.ops.adapt_datetimefield_value(now + timedelta(minutes=30))
    with connection.cursor() as cursor:
        cursor.execute(f'INSERT INTO {table} ("key", "count", "expires_at") VALUES (%s, 1, %s) '
                       f'ON CONFLICT ("key") DO UPDATE SET "count" = {table}."count" + 1 RETURNING "count"', [key, expires])
        count = cursor.fetchone()[0]
    if cache.add('rate-bucket-cleanup', True, timeout=900):
        RateBucket.objects.filter(expires_at__lt=now).delete()
    return count > limit


def read_json(request):
    try:
        body = json.loads(request.body)
        return body if isinstance(body, dict) else {}
    except (ValueError, UnicodeDecodeError):
        return {}


@require_GET
def session_info(request):
    return JsonResponse({'foundation_name': settings.FOUNDATION_NAME, 'retention_notice':settings.DATA_RETENTION_NOTICE,
                         'development':settings.DEBUG, 'csrf_token': get_token(request),
                         'user': user_data(request.user) if request.user.is_authenticated else None})


@require_POST
@csrf_protect
def register(request):
    if limited(request, 'register', 5):
        return JsonResponse({'detail': 'Demasiados intentos. Intenta más tarde.'}, status=429)
    serializer = RegistrationSerializer(data=read_json(request))
    if not serializer.is_valid():
        return JsonResponse(serializer.errors, status=400)
    data = serializer.validated_data
    email = data['email'].lower()
    duplicate = {'detail': 'No se puede crear otra cuenta con este correo. Inicia sesión o recupera tu contraseña.'}
    if get_user_model().objects.filter(email__iexact=email).exists():
        return JsonResponse(duplicate, status=409)
    try:
        with transaction.atomic():
            user = get_user_model().objects.create_user(email=email, password=data['password'], first_name=data['first_name'], last_name=data['last_name'])
            group, _ = Group.objects.get_or_create(name='Solicitante' if data['account_type'] == 'requester' else 'Voluntario')
            user.groups.add(group)
            now = timezone.now()
            if data['account_type'] == 'volunteer':
                VolunteerProfile.objects.create(user=user, adult_confirmed_at=now, privacy_accepted_at=now,
                                                phone=data['phone'], commune=data['commune'],
                                                whatsapp_opt_in_at=now if data['whatsapp'] else None)
            else:
                RequesterProfile.objects.create(user=user, requester_type=data['requester_type'],
                    organization=data['organization'] if data['requester_type'] != 'person' else '',
                    phone=data['phone'], commune=data['commune'], privacy_accepted_at=now,
                    adult_confirmed_at=now, representative_confirmed_at=now if data['requester_type'] != 'person' else None)
            EmailAddress.objects.create(user=user, email=email, primary=True, verified=False)
            AuditEvent.objects.create(actor=user, action='account.registered')
    except IntegrityError:
        return JsonResponse(duplicate, status=409)
    return JsonResponse({'detail': 'Cuenta creada correctamente. Ya puedes iniciar sesión.'}, status=201)


@require_POST
@csrf_protect
def sign_in(request):
    if limited(request, 'login', 10):
        return JsonResponse({'detail': 'Demasiados intentos. Intenta más tarde.'}, status=429)
    data = read_json(request)
    email, password = data.get('email', ''), data.get('password', '')
    if not isinstance(email, str) or not isinstance(password, str) or len(password) > 256:
        return JsonResponse({'detail': 'Credenciales no válidas.'}, status=400)
    user = authenticate(request, username=email.strip().lower(), password=password)
    if user is None:
        return JsonResponse({'detail': 'No pudimos iniciar sesión. Revisa tu correo y contraseña.'}, status=400)
    factor = user.authenticator_set.filter(type='totp').first()
    verified_factor = None
    if user.authenticator_set.exists():
        code = data.get('code', '')
        if not isinstance(code, str) or len(code) > 20:
            return JsonResponse({'detail': 'Código no válido.'}, status=400)
        if not code:
            return JsonResponse({'detail': 'Ingresa el código de tu aplicación de autenticación.', 'mfa_required': True}, status=409)
        from allauth.mfa.totp.internal.auth import TOTP
        if factor and TOTP(factor).validate_code(code):
            verified_factor = factor
        else:
            recovery = user.authenticator_set.filter(type='recovery_codes').first()
            from allauth.mfa.recovery_codes.internal.auth import RecoveryCodes
            if recovery and RecoveryCodes(recovery).validate_code(code):
                verified_factor = recovery
        if verified_factor is None:
            return JsonResponse({'detail': 'El código no es válido o ya fue utilizado.', 'mfa_required': True}, status=400)
    login(request, user)
    record_authentication(request, user, method='password')
    if verified_factor:
        record_authentication(request, user, method='mfa', type=verified_factor.type, id=verified_factor.pk)
    AuditEvent.objects.create(actor=user, action='account.login')
    return JsonResponse({'user': user_data(user), 'csrf_token': get_token(request)})


@require_POST
@csrf_protect
def sign_out(request):
    logout(request)
    return JsonResponse({'detail': 'Sesión cerrada.'})


@api_view(['GET', 'PATCH'])
def profile(request):
    if not is_volunteer(request.user):
        return Response({'detail': 'Esta función pertenece al espacio de voluntario.'}, status=403)
    instance = VolunteerProfile.objects.filter(user=request.user).first()
    if not instance:
        return Response({'detail': 'Esta cuenta no tiene perfil de voluntario.'}, status=404)
    if request.method == 'PATCH':
        allowed = {'first_name', 'last_name', 'phone', 'commune'}
        if set(request.data) - allowed:
            return Response({'detail': 'La solicitud contiene campos no editables.'}, status=400)
        serializer = ProfileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        with transaction.atomic():
            locked_user = get_user_model().objects.select_for_update().get(pk=request.user.pk)
            locked_user.first_name, locked_user.last_name = data['first_name'], data['last_name']
            locked_user.management_revision += 1
            locked_user.save(update_fields=['first_name', 'last_name', 'management_revision'])
            request.user.first_name, request.user.last_name = locked_user.first_name, locked_user.last_name
            request.user.management_revision = locked_user.management_revision
            instance = VolunteerProfile.objects.select_for_update().get(pk=instance.pk)
            if instance.commune != data['commune']:
                instance.location_revision += 1
            instance.phone, instance.commune = data['phone'], data['commune']
            instance.save(update_fields=['phone', 'commune', 'location_revision'])
            AuditEvent.objects.create(actor=request.user, action='profile.updated')
    return Response({**user_data(request.user), 'phone': instance.phone, 'commune': instance.commune})


@api_view(['POST'])
def onboarding(request):
    if not is_volunteer(request.user):
        return Response({'detail': 'Tu cuenta no tiene el rol de voluntario.'}, status=403)
    from .management_serializers import OnboardingSerializer
    serializer = OnboardingSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        now = timezone.now()
        profile, created = VolunteerProfile.objects.get_or_create(user=request.user, defaults={
            'adult_confirmed_at': now, 'privacy_accepted_at': now,
            'whatsapp_opt_in_at': now if serializer.validated_data['whatsapp'] else None,
        })
        if created:
            AuditEvent.objects.create(actor=request.user, action='profile.onboarded', resource=f'profile:{profile.pk}')
    return Response(user_data(request.user), status=201 if created else 200)


@api_view(['GET'])
def operations(request):
    if not request.user.has_perm('accounts.view_volunteerprofile'):
        return Response({'detail': 'No tienes permiso para consultar esta información.'}, status=403)
    from .security import portal_authenticated
    if not portal_authenticated(request):
        return Response({'detail': 'Inicia sesión nuevamente para continuar.'}, status=403)
    return Response({'volunteers': VolunteerProfile.objects.count()})
