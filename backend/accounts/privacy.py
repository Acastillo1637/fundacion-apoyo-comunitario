from django.db import transaction
import csv

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from activities.models import Notification
from activities.services import Conflict
from volunteers.serializers import StrictSerializer
from .models import AuditEvent, PrivacyRequest, PrivacyRequestChange, User, VolunteerProfile
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
def export_volunteers(request):
    require_manager(request)
    if limited(request, 'volunteers-export', 5, identity=str(request.user.pk)):
        return Response({'detail': 'Demasiadas exportaciones. Intenta más tarde.'}, status=429)
    response = HttpResponse('\ufeff', content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="voluntarios.csv"'
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Nombre', 'Apellido', 'Correo', 'Celular', 'Comuna', 'Cuenta activa', 'WhatsApp autorizado', 'Fecha de registro'])
    def safe_cell(value):
        text = str(value or '')
        return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) or text.startswith(('\t', '\r', '\n')) else text
    rows = VolunteerProfile.objects.filter(user__groups__name='Voluntario').select_related('user').order_by('pk')
    for profile in rows.iterator(chunk_size=1000):
        user = profile.user
        writer.writerow([safe_cell(value) for value in [user.first_name, user.last_name, user.email,
            profile.phone, profile.commune, 'Sí' if user.is_active else 'No',
            'Sí' if profile.whatsapp_opt_in_at else 'No', user.date_joined.isoformat()]])
    AuditEvent.objects.create(actor=request.user, action='privacy.volunteers.exported', resource='volunteers:csv')
    return response
