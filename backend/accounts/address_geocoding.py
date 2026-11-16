"""Consent-based home geocoding; addresses and precise results are never persisted."""
import json
import math
from datetime import timedelta
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core import signing
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.views.decorators.cache import never_cache
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from activities.models import GeocodingGate, GeocodingResult
from activities.services import Conflict
from volunteers.serializers import StrictSerializer
from .geography import ProviderUnavailable, SearchBusy, location_data, point
from .models import AuditEvent, VolunteerProfile
from .portals import is_volunteer
from .views import limited

SALT = 'private-address-choice-v1'


class AddressSerializer(StrictSerializer):
    address = serializers.CharField(min_length=5, max_length=250)
    commune = serializers.CharField(min_length=2, max_length=80)
    sector = serializers.CharField(max_length=80, allow_blank=True)
    consent = serializers.BooleanField()
    revision = serializers.IntegerField(min_value=0)
    choice = serializers.CharField(max_length=2000, required=False)


def lookup(request, values, fingerprint):
    cached = GeocodingResult.objects.filter(pk=fingerprint, expires_at__gt=timezone.now()).first()
    if cached:
        return cached.results
    if limited(request._request, 'home-geocode-user', 10, identity=str(request.user.pk)) or limited(request._request, 'home-geocode-ip', 20):
        raise SearchBusy()
    if limited(request._request, 'home-geocode-budget', 20, identity='shared-provider'):
        raise SearchBusy('Se alcanzó el límite compartido de búsquedas de este intervalo. Inténtalo en 15 minutos.')
    with transaction.atomic():
        gate = GeocodingGate.objects.select_for_update().get(pk=1)
        now = timezone.now()
        if gate.next_request_at > now:
            raise SearchBusy()
        gate.next_request_at = now + timedelta(seconds=1.1)
        gate.save(update_fields=['next_request_at'])
    query = urlencode({'text': f"{values['address']}, {values['commune']}, Chile",
                       'filter': 'countrycode:cl', 'limit': 3, 'format': 'json',
                       'apiKey': settings.GEOAPIFY_API_KEY})
    try:
        upstream = Request('https://api.geoapify.com/v1/geocode/search?' + query,
                           headers={'User-Agent': settings.GEOCODING_USER_AGENT})
        with urlopen(upstream, timeout=5) as response:
            raw = response.read(65537)
        if len(raw) > 65536:
            raise ValueError()
        payload = json.loads(raw)
        if not isinstance(payload, dict) or not isinstance(payload.get('results'), list):
            raise ValueError()
        results = []
        for row in payload['results'][:3]:
            if row.get('country_code', '').lower() != 'cl':
                continue
            lat, lon = point(row.get('lat'), row.get('lon'), approximate=True)
            if lat is None:
                continue
            rank = row.get('rank') or {}
            confidence = float(rank.get('confidence', 0))
            if not math.isfinite(confidence):
                continue
            # No street, number or upstream formatted address retained, even in cache.
            label = ', '.join(dict.fromkeys(str(row[k])[:80] for k in ('suburb', 'city', 'county') if row.get(k))) or 'Referencia aproximada en Chile'
            results.append({'latitude': float(lat), 'longitude': float(lon), 'label': label,
                            'exact_match': row.get('result_type') == 'building' and
                            rank.get('match_type') == 'full_match' and confidence >= .95})
    except Exception:
        # Never include upstream URLs, API keys or submitted addresses in errors.
        raise ProviderUnavailable('No se pudo calcular la ubicación. Conservamos tu referencia anterior; inténtalo más tarde.') from None
    GeocodingResult.objects.update_or_create(pk=fingerprint, defaults={
        'results': results, 'expires_at': timezone.now() + timedelta(hours=24)})
    return results


@never_cache
@api_view(['POST'])
def resolve_address(request):
    if not is_volunteer(request.user):
        raise PermissionDenied('Solo puedes calcular tu propia ubicación de voluntario.')
    serializer = AddressSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    values = serializer.validated_data
    if not values['consent']:
        raise ValidationError('Debes autorizar el envío de la dirección a Geoapify para calcularla.')
    if not settings.GEOAPIFY_API_KEY:
        raise ProviderUnavailable('El cálculo por dirección todavía no está configurado.')
    profile = get_object_or_404(VolunteerProfile, user=request.user)
    if profile.location_revision != values['revision']:
        raise Conflict()
    normalized = '|'.join(' '.join(values[k].split()).casefold() for k in ('address', 'commune'))
    fingerprint = salted_hmac('home-geocoding-cache-v1', f'{request.user.pk}|{normalized}', algorithm='sha256').hexdigest()
    if values.get('choice'):
        try:
            selected = signing.loads(values['choice'], salt=SALT, max_age=600)
            if selected['owner'] != str(request.user.pk) or selected['fingerprint'] != fingerprint or selected['revision'] != values['revision']:
                raise ValueError()
            lat, lon = point(selected['latitude'], selected['longitude'], approximate=True)
        except (signing.BadSignature, ValueError, KeyError, TypeError):
            raise ValidationError('La opción venció o no corresponde a esta dirección. Busca nuevamente.') from None
    else:
        results = lookup(request, values, fingerprint)
        if not results:
            raise ValidationError('No encontramos esa dirección en Chile. Revisa la calle, número y comuna o usa una referencia manual.')
        if len(results) != 1 or not results[0]['exact_match']:
            choices = []
            for row in results:
                token = signing.dumps({'owner': str(request.user.pk), 'fingerprint': fingerprint,
                                       'revision': values['revision'], 'latitude': row['latitude'],
                                       'longitude': row['longitude']}, salt=SALT)
                choices.append({'label': row['label'], 'latitude': row['latitude'],
                                'longitude': row['longitude'], 'token': token})
            return Response({'saved': False, 'choices': choices})
        lat, lon = point(results[0]['latitude'], results[0]['longitude'], approximate=True)
    with transaction.atomic():
        profile = get_object_or_404(VolunteerProfile.objects.select_for_update(), user=request.user)
        if profile.location_revision != values['revision']:
            raise Conflict()
        profile.reference_latitude, profile.reference_longitude = lat, lon
        profile.commune, profile.sector = values['commune'], values['sector']
        profile.location_revision += 1
        profile.save(update_fields=['reference_latitude', 'reference_longitude', 'commune', 'sector', 'location_revision'])
        AuditEvent.objects.create(actor=request.user, action='profile.location.geoapify_consent_v1', resource=f'profile:{profile.pk}')
    return Response({'saved': True, 'location': location_data(profile)})
