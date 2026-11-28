from datetime import timedelta

from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.utils import timezone

from activities.participation import eligibility
from activities.test_participation import authenticate_operator, available, event_fixture
from volunteers.models import Skill, VolunteerSkill
from volunteers.tests import make_profile
from .models import VolunteerDocument


@override_settings(DEBUG=True)
class SafeguardingTests(TestCase):
    def setUp(self):
        self.profile = make_profile('resguardo@example.org')
        reviewer = make_profile('revisor@example.org').user
        reviewer.user_permissions.add(Permission.objects.get(codename='review_volunteerdocument'))
        authenticate_operator(self.client, reviewer)
        self.event, self.position = event_fixture()
        available(self.profile, self.event)
        self.skill, _ = Skill.objects.get_or_create(name='Apoyo escolar')
        self.position.required_skills.add(self.skill)
        VolunteerSkill.objects.create(profile=self.profile, skill=self.skill)
        self.documents = [VolunteerDocument.objects.create(profile=self.profile, document_type=kind,
            version=1, storage_key=f'test-only-{kind.pk}', checksum='a'*64, size=10,
            mime_type='application/pdf', scan_status='clean') for kind in self.skill.required_documents.all()]

    def test_explicit_review_required_and_matching_checks_both_certificates(self):
        self.assertTrue(eligibility(self.profile, self.position))
        for document in self.documents:
            data = {'decision': 'validated', 'expires_on': str(timezone.localdate() + timedelta(days=90)),
                    'observation': 'Revisión de resguardo realizada.'}
            url = f'/api/documents/{document.pk}/review/'
            self.assertEqual(self.client.post(url, data, content_type='application/json').status_code, 400)
            data['safeguarding_confirmed'] = True
            self.assertEqual(self.client.post(url, data, content_type='application/json').status_code, 200)
            document.refresh_from_db()
            self.assertTrue(document.safeguarding_confirmed)
            self.assertIsNotNone(document.reviewed_at)
            self.assertIsNotNone(document.reviewer_id)
        self.assertEqual(eligibility(self.profile, self.position), [])
        VolunteerDocument.objects.filter(pk=self.documents[0].pk).update(expires_on=timezone.localdate()-timedelta(days=1))
        self.assertTrue(eligibility(self.profile, self.position))

    def test_old_approval_without_safeguarding_is_pending_again(self):
        document = self.documents[0]
        document.status = 'validated'
        document.save(update_fields=['status'])
        self.assertEqual(document.effective_status, 'pending')
        ids = {item['id'] for item in self.client.get('/api/documents/review-queue/').json()['results']}
        self.assertIn(str(document.pk), ids)
        self.assertTrue(eligibility(self.profile, self.position))
