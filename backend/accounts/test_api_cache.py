from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from .middleware import ApiCacheControlMiddleware


class ApiCacheControlTests(SimpleTestCase):
    def test_api_responses_and_errors_cannot_be_cached_or_shared_between_sessions(self):
        for status in [200, 400, 403, 404, 500]:
            with self.subTest(status=status):
                response = ApiCacheControlMiddleware(lambda request: HttpResponse(status=status))(
                    RequestFactory().get('/api/profile/'))
                for directive in ['private', 'no-store', 'no-cache', 'max-age=0', 'must-revalidate']:
                    self.assertIn(directive, response['Cache-Control'])
                self.assertIn('Cookie', response['Vary'])

    def test_static_assets_keep_their_existing_cache_policy(self):
        response = ApiCacheControlMiddleware(lambda request: HttpResponse(headers={'Cache-Control':'public, max-age=3600'}))(
            RequestFactory().get('/static/app.css'))
        self.assertEqual(response['Cache-Control'], 'public, max-age=3600')
