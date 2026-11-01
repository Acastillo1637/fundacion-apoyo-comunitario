from allauth.account.internal.flows.login import get_authentication_records
from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError

from accounts.models import AuditEvent
from .models import Event, EventPosition, EventTransition, RequestTransition, ServiceRequest


class Conflict(APIException):
    status_code = 409
    default_detail = 'La información cambió en otra sesión. Recarga antes de continuar.'


def require_operator(request):
    if not request.user.has_perm('activities.manage_operations') or not any(
        method.get('method') == 'mfa' for method in get_authentication_records(request, request.user)
    ):
        raise PermissionDenied('La operación requiere permiso de gestión de actividades y MFA.')


def schedule_data(item):
    start = timezone.localtime(item.starts_at)
    end = timezone.localtime(item.ends_at)
    return {'date': start.date(), 'start_time': start.strftime('%H:%M'), 'end_time': end.strftime('%H:%M'), 'timezone': settings.TIME_ZONE}


def request_data(item, detail=False):
    data = {
        'id': str(item.pk), 'requester_type': item.requester_type, 'contact_name': item.contact_name,
        'organization': item.organization, 'quantity': item.quantity, 'commune': item.commune,
        'status': item.status, 'revision': item.revision,
        'email_verified': item.email_verified_at is not None, 'created_at': item.created_at,
        **schedule_data(item),
    }
    if detail:
        data.update(email=item.email, phone=item.phone, description=item.description,
                    address=item.address, observations=item.observations,
                    skills=[{'id': skill.pk, 'name': skill.name} for skill in item.skills.all()],
                    events=[{'id': str(event.pk), 'title': event.title, 'status': event.status} for event in item.events.all()],
                    history=[{'from': change.from_status, 'to': change.to_status, 'reason': change.reason, 'at': change.created_at} for change in item.transitions.all()])
    return data


def event_data(item, private=False):
    positions = list(item.positions.prefetch_related('required_skills__required_documents', 'required_documents'))
    data = {
        'id': str(item.pk), 'title': item.title, 'public_description': item.public_description,
        'commune': item.commune, 'status': item.status, **schedule_data(item),
        'capacity': sum(position.capacity for position in positions),
        'positions': [
            {'id': position.pk, 'name': position.name, 'capacity': position.capacity,
             'required_skills': [{'id': skill.pk, 'name': skill.name} for skill in position.required_skills.all()],
             'required_documents': [{'id': document.pk, 'name': document.name} for document in position.required_documents.all()],
             'inherited_documents': list({document.pk: {'id': document.pk, 'name': document.name}
                                          for skill in position.required_skills.all() for document in skill.required_documents.all()}.values())}
            for position in positions
        ],
    }
    if private:
        data.update(request_id=str(item.request_id), address=item.address, internal_notes=item.internal_notes,
                    revision=item.revision,
                    history=[{'from': change.from_status, 'to': change.to_status, 'reason': change.reason, 'at': change.created_at} for change in item.transitions.all()])
    return data


def send_verification(item):
    token = signing.dumps({'id': str(item.pk), 'nonce': str(item.verification_nonce)}, salt='service-request-email')
    url = f'{settings.PUBLIC_APP_URL.rstrip("/")}/#confirm-request={token}'
    send_mail(
        f'{settings.FOUNDATION_NAME}: confirma tu solicitud',
        f'Confirma tu correo para que la fundación pueda evaluar la solicitud.\n\n{url}\n\n'
        'El enlace vence en 48 horas. No confirma la aprobación de la actividad.\n'
        'Si no realizaste esta solicitud, puedes ignorar el mensaje.',
        settings.DEFAULT_FROM_EMAIL, [item.email], fail_silently=False,
    )


def replace_positions(event, positions):
    event.positions.all().delete()
    for data in positions:
        position = EventPosition.objects.create(event=event, name=data['name'], capacity=data['capacity'])
        position.required_skills.set(data['required_skills'])
        position.required_documents.set(data['required_documents'])


@transaction.atomic
def transition_request(request, request_id, data):
    require_operator(request)
    item = get_object_or_404(ServiceRequest.objects.select_for_update(), pk=request_id)
    if item.revision != data['revision']:
        raise Conflict()
    allowed = {'pending': ['in_review'], 'in_review': ['approved', 'rejected']}
    target = data['status']
    if target not in allowed.get(item.status, []):
        raise ValidationError('Transición de solicitud no permitida.')
    if target == 'approved' and not item.email_verified_at:
        raise ValidationError('El solicitante debe verificar su correo antes de aprobar.')
    if target == 'approved' and item.starts_at <= timezone.now():
        raise ValidationError('La fecha solicitada ya pasó. Coordina una nueva solicitud con fecha vigente.')
    if target == 'rejected' and not data['reason'].strip():
        raise ValidationError('Debes justificar el rechazo.')
    RequestTransition.objects.create(request=item, actor=request.user, from_status=item.status, to_status=target, reason=data['reason'])
    item.status = target
    item.revision += 1
    item.save(update_fields=['status', 'revision'])
    AuditEvent.objects.create(actor=request.user, action=f'request.{target}', resource=f'request:{item.pk}')
    return item


@transaction.atomic
def create_event(request, request_id, data):
    require_operator(request)
    source = get_object_or_404(ServiceRequest.objects.select_for_update(), pk=request_id)
    if source.status != 'approved' or not source.email_verified_at:
        raise ValidationError('Solo una solicitud aprobada y verificada puede generar eventos.')
    positions = data.pop('positions')
    item = Event.objects.create(request=source, **data)
    replace_positions(item, positions)
    AuditEvent.objects.create(actor=request.user, action='event.created', resource=f'event:{item.pk}')
    return item


@transaction.atomic
def edit_event(request, event_id, data):
    require_operator(request)
    item = get_object_or_404(Event.objects.select_for_update(), pk=event_id)
    if item.revision != data.pop('revision'):
        raise Conflict()
    if item.status != 'draft':
        raise ValidationError('Solo se pueden editar borradores. Los cambios de actividades publicadas requieren el flujo de comunicación que se incorporará después.')
    positions = data.pop('positions')
    for field, value in data.items():
        setattr(item, field, value)
    item.revision += 1
    item.save()
    replace_positions(item, positions)
    AuditEvent.objects.create(actor=request.user, action='event.updated', resource=f'event:{item.pk}')
    return item


@transaction.atomic
def transition_event(request, event_id, data):
    require_operator(request)
    item = get_object_or_404(Event.objects.select_for_update(), pk=event_id)
    if item.revision != data['revision']:
        raise Conflict()
    target = data['status']
    allowed = {'draft': ['open', 'cancelled'], 'open': ['finished', 'cancelled']}
    if target not in allowed.get(item.status, []):
        raise ValidationError('Transición de evento no permitida.')
    if target == 'open':
        if item.starts_at <= timezone.now() or not item.positions.exists():
            raise ValidationError('El evento debe ser futuro y tener funciones con cupos.')
        for position in item.positions.all():
            if position.required_skills.filter(is_active=False).exists() or position.required_documents.filter(is_active=False).exists() or position.required_skills.filter(required_documents__is_active=False).exists():
                raise ValidationError('Revisa los requisitos desactivados antes de publicar.')
    if target == 'finished' and item.ends_at > timezone.now():
        raise ValidationError('No se puede finalizar una actividad que aún no termina.')
    if target == 'cancelled' and not data['reason'].strip():
        raise ValidationError('Debes registrar el motivo de cancelación.')
    EventTransition.objects.create(event=item, actor=request.user, from_status=item.status, to_status=target, reason=data['reason'])
    item.status = target
    item.revision += 1
    item.save(update_fields=['status', 'revision'])
    AuditEvent.objects.create(actor=request.user, action=f'event.{target}', resource=f'event:{item.pk}')
    return item
