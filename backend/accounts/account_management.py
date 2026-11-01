from smtplib import SMTPException

from allauth.account.internal.flows.password_reset import request_password_reset
from allauth.account.internal.flows.login import get_authentication_records
from allauth.account.models import EmailAddress
from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from activities.services import Conflict
from .management_serializers import AccessEmailSerializer, CreateAccountSerializer, ROLE_NAMES, UpdateAccountSerializer
from .models import AccountChange, AccountManagementGuard, AuditEvent, User
from .views import limited


def require_account_manager(request):
    if not request.user.has_perm('accounts.manage_accounts') or not any(
        record.get('method') == 'mfa' for record in get_authentication_records(request, request.user)
    ):
        raise PermissionDenied('La administración de cuentas requiere permiso de administrador general y MFA.')


def lock_actor(request):
    guard, _ = AccountManagementGuard.objects.get_or_create(pk=1)
    AccountManagementGuard.objects.select_for_update().get(pk=guard.pk)
    actor = User.objects.get(pk=request.user.pk)
    if not actor.is_active or actor.session_version != request.user.session_version or not actor.has_perm('accounts.manage_accounts'):
        raise PermissionDenied('Tu acceso cambió. Inicia sesión nuevamente.')
    return actor


def protected(user):
    return user.is_superuser or user.user_permissions.exists() or user.groups.exclude(name__in=ROLE_NAMES).exists()


def access_snapshot(user):
    return {'roles': sorted(user.groups.values_list('name', flat=True)), 'is_active': user.is_active}


def account_data(user, actor, detail=False):
    is_self = user.pk == actor.pk
    technical = protected(user)
    data = {
        'id': str(user.pk), 'email': user.email, 'first_name': user.first_name, 'last_name': user.last_name,
        'is_active': user.is_active, 'roles': list(user.groups.values_list('name', flat=True)),
        'email_verified': any(address.verified for address in user.emailaddress_set.all()),
        'has_password': user.has_usable_password(), 'has_mfa': user.authenticator_set.exists(),
        'has_volunteer_profile': hasattr(user, 'volunteer_profile'),
        'revision': user.management_revision, 'date_joined': user.date_joined,
        'last_login': user.last_login, 'is_self': is_self, 'protected': technical,
        'can_edit_access': not technical and not is_self, 'can_edit_identity': not technical or is_self,
    }
    if detail:
        data['history'] = [
            {'action': change.action, 'reason': change.reason, 'fields_changed': change.fields_changed,
             'before_access': change.before_access, 'after_access': change.after_access,
             'actor_name': change.actor.get_full_name() or 'Administrador', 'created_at': change.created_at}
            for change in user.account_changes_received.select_related('actor')[:30]
        ]
    return data


def record_change(actor, target, action, reason, fields, before):
    AccountChange.objects.create(actor=actor, target=target, action=action, reason=reason,
                                 fields_changed=fields, before_access=before, after_access=access_snapshot(target))
    AuditEvent.objects.create(actor=actor, action=f'account.{action}', resource=f'user:{target.pk}')


def send_access_email(request, user, reason):
    if protected(user) or user.pk == request.user.pk:
        raise PermissionDenied('Las cuentas protegidas y tu propia cuenta usan la recuperación personal.')
    if not user.is_active:
        raise ValidationError('Activa la cuenta antes de enviar el enlace.')
    if limited(request, f'access-email:{user.pk}', 3):
        raise ValidationError('Ya se enviaron varios enlaces. Espera antes de reintentar.')
    try:
        # Destinatario explícito: un alias de otra cuenta no debe cambiar el usuario del enlace.
        request_password_reset(request._request, user.email, [user], token_generator=None)
    except (OSError, SMTPException):
        record_change(request.user, user, 'access_email_failed', reason, [], access_snapshot(user))
        return False
    record_change(request.user, user, 'access_email_sent', reason, [], access_snapshot(user))
    return True


@never_cache
@api_view(['GET', 'POST'])
def accounts(request):
    require_account_manager(request)
    if request.method == 'GET':
        queryset = User.objects.order_by('email').prefetch_related('groups', 'emailaddress_set', 'authenticator_set').select_related('volunteer_profile')
        query = request.query_params.get('q', '').strip()
        if len(query) > 100:
            raise ValidationError('La búsqueda no puede superar 100 caracteres.')
        if query:
            queryset = queryset.filter(Q(email__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query))
        state = request.query_params.get('active', '')
        if state not in ['', 'true', 'false']:
            raise ValidationError('Filtro de estado no válido.')
        if state:
            queryset = queryset.filter(is_active=state == 'true')
        role = request.query_params.get('role', '')
        if role:
            if role not in ROLE_NAMES:
                raise ValidationError('Rol no válido.')
            queryset = queryset.filter(groups__name=role)
        try:
            page = int(request.query_params.get('page', 1))
            if not 1 <= page <= 100000:
                raise ValueError
        except ValueError:
            raise ValidationError('Página no válida.')
        return Response({'results': [account_data(user, request.user) for user in queryset[(page - 1) * 20:page * 20]],
                         'total': queryset.count(), 'page': page, 'page_size': 20, 'available_roles': ROLE_NAMES})
    if limited(request, 'admin-create-account', 10):
        return Response({'detail': 'Demasiadas altas. Intenta más tarde.'}, status=429)
    serializer = CreateAccountSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    try:
        with transaction.atomic():
            lock_actor(request)
            if EmailAddress.objects.filter(email__iexact=data['email']).exists():
                raise ValidationError({'email': 'Ese correo ya está asociado a una cuenta.'})
            user = User.objects.create_user(email=data['email'].lower(), first_name=data['first_name'], last_name=data['last_name'],
                                             is_staff='Administrador general' in data['roles'])
            user.groups.set([Group.objects.get_or_create(name=role)[0] for role in data['roles']])
            EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=False)
            record_change(request.user, user, 'created_by_admin', data['reason'], ['email', 'first_name', 'last_name', 'roles'], {})
    except IntegrityError:
        raise ValidationError({'email': 'Ya existe una cuenta con ese correo.'})
    delivered = send_access_email(request, user, data['reason'])
    return Response({'user': account_data(user, request.user, detail=True), 'email_sent': delivered,
                     'detail': 'Cuenta creada. El destinatario debe establecer su contraseña y verificar el correo.' if delivered else 'Cuenta creada, pero falló el envío. Puedes reintentarlo desde el detalle.'}, status=201)


@never_cache
@api_view(['GET', 'PATCH'])
def account_detail(request, user_id):
    require_account_manager(request)
    if request.method == 'GET':
        return Response(account_data(get_object_or_404(User, pk=user_id), request.user, detail=True))
    serializer = UpdateAccountSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = dict(serializer.validated_data)
    reason = data.pop('reason')
    revision = data.pop('revision')
    with transaction.atomic():
        actor = lock_actor(request)
        target = get_object_or_404(User.objects.select_for_update(), pk=user_id)
        if target.management_revision != revision:
            raise Conflict()
        if protected(target) and target.pk != actor.pk:
            raise PermissionDenied('Esta cuenta tiene privilegios técnicos y se administra fuera de esta sección.')
        before = access_snapshot(target)
        roles_changed = 'roles' in data and sorted(data['roles']) != before['roles']
        active_changed = 'is_active' in data and data['is_active'] != target.is_active
        if target.pk == actor.pk and (roles_changed or active_changed):
            raise PermissionDenied('No puedes cambiar tu propio acceso ni tus roles desde esta sección.')
        if (roles_changed or active_changed) and (target.is_superuser or 'Administrador general' in before['roles']):
            still_admin = data.get('is_active', target.is_active) and ('Administrador general' in data.get('roles', before['roles']) or target.is_superuser)
            others = User.objects.filter(is_active=True).exclude(pk=target.pk).filter(Q(is_superuser=True) | Q(groups__name='Administrador general')).exists()
            if not still_admin and not others:
                raise ValidationError('No puedes retirar al último administrador activo.')
        changed = []
        for field in ['first_name', 'last_name', 'is_active']:
            if field in data and data[field] != getattr(target, field):
                setattr(target, field, data[field]); changed.append(field)
        if roles_changed:
            target.groups.set([Group.objects.get_or_create(name=role)[0] for role in data['roles']])
            target.is_staff = 'Administrador general' in data['roles']
            changed.append('roles')
        if active_changed or roles_changed:
            target.session_version += 1
        if changed:
            target.management_revision += 1
            target.save(update_fields=['first_name', 'last_name', 'is_active', 'is_staff', 'session_version', 'management_revision'])
            record_change(actor, target, 'updated_by_admin', reason, changed, before)
        return Response(account_data(target, actor, detail=True))


@never_cache
@api_view(['POST'])
def access_email(request, user_id):
    require_account_manager(request)
    serializer = AccessEmailSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = get_object_or_404(User, pk=user_id)
    if not send_access_email(request, user, serializer.validated_data['reason']):
        return Response({'detail': 'No se pudo enviar el enlace. Reintenta más tarde.'}, status=503)
    return Response({'detail': 'Enlace solicitado. En desarrollo aparece en la terminal de Django; en producción llegará al correo de la cuenta.'})
