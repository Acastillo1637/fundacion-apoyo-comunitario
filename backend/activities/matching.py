import json
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from accounts.geography import distance_km
from accounts.models import AuditEvent, VolunteerProfile
from accounts.security import portal_authenticated
from volunteers.serializers import StrictSerializer
from .models import MatchingPolicy, MatchingPolicyChange
from .services import Conflict, require_operator


def policy_data(policy):
    return {name: getattr(policy, name) for name in ['skills_weight', 'experience_weight', 'distance_weight',
        'distance_limit_km', 'experience_target', 'revision', 'geocoding_enabled', 'geocoding_policy_accepted_at']}


class PolicySerializer(StrictSerializer):
    skills_weight = serializers.IntegerField(min_value=0, max_value=100)
    experience_weight = serializers.IntegerField(min_value=0, max_value=100)
    distance_weight = serializers.IntegerField(min_value=0, max_value=100)
    distance_limit_km = serializers.IntegerField(min_value=1, max_value=500)
    experience_target = serializers.IntegerField(min_value=1, max_value=100)
    revision = serializers.IntegerField(min_value=0)
    reason = serializers.CharField(min_length=8, max_length=500)
    geocoding_enabled = serializers.BooleanField()
    accept_geocoding_policy = serializers.BooleanField(default=False)

    def validate(self, attrs):
        if sum(attrs[name] for name in ['skills_weight', 'experience_weight', 'distance_weight']) != 100:
            raise serializers.ValidationError('Los tres pesos deben sumar 100.')
        return attrs


@api_view(['GET', 'PUT'])
def configuration(request):
    if not request.user.has_perm('accounts.manage_accounts') or not portal_authenticated(request):
        raise PermissionDenied('Solo administración general puede configurar las recomendaciones.')
    if request.method == 'GET':
        return Response(policy_data(MatchingPolicy.objects.get(pk=1)))
    serializer = PolicySerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    values = dict(serializer.validated_data)
    with transaction.atomic():
        policy = MatchingPolicy.objects.select_for_update().get(pk=1)
        before = json.loads(json.dumps(policy_data(policy), cls=DjangoJSONEncoder))
        if policy.revision != values.pop('revision'):
            raise Conflict()
        accepted = values.pop('accept_geocoding_policy')
        reason = values.pop('reason')
        if values['geocoding_enabled'] and not policy.geocoding_policy_accepted_at and not accepted:
            raise ValidationError('Lee y acepta las condiciones de Nominatim antes de habilitar búsquedas externas.')
        if values['geocoding_enabled'] and accepted:
            policy.geocoding_policy_accepted_at = timezone.now()
        for name, value in values.items():
            setattr(policy, name, value)
        policy.revision += 1
        policy.save()
        MatchingPolicyChange.objects.create(policy=policy, actor=request.user, revision=policy.revision, reason=reason,
            before=before, after=json.loads(json.dumps(policy_data(policy), cls=DjangoJSONEncoder)))
        AuditEvent.objects.create(actor=request.user, action='matching.policy.updated', resource=f'matching-policy:{policy.revision}')
    return Response(policy_data(policy))


def ranked_candidates(request, position):
    """Hard gates first; rank the entire eligible cohort before paginating."""
    from .participation import eligibility, prepare_eligibility
    from .views import pagination
    from .models import Participation
    policy = MatchingPolicy.objects.get(pk=1)
    desired = set(position.desired_skills.filter(is_active=True).values_list('pk', flat=True))
    required = set(position.required_skills.values_list('pk', flat=True))
    reference = desired | required
    relevant = Q(participations__attendance='present', participations__assignment='primary', participations__event__status='finished')
    if reference:
        relevant &= Q(participations__position__required_skills__in=reference) | Q(participations__position__desired_skills__in=reference)
    else:
        relevant &= Q(participations__pk__isnull=True)
    profiles = list(VolunteerProfile.objects.filter(user__is_active=True, user__groups__name='Voluntario')
        .select_related('user').annotate(relevant_experience=Count('participations', filter=relevant, distinct=True)).order_by('pk'))
    prepare_eligibility(profiles, [position])
    registered = set(Participation.objects.filter(event=position.event, status__in=['applied', 'confirmed', 'waitlisted', 'invited'])
        .exclude(status='invited', expires_at__lte=timezone.now()).values_list('profile_id', flat=True))
    result = []
    for profile in profiles:
        reasons = eligibility(profile, position, prepared=True)
        if position.event.status != 'open' or position.event.starts_at <= timezone.now():
            reasons.append('La convocatoria no está abierta para nuevas invitaciones')
        declared = {row.skill_id for row in profile.declared_skills.all()}
        matches = len(desired & declared)
        skills_factor = matches / len(desired) if desired else 1
        experience_factor = min(profile.relevant_experience / policy.experience_target, 1)
        distance = None if position.event.is_remote else distance_km(profile.reference_latitude, profile.reference_longitude,
                                                                      position.event.latitude, position.event.longitude)
        distance_factor = 1 if position.event.is_remote else (max(0, 1-distance/policy.distance_limit_km) if distance is not None else 0)
        contributions = {'skills': round(policy.skills_weight*skills_factor, 2),
                         'experience': round(policy.experience_weight*experience_factor, 2),
                         'distance': round(policy.distance_weight*distance_factor, 2)}
        explanation = [f'Habilidades deseables: {matches}/{len(desired)}' if desired else 'Sin habilidades deseables adicionales: componente neutral',
                       f'{profile.relevant_experience} participaciones relevantes con asistencia registrada',
                       'Actividad remota: componente de distancia neutral' if position.event.is_remote else
                       f'{distance:.1f} km aproximados en línea recta' if distance is not None else 'Sin ubicación comparable: no se asignan puntos por distancia']
        result.append({'id': profile.pk, 'name': profile.user.get_full_name(), 'commune': profile.commune,
            'nearby': bool(profile.commune.strip() and profile.commune.casefold() == position.event.commune.casefold()),
            'eligible': not reasons, 'reasons': reasons, 'already_registered': profile.pk in registered,
            'score': round(sum(contributions.values()), 1) if not reasons else None,
            'score_components': contributions if not reasons else {}, 'recommendation_reasons': explanation if not reasons else [],
            'distance_km': distance, 'distance_type': 'straight_line_approximate',
            'location': {'latitude':float(profile.reference_latitude), 'longitude':float(profile.reference_longitude)}
                if not reasons and not position.event.is_remote and profile.reference_latitude is not None else None,
            'contact_allowed': bool(profile.whatsapp_opt_in_at and profile.phone)})
    result.sort(key=lambda row: (not row['eligible'], -(row['score'] or 0), row['distance_km'] if row['distance_km'] is not None else float('inf'), row['name'].casefold(), row['id']))
    mode = request.query_params.get('eligible_only', '')
    if mode not in ['', '0', '1']:
        raise ValidationError('Filtro de elegibilidad no válido.')
    if mode == '1':
        result = [row for row in result if row['eligible']]
    page, rows = pagination(request, result)
    return Response({'results':rows, 'total':len(result), 'page':page, 'policy':policy_data(policy),
        'event_location': {'latitude':position.event.latitude, 'longitude':position.event.longitude, 'is_remote':position.event.is_remote},
        'distance_notice':'Estimación en línea recta entre referencias geográficas; no es una ruta ni un tiempo de traslado.'})
