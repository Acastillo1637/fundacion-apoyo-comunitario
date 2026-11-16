import re
import tempfile
from datetime import timedelta
from pathlib import Path

from django.contrib.auth.models import Permission
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from accounts.models import AuditEvent, User, VolunteerProfile
from documents.tests import image_file
from volunteers.models import DocumentType, Skill, VolunteerSkill
from volunteers.tests import make_profile
from .models import ContactChange, ContactInvitation, Event, Participation
from .test_participation import authenticate_operator, available, event_fixture


@override_settings(DEBUG=True, DOCUMENT_SCAN_REQUIRED=False, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class Pro12EndToEndApiTests(TestCase):
    """Real middleware/API/file flow on an isolated database, not a browser test."""
    def setUp(self):
        self.storage = tempfile.TemporaryDirectory()
        self.addCleanup(self.storage.cleanup)
        self.settings_override = override_settings(PRIVATE_DOCUMENT_ROOT=Path(self.storage.name))
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.operator = User.objects.create_user('flow-coordinator@example.org')
        self.operator.user_permissions.add(Permission.objects.get(codename='manage_operations'), Permission.objects.get(codename='review_volunteerdocument'))
        self.staff = Client()
        authenticate_operator(self.staff, self.operator)
        self.source_event, self.source_position = event_fixture()
        self.skill = Skill.objects.create(name='Competencia del flujo')
        self.document_type = DocumentType.objects.create(name='Certificación del flujo')

    def json_request(self, client, method, path, payload, expected=200):
        response = getattr(client, method)('/api/'+path, payload, content_type='application/json')
        self.assertEqual(response.status_code,expected,response.content)
        return response.json()

    def test_registration_document_matching_contact_confirmation_and_replacement(self):
        password = 'Flow-only-test-password-58392!'
        self.json_request(self.client,'post','register/',{'email':'flow-volunteer@example.org','password':password,
            'first_name':'Camila','last_name':'Prueba','adult':True,'privacy':True,'whatsapp':False},201)
        self.assertEqual(len(mail.outbox),0)
        self.json_request(self.client,'post','login/',{'email':'flow-volunteer@example.org','password':password})
        profile = VolunteerProfile.objects.get(user__email='flow-volunteer@example.org')
        self.json_request(self.client,'put','volunteer/qualifications/',{'revision':0,'skills':[self.skill.pk],'professions':[]})
        start,end=timezone.localtime(self.source_event.starts_at),timezone.localtime(self.source_event.ends_at)
        self.json_request(self.client,'put','volunteer/availability/',{'revision':0,'slots':[{'weekday':start.weekday(),'start_time':start.strftime('%H:%M'),'end_time':end.strftime('%H:%M')}],'unavailable_dates':[]})
        self.json_request(self.client,'put','volunteer/location/',{'revision':0,'latitude':-33.45,'longitude':-70.66,'commune':'Santiago','sector':'Centro'})
        upload = self.client.post('/api/documents/',{'document_type':self.document_type.pk,'file':image_file()})
        self.assertEqual(upload.status_code,201,upload.content)
        document_id=upload.json()['id']
        self.json_request(self.staff,'post',f'documents/{document_id}/review/',{'decision':'validated','expires_on':str(end.date()+timedelta(days=1))})
        event=self.json_request(self.staff,'post',f'activities/operations/requests/{self.source_event.request_id}/events/',{
            'title':'Actividad integral del flujo','public_description':'Actividad de prueba completa para coordinación de voluntariado.',
            'date':str(start.date()),'start_time':start.strftime('%H:%M'),'end_time':end.strftime('%H:%M'),
            'address':'Plaza pública de prueba','commune':'Santiago','internal_notes':'Datos ficticios de prueba',
            'latitude':-33.45,'longitude':-70.66,'is_remote':False,
            'positions':[{'name':'Apoyo acreditado','capacity':1,'required_skills':[self.skill.pk],'desired_skills':[self.skill.pk],'required_documents':[self.document_type.pk]}]},201)
        event=self.json_request(self.staff,'post',f'activities/operations/events/{event["id"]}/transition/',{'revision':event['revision'],'status':'open','reason':''})
        position_id=event['positions'][0]['id']
        self.assertEqual(float(event['location']['latitude']),-33.45)
        url=f'activities/operations/events/{event["id"]}/positions/{position_id}/candidates/?eligible_only=1'
        ranking=self.staff.get('/api/'+url).json()
        self.assertEqual(ranking['results'][0]['id'],profile.pk)
        self.assertEqual(ranking['results'][0]['distance_km'],0)
        self.assertIsNotNone(ranking['results'][0]['location'])
        self.json_request(self.client,'put','volunteer/contact-preferences/',{'revision':0,'phone':'+56912345678','whatsapp':True})
        contact=self.json_request(self.staff,'post',f'activities/operations/events/{event["id"]}/contacts/',{'profile_id':profile.pk,'position_id':position_id},201)
        def contact_action(item,action):
            return self.json_request(self.staff,'post',f'activities/operations/contacts/{item["id"]}/action/',{'action':action,'revision':item['revision'],'note':'Respuesta ficticia registrada para la prueba integral'})
        contact=contact_action(contact,'start')
        self.assertTrue(contact['whatsapp_url'].startswith('https://wa.me/'))
        self.assertEqual(contact['status'],'contact_started')
        contact=contact_action(contact,'sent')
        contact=contact_action(contact,'accepted')
        self.assertFalse(Participation.objects.filter(event_id=event['id'],profile=profile).exists())
        contact=contact_action(contact,'confirm')
        participation=Participation.objects.get(event_id=event['id'],profile=profile)
        self.assertEqual(participation.status,'confirmed')
        self.json_request(self.client,'post',f'activities/participations/{participation.pk}/decision/',{'revision':participation.revision,'action':'withdraw'})
        replacement=make_profile('flow-replacement@example.org')
        VolunteerSkill.objects.create(profile=replacement,skill=self.skill)
        current=Event.objects.get(pk=event['id'])
        available(replacement,current)
        replacement_client=Client(); replacement_client.force_login(replacement.user)
        upload=replacement_client.post('/api/documents/',{'document_type':self.document_type.pk,'file':image_file()})
        self.assertEqual(upload.status_code,201,upload.content)
        self.json_request(self.staff,'post',f'documents/{upload.json()["id"]}/review/',{'decision':'validated','expires_on':str(end.date()+timedelta(days=1))})
        candidates=self.staff.get('/api/'+url).json()['results']
        self.assertIn(replacement.pk,[row['id'] for row in candidates])
        invitation=self.json_request(self.staff,'post',f'activities/operations/events/{event["id"]}/participants/',{'profile_id':replacement.pk,'position_id':position_id},201)
        self.json_request(replacement_client,'post',f'activities/participations/{invitation["id"]}/decision/',{'revision':invitation['revision'],'action':'accept'})
        self.assertEqual(Participation.objects.filter(event_id=event['id'],status='confirmed').count(),1)
        participation.refresh_from_db()
        self.assertEqual(participation.status,'cancelled')
        self.assertTrue(AuditEvent.objects.filter(action='contact.confirm').exists())
        self.assertTrue(ContactChange.objects.filter(contact_id=contact['id'],action='confirm').exists())
