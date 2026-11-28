from django.test import SimpleTestCase

from accounts.serializers import ProfileSerializer
from activities.contacts import PreferenceSerializer


class PhoneLengthTests(SimpleTestCase):
    def test_profile_phone_limit_includes_plus(self):
        for phone, expected in [('+56912345678', True), ('912345678', True), ('+12125550199', False), ('+569123456789', False), ('', False)]:
            with self.subTest(phone=phone):
                serializer = ProfileSerializer(data={
                    'first_name': 'Ana', 'last_name': 'Pérez',
                    'phone': phone, 'commune': 'Maipú',
                })
                self.assertEqual(serializer.is_valid(), expected, serializer.errors)

    def test_preferences_cannot_bypass_profile_phone_limit(self):
        for phone, expected in [('+56912345678', True), ('+569123456789', False)]:
            with self.subTest(phone=phone):
                serializer = PreferenceSerializer(data={'phone': phone, 'whatsapp': True, 'revision': 0})
                self.assertEqual(serializer.is_valid(), expected, serializer.errors)

    def test_preferences_require_whatsapp_and_normalize_chilean_mobile(self):
        serializer = PreferenceSerializer(data={'phone': '912345678', 'whatsapp': True, 'revision': 0})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['phone'], '+56912345678')
        serializer = PreferenceSerializer(data={'phone': '912345678', 'whatsapp': False, 'revision': 0})
        self.assertFalse(serializer.is_valid())
        self.assertIn('whatsapp', serializer.errors)
