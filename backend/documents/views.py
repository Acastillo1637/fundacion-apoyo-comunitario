from django.conf import settings
from django.db import transaction
from django.db.models import Max, Q, Sum
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from rest_framework.decorators import api_view, parser_classes
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from accounts.models import AuditEvent, VolunteerProfile
from accounts.views import limited
from accounts.portals import is_volunteer
from volunteers.models import DocumentType
from .models import VolunteerDocument
from .serializers import ReviewSerializer, UploadSerializer
from .services import can_review, document_data, require_reviewer, review_document
from .storage import private_storage, save_file, validate_upload


def requirements(profile):
    return DocumentType.objects.filter(
        Q(skill__volunteerskill__profile=profile, skill__is_active=True)
        | Q(profession__volunteerprofession__profile=profile, profession__is_active=True)
    ).distinct().order_by('name')


@never_cache
@api_view(['GET', 'POST'])
@parser_classes([MultiPartParser, FormParser])
def documents(request):
    if not is_volunteer(request.user):
        raise PermissionDenied('La carga documental pertenece al espacio de voluntario.')
    profile = get_object_or_404(VolunteerProfile, user=request.user)
    if request.method == 'GET':
        history = profile.documents.select_related('document_type').all()
        required = list(requirements(profile))
        types = DocumentType.objects.filter(Q(is_active=True) | Q(pk__in=[item.pk for item in required])).order_by('name')
        return Response({
            'documents': [document_data(document) for document in history],
            'types': [{'id': item.pk, 'name': item.name, 'is_active': item.is_active} for item in types],
            'required_type_ids': [item.pk for item in required],
            'max_file_bytes': settings.DOCUMENT_MAX_BYTES,
            'quota_bytes': settings.DOCUMENT_USER_QUOTA_BYTES,
            'used_bytes': profile.documents.aggregate(total=Sum('size'))['total'] or 0,
            'antimalware_required': settings.DOCUMENT_SCAN_REQUIRED or not settings.DEBUG,
        })
    if limited(request, 'document-upload', 20):
        return Response({'detail': 'Demasiadas cargas. Intenta más tarde.'}, status=429)
    serializer = UploadSerializer(data=request.data)
    if getattr(request, 'document_upload_rejected', False):
        raise ValidationError('Carga un solo archivo de hasta 10 MB por solicitud.')
    serializer.is_valid(raise_exception=True)
    type_id = serializer.validated_data['document_type']
    get_object_or_404(DocumentType, pk=type_id, is_active=True)
    data, mime, extension, scan = validate_upload(serializer.validated_data['file'])
    storage_key = None
    try:
        with transaction.atomic():
            profile = VolunteerProfile.objects.select_for_update().get(pk=profile.pk)
            document_type = get_object_or_404(DocumentType.objects.select_for_update(), pk=type_id, is_active=True)
            totals = profile.documents.aggregate(total=Sum('size'))
            if (totals['total'] or 0) + len(data) > settings.DOCUMENT_USER_QUOTA_BYTES or profile.documents.count() >= settings.DOCUMENT_MAX_VERSIONS:
                raise ValidationError('Alcanzaste el límite de almacenamiento. Contacta al equipo antes de cargar más versiones.')
            version = (profile.documents.filter(document_type=document_type).aggregate(latest=Max('version'))['latest'] or 0) + 1
            storage_key, checksum = save_file(data, extension)
            document = VolunteerDocument.objects.create(
                profile=profile, document_type=document_type, version=version,
                storage_key=storage_key, checksum=checksum, mime_type=mime,
                size=len(data), scan_status=scan,
            )
            AuditEvent.objects.create(actor=request.user, action='document.uploaded', resource=f'document:{document.pk}')
        return Response(document_data(document), status=201)
    except Exception:
        if storage_key:
            private_storage().delete(storage_key)
        raise


@never_cache
@api_view(['GET'])
def download(request, document_id):
    visible = VolunteerDocument.objects.filter(profile__user=request.user)
    if can_review(request):
        visible = VolunteerDocument.objects.all()
    document = get_object_or_404(visible, pk=document_id)
    if not settings.DEBUG and document.scan_status != 'clean':
        raise PermissionDenied('El documento requiere análisis antimalware antes de su descarga.')
    try:
        file = private_storage().open(document.storage_key, 'rb')
    except FileNotFoundError as exc:
        raise Http404('Archivo no disponible.') from exc
    response = FileResponse(file, content_type=document.mime_type, as_attachment=True,
                            filename=f'documento-{document.pk}{".pdf" if document.mime_type == "application/pdf" else ".png" if document.mime_type == "image/png" else ".jpg"}')
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    AuditEvent.objects.create(actor=request.user, action='document.downloaded', resource=f'document:{document.pk}')
    return response


@never_cache
@api_view(['GET'])
def review_queue(request):
    require_reviewer(request)
    try:
        page = max(1, int(request.query_params.get('page', '1')))
    except ValueError:
        raise ValidationError('Página no válida.')
    pending = VolunteerDocument.objects.filter(status='pending').exclude(profile__user=request.user).select_related('document_type', 'profile__user')
    # Una versión antigua no puede acreditar el archivo más reciente.
    from django.db.models import Exists, OuterRef
    newer = VolunteerDocument.objects.filter(profile_id=OuterRef('profile_id'), document_type_id=OuterRef('document_type_id'), version__gt=OuterRef('version'))
    pending = pending.annotate(has_newer=Exists(newer)).filter(has_newer=False)
    total = pending.count()
    results = []
    for document in pending[(page - 1) * 20:page * 20]:
        results.append({**document_data(document), 'volunteer_name': document.profile.user.get_full_name() or 'Voluntario'})
    return Response({'results': results, 'total': total, 'page': page, 'page_size': 20})


@never_cache
@api_view(['POST'])
def review(request, document_id):
    require_reviewer(request)
    serializer = ReviewSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return Response(document_data(review_document(request, document_id, serializer.validated_data)))
