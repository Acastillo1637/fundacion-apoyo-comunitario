from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from activities.models import Notification
from activities.services import Conflict
from volunteers.serializers import StrictSerializer
from .models import AuditEvent, PrivacyRequest, PrivacyRequestChange, RequesterProfile, User, VolunteerProfile
from .security import portal_authenticated
from .views import limited


def require_manager(request):
    if not request.user.has_perm('accounts.manage_accounts') or not portal_authenticated(request):
        raise PermissionDenied('La revisión requiere administración general y una sesión vigente.')


class RequestSerializer(StrictSerializer):
    kind = serializers.ChoiceField(choices=['access','rectification','deletion','other'])
    note = serializers.CharField(min_length=10,max_length=1000)


class ReviewSerializer(StrictSerializer):
    revision = serializers.IntegerField(min_value=0)
    status = serializers.ChoiceField(choices=['in_review','answered','rejected'])
    response = serializers.CharField(min_length=8,max_length=2000)


def data(item):
    return {'id':item.pk,'kind':item.kind,'note':item.note,'status':item.status,'response':item.response,
            'owner_name':item.owner.get_full_name() if item.owner else 'Cuenta retirada',
            'revision':item.revision,'created_at':item.created_at,'updated_at':item.updated_at,
            'reviewer':item.reviewed_by.get_full_name() if item.reviewed_by else ''}


@api_view(['GET','POST'])
def requests(request):
    if request.method == 'POST':
        if limited(request._request,'privacy-request',5):
            raise ValidationError('Ya has registrado varias solicitudes. Espera antes de volver a enviar.')
        serializer=RequestSerializer(data=request.data); serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            item=PrivacyRequest.objects.create(owner=request.user,**serializer.validated_data)
            administrators=User.objects.filter(is_active=True,groups__name='Administrador general').distinct()
            Notification.objects.bulk_create([Notification(user=admin,target='privacy-requests',
                message=f'Nueva solicitud de privacidad #{item.pk}. Revisa la bandeja de administración.') for admin in administrators])
            AuditEvent.objects.create(actor=request.user,action='privacy.request.created',resource=f'privacy-request:{item.pk}')
        item.reviewed_by=None
        return Response(data(item),status=201)
    scope=request.query_params.get('scope','mine')
    if scope not in ['mine','all']:
        raise ValidationError('Ámbito de consulta no válido.')
    rows=PrivacyRequest.objects.select_related('owner','reviewed_by')
    if scope=='all':
        require_manager(request)
    else:
        rows=rows.filter(owner=request.user)
    from activities.views import pagination
    page,items=pagination(request,rows)
    return Response({'results':[data(item) for item in items],'total':rows.count(),'page':page})


@api_view(['POST'])
def review(request, request_id):
    require_manager(request)
    serializer=ReviewSerializer(data=request.data); serializer.is_valid(raise_exception=True)
    values=serializer.validated_data
    with transaction.atomic():
        item=get_object_or_404(PrivacyRequest.objects.select_for_update(),pk=request_id)
        if item.revision!=values['revision']:
            raise Conflict()
        if item.status not in ['pending','in_review'] or (item.status=='in_review' and values['status']=='in_review'):
            raise ValidationError('La solicitud ya fue atendida o no cambia de estado.')
        previous=item.status
        item.status,item.response,item.reviewed_by=values['status'],values['response'],request.user
        item.revision+=1; item.save()
        PrivacyRequestChange.objects.create(request=item,actor=request.user,from_status=previous,to_status=item.status,response=item.response)
        AuditEvent.objects.create(actor=request.user,action='privacy.request.'+item.status,resource=f'privacy-request:{item.pk}')
        if item.owner_id:
            Notification.objects.create(user_id=item.owner_id,target='privacy-requests',message=f'Se actualizó tu solicitud de privacidad #{item.pk}. Consulta la respuesta en la plataforma.')
    return Response(data(item))


@never_cache
@api_view(['GET'])
def export_own(request):
    from documents.services import document_data
    from activities.participation import data as participation_data
    user=request.user
    result={'account':{'email':user.email,'first_name':user.first_name,'last_name':user.last_name,'is_active':user.is_active,
                       'created_at':user.date_joined},'volunteer':None,'requester':None}
    profile=VolunteerProfile.objects.filter(user=user).first()
    if profile:
        result['volunteer']={'phone':profile.phone,'commune':profile.commune,'sector':profile.sector,
            'reference_latitude':profile.reference_latitude,'reference_longitude':profile.reference_longitude,
            'privacy_accepted_at':profile.privacy_accepted_at,'whatsapp_opt_in_at':profile.whatsapp_opt_in_at,
            'skills':list(profile.declared_skills.values_list('skill__name',flat=True)),
            'professions':list(profile.declared_professions.values_list('profession__name',flat=True)),
            'availability':list(profile.availability_slots.values('weekday','start_time','end_time')),
            'unavailable_dates':list(profile.unavailable_dates.values_list('date',flat=True)),
            'documents':[document_data(doc) for doc in profile.documents.select_related('document_type')],
            'participations':[participation_data(row) for row in profile.participations.select_related('event','position')]}
    requester=RequesterProfile.objects.filter(user=user).first()
    if requester:
        result['requester']={'type':requester.requester_type,'organization':requester.organization,'phone':requester.phone,
            'commune':requester.commune,'privacy_accepted_at':requester.privacy_accepted_at,
            'requests':list(requester.requests.values('id','status','description','starts_at','ends_at','commune','created_at'))}
    AuditEvent.objects.create(actor=user,action='privacy.export.downloaded',resource=f'user:{user.pk}')
    response=JsonResponse(result,json_dumps_params={'ensure_ascii':False})
    response['Content-Disposition']='attachment; filename="mis-datos-fundacion.json"'
    response['Cache-Control']='private, no-store'
    return response
