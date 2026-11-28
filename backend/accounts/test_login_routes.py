from django.test import SimpleTestCase


class CanonicalLoginTests(SimpleTestCase):
    def test_legacy_login_link_goes_to_the_platform_login(self):
        response = self.client.get('/accounts/login/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/iniciar-sesion')

    def test_legacy_login_form_cannot_bypass_the_controlled_api(self):
        response = self.client.post('/accounts/login/', {'login': 'persona@example.org', 'password': 'irrelevant-test-only'})
        self.assertEqual(response.status_code, 405)
        self.assertNotIn('sessionid', response.cookies)
