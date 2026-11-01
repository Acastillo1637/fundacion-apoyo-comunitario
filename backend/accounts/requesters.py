from allauth.account.models import EmailAddress
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.response import Response

from activities.models import ServiceRequest
from activities.serializers import LocalScheduleSerializer, RequestSerializer, active_choices
from volunteers.models import Skill
from volunteers.serializers import StrictSerializer
from .models import AuditEvent, RequesterProfile, User
from .portals import is_requester
from .views import limited, user_data


class RequesterSerializer(StrictSerializer):
    first_name = serializers.CharField(max_length=80)
    last_name = serializers.CharField(max_length=80)
    requester_type = serializers.ChoiceField(choices=['person', 'company', 'institution'])
    organization = serializers.CharField(max_length=150, allow_blank=True, default='')
    phone = serializers.RegexField(r'^\+?[0-9 ()-]{7,20}$')
    commune = serializers.CharField(max_length=80, allow_blank=True)
    revision = serializers.IntegerField(min_value=0)
    adult = serializers.BooleanField()
    privacy = serializers.BooleanField()
    authorized_representative = serializers.BooleanField(default=False)

    def validate(self, attrs):
        if not attrs['adult'] or not attrs['privacy']:
            raise serializers.ValidationError('Confirma tu mayoría de edad y el tratamiento de datos.')
        if attrs['requester_type'] != 'person' and (not attrs['organization'] or not attrs['authorized_representative']):
            raise serializers.ValidationError('Indica la entidad y confirma que puedes representarla.')
        return attrs


def require_requester(request):
    if not is_requester(request.user):
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied('Esta función pertenece al espacio de solicitante.')
    if not EmailAddress.objects.filter(user=request.user, verified=True).exists():
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied('Verifica tu correo antes de continuar.')


def profile_data(user, profile):
    return {**user_data(user), 'requester_type': profile.requester_type,
            'organization': profile.organization, 'phone': profile.phone,
            'commune': profile.commune, 'revision': profile.revision}


@api_view(['GET', 'PUT'])
def profile(request):
    require_requester(request)
    instance = RequesterProfile.objects.filter(user=request.user).first()
    if request.method == 'GET':
        return Response({'profile': profile_data(request.user, instance) if instance else None})
    serializer = RequesterSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=request.user.pk)
        instance = RequesterProfile.objects.select_for_update().filter(user=user).first()
        if data['revision'] != (instance.revision if instance else 0):
            return Response({'detail': 'El perfil cambió. Recarga antes de guardar.'}, status=409)
        now = timezone.now()
        if instance is None:
            instance = RequesterProfile(user=user, adult_confirmed_at=now, privacy_accepted_at=now)
        entity_changed = instance.requester_type != data['requester_type'] or instance.organization != data['organization']
        for field in ['requester_type', 'phone', 'commune']:
            setattr(instance, field, data[field])
        instance.organization = data['organization'] if data['requester_type'] != 'person' else ''
        if instance.requester_type == 'person':
            instance.representative_confirmed_at = None
        elif entity_changed or not instance.representative_confirmed_at:
            instance.representative_confirmed_at = now
        instance.revision += 1
        instance.save()
        user.first_name, user.last_name = data['first_name'], data['last_name']
        user.management_revision += 1
        user.save(update_fields=['first_name', 'last_name', 'management_revision'])
        AuditEvent.objects.create(actor=user, action='requester.profile.updated')
    return Response(profile_data(user, instance))


class OwnedRequestSerializer(RequestSerializer):
    def get_fields(self):
        fields = super().get_fields()
        for name in ['requester_type', 'contact_name', 'organization', 'email', 'phone']:
            fields.pop(name)
        return fields

    def validate(self, attrs):
        attrs = LocalScheduleSerializer.validate(self, attrs)
        if not attrs['privacy']:
            raise serializers.ValidationError({'privacy': 'Acepta el tratamiento de datos.'})
        attrs['skills'] = active_choices(Skill, attrs['skills'], 'skills')
        return attrs


def request_data(item):
    return {'id': str(item.pk), 'description': item.description, 'status': item.status,
            'quantity': item.quantity, 'starts_at': item.starts_at, 'ends_at': item.ends_at,
            'address': item.address, 'commune': item.commune, 'created_at': item.created_at,
            'organization': item.organization,
            'history': [{'status': entry.to_status, 'at': entry.created_at}
                        for entry in item.transitions.all()]}


@api_view(['GET', 'POST'])
def requests(request):
    require_requester(request)
    owner = get_object_or_404(RequesterProfile, user=request.user)
    if request.method == 'GET':
        from activities.views import pagination
        rows = ServiceRequest.objects.filter(requester=owner).prefetch_related('transitions')
        page, items = pagination(request, rows)
        return Response({'results': [request_data(item) for item in items], 'count': rows.count(), 'page': page})
    if limited(request, 'owned-request', 5):
        return Response({'detail': 'Demasiadas solicitudes. Intenta más tarde.'}, status=429)
    serializer = OwnedRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = dict(serializer.validated_data)
    if data.pop('website'):
        return Response({'detail': 'No se pudo enviar la solicitud.'}, status=400)
    data.pop('privacy')
    skills = data.pop('skills')
    with transaction.atomic():
        User.objects.select_for_update().get(pk=request.user.pk)
        owner = RequesterProfile.objects.select_for_update().get(pk=owner.pk)
        item, created = ServiceRequest.objects.get_or_create(submission_id=data['submission_id'], defaults={
            **data, 'requester': owner, 'requester_type': owner.requester_type,
            'organization': owner.organization, 'contact_name': request.user.get_full_name()[:120],
            'email': request.user.email, 'phone': owner.phone,
            'privacy_accepted_at': timezone.now(), 'email_verified_at': timezone.now(),
        })
        if item.requester_id != owner.pk:
            return Response({'detail': 'Identificador de envío no disponible. Abre un nuevo formulario.'}, status=409)
        if created:
            item.skills.set(skills)
            AuditEvent.objects.create(actor=request.user, action='request.created', resource=f'request:{item.pk}')
    return Response({'detail': 'Solicitud registrada. Puedes seguir su estado en Mis solicitudes.', 'id': str(item.pk)}, status=201 if created else 200)


@api_view(['GET'])
def request_detail(request, request_id):
    require_requester(request)
    item = get_object_or_404(ServiceRequest, pk=request_id, requester__user=request.user)
    return Response(request_data(item))
