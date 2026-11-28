from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.db import transaction
from django.db.models import F, OuterRef, Prefetch, Subquery, Window
from django.db.models.functions import RowNumber
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from accounts.models import AuditEvent, VolunteerProfile
from accounts.phones import ChileanMobileField, chilean_mobile
from accounts.portals import is_volunteer
from volunteers.serializers import StrictSerializer
from .models import ContactChange, ContactInvitation, Event, EventPosition, Participation
from .services import Conflict, require_operator


def normalize_phone(value):
    return chilean_mobile(value)[1:]


def whatsapp_link(profile, event=None):
    if not profile.whatsapp_opt_in_at or not profile.phone:
        raise ValidationError('El voluntario no tiene teléfono válido y consentimiento vigente para WhatsApp.')
    phone = normalize_phone(profile.phone)
    message = f'Hola {profile.user.first_name}, te contactamos de {settings.FOUNDATION_NAME}.'
    if event:
        date = timezone.localtime(event.starts_at).strftime('%d/%m/%Y a las %H:%M')
        place = 'modalidad remota' if event.is_remote else event.commune
        message += f' Tenemos la actividad {event.title}, programada para el {date}, en {place}. Consideramos que tu perfil podría ser adecuado. ¿Te gustaría participar?'
    else:
        message += ' Quisiéramos coordinar contigo una oportunidad de voluntariado. ¿Podemos conversar?'
    return 'https://wa.me/'+phone+'?'+urlencode({'text':message})


class PreferenceSerializer(StrictSerializer):
    phone = ChileanMobileField()
    whatsapp = serializers.BooleanField()
    revision = serializers.IntegerField(min_value=0)

    def validate_whatsapp(self, value):
        if not value:
            raise ValidationError('Autoriza el contacto por WhatsApp para guardar la configuración de coordinación.')
        return value


def preference_data(profile):
    return {'phone':profile.phone, 'whatsapp':bool(profile.whatsapp_opt_in_at),
            'consent_at':profile.whatsapp_opt_in_at, 'revision':profile.user.management_revision}


class WithdrawConsentSerializer(StrictSerializer):
    revision = serializers.IntegerField(min_value=0)


@api_view(['POST'])
def withdraw_consent(request):
    if not is_volunteer(request.user):
        raise PermissionDenied('Solo puedes retirar tu propia autorización.')
    serializer = WithdrawConsentSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    from accounts.models import User
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=request.user.pk)
        profile = get_object_or_404(VolunteerProfile.objects.select_for_update(), user=user)
        if user.management_revision != serializer.validated_data['revision']:
            raise Conflict()
        profile.whatsapp_opt_in_at = None
        profile.save(update_fields=['whatsapp_opt_in_at'])
        user.management_revision += 1
        user.save(update_fields=['management_revision'])
        profile.user = user
        AuditEvent.objects.create(actor=user, action='profile.whatsapp_consent.withdrawn', resource=f'profile:{profile.pk}')
    return Response(preference_data(profile))


@api_view(['GET', 'PUT'])
def preferences(request):
    if not is_volunteer(request.user):
        raise PermissionDenied('Solo puedes gestionar tus propias preferencias.')
    profile = get_object_or_404(VolunteerProfile.objects.select_related('user'), user=request.user)
    if request.method == 'GET':
        return Response(preference_data(profile))
    serializer = PreferenceSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    values = serializer.validated_data
    phone = values['phone']
    from accounts.models import User
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=request.user.pk)
        profile = VolunteerProfile.objects.select_for_update().get(pk=profile.pk)
        if user.management_revision != values['revision']:
            raise Conflict()
        profile.phone = phone
        profile.whatsapp_opt_in_at = (profile.whatsapp_opt_in_at or timezone.now()) if values['whatsapp'] else None
        profile.save(update_fields=['phone', 'whatsapp_opt_in_at'])
        user.management_revision += 1
        user.save(update_fields=['management_revision'])
        profile.user = user
        AuditEvent.objects.create(actor=request.user, action='profile.contact_preferences.updated', resource=f'profile:{profile.pk}')
    return Response(preference_data(profile))


def load_delivery(contacts):
    """At most three audit rows per contact, irrespective of repeated openings."""
    contacts = list(contacts)
    by_id = {contact.pk: contact for contact in contacts}
    for contact in contacts:
        contact.delivery_events = {}
    if not contacts:
        return
    rows = ContactChange.objects.filter(contact_id__in=by_id, action__in=['start', 'sent', 'reopen']).annotate(
        latest=Window(RowNumber(), partition_by=[F('contact_id'), F('action')],
                      order_by=[F('created_at').desc(), F('pk').desc()])).filter(latest=1).select_related('actor')
    for row in rows:
        by_id[row.contact_id].delivery_events[row.action] = row


def delivery_data(contact):
    if not hasattr(contact, 'delivery_events'):
        load_delivery([contact])
    events = contact.delivery_events
    reopened = events.get('reopen')
    def current(action):
        row = events.get(action)
        return row if row and (not reopened or (row.created_at, row.pk) > (reopened.created_at, reopened.pk)) else None
    opened, sent = current('start'), current('sent')
    def details(row):
        return {'at': row.created_at, 'actor_id': str(row.actor_id),
                'actor': row.actor.get_full_name() or 'Personal autorizado'} if row else None
    return {'opened': details(opened), 'sent': details(sent), 'send_confirmed': bool(sent),
            'can_confirm_send': bool(opened and not sent and contact.status in ['contact_started', 'no_response', 'accepted'])}


def candidate_contacts(rows, event):
    contacts = list(ContactInvitation.objects.filter(event=event, profile_id__in=[row['id'] for row in rows]))
    load_delivery(contacts)
    mapped = {contact.profile_id: {'id': contact.pk, 'status': contact.status, 'revision': contact.revision,
                                  'expires_at': contact.expires_at,
                                  'delivery': delivery_data(contact)} for contact in contacts}
    for row in rows:
        row['contact'] = mapped.get(row['id'])


def contact_data(contact):
    return {'id':contact.pk, 'profile_id':contact.profile_id, 'name':contact.profile.user.get_full_name(),
            'position_id':contact.position_id, 'position':contact.position.name, 'status':contact.status,
            'revision':contact.revision, 'updated_at':contact.updated_at, 'expires_at':contact.expires_at,
            'delivery': delivery_data(contact),
            'participation_status': contact.participation_status if hasattr(contact, 'participation_status') else Participation.objects.filter(event_id=contact.event_id, profile_id=contact.profile_id).values_list('status', flat=True).first(),
            'history':[{'action':row.action, 'from':row.from_status, 'to':row.to_status,
                        'note':row.note, 'at':row.created_at, 'actor_id':str(row.actor_id),
                        'actor':row.actor.get_full_name() or 'Personal autorizado'}
                       for row in (contact.loaded_changes if hasattr(contact,'loaded_changes') else contact.changes.select_related('actor')[:20])]}


class ContactSerializer(StrictSerializer):
    profile_id = serializers.IntegerField(min_value=1)
    position_id = serializers.IntegerField(min_value=1)


@api_view(['GET', 'POST'])
def event_contacts(request, event_id):
    require_operator(request)
    event = get_object_or_404(Event, pk=event_id)
    if request.method == 'GET':
        from .views import pagination
        rows = event.contacts.select_related('profile__user', 'position').annotate(participation_status=Subquery(
            Participation.objects.filter(event_id=OuterRef('event_id'), profile_id=OuterRef('profile_id')).values('status')[:1])).prefetch_related(
                Prefetch('changes',queryset=ContactChange.objects.select_related('actor').order_by('-created_at','-pk')[:20],to_attr='loaded_changes'))
        page, items = pagination(request, rows)
        items = list(items)
        load_delivery(items)
        return Response({'results':[contact_data(item) for item in items], 'total':rows.count(), 'page':page})
    serializer = ContactSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    values = serializer.validated_data
    from .participation import open_event, eligibility, locked_profile
    with transaction.atomic():
        event = Event.objects.select_for_update().get(pk=event.pk)
        open_event(event)
        profile = locked_profile(values['profile_id'])
        position = get_object_or_404(EventPosition.objects.select_related('event'), pk=values['position_id'], event=event)
        reasons = eligibility(profile, position)
        if reasons:
            raise ValidationError(' · '.join(reasons))
        contact, created = ContactInvitation.objects.get_or_create(event=event, profile=profile, defaults={
            'position':position,'expires_at':min(timezone.now()+timedelta(hours=48),event.starts_at)})
        if not created and contact.position_id != position.pk:
            raise Conflict('Ya existe seguimiento para otra función de este evento.')
        if created:
            ContactChange.objects.create(contact=contact, actor=request.user, to_status=contact.status, action='created')
            AuditEvent.objects.create(actor=request.user, action='contact.created', resource=f'contact:{contact.pk}')
    return Response(contact_data(contact), status=201 if created else 200)


class ContactActionSerializer(StrictSerializer):
    revision = serializers.IntegerField(min_value=0)
    action = serializers.ChoiceField(choices=['start', 'sent', 'accepted', 'declined', 'no_response', 'cancelled', 'confirm', 'reopen'])
    note = serializers.CharField(max_length=500, allow_blank=True, default='')


@api_view(['POST'])
def contact_action(request, contact_id):
    require_operator(request)
    serializer = ContactActionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    values = serializer.validated_data
    identity = get_object_or_404(ContactInvitation, pk=contact_id)
    from .participation import confirm, notify, open_event, locked_profile, eligibility
    with transaction.atomic():
        event = Event.objects.select_for_update().get(pk=identity.event_id)
        profile = locked_profile(identity.profile_id)
        contact = ContactInvitation.objects.select_for_update(of=('self',)).select_related('position', 'profile__user').get(pk=identity.pk)
        if contact.revision != values['revision']:
            raise Conflict()
        action = values['action']
        previous = contact.status
        url = None
        if action != 'cancelled':
            open_event(event)
        expires=contact.expires_at or min(contact.created_at+timedelta(hours=48),event.starts_at)
        if action in ['start','sent','accepted','confirm'] and expires<=timezone.now():
            raise ValidationError('El contacto venció. Registra una nueva ronda antes de invitar o confirmar.')
        if action == 'reopen':
            if len(values['note'].strip())<8 or (contact.status not in ['declined','cancelled','accepted','no_response'] and expires>timezone.now()):
                raise ValidationError('Justifica la nueva ronda de contacto o termina la ronda actual.')
            if Participation.objects.filter(event=event,profile=profile,status__in=['applied','invited','confirmed','waitlisted']).exists():
                raise Conflict('Existe una participación activa; revísala antes de iniciar otra ronda.')
            reasons=eligibility(profile,contact.position)
            if reasons:
                raise ValidationError(' · '.join(reasons))
            contact.status='pending_contact'
            contact.expires_at=min(timezone.now()+timedelta(hours=48),event.starts_at)
        elif action == 'start':
            if contact.status not in ['pending_contact', 'contact_started', 'sent', 'no_response']:
                raise ValidationError('Este contacto ya tiene una respuesta final.')
            url = whatsapp_link(profile, event)
            if contact.status == 'pending_contact':
                contact.status = 'contact_started'
        elif action == 'sent':
            delivery = delivery_data(contact)
            if delivery['send_confirmed']:
                raise Conflict('El envío de esta ronda ya fue confirmado.')
            if not delivery['can_confirm_send']:
                raise ValidationError('Abre primero WhatsApp para esta ronda antes de confirmar el envío.')
            values['note'] = values['note'].strip() or 'Envío por WhatsApp confirmado manualmente por coordinación.'
            if len(values['note']) < 8:
                raise ValidationError('La referencia opcional debe tener al menos 8 caracteres.')
            if contact.status != 'accepted':
                contact.status = 'sent'
        elif action == 'confirm':
            if contact.status != 'accepted' or len(values['note'].strip()) < 8:
                raise ValidationError('Registra la aceptación y una referencia de consentimiento antes de confirmar.')
            item, created = Participation.objects.get_or_create(event=event, profile=profile, defaults={'position':contact.position})
            if not created:
                if item.assignment != 'primary' or item.position_id != contact.position_id or item.status=='confirmed':
                    raise Conflict('Gestiona la participación actual antes de confirmar este contacto.')
                if item.status in ['declined','cancelled','rejected']:
                    accepted=contact.changes.filter(action='accepted').order_by('-created_at').first()
                    if not accepted or accepted.created_at<=item.updated_at:
                        raise Conflict('La persona retiró o rechazó su participación. Se necesita una nueva aceptación registrada.')
            item.position.event = event
            item.profile = profile
            confirm(item)
            item.revision += 1
            item.save(update_fields=['status', 'revision', 'updated_at'])
            notify(profile, f'{event.title}: coordinación registró tu aceptación por contacto y tu estado es {item.status}.')
        else:
            allowed = {'sent':['contact_started', 'no_response'], 'accepted':['contact_started', 'sent', 'no_response'],
                       'declined':['contact_started', 'sent', 'no_response'], 'no_response':['contact_started', 'sent'],
                       'cancelled':['pending_contact', 'contact_started', 'sent', 'no_response', 'accepted']}
            if contact.status not in allowed.get(action, []) or len(values['note'].strip()) < 8:
                raise ValidationError('Transición no permitida o falta una referencia de al menos 8 caracteres.')
            contact.status = action
            if action in ['declined', 'cancelled']:
                pending = Participation.objects.select_for_update().filter(event=event, profile=profile, status='invited').first()
                if pending:
                    pending.status = 'declined' if action == 'declined' else 'cancelled'
                    pending.revision += 1
                    pending.save(update_fields=['status','revision','updated_at'])
        contact.revision += 1
        contact.save(update_fields=['status','revision','expires_at','updated_at'])
        ContactChange.objects.create(contact=contact, actor=request.user, from_status=previous, to_status=contact.status,
                                     action=action, note=values['note'])
        AuditEvent.objects.create(actor=request.user, action=f'contact.{action}', resource=f'contact:{contact.pk}')
    load_delivery([contact])
    result = contact_data(contact)
    if url:
        result['whatsapp_url'] = url
        result['notice'] = 'Se registró un intento de contacto. Abrir WhatsApp no confirma envío ni recepción.'
    return Response(result)


@api_view(['POST'])
def profile_whatsapp(request, profile_id):
    require_operator(request)
    if request.data:
        raise ValidationError('No se requieren datos adicionales.')
    profile = get_object_or_404(VolunteerProfile.objects.select_related('user'), pk=profile_id, user__is_active=True, user__groups__name='Voluntario')
    url = whatsapp_link(profile)
    AuditEvent.objects.create(actor=request.user, action='contact.profile_started', resource=f'profile:{profile.pk}')
    return Response({'whatsapp_url':url, 'notice':'Intento de contacto registrado; envío y recepción no confirmados.'})
