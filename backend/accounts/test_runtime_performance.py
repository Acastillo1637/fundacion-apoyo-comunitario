from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser, Group, Permission
from django.core.cache import cache
from django.db import connection, connections
from django.test import RequestFactory, TestCase, TransactionTestCase
from django.utils import timezone

from activities.models import Participation
from activities.test_participation import available, event_fixture
from documents.models import VolunteerDocument
from volunteers.models import DocumentType, Skill, VolunteerSkill
from volunteers.tests import make_profile
from .backends import OptimizedModelBackend
from .models import RateBucket, User
from .views import limited


class PermissionQueryTests(TestCase):
    def test_direct_and_group_permissions_share_one_query(self):
        user = User.objects.create_user('permission-performance@example.org')
        direct = Permission.objects.get(codename='manage_accounts')
        grouped = Permission.objects.get(codename='manage_operations')
        group = Group.objects.create(name='Performance group')
        group.permissions.add(grouped)
        user.groups.add(group)
        user.user_permissions.add(direct)
        with self.assertNumQueries(1):
            self.assertEqual(OptimizedModelBackend().get_all_permissions(user),
                             {'accounts.manage_accounts', 'activities.manage_operations'})
        user.user_permissions.clear()
        user.groups.clear()
        self.assertEqual(OptimizedModelBackend().get_all_permissions(User.objects.get(pk=user.pk)), set())

    def test_disabled_anonymous_and_object_checks_stay_denied(self):
        user = User.objects.create_user('inactive-performance@example.org', is_active=False)
        user.user_permissions.add(Permission.objects.get(codename='manage_accounts'))
        backend = OptimizedModelBackend()
        with self.assertNumQueries(0):
            self.assertEqual(backend.get_all_permissions(user), set())
            self.assertEqual(backend.get_all_permissions(AnonymousUser()), set())
            user.is_active = True
            self.assertEqual(backend.get_all_permissions(user, obj=object()), set())


class RateLimitQueryTests(TestCase):
    def test_atomic_counter_preserves_limit_in_one_query(self):
        cache.set('rate-bucket-cleanup', True, timeout=900)
        request = RequestFactory().get('/', REMOTE_ADDR='192.0.2.42')
        for expected in [False, False, True]:
            with self.assertNumQueries(1):
                self.assertEqual(limited(request, 'performance', 2), expected)
        self.assertEqual(RateBucket.objects.get().count, 3)

    def test_windows_and_scopes_have_independent_counters(self):
        request = RequestFactory().get('/', REMOTE_ADDR='192.0.2.43')
        self.assertFalse(limited(request, 'first', 1))
        self.assertTrue(limited(request, 'first', 1))
        self.assertFalse(limited(request, 'second', 1))
        future = timezone.now() + timedelta(minutes=16)
        with patch('accounts.views.timezone.now', return_value=future):
            self.assertFalse(limited(request, 'first', 1))


@skipUnless(connection.vendor == 'postgresql', 'Requiere concurrencia PostgreSQL')
class RateLimitConcurrencyTests(TransactionTestCase):
    def test_simultaneous_requests_cannot_lose_increments(self):
        cache.set('rate-bucket-cleanup', True, timeout=900)
        barrier = Barrier(6)
        def worker(_):
            try:
                request = RequestFactory().get('/', REMOTE_ADDR='192.0.2.44')
                barrier.wait(timeout=10)
                return limited(request, 'concurrent-performance', 3)
            finally:
                connections['default'].close()
        with patch('accounts.views.timezone.now', return_value=timezone.now()):
            with ThreadPoolExecutor(max_workers=6) as pool:
                results = list(pool.map(worker, range(6)))
        self.assertEqual(sum(results), 3)
        self.assertEqual(RateBucket.objects.get().count, 6)


class VolunteerOverviewTests(TestCase):
    def setUp(self):
        self.profile = make_profile('overview-owner@example.org')
        self.other = make_profile('overview-other@example.org')
        self.client.force_login(self.profile.user)

    def test_overview_contains_only_own_data_and_latest_document_version(self):
        skill = Skill.objects.create(name='Habilidad propia')
        other_skill = Skill.objects.create(name='Habilidad ajena')
        VolunteerSkill.objects.create(profile=self.profile, skill=skill)
        VolunteerSkill.objects.create(profile=self.other, skill=other_skill)
        document_type = DocumentType.objects.create(name='Documento')
        for profile, version in [(self.profile, 1), (self.profile, 2), (self.other, 1)]:
            VolunteerDocument.objects.create(profile=profile, document_type=document_type, version=version,
                storage_key=f'overview-{profile.pk}-{version}', size=10, mime_type='application/pdf',
                checksum='a' * 64, scan_status='not_scanned')
        event, position = event_fixture()
        available(self.profile, event)
        Participation.objects.create(profile=self.profile, event=event, position=position)
        result = self.client.get('/api/volunteer-overview/').json()
        self.assertEqual(result['qualifications']['skills'], [{'id': skill.pk, 'name': skill.name}])
        self.assertEqual([row['version'] for row in result['documents']['documents']], [2])
        self.assertEqual(result['participations']['total'], 1)
        self.assertEqual(len(result['availability']['slots']), 1)

    def test_non_volunteer_cannot_use_overview(self):
        user = User.objects.create_user('overview-no-role@example.org')
        self.client.force_login(user)
        self.assertEqual(self.client.get('/api/volunteer-overview/').status_code, 403)

    def test_empty_overview_has_zero_totals_and_own_restriction(self):
        self.profile.is_restricted = True
        self.profile.restriction_reason = 'Motivo de prueba propio'
        self.profile.save(update_fields=['is_restricted', 'restriction_reason'])
        result = self.client.get('/api/volunteer-overview/').json()
        self.assertEqual(result['participations'], {'results': [], 'total': 0})
        self.assertTrue(result['participationStatus']['restricted'])
        self.assertEqual(result['participationStatus']['reason'], 'Motivo de prueba propio')
