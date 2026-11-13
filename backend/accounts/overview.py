from django.conf import settings
from django.db.models import Count, Value, Window
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from activities.participation import data as participation_data
from documents.services import document_data
from volunteers.serializers import SlotSerializer
from .models import VolunteerProfile
from .portals import is_volunteer


@api_view(['GET'])
def volunteer_overview(request):
    """Load the volunteer home once, without repeating session/profile lookups."""
    if not is_volunteer(request.user):
        raise PermissionDenied('Esta función pertenece al voluntariado.')
    profile = get_object_or_404(VolunteerProfile, user=request.user)
    qualifications = list(profile.declared_skills.annotate(kind=Value('skill')).values_list('kind', 'skill_id', 'skill__name').union(
        profile.declared_professions.annotate(kind=Value('profession')).values_list('kind', 'profession_id', 'profession__name')))
    documents = list(profile.documents.select_related('document_type').order_by('document_type_id', '-version'))
    latest = {}
    for document in documents:
        latest.setdefault(document.document_type_id, document)
    rows = profile.participations.select_related('event', 'position')
    # Use a window total so the cards and their count share one round trip.
    participations = list(rows.annotate(total=Window(Count('pk')))[:4])
    restricted = profile.participation_restricted
    return Response({
        'profile': {'commune': profile.commune},
        'qualifications': {
            'skills': [{'id': identifier, 'name': name} for kind, identifier, name in qualifications if kind == 'skill'],
            'professions': [{'id': identifier, 'name': name} for kind, identifier, name in qualifications if kind == 'profession'],
        },
        'documents': {'documents': [document_data(document) for document in latest.values()]},
        'participations': {'results': [participation_data(item) for item in participations],
                           'total': participations[0].total if participations else 0},
        'participationStatus': {'restricted': restricted, 'reason': profile.restriction_reason if restricted else '',
                                'expires_at': profile.restriction_expires_at if restricted else None},
        'availability': {'revision': profile.availability_revision, 'timezone': settings.TIME_ZONE,
                         'slots': SlotSerializer(profile.availability_slots.all(), many=True).data,
                         'unavailable_dates': list(profile.unavailable_dates.values_list('date', flat=True))},
    })
