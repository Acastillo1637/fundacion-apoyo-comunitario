from io import BytesIO, StringIO
from pathlib import Path
import tempfile

from django.core.management import call_command
from django.test import TestCase, override_settings
from pypdf import PdfReader

from accounts.models import User, VolunteerProfile
from activities.models import Event, Participation
from activities.participation import eligibility
from documents.models import VolunteerDocument
from documents.storage import private_storage


class MatchingDemoTests(TestCase):
    def test_complete_additive_idempotent_scenario_without_external_contacts(self):
        with tempfile.TemporaryDirectory() as folder, override_settings(DEBUG=True,
                BASE_DIR=Path(folder)/'backend', PRIVATE_DOCUMENT_ROOT=Path(folder)/'documents'):
            call_command('setup_roles',stdout=StringIO())
            call_command('seed_matching_demo',stdout=StringIO())
            self.assertEqual(User.objects.count(),0)
            call_command('seed_matching_demo',apply=True,stdout=StringIO())
            event=Event.objects.get(); position=event.positions.get()
            for profile in VolunteerProfile.objects.all():
                self.assertEqual(eligibility(profile,position),[])
                self.assertIsNone(profile.whatsapp_opt_in_at)
                self.assertFalse(profile.phone)
                document=VolunteerDocument.objects.get(profile=profile)
                with private_storage().open(document.storage_key,'rb') as file:
                    self.assertIn('DOCUMENTO FICTICIO SIN VALIDEZ',PdfReader(BytesIO(file.read())).pages[0].extract_text())
            call_command('seed_matching_demo',apply=True,stdout=StringIO())
            self.assertEqual(User.objects.count(),3)
            self.assertEqual(Event.objects.count(),1)
            self.assertEqual(VolunteerDocument.objects.count(),3)
            self.assertFalse(Participation.objects.exists())
