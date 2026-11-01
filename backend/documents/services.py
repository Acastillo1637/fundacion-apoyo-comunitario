from allauth.account.internal.flows.login import get_authentication_records
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from accounts.models import AuditEvent, VolunteerProfile
from .models import VolunteerDocument


def can_review(request):
    return request.user.has_perm('documents.review_volunteerdocument') and any(
        method.get('method') == 'mfa' for method in get_authentication_records(request, request.user)
    )


def require_reviewer(request):
    if not can_review(request):
        raise PermissionDenied('La revisión documental requiere permiso específico y MFA.')


def document_data(document):
    return {
        'id': str(document.pk), 'document_type': document.document_type_id,
        'type_name': document.document_type.name, 'version': document.version,
        'status': document.effective_status, 'uploaded_at': document.uploaded_at,
        'reviewed_at': document.reviewed_at, 'observation': document.observation,
        'expires_on': document.expires_on, 'scan_status': document.scan_status,
        'size': document.size,
        'download_url': f'/api/documents/{document.pk}/download/',
    }


@transaction.atomic
def review_document(request, document_id, data):
    require_reviewer(request)
    # Bloqueo en el mismo orden que la carga: perfil y después versión.
    identity = get_object_or_404(VolunteerDocument, pk=document_id)
    profile = VolunteerProfile.objects.select_for_update().get(pk=identity.profile_id)
    document = VolunteerDocument.objects.select_for_update().select_related('document_type').get(pk=document_id)
    if profile.user_id == request.user.pk:
        raise PermissionDenied('No puedes revisar tus propios documentos.')
    if document.status != VolunteerDocument.Status.PENDING:
        raise ValidationError('Esta versión ya fue revisada. La decisión no puede sobrescribirse.')
    if VolunteerDocument.objects.filter(profile=profile, document_type=document.document_type, version__gt=document.version).exists():
        raise ValidationError('Hay una versión más reciente. Revisa el archivo nuevo.')
    from django.conf import settings
    if not settings.DEBUG and document.scan_status != 'clean':
        raise ValidationError('Se requiere análisis antimalware antes de revisar este documento.')
    document.status = data['decision']
    document.observation = data['observation']
    document.expires_on = data['expires_on']
    document.reviewer = request.user
    document.reviewed_at = timezone.now()
    document.save(update_fields=['status', 'observation', 'expires_on', 'reviewer', 'reviewed_at'])
    AuditEvent.objects.create(actor=request.user, action=f'document.{document.status}', resource=f'document:{document.pk}')
    return document
