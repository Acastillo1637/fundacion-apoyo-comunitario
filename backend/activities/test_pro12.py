import io
import json
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core import mail
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.geography import distance_km, point
from accounts.models import AuditEvent, User
from documents.models import VolunteerDocument
from documents.tests import image_file
from volunteers.models import AvailabilitySlot, DocumentType, Skill, VolunteerSkill
from volunteers.tests import make_profile
from .contacts import normalize_phone
from .models import ContactChange, ContactInvitation, GeocodingGate, GeocodingResult, MatchingPolicy, MatchingPolicyChange, Participation
from .test_participation import authenticate_operator, available, event_fixture


class GeographyMathTests(SimpleTestCase):
    def test_haversine_known_distances(self):
        self.assertEqual(distance_km(-33, -70, -33, -70), 0)
        self.assertAlmostEqual(distance_km(0, 0, 1, 0), 111.195, places=2)
        self.assertAlmostEqual(distance_km(0, 179, 0, -179), 222.390, places=2)
        self.assertAlmostEqual(distance_km(0, 0, 0, 180), 20015.114, places=2)

    def test_invalid_and_missing_coordinates(self):
        self.assertIsNone(distance_km(None, None, 0, 0))
        for lat, lon in [(91, 0), (0, 181), (float('nan'), 0), (0, float('inf')), (None, 0)]:
            with self.subTest(lat=lat, lon=lon), self.assertRaises(ValidationError):
                point(lat, lon)

    def test_reference_is_rounded_not_exact(self):
        lat, lon = point(-33.456789, -70.654321, approximate=True)
        self.assertEqual((str(lat), str(lon)), ('-33.46', '-70.65'))

    def test_phone_normalization(self):
        self.assertEqual(normalize_phone('+56 9 1234 5678'), '56912345678')
        self.assertEqual(normalize_phone('9 1234 5678'), '56912345678')
        self.assertEqual(normalize_phone('0056 9 1234 5678'), '56912345678')
        for raw in ['++56912345678', 'abc', '123', '+00 123456789', '+56;alert(1)']:
            with self.subTest(raw=raw), self.assertRaises(ValidationError):
                normalize_phone(raw)


@override_settings(DEBUG=True, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class Pro12ApiTests(TestCase):
    def setUp(self):
        self.owner = make_profile('pro12-volunteer@example.org')
        self.other = make_profile('pro12-other@example.org')
        self.operator = User.objects.create_user('pro12-operator@example.org')
        self.operator.user_permissions.add(Permission.objects.get(codename='manage_operations'),
            Permission.objects.get(codename='manage_accounts'), Permission.objects.get(codename='review_volunteerdocument'))
        self.staff = Client()
        authenticate_operator(self.staff, self.operator)
        self.client.force_login(self.owner.user)
        self.event, self.position = event_fixture()
        available(self.owner, self.event)
        available(self.other, self.event)
        self.event.latitude, self.event.longitude = '-33.450000', '-70.660000'
        self.event.save(update_fields=['latitude','longitude'])
        self.owner.reference_latitude, self.owner.reference_longitude = '-33.45', '-70.66'
        self.owner.phone, self.owner.whatsapp_opt_in_at = '+56 9 1234 5678', timezone.now()
        self.owner.save()
        self.policy = MatchingPolicy.objects.get(pk=1)

    def candidates(self, client=None, extra=''):
        return (client or self.staff).get(f'/api/activities/operations/events/{self.event.pk}/positions/{self.position.pk}/candidates/?{extra}')

    def contact(self, profile=None):
        response = self.staff.post(f'/api/activities/operations/events/{self.event.pk}/contacts/',
            {'profile_id':(profile or self.owner).pk,'position_id':self.position.pk}, content_type='application/json')
        self.assertIn(response.status_code, [200,201], response.content)
        return response.json()

    def action(self, contact, action, **changes):
        return self.staff.post(f'/api/activities/operations/contacts/{contact["id"]}/action/',
            {'revision':contact['revision'],'action':action,'note':'Referencia manual de prueba', **changes}, content_type='application/json')

    def test_location_is_own_only_rounded_and_versioned(self):
        payload = {'latitude':-33.456789,'longitude':-70.654321,'commune':'Santiago','sector':'Centro','revision':0}
        result = self.client.put('/api/volunteer/location/', payload, content_type='application/json')
        self.assertEqual(result.status_code, 200, result.content)
        self.owner.refresh_from_db()
        self.assertEqual(str(self.owner.reference_latitude), '-33.46')
        self.assertEqual(self.client.put('/api/volunteer/location/', payload, content_type='application/json').status_code, 409)
        self.assertEqual(self.client.put('/api/volunteer/location/', {**payload,'profile_id':self.other.pk}, content_type='application/json').status_code, 400)
        self.client.force_login(self.other.user)
        self.assertIsNone(self.client.get('/api/volunteer/location/').json()['latitude'])

    def test_invalid_coordinates_and_non_volunteer_are_rejected(self):
        self.assertEqual(self.client.put('/api/volunteer/location/', {'latitude':91,'longitude':0,'commune':'','sector':'','revision':0}, content_type='application/json').status_code, 400)
        self.client.force_login(self.operator)
        self.assertEqual(self.client.get('/api/volunteer/location/').status_code, 403)

    def test_public_events_never_expose_private_coordinates(self):
        response = Client().get('/api/activities/public-events/').json()
        row = response['results'][0]
        self.assertNotIn('location', row)
        self.assertNotIn('latitude', row)
        self.assertNotIn('address', row)
        self.assertEqual(self.candidates(self.client).status_code, 403)

    def test_event_location_changes_are_audited_and_reject_stale_revision(self):
        url = f'/api/activities/operations/events/{self.event.pk}/location/'
        values = {'latitude':-33.5,'longitude':-70.7,'is_remote':False,'address':'Plaza pública','commune':'Santiago','revision':0,'reason':'Cambio coordinado de lugar'}
        self.assertEqual(self.client.put(url, values, content_type='application/json').status_code, 403)
        self.assertEqual(self.staff.put(url, values, content_type='application/json').status_code, 200)
        self.assertEqual(self.staff.put(url, values, content_type='application/json').status_code, 409)
        self.assertIn('latitude', self.event.changes.get().fields_changed)

    def test_matching_ranks_distance_and_explains_missing_location(self):
        result = self.candidates().json()
        self.assertEqual(result['results'][0]['id'], self.owner.pk)
        self.assertEqual(result['results'][0]['distance_km'], 0)
        self.assertEqual(result['results'][1]['distance_km'], None)
        self.assertIsNotNone(result['results'][0]['score'])
        self.assertIn('línea recta', result['distance_notice'])

    def test_required_skills_gate_before_score(self):
        skill = Skill.objects.create(name='Competencia obligatoria')
        self.position.required_skills.add(skill)
        VolunteerSkill.objects.create(profile=self.owner, skill=skill)
        result = self.candidates(extra='eligible_only=1').json()
        self.assertEqual([row['id'] for row in result['results']], [self.owner.pk])
        all_rows = self.candidates().json()['results']
        other = next(row for row in all_rows if row['id'] == self.other.pk)
        self.assertFalse(other['eligible'])
        self.assertIsNone(other['score'])
        self.assertIsNone(other['location'])

    def test_desired_skills_change_score_but_do_not_exclude(self):
        skill = Skill.objects.create(name='Habilidad deseable')
        self.position.desired_skills.add(skill)
        VolunteerSkill.objects.create(profile=self.other, skill=skill)
        result = self.candidates().json()['results']
        self.assertEqual(result[0]['id'], self.other.pk)
        self.assertTrue(all(row['eligible'] for row in result))

    def test_ranking_is_global_before_pagination(self):
        desired = Skill.objects.create(name='Puntaje global')
        self.position.desired_skills.add(desired)
        self.policy.skills_weight, self.policy.experience_weight, self.policy.distance_weight = 100, 0, 0
        self.policy.save()
        for index in range(22):
            profile = make_profile(f'global-rank-{index}@example.org')
            available(profile, self.event)
        VolunteerSkill.objects.create(profile=profile, skill=desired)
        rows = self.candidates(extra='eligible_only=1').json()
        self.assertEqual(rows['results'][0]['id'], profile.pk)
        self.assertEqual(rows['results'][0]['score'],100)
        self.assertEqual(rows['total'],24)
        self.assertEqual(len(rows['results']),20)

    def test_document_valid_today_but_not_at_event_is_ineligible(self):
        document_type = DocumentType.objects.create(name='Certificación temporal')
        self.position.required_documents.add(document_type)
        VolunteerDocument.objects.create(profile=self.owner,document_type=document_type,version=1,
            storage_key='expiry-test',size=1,mime_type='application/pdf',checksum='a'*64,scan_status='clean',
            status='validated',expires_on=timezone.localdate()+timedelta(days=1))
        row = next(row for row in self.candidates().json()['results'] if row['id']==self.owner.pk)
        self.assertFalse(row['eligible'])
        self.assertIn('Falta documentación vigente para la fecha del evento',row['reasons'])

    def test_experience_uses_relevant_recorded_attendance(self):
        required = Skill.objects.create(name='Experiencia relevante')
        self.position.desired_skills.add(required)
        past, past_position = event_fixture()
        past.starts_at, past.ends_at = timezone.now()-timedelta(days=3), timezone.now()-timedelta(days=2)
        past.status='finished'; past.save()
        past_position.required_skills.add(required)
        Participation.objects.create(event=past,position=past_position,profile=self.owner,status='confirmed',attendance='present')
        self.policy.skills_weight,self.policy.experience_weight,self.policy.distance_weight=0,100,0
        self.policy.save()
        rows=self.candidates().json()['results']
        self.assertEqual(rows[0]['id'],self.owner.pk)
        self.assertEqual(rows[0]['score_components']['experience'],20)

    def test_remote_events_have_no_distance_or_reference_points(self):
        self.event.is_remote = True
        self.event.latitude = self.event.longitude = None
        self.event.save()
        rows = self.candidates().json()['results']
        self.assertTrue(all(row['distance_km'] is None and row['location'] is None for row in rows))
        self.assertEqual(rows[0]['score_components']['distance'], 25)

    def test_closed_event_cannot_recommend_eligible_volunteers(self):
        self.event.status = 'cancelled'
        self.event.save()
        self.assertEqual(self.candidates(extra='eligible_only=1').json()['total'], 0)

    def test_weights_require_admin_and_valid_total_and_audit(self):
        url = '/api/management/matching-policy/'
        values = {'skills_weight':70,'experience_weight':10,'distance_weight':20,'distance_limit_km':50,'experience_target':5,'geocoding_enabled':False,'revision':0,'reason':'Ajuste de criterios de prueba'}
        self.assertEqual(self.client.put(url,values,content_type='application/json').status_code,403)
        self.assertEqual(self.staff.put(url,{**values,'skills_weight':90},content_type='application/json').status_code,400)
        self.assertEqual(self.staff.put(url,values,content_type='application/json').status_code,200)
        self.assertTrue(MatchingPolicyChange.objects.filter(actor=self.operator, revision=1).exists())
        self.assertEqual(self.staff.put(url,values,content_type='application/json').status_code,409)

    def test_geocoding_needs_deliberate_enablement(self):
        self.assertEqual(self.client.post('/api/maps/search/',{'query':'Plaza de Maipú'},content_type='application/json').status_code,503)
        values = {'skills_weight':60,'experience_weight':15,'distance_weight':25,'distance_limit_km':50,'experience_target':5,'geocoding_enabled':True,'revision':0,'reason':'Habilitación para prueba controlada'}
        self.assertEqual(self.staff.put('/api/management/matching-policy/',values,content_type='application/json').status_code,400)

    def enable_geocoding(self):
        self.policy.geocoding_enabled = True
        self.policy.geocoding_policy_accepted_at = timezone.now()
        self.policy.save()

    def test_geocoding_cache_prevents_duplicate_upstream_requests(self):
        self.enable_geocoding()
        body = json.dumps([{'lat':'-33.51','lon':'-70.75','display_name':'Plaza pública'}]).encode()
        with patch('accounts.geography.urlopen') as upstream:
            upstream.return_value.__enter__.return_value.read.return_value = body
            first = self.client.post('/api/maps/search/',{'query':'Plaza de Maipú'},content_type='application/json')
            second = self.client.post('/api/maps/search/',{'query':'plaza DE maipú'},content_type='application/json')
        self.assertEqual(first.status_code,200,first.content)
        self.assertTrue(second.json()['cached'])
        self.assertEqual(upstream.call_count,1)

    def test_geocoding_limits_shared_gate_and_handles_failure(self):
        self.enable_geocoding()
        with patch('accounts.geography.urlopen', side_effect=TimeoutError()):
            self.assertEqual(self.client.post('/api/maps/search/',{'query':'Lugar público A'},content_type='application/json').status_code,503)
            self.assertEqual(self.client.post('/api/maps/search/',{'query':'Lugar público B'},content_type='application/json').status_code,429)
        self.assertEqual(GeocodingResult.objects.count(),0)

    def test_whatsapp_start_is_not_marked_sent(self):
        contact = self.contact()
        self.assertEqual(contact['status'],'pending_contact')
        response = self.action(contact,'start')
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(response.json()['status'],'contact_started')
        self.assertTrue(response.json()['whatsapp_url'].startswith('https://wa.me/56912345678?'))
        self.assertFalse(Participation.objects.exists())
        self.assertFalse(ContactChange.objects.filter(to_status='sent').exists())

    def test_withdrawing_consent_prevents_contact(self):
        contact = self.contact()
        response = self.client.put('/api/volunteer/contact-preferences/',{'phone':'+56912345678','whatsapp':False,'revision':0},content_type='application/json')
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(self.action(contact,'start').status_code,400)
        self.assertEqual(self.staff.post(f'/api/operations/volunteers/{self.owner.pk}/whatsapp/',{},content_type='application/json').status_code,400)

    def test_expired_contact_requires_audited_new_round(self):
        contact=self.contact()
        ContactInvitation.objects.filter(pk=contact['id']).update(expires_at=timezone.now()-timedelta(seconds=1))
        self.assertEqual(self.action(contact,'start').status_code,400)
        response=self.action(contact,'reopen')
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(self.action(response.json(),'start').status_code,200)
        self.assertTrue(ContactChange.objects.filter(contact_id=contact['id'],action='reopen').exists())

    def accepted(self, profile=None):
        contact = self.contact(profile)
        response = self.action(contact,'start')
        self.assertEqual(response.status_code,200,response.content)
        response = self.action(response.json(),'sent')
        self.assertEqual(response.status_code,200,response.content)
        response = self.action(response.json(),'accepted')
        self.assertEqual(response.status_code,200,response.content)
        return response.json()

    def test_manual_acceptance_does_not_confirm_until_explicit_check(self):
        contact = self.accepted()
        self.assertFalse(Participation.objects.exists())
        response = self.action(contact,'confirm')
        self.assertEqual(response.status_code,200,response.content)
        self.assertEqual(Participation.objects.get().status,'confirmed')
        self.assertEqual(response.json()['participation_status'],'confirmed')
        self.assertEqual(self.action(contact,'confirm').status_code,409)

    def test_manual_confirmation_rechecks_availability(self):
        contact = self.accepted()
        self.owner.availability_slots.all().delete()
        self.assertEqual(self.action(contact,'confirm').status_code,400)
        self.assertFalse(Participation.objects.exists())

    def test_manual_confirmation_honours_capacity(self):
        Participation.objects.create(event=self.event,position=self.position,profile=self.other,status='confirmed')
        contact = self.accepted()
        self.assertEqual(self.action(contact,'confirm').status_code,200)
        self.assertEqual(Participation.objects.get(profile=self.owner).status,'waitlisted')
        self.assertEqual(Participation.objects.filter(status='confirmed').count(),1)

    def test_contacts_are_not_visible_to_volunteers_and_cannot_forge_event_position(self):
        contact = self.contact()
        self.assertEqual(self.client.get(f'/api/activities/operations/events/{self.event.pk}/contacts/').status_code,403)
        self.assertEqual(self.client.post(f'/api/activities/operations/contacts/{contact["id"]}/action/',{'revision':0,'action':'start'},content_type='application/json').status_code,403)
        other_event, other_position = event_fixture()
        self.assertEqual(self.staff.post(f'/api/activities/operations/events/{self.event.pk}/contacts/',{'profile_id':self.owner.pk,'position_id':other_position.pk},content_type='application/json').status_code,404)
