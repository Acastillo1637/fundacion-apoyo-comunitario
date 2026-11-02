from datetime import timedelta
from collections.abc import Mapping
from smtplib import SMTPException
from urllib.parse import urlsplit
from uuid import UUID

from django.conf import settings
from django.core import signing
from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone
from django.views.decorators.cache import never_cache
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from accounts.models import AuditEvent
from accounts.views import limited
from volunteers.models import DocumentType, Skill
from .models import Event, EventChange, ServiceRequest
from .serializers import EditEventSerializer, EventSerializer, PublishedEventSerializer, RequestSerializer, TransitionSerializer
from .services import create_event, edit_event, event_data, request_data, require_operator, send_verification, transition_event, transition_request, update_published_event


def pagination(request, queryset):
    try:
        page = int(request.query_params.get('page', 1))
        if not 1 <= page <= 100000:
            raise ValueError
    except ValueError:
        raise ValidationError('Página no válida.')
    return page, queryset[(page - 1) * 20:page * 20]


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def public_options(request):
    return Response({'skills': list(Skill.objects.filter(is_active=True).values('id', 'name')), 'timezone': settings.TIME_ZONE,
                     'console_email': settings.DEBUG and settings.EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend'})


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def submit_request(request):
    # DRF no exige CSRF a anónimos por defecto: este formulario público sí.
    SessionAuthentication().enforce_csrf(request)
    if limited(request, 'public-request', 5):
        return Response({'detail': 'Demasiadas solicitudes. Intenta más tarde.'}, status=429)
    serializer = RequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = dict(serializer.validated_data)
    generic = {'detail': 'Solicitud recibida. Si corresponde, recibirás un enlace para confirmar el correo antes de su evaluación.'}
    if data.pop('website'):
        return Response(generic, status=202)
    origin = urlsplit(settings.PUBLIC_APP_URL)
    if not origin.netloc or origin.scheme not in ['http', 'https'] or (not settings.DEBUG and origin.scheme != 'https'):
        return Response({'detail': 'El formulario no está disponible hasta configurar el dominio de la plataforma.'}, status=503)
    data.pop('privacy')
    skills = data.pop('skills')
    with transaction.atomic():
        item, created = ServiceRequest.objects.get_or_create(
            submission_id=data['submission_id'], defaults={**data, 'privacy_accepted_at': timezone.now()},
        )
        if created:
            item.skills.set(skills)
            AuditEvent.objects.create(actor=None, action='request.created', resource=f'request:{item.pk}')
    try:
        with transaction.atomic():
            item = ServiceRequest.objects.select_for_update().get(pk=item.pk)
            if item.email == data['email'] and not item.email_verified_at and (
                not item.verification_sent_at or item.verification_sent_at < timezone.now() - timedelta(minutes=1)
            ):
                send_verification(item)
                item.verification_sent_at = timezone.now()
                item.save(update_fields=['verification_sent_at'])
    except (OSError, SMTPException):
        return Response({'detail': 'No se pudo enviar la verificación. Vuelve a intentar con este formulario; no se duplicará tu solicitud.'}, status=503)
    return Response(generic, status=202)


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def verify_request(request):
    SessionAuthentication().enforce_csrf(request)
    if limited(request, 'request-verification', 15):
        return Response({'detail': 'Demasiados intentos. Intenta más tarde.'}, status=429)
    if not isinstance(request.data, Mapping):
        raise ValidationError('Enlace no válido.')
    token = request.data.get('token')
    if not isinstance(token, str) or len(token) > 1000 or set(request.data) != {'token'}:
        raise ValidationError('Enlace no válido.')
    try:
        signed = signing.loads(token, salt='service-request-email', max_age=48 * 3600)
    except signing.BadSignature:
        raise ValidationError('El enlace no es válido o venció. Contacta a la fundación para solicitar ayuda.')
    if not isinstance(signed, dict) or set(signed) != {'id', 'nonce'}:
        raise ValidationError('Enlace no válido.')
    try:
        request_id = UUID(str(signed['id']))
        nonce = UUID(str(signed['nonce']))
    except (ValueError, TypeError):
        raise ValidationError('Enlace no válido.')
    with transaction.atomic():
        item = ServiceRequest.objects.select_for_update().filter(pk=request_id, verification_nonce=nonce).first()
        if not item:
            raise ValidationError('Enlace no válido.')
        if not item.email_verified_at:
            item.email_verified_at = timezone.now()
            item.revision += 1
            item.save(update_fields=['email_verified_at', 'revision'])
            AuditEvent.objects.create(actor=None, action='request.email_verified', resource=f'request:{item.pk}')
    return Response({'detail': 'Correo confirmado. La solicitud quedó disponible para evaluación; todavía no está aprobada.'})


@never_cache
@api_view(['GET'])
def requests(request):
    require_operator(request)
    queryset = ServiceRequest.objects.all()
    status = request.query_params.get('status')
    if status:
        if status not in ServiceRequest.Status.values:
            raise ValidationError('Estado no válido.')
        queryset = queryset.filter(status=status)
    page, rows = pagination(request, queryset)
    return Response({'results': [request_data(item) for item in rows], 'page': page, 'page_size': 20, 'total': queryset.count()})


@never_cache
@api_view(['GET'])
def request_detail(request, request_id):
    require_operator(request)
    from django.shortcuts import get_object_or_404
    return Response(request_data(get_object_or_404(ServiceRequest, pk=request_id), detail=True))


@never_cache
@api_view(['POST'])
def request_transition(request, request_id):
    require_operator(request)
    serializer = TransitionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return Response(request_data(transition_request(request, request_id, serializer.validated_data), detail=True))


@never_cache
@api_view(['POST'])
def event_create(request, request_id):
    require_operator(request)
    serializer = EventSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return Response(event_data(create_event(request, request_id, dict(serializer.validated_data)), private=True), status=201)


@never_cache
@api_view(['GET'])
def events(request):
    require_operator(request)
    queryset = Event.objects.prefetch_related(
        'positions__required_skills__required_documents', 'positions__required_documents', 'transitions',
        Prefetch('changes', queryset=EventChange.objects.select_related('actor').all()[:20], to_attr='loaded_changes'))
    page, rows = pagination(request, queryset)
    return Response({'results': [event_data(item, private=True) for item in rows], 'page': page, 'page_size': 20, 'total': queryset.count()})


@never_cache
@api_view(['GET', 'PUT', 'PATCH'])
def event_detail(request, event_id):
    require_operator(request)
    if request.method == 'GET':
        from django.shortcuts import get_object_or_404
        return Response(event_data(get_object_or_404(Event, pk=event_id), private=True))
    if request.method == 'PATCH':
        serializer = PublishedEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(event_data(update_published_event(request, event_id, serializer.validated_data), private=True))
    serializer = EditEventSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return Response(event_data(edit_event(request, event_id, dict(serializer.validated_data)), private=True))


@never_cache
@api_view(['POST'])
def event_transition(request, event_id):
    require_operator(request)
    serializer = TransitionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return Response(event_data(transition_event(request, event_id, serializer.validated_data), private=True))


@api_view(['GET'])
def operator_options(request):
    require_operator(request)
    return Response({'skills': list(Skill.objects.filter(is_active=True).values('id', 'name')),
                     'documents': list(DocumentType.objects.filter(is_active=True).values('id', 'name'))})


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def public_events(request):
    queryset = Event.objects.filter(status='open', starts_at__gt=timezone.now()).prefetch_related(
        'positions__required_skills__required_documents', 'positions__required_documents')
    page, rows = pagination(request, queryset)
    return Response({'results': [event_data(item) for item in rows], 'page': page, 'page_size': 20, 'total': queryset.count()})
