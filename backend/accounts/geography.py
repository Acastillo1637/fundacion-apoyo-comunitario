"""Private reference points, straight-line distance and opt-in place search."""
import hashlib
import json
import math
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.cache import never_cache
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import APIException, PermissionDenied, ValidationError
from rest_framework.response import Response

from activities.models import Event, EventChange, GeocodingGate, GeocodingResult, MatchingPolicy, Notification
from activities.services import Conflict, require_operator
from volunteers.serializers import StrictSerializer
from .models import AuditEvent, VolunteerProfile
from .portals import is_volunteer
from .views import limited


class ProviderUnavailable(APIException):
    status_code = 503
    default_detail = 'La búsqueda de lugares no está disponible. Puedes marcar el mapa o ingresar coordenadas.'


class SearchBusy(APIException):
    status_code = 429
    default_detail = 'Espera un momento antes de buscar otro lugar.'


@api_view(['GET'])
def map_config(request):
    if not (is_volunteer(request.user) or request.user.has_perm('activities.manage_operations')):
        raise PermissionDenied('No tienes acceso a mapas privados.')
    policy = MatchingPolicy.objects.filter(pk=1).first()
    return Response({'tile_url': settings.MAP_TILE_URL, 'geocoding_enabled':bool(policy and policy.geocoding_enabled),
                     'attribution':'© OpenStreetMap contributors', 'max_zoom':17})


def point(latitude, longitude, approximate=False):
    if latitude is None and longitude is None:
        return None, None
    if latitude is None or longitude is None:
        raise ValidationError('Indica ambas coordenadas o elimina ambas.')
    try:
        lat, lon = Decimal(str(latitude)), Decimal(str(longitude))
        if not lat.is_finite() or not lon.is_finite() or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError()
    except (ValueError, ArithmeticError):
        raise ValidationError('Las coordenadas no son válidas.')
    precision = Decimal('0.01' if approximate else '0.000001')
    return lat.quantize(precision, rounding=ROUND_HALF_UP), lon.quantize(precision, rounding=ROUND_HALF_UP)


def distance_km(lat1, lon1, lat2, lon2):
    if any(value is None for value in [lat1, lon1, lat2, lon2]):
        return None
    a, b = point(lat1, lon1)
    c, d = point(lat2, lon2)
    lat1, lon1, lat2, lon2 = map(math.radians, map(float, [a, b, c, d]))
    hav = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return round(6371.0088 * 2 * math.asin(math.sqrt(min(1, max(0, hav)))), 3)


def location_data(profile):
    return {'latitude': profile.reference_latitude, 'longitude': profile.reference_longitude,
            'commune': profile.commune, 'sector': profile.sector, 'revision': profile.location_revision,
            'address_geocoding_enabled': bool(settings.GEOAPIFY_API_KEY),
            'precision': 'Referencia redondeada a 0,01 grados; no representa un domicilio.'}


class LocationSerializer(StrictSerializer):
    latitude = serializers.FloatField(allow_null=True)
    longitude = serializers.FloatField(allow_null=True)
    commune = serializers.CharField(max_length=80, allow_blank=True)
    sector = serializers.CharField(max_length=80, allow_blank=True)
    revision = serializers.IntegerField(min_value=0)


@never_cache
@api_view(['GET', 'PUT'])
def own_location(request):
    if not is_volunteer(request.user):
        raise PermissionDenied('Solo puedes gestionar tu propia referencia de voluntario.')
    if request.method == 'GET':
        return Response(location_data(get_object_or_404(VolunteerProfile, user=request.user)))
    serializer = LocationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    values = serializer.validated_data
    lat, lon = point(values['latitude'], values['longitude'], approximate=True)
    with transaction.atomic():
        profile = get_object_or_404(VolunteerProfile.objects.select_for_update(), user=request.user)
        if profile.location_revision != values['revision']:
            raise Conflict()
        profile.reference_latitude, profile.reference_longitude = lat, lon
        profile.commune, profile.sector = values['commune'], values['sector']
        profile.location_revision += 1
        profile.save(update_fields=['reference_latitude', 'reference_longitude', 'commune', 'sector', 'location_revision'])
        AuditEvent.objects.create(actor=request.user, action='profile.location.updated', resource=f'profile:{profile.pk}')
    return Response(location_data(profile))


class EventLocationSerializer(StrictSerializer):
    latitude = serializers.FloatField(allow_null=True)
    longitude = serializers.FloatField(allow_null=True)
    is_remote = serializers.BooleanField()
    address = serializers.CharField(max_length=250, allow_blank=True)
    commune = serializers.CharField(max_length=80, allow_blank=True)
    revision = serializers.IntegerField(min_value=0)
    reason = serializers.CharField(min_length=8, max_length=1000)


@api_view(['PUT'])
def event_location(request, event_id):
    require_operator(request)
    serializer = EventLocationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    values = serializer.validated_data
    lat, lon = point(values['latitude'], values['longitude'])
    if values['is_remote']:
        lat = lon = None
    elif not values['address'].strip() or not values['commune'].strip():
        raise ValidationError('Indica dirección y comuna para una actividad presencial.')
    with transaction.atomic():
        event = get_object_or_404(Event.objects.select_for_update(), pk=event_id)
        if event.revision != values['revision']:
            raise Conflict()
        if event.status not in ['draft', 'open'] or event.starts_at <= timezone.now():
            raise ValidationError('Solo se actualiza la ubicación de actividades futuras en borrador o abiertas.')
        fields = ['latitude', 'longitude', 'is_remote', 'address', 'commune']
        before = {'is_remote': event.is_remote, 'commune': event.commune}
        for name in fields:
            setattr(event, name, {'latitude': lat, 'longitude': lon}.get(name, values.get(name)))
        event.revision += 1
        event.save(update_fields=fields+['revision'])
        EventChange.objects.create(event=event, actor=request.user, revision=event.revision, reason=values['reason'],
            fields_changed=fields, before_public=before, after_public={'is_remote': event.is_remote, 'commune': event.commune})
        if event.status == 'open':
            recipients = event.participations.filter(status__in=['applied', 'invited', 'confirmed', 'waitlisted']).values_list('profile__user_id', flat=True).distinct()
            Notification.objects.bulk_create([Notification(user_id=pk, target='participations',
                message=f'Se actualizó la ubicación de {event.title}. Revisa la convocatoria antes de participar.') for pk in recipients])
        AuditEvent.objects.create(actor=request.user, action='event.location.updated', resource=f'event:{event.pk}')
    from activities.services import event_data
    return Response(event_data(event, private=True))


@api_view(['POST'])
def geocode(request):
    if not (is_volunteer(request.user) or request.user.has_perm('activities.manage_operations')):
        raise PermissionDenied('No tienes acceso a búsqueda de lugares.')
    if request.user.has_perm('activities.manage_operations') and not is_volunteer(request.user):
        require_operator(request)
    if set(request.data) != {'query'} or not isinstance(request.data['query'], str) or not 3 <= len(request.data['query'].strip()) <= 150:
        raise ValidationError('Escribe una comuna, sector o lugar público entre 3 y 150 caracteres.')
    policy = MatchingPolicy.objects.filter(pk=1).first()
    if not policy or not policy.geocoding_enabled or not policy.geocoding_policy_accepted_at:
        raise ProviderUnavailable('La búsqueda externa está desactivada. Marca el mapa o introduce coordenadas; administración puede habilitarla tras aceptar las condiciones.')
    query = ' '.join(request.data['query'].split())
    endpoint = settings.GEOCODING_URL
    if urlsplit(endpoint).scheme != 'https' or not urlsplit(endpoint).hostname:
        raise ProviderUnavailable()
    key = hashlib.sha256((endpoint+'|cl|'+query.casefold()).encode()).hexdigest()
    cached = GeocodingResult.objects.filter(pk=key, expires_at__gt=timezone.now()).first()
    if cached:
        return Response({'results': cached.results, 'cached': True, 'attribution': '© OpenStreetMap contributors'})
    if limited(request._request, 'place-search', 20):
        raise SearchBusy()
    with transaction.atomic():
        gate = GeocodingGate.objects.select_for_update().get(pk=1)
        now = timezone.now()
        if gate.next_request_at > now:
            raise SearchBusy()
        gate.next_request_at = now + timedelta(seconds=1.1)
        gate.save(update_fields=['next_request_at'])
    url = endpoint+'?'+urlencode({'q':query, 'format':'jsonv2', 'limit':3, 'countrycodes':'cl'})
    try:
        upstream = Request(url, headers={'User-Agent': settings.GEOCODING_USER_AGENT, 'Referer': settings.PUBLIC_APP_URL})
        with urlopen(upstream, timeout=4) as response:
            raw = response.read(65537)
        if len(raw) > 65536:
            raise ValueError()
        payload = json.loads(raw)
        if not isinstance(payload, list):
            raise ValueError()
        results = []
        for row in payload[:3]:
            lat, lon = point(row.get('lat'), row.get('lon'))
            if lat is not None:
                results.append({'latitude': float(lat), 'longitude': float(lon), 'label': str(row.get('display_name', 'Lugar'))[:250]})
    except Exception:
        raise ProviderUnavailable()
    GeocodingResult.objects.update_or_create(pk=key, defaults={'results':results, 'expires_at':timezone.now()+timedelta(days=7)})
    return Response({'results':results, 'cached':False, 'attribution':'© OpenStreetMap contributors'})
