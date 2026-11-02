from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from accounts.models import AuditEvent, VolunteerProfile
from accounts.portals import is_volunteer
from volunteers.serializers import StrictSerializer
from .models import Event, EventPosition, Notification, Participation
from .services import Conflict, require_operator


def own_profile(request):
    if not is_volunteer(request.user):
        raise PermissionDenied('Esta función pertenece al voluntariado.')
    return get_object_or_404(VolunteerProfile, user=request.user)


def eligibility(profile, position):
    event = position.event
    reasons = []
    if position.required_skills.filter(is_active=False).exists() or position.required_documents.filter(is_active=False).exists() or position.required_skills.filter(required_documents__is_active=False).exists():
        reasons.append('La coordinación debe revisar requisitos desactivados')
    if not profile.user.is_active or not profile.user.groups.filter(name='Voluntario').exists() or profile.is_restricted:
        reasons.append('Participación no habilitada')
    required = set(position.required_skills.values_list('pk', flat=True))
    declared = set(profile.declared_skills.values_list('skill_id', flat=True))
    if not required.issubset(declared):
        reasons.append('Faltan habilidades requeridas')
    documents = set(position.required_documents.values_list('pk', flat=True))
    for skill in position.required_skills.all():
        documents.update(skill.required_documents.values_list('pk', flat=True))
    for document_id in documents:
        latest = profile.documents.filter(document_type_id=document_id).order_by('-version').first()
        event_date = timezone.localtime(event.ends_at).date()
        if (not latest or latest.effective_status != 'validated'
                or (latest.expires_on and latest.expires_on < event_date)
                or (not settings.DEBUG and latest.scan_status != 'clean')):
            reasons.append('Falta documentación vigente para la fecha del evento')
            break
    start, end = timezone.localtime(event.starts_at), timezone.localtime(event.ends_at)
    if start.date() != end.date() or profile.unavailable_dates.filter(date=start.date()).exists() or not profile.availability_slots.filter(
            weekday=start.weekday(), start_time__lte=start.time(), end_time__gte=end.time()).exists():
        reasons.append('Fuera de la disponibilidad declarada')
    if profile.participations.filter(status='confirmed', event__status='open', event__starts_at__lt=event.ends_at,
                                    event__ends_at__gt=event.starts_at).exclude(event=event).exists():
        reasons.append('Coincide con otra participación confirmada')
    return reasons


def notify(profile, message):
    Notification.objects.create(user=profile.user, message=message[:300])


def data(item, operator=False):
    expired = item.status == 'invited' and item.expires_at <= timezone.now()
    result = {'id': str(item.pk), 'event_id': str(item.event_id), 'title': item.event.title,
              'position': item.position.name, 'position_id': item.position_id,
              'status': 'expired' if expired else item.status, 'event_status': item.event.status,
              'starts_at': item.event.starts_at, 'ends_at': item.event.ends_at,
              'commune': item.event.commune, 'expires_at': item.expires_at,
              'attendance': item.attendance, 'revision': item.revision}
    if item.status == 'confirmed' and item.event.status != 'cancelled':
        result['address'] = item.event.address
    if operator:
        result.update(name=item.profile.user.get_full_name(), email=item.profile.user.email,
                      profile_id=item.profile_id, eligible=not eligibility(item.profile, item.position))
        if item.profile.whatsapp_opt_in_at and item.profile.phone:
            phone = ''.join(character for character in item.profile.phone if character.isdigit())
            if 8 <= len(phone) <= 15:
                text = f'{settings.FOUNDATION_NAME}: tienes una invitación para {item.event.title}. Revisa tu espacio en {settings.PUBLIC_APP_URL}/'
                result['whatsapp_url'] = f'https://wa.me/{phone}?{urlencode({"text": text})}'
    return result


class ApplySerializer(StrictSerializer):
    position_id = serializers.IntegerField(min_value=1)


class InviteSerializer(StrictSerializer):
    position_id = serializers.IntegerField(min_value=1)
    profile_id = serializers.IntegerField(min_value=1)


class DecisionSerializer(StrictSerializer):
    revision = serializers.IntegerField(min_value=0)
    action = serializers.ChoiceField(choices=['accept', 'decline', 'withdraw', 'confirm', 'reject', 'cancel', 'present', 'absent'])


def open_event(event):
    if event.status != 'open' or event.starts_at <= timezone.now():
        raise ValidationError('La convocatoria no está abierta o ya comenzó.')


def confirm(item):
    reasons = eligibility(item.profile, item.position)
    if reasons:
        raise ValidationError(' · '.join(reasons))
    taken = Participation.objects.filter(position=item.position, status='confirmed').exclude(pk=item.pk).count()
    item.status = 'confirmed' if taken < item.position.capacity else 'waitlisted'


@api_view(['GET', 'POST'])
def mine(request):
    profile = own_profile(request)
    if request.method == 'GET':
        from .views import pagination
        rows = profile.participations.select_related('event', 'position')
        page, items = pagination(request, rows)
        return Response({'results': [data(item) for item in items], 'total': rows.count(), 'page': page})
    serializer = ApplySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    identity = get_object_or_404(EventPosition, pk=serializer.validated_data['position_id'])
    with transaction.atomic():
        event = Event.objects.select_for_update().get(pk=identity.event_id)
        profile = VolunteerProfile.objects.select_for_update().get(pk=profile.pk)
        position = EventPosition.objects.select_related('event').get(pk=identity.pk)
        open_event(event)
        reasons = eligibility(profile, position)
        if reasons:
            raise ValidationError(' · '.join(reasons))
        item, created = Participation.objects.get_or_create(event=event, profile=profile, defaults={'position': position})
        if not created:
            raise Conflict('Ya existe una postulación o invitación para esta actividad. Revísala en Mis participaciones.')
        AuditEvent.objects.create(actor=request.user, action='participation.applied', resource=f'participation:{item.pk}')
        notify(profile, f'Postulación recibida: {event.title}. El equipo revisará tu participación.')
    return Response(data(item), status=201)


@api_view(['GET', 'POST'])
def event_participants(request, event_id):
    require_operator(request)
    event = get_object_or_404(Event, pk=event_id)
    if request.method == 'GET':
        from .views import pagination
        rows = event.participations.select_related('profile__user', 'event', 'position')
        page, items = pagination(request, rows)
        from django.db.models import Sum
        return Response({'results': [data(item, True) for item in items], 'total': rows.count(), 'page': page,
                         'stats': {'capacity': event.positions.aggregate(total=Sum('capacity'))['total'] or 0,
                                   'confirmed': rows.filter(status='confirmed').count(),
                                   'waiting': rows.filter(status='waitlisted').count(),
                                   'invited': rows.filter(status='invited', expires_at__gt=timezone.now()).count()}})
    serializer = InviteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    values = serializer.validated_data
    with transaction.atomic():
        event = Event.objects.select_for_update().get(pk=event.pk)
        profile = get_object_or_404(VolunteerProfile.objects.select_for_update().select_related('user'), pk=values['profile_id'])
        position = get_object_or_404(EventPosition.objects.select_related('event'), pk=values['position_id'], event=event)
        open_event(event)
        reasons = eligibility(profile, position)
        if reasons:
            raise ValidationError(' · '.join(reasons))
        item, created = Participation.objects.get_or_create(event=event, profile=profile, defaults={
            'position': position, 'status': 'invited', 'expires_at': min(timezone.now() + timedelta(hours=48), event.starts_at)})
        if not created:
            if item.status not in ['declined', 'cancelled', 'rejected'] and not (item.status == 'invited' and item.expires_at <= timezone.now()):
                raise Conflict('Esta persona ya tiene una participación activa para el evento.')
            item.position = position
            item.status = 'invited'
            item.expires_at = min(timezone.now() + timedelta(hours=48), event.starts_at)
            item.revision += 1
            item.save(update_fields=['position', 'status', 'expires_at', 'revision', 'updated_at'])
        notify(profile, f'Invitación: {event.title}. Responde antes de {timezone.localtime(item.expires_at):%d/%m %H:%M}.')
        AuditEvent.objects.create(actor=request.user, action='participation.invited', resource=f'participation:{item.pk}')
    return Response(data(item, True), status=201)


@api_view(['GET'])
def candidates(request, event_id, position_id):
    require_operator(request)
    position = get_object_or_404(EventPosition.objects.select_related('event'), pk=position_id, event_id=event_id)
    from .views import pagination
    rows = VolunteerProfile.objects.filter(user__is_active=True, user__groups__name='Voluntario').select_related('user').order_by('user__first_name', 'pk').distinct()
    page, items = pagination(request, rows)
    return Response({'results': [{'id': item.pk, 'name': item.user.get_full_name(), 'commune': item.commune,
                                 'nearby': bool(item.commune.strip() and item.commune.strip().casefold() == position.event.commune.strip().casefold()),
                                 'eligible': not (reasons := eligibility(item, position)), 'reasons': reasons,
                                 'already_registered': position.event.participations.filter(profile=item, status__in=['applied', 'confirmed', 'waitlisted', 'invited']).exclude(status='invited', expires_at__lte=timezone.now()).exists()}
                                for item in items], 'total': rows.count(), 'page': page})


@api_view(['POST'])
def decision(request, participation_id):
    serializer = DecisionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    action, revision = serializer.validated_data['action'], serializer.validated_data['revision']
    operator = action in ['confirm', 'reject', 'cancel', 'present', 'absent']
    if operator:
        require_operator(request)
        identity = get_object_or_404(Participation, pk=participation_id)
    else:
        profile = own_profile(request)
        identity = get_object_or_404(Participation, pk=participation_id, profile=profile)
    with transaction.atomic():
        event = Event.objects.select_for_update().get(pk=identity.event_id)
        VolunteerProfile.objects.select_for_update().get(pk=identity.profile_id)
        item = Participation.objects.select_for_update().select_related('event', 'position', 'profile__user').get(pk=identity.pk)
        if item.revision != revision:
            raise Conflict()
        if action in ['present', 'absent']:
            if item.status != 'confirmed' or event.status not in ['open', 'finished'] or event.starts_at > timezone.now():
                raise ValidationError('La asistencia se registra para participantes confirmados desde el inicio del evento.')
            item.attendance = action
        elif action == 'withdraw':
            open_event(event)
            if item.status not in ['applied', 'invited', 'confirmed', 'waitlisted']:
                raise ValidationError('No puedes retirar esta participación.')
            item.status = 'cancelled'
        elif action == 'cancel':
            if item.status not in ['applied', 'invited', 'confirmed', 'waitlisted'] or event.status != 'open':
                raise ValidationError('No se puede cancelar esta participación.')
            item.status = 'cancelled'
        else:
            open_event(event)
            if action in ['accept', 'decline']:
                if item.status != 'invited' or item.expires_at <= timezone.now():
                    raise ValidationError('La invitación ya fue respondida o venció.')
                if action == 'accept':
                    confirm(item)
                else:
                    item.status = 'declined'
            elif action in ['confirm', 'reject']:
                if item.status not in ['applied', 'waitlisted']:
                    raise ValidationError('La decisión requiere una postulación o lista de espera.')
                if action == 'confirm':
                    confirm(item)
                else:
                    item.status = 'rejected'
        item.revision += 1
        item.save(update_fields=['status', 'attendance', 'revision', 'updated_at'])
        notify(item.profile, f'{event.title}: participación actualizada ({item.status}).')
        AuditEvent.objects.create(actor=request.user, action=f'participation.{action}', resource=f'participation:{item.pk}')
    return Response(data(item, operator))


@api_view(['GET', 'POST'])
def notifications(request):
    if request.method == 'POST':
        if request.data != {'read_all': True}:
            raise ValidationError('Solicitud no válida.')
        request.user.notifications.filter(read_at__isnull=True).update(read_at=timezone.now())
    rows = request.user.notifications.all()
    return Response({'unread': rows.filter(read_at__isnull=True).count(), 'results': list(rows[:30].values('id', 'message', 'read_at', 'created_at'))})
