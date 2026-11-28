from io import StringIO
from uuid import NAMESPACE_URL, uuid5

from django.core.management import call_command
from django.test import TestCase

from activities.models import Event
from activities.test_participation import event_fixture
from volunteers.models import DocumentType, Skill
from volunteers.tests import make_profile
from .models import AuditEvent, User


class ArchiveDemoTests(TestCase):
    def test_archive_is_explicit_repeat_safe_and_preserves_users_and_history(self):
        person = make_profile('cuenta-conservada@example.org')
        synthetic = Skill.objects.create(name='DEMO — Preparación de kits')
        real = Skill.objects.create(name='Demografía comunitaria')
        document = DocumentType.objects.create(name='DEMO — Constancia de inducción (sin validez)')
        source_event, _ = event_fixture()
        batch = 'matching-map-demo-v1'
        synthetic_event = Event.objects.create(id=uuid5(NAMESPACE_URL, f'fundacion:{batch}:event'),
            request=source_event.request, title='DEMO — Actividad sintética', status='open',
            starts_at=source_event.starts_at, ends_at=source_event.ends_at, address='Referencia', commune='Santiago')
        AuditEvent.objects.create(action='demo.seed.completed', resource=batch)
        call_command('archive_demo_catalogs', stdout=StringIO())
        self.assertTrue(Skill.objects.get(pk=synthetic.pk).is_active)
        for _ in range(2):
            call_command('archive_demo_catalogs', apply=True, stdout=StringIO())
        self.assertFalse(Skill.objects.get(pk=synthetic.pk).is_active)
        self.assertFalse(DocumentType.objects.get(pk=document.pk).is_active)
        self.assertTrue(Skill.objects.get(pk=real.pk).is_active)
        self.assertTrue(User.objects.filter(pk=person.user_id).exists())
        self.assertEqual(Event.objects.get(pk=synthetic_event.pk).status, 'cancelled')
        self.assertEqual(Event.objects.get(pk=source_event.pk).status, 'open')
        self.assertEqual(AuditEvent.objects.filter(action='catalog.demo.archived').count(), 1)
