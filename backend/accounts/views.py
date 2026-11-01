import hashlib
import json
from datetime import timedelta

from allauth.account.models import EmailAddress
from allauth.account.internal.flows.login import get_authentication_records
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import AuditEvent, RateBucket, VolunteerProfile
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
    return {'id': str(user.pk), 'email': user.email, 'first_name': user.first_name,
            'last_name': user.last_name, 'roles': list(user.groups.values_list('name', flat=True)),
            'can_manage_volunteers': user.has_perm('accounts.view_volunteerprofile'),
            'can_manage_catalogs': user.is_staff and any(
                user.has_perm(f'volunteers.change_{model}')
                for model in ['skill', 'profession', 'documenttype']
            )}


def limited(request, scope, limit):
    # Claves sin datos de contacto/IP en claro; no se confía en X-Forwarded-For.
    now = timezone.now()
    window = int(now.timestamp()) // 900
    raw = f'{scope}:{request.META.get("REMOTE_ADDR", "")}:{window}'
    key = hashlib.sha256(raw.encode()).hexdigest()
    with transaction.atomic():
        bucket, _ = RateBucket.objects.get_or_create(key=key, defaults={'expires_at': now + timedelta(minutes=30)})
        bucket = RateBucket.objects.select_for_update().get(pk=bucket.pk)
        bucket.count += 1
        bucket.save(update_fields=['count'])
    RateBucket.objects.filter(expires_at__lt=now).delete()
    return bucket.count > limit


def read_json(request):
    try:
        body = json.loads(request.body)
        return body if isinstance(body, dict) else {}
    except (ValueError, UnicodeDecodeError):
        return {}


@require_GET
def session_info(request):
    return JsonResponse({'foundation_name': settings.FOUNDATION_NAME, 'csrf_token': get_token(request),
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
    generic = {'detail': 'Si el correo puede registrarse, recibirás un enlace de verificación. Revisa también spam.'}
    if get_user_model().objects.filter(email__iexact=email).exists():
        return JsonResponse(generic, status=202)
    try:
        with transaction.atomic():
            user = get_user_model().objects.create_user(email=email, password=data['password'], first_name=data['first_name'], last_name=data['last_name'])
            group, _ = Group.objects.get_or_create(name='Voluntario')
            user.groups.add(group)
            now = timezone.now()
            VolunteerProfile.objects.create(user=user, adult_confirmed_at=now, privacy_accepted_at=now,
                                            whatsapp_opt_in_at=now if data['whatsapp'] else None)
            address = EmailAddress.objects.create(user=user, email=email, primary=True, verified=False)
            AuditEvent.objects.create(actor=user, action='account.registered')
    except IntegrityError:
        return JsonResponse(generic, status=202)
    address.send_confirmation(request, signup=True)
    return JsonResponse(generic, status=202)


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
    if user is None or not EmailAddress.objects.filter(user=user, verified=True).exists():
        return JsonResponse({'detail': 'No pudimos iniciar sesión. Revisa tus datos y verifica tu correo.'}, status=400)
    # No se permite omitir un factor configurado mediante este endpoint.
    if user.is_staff or user.is_superuser or user.get_all_permissions() or user.authenticator_set.exists():
        return JsonResponse({'detail': 'Continúa mediante el acceso protegido.', 'continue_url': '/accounts/login/'}, status=409)
    login(request, user)
    AuditEvent.objects.create(actor=user, action='account.login')
    return JsonResponse({'user': user_data(user), 'csrf_token': get_token(request)})


@require_POST
@csrf_protect
def sign_out(request):
    logout(request)
    return JsonResponse({'detail': 'Sesión cerrada.'})


@api_view(['GET', 'PATCH'])
def profile(request):
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
            request.user.first_name, request.user.last_name = data['first_name'], data['last_name']
            request.user.save(update_fields=['first_name', 'last_name'])
            instance.phone, instance.commune = data['phone'], data['commune']
            instance.save(update_fields=['phone', 'commune'])
            AuditEvent.objects.create(actor=request.user, action='profile.updated')
    return Response({**user_data(request.user), 'phone': instance.phone, 'commune': instance.commune})


@api_view(['GET'])
def operations(request):
    if not request.user.has_perm('accounts.view_volunteerprofile'):
        return Response({'detail': 'No tienes permiso para consultar esta información.'}, status=403)
    methods = get_authentication_records(request, request.user)
    if not any(method.get('method') == 'mfa' for method in methods):
        return Response({'detail': 'Se requiere MFA para operaciones administrativas.'}, status=403)
    return Response({'volunteers': VolunteerProfile.objects.count()})
