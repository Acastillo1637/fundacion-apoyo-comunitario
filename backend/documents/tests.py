import io
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from pypdf import PdfWriter
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from accounts.models import AuditEvent
from volunteers.models import DocumentType, Profession, VolunteerProfession
from volunteers.tests import make_profile
from .models import VolunteerDocument


def image_file(name='certificado.png', mime='image/png'):
    stream = io.BytesIO()
    Image.new('RGB', (12, 12), 'white').save(stream, format='PNG')
    return SimpleUploadedFile(name, stream.getvalue(), content_type=mime)


def pdf_file(active=False, encrypted=False):
    stream = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    if active:
        writer.add_js('app.alert("test")')
    if encrypted:
        writer.encrypt('test-only')
    writer.write(stream)
    return SimpleUploadedFile('certificado.pdf', stream.getvalue(), content_type='application/pdf')


@override_settings(DEBUG=True, DOCUMENT_SCAN_REQUIRED=False, CLAMAV_HOST='')
class DocumentTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.profile = make_profile('documentos@example.org')
        cls.other = make_profile('otro-documentos@example.org')
        cls.type = DocumentType.objects.create(name='Acreditación de prueba')

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.override = override_settings(PRIVATE_DOCUMENT_ROOT=Path(self.directory.name))
        self.override.enable()
        self.client.force_login(self.profile.user)

    def tearDown(self):
        self.override.disable()
        self.directory.cleanup()

    def upload(self, file=None, **extra):
        return self.client.post('/api/documents/', {'document_type': self.type.pk, 'file': file or image_file(), **extra})

    def reviewer(self, profile=None, mfa=True):
        profile = profile or self.other
        profile.user.user_permissions.add(Permission.objects.get(codename='review_volunteerdocument'))
        self.client.force_login(profile.user)
        if mfa:
            session = self.client.session
            session['account_authentication_methods_user'] = str(profile.user_id)
            session['account_authentication_methods'] = [{'method': 'mfa', 'at': timezone.now().timestamp()}]
            session.save()

    def review(self, document_id, **overrides):
        return self.client.post(f'/api/documents/{document_id}/review/', {
            'decision': 'validated', 'observation': '', 'expires_on': None, **overrides,
        }, content_type='application/json')

    def test_anonymous_cannot_list_or_upload(self):
        self.client.logout()
        self.assertEqual(self.client.get('/api/documents/').status_code, 403)
        self.assertEqual(self.upload().status_code, 403)

    def test_upload_is_private_pending_and_has_no_public_storage_path(self):
        response = self.upload()
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['status'], 'pending')
        self.assertEqual(data['scan_status'], 'not_scanned')
        self.assertNotIn('storage_key', data)
        document = VolunteerDocument.objects.get(pk=data['id'])
        self.assertTrue((Path(self.directory.name) / document.storage_key).exists())
        self.assertNotIn('certificado', document.storage_key)
        self.assertEqual(self.client.get(f'/media/{document.storage_key}').status_code, 404)
        self.assertTrue(AuditEvent.objects.filter(action='document.uploaded', actor=self.profile.user).exists())

    def test_pdf_upload_is_supported(self):
        self.assertEqual(self.upload(pdf_file()).status_code, 201)

    def test_fake_extension_mime_and_content_are_rejected(self):
        files = [
            image_file(name='archivo.exe'),
            image_file(mime='application/pdf'),
            image_file(name='falso.jpg', mime='image/jpeg'),
            SimpleUploadedFile('falso.pdf', b'%PDF-not-a-document', content_type='application/pdf'),
            SimpleUploadedFile('falso.png', b'not an image', content_type='image/png'),
        ]
        for file in files:
            with self.subTest(name=file.name):
                self.assertEqual(self.upload(file).status_code, 400)
        self.assertFalse(VolunteerDocument.objects.exists())
        self.assertEqual(list(Path(self.directory.name).iterdir()), [])

    def test_encrypted_and_active_pdf_are_rejected(self):
        self.assertEqual(self.upload(pdf_file(active=True)).status_code, 400)
        self.assertEqual(self.upload(pdf_file(encrypted=True)).status_code, 400)

    @override_settings(DOCUMENT_MAX_BYTES=20)
    def test_upload_handler_cuts_off_oversized_file(self):
        self.assertEqual(self.upload().status_code, 400)
        self.assertFalse(VolunteerDocument.objects.exists())

    def test_owner_can_download_with_attachment_and_no_store(self):
        data = self.upload().json()
        response = self.client.get(data['download_url'])
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        # El cliente de Django cierra el stream sin cerrar la transacción de TestCase.
        self.assertTrue(b''.join(response.streaming_content).startswith(b'\x89PNG'))

    def test_other_user_cannot_download_or_see_document(self):
        data = self.upload().json()
        self.client.force_login(self.other.user)
        self.assertEqual(self.client.get(data['download_url']).status_code, 404)
        self.assertEqual(self.client.get('/api/documents/').json()['documents'], [])
        self.assertEqual(self.review(data['id']).status_code, 403)

    def test_ownership_and_review_fields_cannot_be_injected_in_upload(self):
        self.assertEqual(self.upload(profile=str(self.other.pk), status='validated').status_code, 400)
        self.assertFalse(VolunteerDocument.objects.exists())

    def test_reviewer_requires_permission_and_mfa(self):
        data = self.upload().json()
        self.reviewer(mfa=False)
        self.assertEqual(self.client.get('/api/documents/review-queue/').status_code, 403)
        self.assertEqual(self.review(data['id']).status_code, 403)
        self.assertEqual(self.client.get(data['download_url']).status_code, 404)

    def test_reviewer_can_download_and_validate(self):
        data = self.upload().json()
        self.reviewer()
        queue = self.client.get('/api/documents/review-queue/').json()
        self.assertEqual(queue['total'], 1)
        response = self.client.get(data['download_url'])
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b''.join(response.streaming_content))
        response = self.review(data['id'])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'validated')
        document = VolunteerDocument.objects.get(pk=data['id'])
        self.assertEqual(document.reviewer_id, self.other.user_id)
        self.assertIsNotNone(document.reviewed_at)
        self.assertTrue(AuditEvent.objects.filter(action='document.validated').exists())

    def test_even_privileged_owner_cannot_review_self(self):
        data = self.upload().json()
        self.reviewer(profile=self.profile)
        self.assertEqual(self.review(data['id']).status_code, 403)
        self.assertEqual(self.client.get('/api/documents/review-queue/').json()['total'], 0)

    def test_rejection_requires_reason(self):
        data = self.upload().json()
        self.reviewer()
        self.assertEqual(self.review(data['id'], decision='rejected').status_code, 400)
        response = self.review(data['id'], decision='rejected', observation='Falta la información requerida.')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'rejected')

    def test_expiration_is_effective_without_scheduled_job(self):
        data = self.upload().json()
        self.reviewer()
        response = self.review(data['id'], expires_on=str(timezone.localdate() - timedelta(days=1)))
        self.assertEqual(response.json()['status'], 'expired')
        self.assertEqual(VolunteerDocument.objects.get(pk=data['id']).status, 'validated')

    def test_new_version_is_pending_and_prior_review_is_preserved(self):
        first = self.upload().json()
        self.reviewer()
        self.review(first['id'])
        self.client.force_login(self.profile.user)
        second = self.upload().json()
        self.assertEqual(second['version'], 2)
        self.assertEqual(second['status'], 'pending')
        self.assertEqual(VolunteerDocument.objects.get(pk=first['id']).status, 'validated')

    def test_old_pending_version_cannot_be_reviewed_and_is_not_queued(self):
        first = self.upload().json()
        second = self.upload().json()
        self.reviewer()
        self.assertEqual(self.review(first['id']).status_code, 400)
        queue = self.client.get('/api/documents/review-queue/').json()
        self.assertEqual(queue['total'], 1)
        self.assertEqual(queue['results'][0]['id'], second['id'])

    def test_review_cannot_be_overwritten(self):
        data = self.upload().json()
        self.reviewer()
        self.assertEqual(self.review(data['id']).status_code, 200)
        self.assertEqual(self.review(data['id'], decision='rejected', observation='Otro motivo').status_code, 400)
        self.assertEqual(VolunteerDocument.objects.get(pk=data['id']).status, 'validated')

    def test_requirements_follow_declared_profession(self):
        profession = Profession.objects.create(name='Profesión de prueba')
        profession.required_documents.add(self.type)
        VolunteerProfession.objects.create(profile=self.profile, profession=profession)
        self.assertEqual(self.client.get('/api/documents/').json()['required_type_ids'], [self.type.pk])

    @override_settings(DOCUMENT_USER_QUOTA_BYTES=1)
    def test_quota_rejection_leaves_no_stored_file(self):
        self.assertEqual(self.upload().status_code, 400)
        self.assertEqual(list(Path(self.directory.name).iterdir()), [])

    def test_inactive_document_type_cannot_receive_uploads(self):
        self.type.is_active = False
        self.type.save()
        self.assertEqual(self.upload().status_code, 404)

    @override_settings(DEBUG=False, SECURE_SSL_REDIRECT=False, DOCUMENT_SCAN_REQUIRED=True)
    def test_production_requires_available_scanner(self):
        self.assertEqual(self.upload().status_code, 503)
        self.assertFalse(VolunteerDocument.objects.exists())

    def test_scanner_detection_rejects_upload(self):
        from rest_framework.exceptions import ValidationError
        with patch('documents.storage.check_antimalware', side_effect=ValidationError('Archivo rechazado.')):
            self.assertEqual(self.upload().status_code, 400)
        self.assertFalse(VolunteerDocument.objects.exists())

    def test_upload_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.profile.user)
        response = client.post('/api/documents/', {'document_type': self.type.pk, 'file': image_file()})
        self.assertEqual(response.status_code, 403)

    def test_review_cannot_inject_reviewer_or_owner(self):
        data = self.upload().json()
        self.reviewer()
        self.assertEqual(self.review(data['id'], reviewer=str(self.profile.user_id)).status_code, 400)

    def test_request_with_two_files_does_not_save_first_file(self):
        response = self.client.post('/api/documents/', {'document_type': self.type.pk, 'file': [image_file(), image_file('otra.png')]})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(VolunteerDocument.objects.exists())

    @override_settings(CLAMAV_HOST='scanner.internal')
    def test_clamav_clean_response_is_recorded(self):
        with patch('documents.storage.socket.create_connection') as connect:
            scanner = connect.return_value.__enter__.return_value
            scanner.recv.return_value = b'stream: OK\0'
            response = self.upload()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['scan_status'], 'clean')

    @override_settings(CLAMAV_HOST='scanner.internal')
    def test_clamav_infected_or_unavailable_never_saves_file(self):
        for result, status in [(b'stream: test-virus FOUND\0', 400), (b'stream: scanner ERROR\0', 503)]:
            with self.subTest(result=result), patch('documents.storage.socket.create_connection') as connect:
                connect.return_value.__enter__.return_value.recv.return_value = result
                self.assertEqual(self.upload().status_code, status)
        with patch('documents.storage.socket.create_connection', side_effect=OSError('Unavailable')):
            self.assertEqual(self.upload().status_code, 503)
        self.assertFalse(VolunteerDocument.objects.exists())

    def test_unscanned_local_file_cannot_be_downloaded_or_validated_in_production(self):
        data = self.upload().json()
        with override_settings(DEBUG=False, SECURE_SSL_REDIRECT=False):
            self.assertEqual(self.client.get(data['download_url']).status_code, 403)
            self.reviewer()
            self.assertEqual(self.review(data['id']).status_code, 400)

    @override_settings(DOCUMENT_MAX_VERSIONS=1)
    def test_version_limit_is_enforced(self):
        self.assertEqual(self.upload().status_code, 201)
        self.assertEqual(self.upload().status_code, 400)
        self.assertEqual(VolunteerDocument.objects.count(), 1)
