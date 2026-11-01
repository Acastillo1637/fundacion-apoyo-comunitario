from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from accounts.models import AuditEvent, VolunteerProfile
from .models import AvailabilitySlot, Profession, Skill, UnavailableDate, VolunteerProfession, VolunteerSkill
from .serializers import AvailabilitySerializer, QualificationsSerializer, SlotSerializer


def own_profile(request, lock=False):
    profiles = VolunteerProfile.objects.select_for_update() if lock else VolunteerProfile.objects
    return get_object_or_404(profiles, user=request.user)


def catalog_rows(model, selected):
    return [
        {'id': item.pk, 'name': item.name, 'description': item.description,
         'is_active': item.is_active,
         'required_documents': [
             {'id': document.pk, 'name': document.name, 'is_active': document.is_active}
             for document in item.required_documents.all()
         ]}
        for item in model.objects.filter(Q(is_active=True) | Q(pk__in=selected)).prefetch_related('required_documents')
    ]


def qualification_data(profile):
    return {
        'revision': profile.qualifications_revision,
        'skills': list(profile.declared_skills.order_by('skill_id').values_list('skill_id', flat=True)),
        'professions': list(profile.declared_professions.order_by('profession_id').values_list('profession_id', flat=True)),
        'status': 'declared',
    }


@api_view(['GET'])
def catalogs(request):
    profile = own_profile(request)
    data = qualification_data(profile)
    return Response({
        'skills': catalog_rows(Skill, data['skills']),
        'professions': catalog_rows(Profession, data['professions']),
    })


def selected_catalog(model, ids, previous):
    # Se bloquea también el catálogo para coordinarlo con una desactivación concurrente.
    rows = list(model.objects.select_for_update().filter(pk__in=ids).order_by('pk'))
    if len(rows) != len(ids) or any(not row.is_active and row.pk not in previous for row in rows):
        raise ValidationError('Selecciona opciones vigentes del catálogo. No se pueden agregar opciones desactivadas.')
    return rows


@api_view(['GET', 'PUT'])
def qualifications(request):
    if request.method == 'GET':
        return Response(qualification_data(own_profile(request)))
    serializer = QualificationsSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    with transaction.atomic():
        profile = own_profile(request, lock=True)
        if data['revision'] != profile.qualifications_revision:
            return Response({'detail': 'Tu perfil cambió en otra sesión. Recarga antes de guardar.'}, status=409)
        previous = qualification_data(profile)
        skills = selected_catalog(Skill, data['skills'], previous['skills'])
        professions = selected_catalog(Profession, data['professions'], previous['professions'])
        profile.declared_skills.exclude(skill_id__in=data['skills']).delete()
        profile.declared_professions.exclude(profession_id__in=data['professions']).delete()
        VolunteerSkill.objects.bulk_create([VolunteerSkill(profile=profile, skill=item) for item in skills if item.pk not in previous['skills']])
        VolunteerProfession.objects.bulk_create([VolunteerProfession(profile=profile, profession=item) for item in professions if item.pk not in previous['professions']])
        profile.qualifications_revision += 1
        profile.save(update_fields=['qualifications_revision'])
        AuditEvent.objects.create(actor=request.user, action='qualifications.updated', resource=f'profile:{profile.pk}')
        return Response(qualification_data(profile))


def availability_data(profile):
    return {
        'revision': profile.availability_revision,
        'timezone': settings.TIME_ZONE,
        'slots': SlotSerializer(profile.availability_slots.all(), many=True).data,
        'unavailable_dates': list(profile.unavailable_dates.values_list('date', flat=True)),
    }


@api_view(['GET', 'PUT'])
def availability(request):
    if request.method == 'GET':
        return Response(availability_data(own_profile(request)))
    serializer = AvailabilitySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    with transaction.atomic():
        profile = own_profile(request, lock=True)
        if data['revision'] != profile.availability_revision:
            return Response({'detail': 'Tu disponibilidad cambió en otra sesión. Recarga antes de guardar.'}, status=409)
        profile.availability_slots.all().delete()
        profile.unavailable_dates.all().delete()
        AvailabilitySlot.objects.bulk_create([AvailabilitySlot(profile=profile, **slot) for slot in data['slots']])
        UnavailableDate.objects.bulk_create([UnavailableDate(profile=profile, date=date) for date in data['unavailable_dates']])
        profile.availability_revision += 1
        profile.save(update_fields=['availability_revision'])
        AuditEvent.objects.create(actor=request.user, action='availability.updated', resource=f'profile:{profile.pk}')
        return Response(availability_data(profile))
