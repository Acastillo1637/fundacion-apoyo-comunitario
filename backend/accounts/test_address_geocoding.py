import io
import json
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from activities.models import GeocodingGate, GeocodingResult
from volunteers.tests import make_profile
from .models import AuditEvent, User


@override_settings(GEOAPIFY_API_KEY='private-test-key')
class AddressGeocodingTests(TestCase):
    def setUp(self):
        self.profile = make_profile('geocode@example.org')
        self.profile.reference_latitude = '-33.40'
        self.profile.reference_longitude = '-70.60'
        self.profile.save()
        self.client.force_login(self.profile.user)
        self.body = {'address': 'Calle ficticia 123', 'commune': 'Santiago', 'sector': '',
                     'consent': True, 'revision': 0}
        GeocodingGate.objects.update_or_create(pk=1, defaults={'next_request_at': timezone.now()})

    def post(self, **changes):
        return self.client.post('/api/volunteer/location/address/', {**self.body, **changes}, content_type='application/json')

    def provider(self, confidence=1, result_type='building'):
        return io.BytesIO(json.dumps({'results': [{'lat': -33.45678, 'lon': -70.65432,
            'country_code': 'cl', 'result_type': result_type, 'formatted': 'Calle ficticia 123, Santiago',
            'city': 'Santiago', 'rank': {'confidence': confidence, 'match_type': 'full_match'}}]}).encode())

    @patch('accounts.address_geocoding.urlopen')
    def test_automatic_rounding_private_cache_and_audit(self, upstream):
        upstream.return_value = self.provider()
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertTrue(response.json()['saved'])
        self.profile.refresh_from_db()
        self.assertEqual(str(self.profile.reference_latitude), '-33.46')
        self.assertEqual(str(self.profile.reference_longitude), '-70.65')
        self.assertEqual(self.profile.location_revision, 1)
        for text in (response.content.decode(), json.dumps(GeocodingResult.objects.get().results),
                     str(list(AuditEvent.objects.values()))):
            self.assertNotIn('Calle ficticia', text)
            self.assertNotIn('private-test-key', text)
            self.assertNotIn('-33.45678', text)

    @patch('accounts.address_geocoding.urlopen')
    def test_ambiguity_requires_bound_confirmation_and_reuses_cache(self, upstream):
        upstream.return_value = self.provider(.7, 'street')
        result = self.post().json()
        self.assertFalse(result['saved'])
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.location_revision, 0)
        self.assertEqual(str(self.profile.reference_latitude), '-33.40')
        self.post()
        self.assertEqual(upstream.call_count, 1)
        token = result['choices'][0]['token']
        self.assertEqual(self.post(choice=token, address='Otra calle 456').status_code, 400)
        other = make_profile('geocode-other@example.org')
        self.client.force_login(other.user)
        self.assertEqual(self.post(choice=token).status_code, 400)
        self.client.force_login(self.profile.user)
        self.assertTrue(self.post(choice=token).json()['saved'])
        self.assertEqual(self.post(choice=token).status_code, 409)

    @patch('accounts.address_geocoding.urlopen')
    def test_consent_permissions_unknown_fields_and_stale_revision(self, upstream):
        self.assertEqual(self.post(consent=False).status_code, 400)
        self.assertEqual(self.post(user_id='other').status_code, 400)
        self.assertEqual(self.post(revision=1).status_code, 409)
        self.client.force_login(User.objects.create_user('not-volunteer@example.org'))
        self.assertEqual(self.post().status_code, 403)
        upstream.assert_not_called()

    @patch('accounts.address_geocoding.urlopen', side_effect=OSError('private-test-key Calle ficticia'))
    def test_provider_error_preserves_previous_location(self, upstream):
        response = self.post()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private-test-key', response.content.decode())
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.location_revision, 0)
        self.assertEqual(str(self.profile.reference_latitude), '-33.40')

    @override_settings(GEOAPIFY_API_KEY='')
    @patch('accounts.address_geocoding.urlopen')
    def test_missing_key_and_consent_never_contact_provider(self, upstream):
        self.assertEqual(self.post().status_code, 503)
        self.assertFalse(self.client.get('/api/volunteer/location/').json()['address_geocoding_enabled'])
        upstream.assert_not_called()

    @patch('accounts.address_geocoding.urlopen')
    def test_empty_or_invalid_provider_results_do_not_save(self, upstream):
        for raw in [b'{"results": []}', b'{"results": [{"lat": 91, "lon": 0, "country_code":"cl"}]}', b'no-json']:
            GeocodingResult.objects.all().delete()
            GeocodingGate.objects.filter(pk=1).update(next_request_at=timezone.now())
            upstream.return_value = io.BytesIO(raw)
            self.assertIn(self.post().status_code, [400, 503])
            self.profile.refresh_from_db()
            self.assertEqual(self.profile.location_revision, 0)

    @patch('accounts.address_geocoding.urlopen')
    def test_revision_changed_during_lookup_is_not_overwritten(self, upstream):
        def provider(*args, **kwargs):
            type(self.profile).objects.filter(pk=self.profile.pk).update(location_revision=1)
            return self.provider()
        upstream.side_effect = provider
        self.assertEqual(self.post().status_code, 409)
        self.profile.refresh_from_db()
        self.assertEqual(str(self.profile.reference_latitude), '-33.40')
