"""Fresh PostgreSQL matching reads without sequential relation round trips.

Only read-only recommendations use this snapshot. Writes keep the existing
locked eligibility queries. SQLite retains the portable prefetch path.
"""
from datetime import date, datetime, time
from uuid import UUID

from django.contrib.auth.models import Group
from django.contrib.postgres.expressions import ArraySubquery
from django.db.models import Count, Exists, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce, JSONObject
from django.utils import timezone

from accounts.models import VolunteerProfile
from documents.models import VolunteerDocument
from volunteers.models import AvailabilitySlot, DocumentType, Skill, UnavailableDate, VolunteerSkill
from .models import Event, EventPosition, Participation


def json_rows(queryset, **fields):
    return ArraySubquery(queryset.order_by().annotate(payload=JSONObject(**fields)).values('payload'))


def positions():
    inherited = json_rows(DocumentType.objects.filter(skill=OuterRef('pk')), id='pk', active='is_active')
    skills = Skill.objects.filter(eventposition=OuterRef('pk')).annotate(documents=inherited)
    return EventPosition.objects.select_related('event').annotate(
        matching_required=json_rows(skills, id='pk', active='is_active', documents='documents'),
        matching_documents=json_rows(DocumentType.objects.filter(eventposition=OuterRef('pk')), id='pk', active='is_active'),
        matching_desired=ArraySubquery(Skill.objects.filter(desirable_positions=OuterRef('pk'), is_active=True).order_by().values('pk')))


def candidates(position):
    if not hasattr(position, 'matching_required'):
        loaded = positions().get(pk=position.pk)
        for field in ['matching_required', 'matching_documents', 'matching_desired']:
            setattr(position, field, getattr(loaded, field))
    skills, document_ids = [], set()
    for row in position.matching_required:
        skill = Skill(pk=row['id'], is_active=row['active'])
        documents = [DocumentType(pk=doc['id'], is_active=doc['active']) for doc in row['documents']]
        skill._prefetched_objects_cache = {'required_documents': documents}
        document_ids.update(doc.pk for doc in documents)
        skills.append(skill)
    documents = [DocumentType(pk=row['id'], is_active=row['active']) for row in position.matching_documents]
    document_ids.update(doc.pk for doc in documents)
    position._prefetched_objects_cache = {'required_skills': skills, 'required_documents': documents}
    desired, required = set(position.matching_desired), {skill.pk for skill in skills}
    reference = desired | required
    event = position.event
    start, end = timezone.localtime(event.starts_at), timezone.localtime(event.ends_at)
    relevant = Participation.objects.filter(profile_id=OuterRef('pk'), attendance='present', assignment='primary', event__status='finished')
    relevant = relevant.filter(Q(position__required_skills__in=reference) | Q(position__desired_skills__in=reference)) if reference else relevant.none()
    experience = relevant.order_by().values('profile_id').annotate(total=Count('pk', distinct=True)).values('total')[:1]
    overlapping = Participation.objects.filter(profile_id=OuterRef('pk'), status='confirmed', assignment='primary',
        event__status='open', event__starts_at__lt=event.ends_at, event__ends_at__gt=event.starts_at).exclude(event=event)
    slots = AvailabilitySlot.objects.filter(profile_id=OuterRef('pk'), weekday=start.weekday(), start_time__lte=start.time(), end_time__gte=end.time())
    history = VolunteerDocument.objects.filter(profile_id=OuterRef('pk'), document_type_id__in=document_ids)
    history = history.order_by('document_type_id', '-version').distinct('document_type_id').annotate(payload=JSONObject(
        type='document_type_id', version='version', status='status', expires='expires_on', scan='scan_status')).values('payload')
    profiles = list(VolunteerProfile.objects.filter(user__is_active=True, user__groups__name='Voluntario').select_related('user').annotate(
        relevant_experience=Coalesce(Subquery(experience), 0),
        matching_skills=ArraySubquery(VolunteerSkill.objects.filter(profile_id=OuterRef('pk')).order_by().values('skill_id')),
        matching_docs=ArraySubquery(history),
        matching_slots=json_rows(slots, weekday='weekday', start='start_time', end='end_time'),
        matching_unavailable=Exists(UnavailableDate.objects.filter(profile_id=OuterRef('pk'), date=start.date())),
        matching_overlaps=json_rows(overlapping, event='event_id', start='event__starts_at', end='event__ends_at'),
        matching_registered=Exists(Participation.objects.filter(profile_id=OuterRef('pk'), event=event,
            status__in=['applied', 'confirmed', 'waitlisted', 'invited']).exclude(status='invited', expires_at__lte=timezone.now()))).order_by('pk'))
    for profile in profiles:
        # Membership follows the active-user + exact role filter above, not client input.
        profile.user._prefetched_objects_cache = {'groups': [Group(name='Voluntario')]}
        docs = [VolunteerDocument(profile_id=profile.pk, document_type_id=row['type'], version=row['version'],
            status=row['status'], expires_on=date.fromisoformat(row['expires']) if row['expires'] else None,
            scan_status=row['scan']) for row in (profile.matching_docs or [])]
        profile._prefetched_objects_cache = {
            'declared_skills': [VolunteerSkill(profile_id=profile.pk, skill_id=pk) for pk in profile.matching_skills],
            'documents': docs,
            'unavailable_dates': [UnavailableDate(date=start.date())] if profile.matching_unavailable else [],
            'availability_slots': [AvailabilitySlot(weekday=row['weekday'], start_time=time.fromisoformat(row['start']),
                end_time=time.fromisoformat(row['end'])) for row in profile.matching_slots]}
        profile.matching_confirmed = [Participation(event=Event(pk=UUID(row['event']), starts_at=datetime.fromisoformat(row['start']),
            ends_at=datetime.fromisoformat(row['end']))) for row in profile.matching_overlaps]
    return desired, required, profiles, {profile.pk for profile in profiles if profile.matching_registered}
