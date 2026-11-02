from django.test import TestCase
from django.db import connection
from django.test.utils import CaptureQueriesContext

from accounts.models import VolunteerProfile
from volunteers.tests import make_profile
from volunteers.models import UnavailableDate, Skill
from django.utils import timezone
from .participation import eligibility, prepare_eligibility
from .test_participation import event_fixture, available


class MatchingPerformanceTests(TestCase):
    def setUp(self):
        self.event, self.position = event_fixture()
        self.profile = make_profile('matching@example.org')
        available(self.profile, self.event)

    def test_prepared_matching_preserves_reasons_without_per_person_queries(self):
        skill = Skill.objects.create(name='Habilidad necesaria')
        self.position.required_skills.add(skill)
        UnavailableDate.objects.create(profile=self.profile, date=timezone.localtime(self.event.starts_at).date())
        expected = eligibility(self.profile, self.position)
        prepare_eligibility([self.profile], [self.position])
        with self.assertNumQueries(0):
            self.assertEqual(eligibility(self.profile, self.position, prepared=True), expected)
        self.assertIn('Faltan habilidades requeridas', expected)
        self.assertIn('Fuera de la disponibilidad declarada', expected)

    def test_query_count_does_not_grow_with_candidate_count(self):
        def measure():
            profiles = list(VolunteerProfile.objects.select_related('user'))
            from .models import EventPosition
            position = EventPosition.objects.select_related('event').get(pk=self.position.pk)
            with CaptureQueriesContext(connection) as queries:
                prepare_eligibility(profiles, [position])
                for profile in profiles:
                    eligibility(profile, position, prepared=True)
            return len(queries)
        single = measure()
        for index in range(8):
            make_profile(f'matching-{index}@example.org')
        self.assertEqual(measure(), single)
