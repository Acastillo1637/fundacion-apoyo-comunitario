from datetime import datetime, time
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from activities.models import Event, Notification, Participation, ServiceRequest
from activities.services import Conflict, require_operator
from documents.models import VolunteerDocument
from volunteers.models import DocumentType, Profession, Skill
from volunteers.serializers import StrictSerializer
from .models import AccountChange, AuditEvent, User, VolunteerProfile
from .portals import portal_access
from .security import portal_authenticated


class AccountProfileSerializer(StrictSerializer):
    first_name = serializers.CharField(max_length=80)
    last_name = serializers.CharField(max_length=80)
    revision = serializers.IntegerField(min_value=0)


@api_view(['PATCH'])
def account_profile(request):
    serializer = AccountProfileSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    values = serializer.validated_data
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=request.user.pk)
        if user.management_revision != values['revision']:
            from activities.services import Conflict
            raise Conflict()
        user.first_name, user.last_name = values['first_name'], values['last_name']
        user.management_revision += 1
        user.save(update_fields=['first_name', 'last_name', 'management_revision'])
        AuditEvent.objects.create(actor=user, action='account.profile.updated')
    from .views import user_data
    return Response(user_data(user))


def counts(rows):
    return {item['status']: item['count'] for item in rows.values('status').annotate(count=Count('pk'))}


@api_view(['GET'])
def summary(request):
    portal = request.query_params.get('portal')
    if portal not in portal_access(request.user):
        raise PermissionDenied('No tienes acceso a este espacio.')
    if portal in ['administration', 'operations'] and not portal_authenticated(request):
        raise PermissionDenied('Inicia sesión nuevamente para continuar.')
    result = {'portal': portal}
    if portal == 'administration':
        if request.user.has_perm('accounts.manage_accounts'):
            result['metrics'] = [
                {'label': 'Cuentas activas', 'value': User.objects.filter(is_active=True).count(), 'target': 'users'},
                {'label': 'Cuentas inactivas', 'value': User.objects.filter(is_active=False).count(), 'target': 'users'},
                {'label': 'Voluntarios', 'value': User.objects.filter(groups__name='Voluntario', is_active=True).count(), 'target': 'users'},
                {'label': 'Solicitantes', 'value': User.objects.filter(groups__name='Solicitante', is_active=True).count(), 'target': 'users'},
            ]
        else:
            result['metrics'] = []
    elif portal == 'operations':
        result['metrics'] = []
        if request.user.has_perm('activities.manage_operations'):
            result['metrics'] += [
                {'label': 'Solicitudes pendientes', 'value': ServiceRequest.objects.filter(status__in=['pending', 'in_review'], email_verified_at__isnull=False).count(), 'target': 'operations'},
                {'label': 'Eventos abiertos', 'value': Event.objects.filter(status='open', starts_at__gt=timezone.now()).count(), 'target': 'operations'},
                {'label': 'Postulaciones por revisar', 'value': Participation.objects.filter(status='applied', event__status='open', event__starts_at__gt=timezone.now()).count(), 'target': 'participants'},
                {'label': 'Titulares confirmados', 'value': Participation.objects.filter(status='confirmed', assignment='primary', event__status='open').count(), 'target': 'participants'},
                {'label': 'Respaldos confirmados', 'value': Participation.objects.filter(status='confirmed', assignment='backup', event__status='open').count(), 'target': 'participants'},
            ]
        if request.user.has_perm('documents.review_volunteerdocument'):
            # Only latest versions are actionable in the review queue.
            from django.db.models import OuterRef, Exists
            newer = VolunteerDocument.objects.filter(profile_id=OuterRef('profile_id'), document_type_id=OuterRef('document_type_id'), version__gt=OuterRef('version'))
            result['metrics'].append({'label': 'Documentos por revisar', 'value': VolunteerDocument.objects.filter(status='pending').annotate(newer=Exists(newer)).filter(newer=False).exclude(profile__user=request.user).count(), 'target': 'document-review'})
    elif portal == 'requester':
        rows = ServiceRequest.objects.filter(requester__user=request.user)
        result['metrics'] = [{'label': label, 'value': rows.filter(status=status).count(), 'target': 'my-requests'} for status, label in ServiceRequest.Status.choices]
    else:
        rows = Participation.objects.filter(profile__user=request.user)
        result['metrics'] = [
            {'label': 'Invitaciones vigentes', 'value': rows.filter(status='invited', expires_at__gt=timezone.now(), event__status='open').count(), 'target': 'participations'},
            {'label': 'Titulares confirmados', 'value': rows.filter(status='confirmed', assignment='primary', event__status='open', event__starts_at__gt=timezone.now()).count(), 'target': 'participations'},
            {'label': 'Respaldos confirmados', 'value': rows.filter(status='confirmed', assignment='backup', event__status='open', event__starts_at__gt=timezone.now()).count(), 'target': 'participations'},
            {'label': 'Postulaciones pendientes', 'value': rows.filter(status='applied', event__status='open').count(), 'target': 'participations'},
        ]
    if portal in ['administration', 'operations']:
        from django.db.models import Q, Sum
        result['events'] = []
        if request.user.has_perm('activities.manage_operations'):
            for event in Event.objects.filter(status='open', ends_at__gt=timezone.now()).order_by('starts_at')[:5]:
                capacity = event.positions.aggregate(total=Sum('capacity'))['total'] or 0
                result['events'].append({'id': str(event.pk), 'title': event.title, 'commune': event.commune,
                    'starts_at': event.starts_at, 'capacity': capacity,
                    'confirmed': event.participations.filter(status='confirmed', assignment='primary').count(),
                    'backups': event.participations.filter(status='confirmed', assignment='backup').count(), 'waiting': event.participations.filter(status='waitlisted').count()})
        result['reviews'] = []
        if request.user.has_perm('documents.review_volunteerdocument'):
            from django.db.models import OuterRef, Exists
            newer = VolunteerDocument.objects.filter(profile_id=OuterRef('profile_id'), document_type_id=OuterRef('document_type_id'), version__gt=OuterRef('version'))
            rows = VolunteerDocument.objects.filter(status='pending').exclude(profile__user=request.user).annotate(newer=Exists(newer)).filter(newer=False).select_related('profile__user', 'document_type')
            result['reviews'] = [{'id': str(row.pk), 'type_name': row.document_type.name, 'name': row.profile.user.get_full_name(), 'uploaded_at': row.uploaded_at} for row in rows[:3]]
        audit = AuditEvent.objects.select_related('actor').order_by('-created_at', '-pk')
        if portal != 'administration' or not request.user.has_perm('accounts.manage_accounts'):
            audit = audit.filter(Q(action__startswith='event.') | Q(action__startswith='request.') | Q(action__startswith='participation.') | Q(action__startswith='document.'))
        result['audit'] = [{'id': row.pk, 'action': row.action, 'actor': row.actor.get_full_name() if row.actor else 'Portal público', 'created_at': row.created_at, 'resource': row.resource} for row in audit[:10]]
    return Response(result)


class CatalogSerializer(StrictSerializer):
    id = serializers.IntegerField(min_value=1, required=False)
    name = serializers.CharField(max_length=100)
    description = serializers.CharField(max_length=500, allow_blank=True, default='')
    is_active = serializers.BooleanField()
    required_documents = serializers.ListField(child=serializers.IntegerField(min_value=1), default=list, max_length=50)


def catalog_data(item):
    return {'id': item.pk, 'name': item.name, 'description': item.description, 'is_active': item.is_active,
            'required_documents': list(item.required_documents.values_list('pk', flat=True)) if hasattr(item, 'required_documents') else []}


@api_view(['GET', 'POST', 'PUT'])
def catalogs(request, kind):
    model = {'skills': Skill, 'professions': Profession, 'documents': DocumentType}.get(kind)
    if model is None:
        raise ValidationError('Catálogo no válido.')
    operation = {'GET': 'view', 'POST': 'add', 'PUT': 'change'}[request.method]
    if not request.user.has_perm(f'volunteers.{operation}_{model._meta.model_name}') or not portal_authenticated(request):
        raise PermissionDenied('No tienes acceso a este catálogo.')
    if request.method == 'GET':
        return Response({'results': [catalog_data(item) for item in model.objects.all()], 'documents': list(DocumentType.objects.filter(is_active=True).values('id', 'name'))})
    serializer = CatalogSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    values = dict(serializer.validated_data)
    identifier = values.pop('id', None)
    if (request.method == 'POST' and identifier is not None) or (request.method == 'PUT' and identifier is None):
        raise ValidationError('Envía un identificador solo al editar una entrada existente.')
    document_ids = values.pop('required_documents')
    if kind == 'documents' and document_ids:
        raise ValidationError('Un tipo documental no admite requisitos.')
    if len(set(document_ids)) != len(document_ids) or DocumentType.objects.filter(pk__in=document_ids).count() != len(document_ids):
        raise ValidationError('Requisitos documentales no válidos.')
    try:
        with transaction.atomic():
            item = get_object_or_404(model.objects.select_for_update(), pk=identifier) if request.method == 'PUT' else model()
            for key, value in values.items():
                setattr(item, key, value)
            item.save()
            if kind != 'documents':
                item.required_documents.set(document_ids)
            AuditEvent.objects.create(actor=request.user, action='catalog.updated', resource=f'{kind}:{item.pk}')
    except IntegrityError:
        raise ValidationError('Ya existe una entrada con ese nombre.')
    return Response(catalog_data(item), status=201 if request.method == 'POST' else 200)


class RestrictionSerializer(StrictSerializer):
    id = serializers.IntegerField(min_value=1)
    restricted = serializers.BooleanField()
    reason = serializers.CharField(min_length=8, max_length=1000)
    until = serializers.DateField(required=False, allow_null=True, default=None)
    revision = serializers.IntegerField(min_value=0, default=0)

    def validate(self, attrs):
        if attrs['until'] and (not attrs['restricted'] or attrs['until'] < timezone.localdate()):
            raise ValidationError({'until': 'Selecciona una fecha de término vigente solo al aplicar una restricción.'})
        return attrs


def restriction_data(profile):
    return {'restricted': profile.participation_restricted, 'reason': profile.restriction_reason,
            'restriction_expires_at': profile.restriction_expires_at, 'restriction_revision': profile.restriction_revision}


@api_view(['GET', 'POST'])
def volunteers(request):
    require_operator(request)
    if request.method == 'POST':
        serializer = RestrictionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            profile = get_object_or_404(VolunteerProfile.objects.select_for_update(), pk=serializer.validated_data['id'])
            if profile.restriction_revision != serializer.validated_data['revision']:
                raise Conflict('La restricción cambió en otra sesión. Vuelve a abrir la ficha.')
            previous = {'participation_restricted': profile.participation_restricted,
                        'restriction_expires_at': profile.restriction_expires_at.isoformat() if profile.restriction_expires_at else None}
            profile.is_restricted = serializer.validated_data['restricted']
            profile.restriction_reason = serializer.validated_data['reason']
            until = serializer.validated_data['until']
            profile.restriction_expires_at = timezone.make_aware(datetime.combine(until, time.max), ZoneInfo(settings.TIME_ZONE)) if until else None
            profile.restriction_revision += 1
            profile.save(update_fields=['is_restricted', 'restriction_reason', 'restriction_expires_at', 'restriction_revision'])
            AuditEvent.objects.create(actor=request.user, action='volunteer.restriction.updated', resource=f'profile:{profile.pk}')
            AccountChange.objects.create(actor=request.user, target=profile.user, action='participation_restriction',
                reason=profile.restriction_reason, fields_changed=['participation_restricted', 'restriction_expires_at'],
                before_access=previous, after_access={'participation_restricted': profile.participation_restricted,
                    'restriction_expires_at': profile.restriction_expires_at.isoformat() if profile.restriction_expires_at else None})
            status = 'Se actualizó una restricción de participación en tu cuenta.' if profile.is_restricted else 'Se retiró la restricción de participación de tu cuenta.'
            Notification.objects.create(user=profile.user, target='participations', message=f'{status} Revisa el estado en tu espacio.')
    from activities.views import pagination
    rows = VolunteerProfile.objects.filter(user__groups__name='Voluntario').select_related('user').order_by('user__first_name', 'pk')
    query = request.query_params.get('q', '')[:100].strip()
    if query:
        rows = rows.filter(Q(user__first_name__icontains=query) | Q(user__last_name__icontains=query) | Q(commune__icontains=query))
    restriction = request.query_params.get('restricted', '')
    if restriction not in ['', 'true', 'false']:
        raise ValidationError('Filtro de estado no válido.')
    if restriction:
        active = Q(is_restricted=True) & (Q(restriction_expires_at__isnull=True) | Q(restriction_expires_at__gt=timezone.now()))
        rows = rows.filter(active) if restriction == 'true' else rows.exclude(active)
    page, items = pagination(request, rows)
    return Response({'results': [{'id': profile.pk, 'name': profile.user.get_full_name(), 'commune': profile.commune,
                                 **restriction_data(profile)} for profile in items], 'total': rows.count(), 'page': page})


@api_view(['GET'])
def volunteer_detail(request, profile_id):
    require_operator(request)
    profile = get_object_or_404(VolunteerProfile.objects.select_related('user'), pk=profile_id, user__groups__name='Voluntario')
    attended = profile.participations.filter(attendance='present', assignment='primary', event__status='finished').select_related('event')
    hours = sum((item.event.ends_at - item.event.starts_at).total_seconds() / 3600 for item in attended)
    result = {'id': profile.pk, 'name': profile.user.get_full_name(), 'email': profile.user.email,
              'commune': profile.commune, **restriction_data(profile),
              'skills': list(profile.declared_skills.values_list('skill__name', flat=True)),
              'professions': list(profile.declared_professions.values_list('profession__name', flat=True)),
              'attended_events': attended.count(), 'recorded_hours': round(hours, 1),
              'availability': list(profile.availability_slots.values('weekday', 'start_time', 'end_time')),
              'participations': [{'title': item.event.title, 'position': item.position.name, 'status': item.status, 'assignment': item.assignment,
                                  'starts_at': item.event.starts_at, 'attendance': item.attendance}
                                 for item in profile.participations.select_related('event', 'position')[:6]],
              'restriction_history': list(AccountChange.objects.filter(target=profile.user, action='participation_restriction')[:5].values('reason', 'created_at', 'after_access', 'actor_id', 'actor__first_name', 'actor__last_name'))}
    if request.user.has_perm('documents.review_volunteerdocument'):
        from documents.services import document_data
        latest = {}
        for document in profile.documents.select_related('document_type').order_by('document_type_id', '-version'):
            latest.setdefault(document.document_type_id, document)
        result['documents'] = [document_data(document) for document in latest.values()]
    if profile.whatsapp_opt_in_at and profile.phone:
        phone = ''.join(character for character in profile.phone if character.isdigit())
        if 8 <= len(phone) <= 15:
            result['whatsapp_url'] = f'https://wa.me/{phone}'
    return Response(result)
