import uuid

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower


class ServiceRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendiente'
        IN_REVIEW = 'in_review', 'En revisión'
        APPROVED = 'approved', 'Aprobada'
        REJECTED = 'rejected', 'Rechazada'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submission_id = models.UUIDField(unique=True)
    requester = models.ForeignKey('accounts.RequesterProfile', on_delete=models.PROTECT, null=True, blank=True, related_name='requests')
    requester_type = models.CharField(max_length=20, choices=[('person', 'Persona'), ('company', 'Empresa'), ('institution', 'Institución')])
    contact_name = models.CharField(max_length=120)
    organization = models.CharField(max_length=150, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    description = models.TextField(max_length=3000)
    quantity = models.PositiveIntegerField()
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    address = models.CharField(max_length=250)
    commune = models.CharField(max_length=80)
    observations = models.CharField(max_length=1500, blank=True)
    skills = models.ManyToManyField('volunteers.Skill', blank=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    verification_sent_at = models.DateTimeField(null=True, blank=True)
    verification_nonce = models.UUIDField(default=uuid.uuid4, editable=False)
    privacy_accepted_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    revision = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', 'pk']
        permissions = [('manage_operations', 'Puede gestionar solicitudes y eventos')]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gte=1, quantity__lte=500), name='request_quantity_bounds'),
            models.CheckConstraint(condition=models.Q(ends_at__gt=models.F('starts_at')), name='request_positive_duration'),
        ]


class RequestTransition(models.Model):
    request = models.ForeignKey(ServiceRequest, on_delete=models.PROTECT, related_name='transitions')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    from_status = models.CharField(max_length=20)
    to_status = models.CharField(max_length=20)
    reason = models.CharField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'pk']


class Event(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Borrador'
        OPEN = 'open', 'Abierto'
        FINISHED = 'finished', 'Finalizado'
        CANCELLED = 'cancelled', 'Cancelado'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(ServiceRequest, on_delete=models.PROTECT, related_name='events')
    title = models.CharField(max_length=150)
    public_description = models.TextField(max_length=2000)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    address = models.CharField(max_length=250)
    commune = models.CharField(max_length=80)
    internal_notes = models.CharField(max_length=1500, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    revision = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['starts_at', 'pk']
        constraints = [models.CheckConstraint(condition=models.Q(ends_at__gt=models.F('starts_at')), name='event_positive_duration')]


class EventPosition(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='positions')
    name = models.CharField(max_length=100)
    capacity = models.PositiveIntegerField()
    required_skills = models.ManyToManyField('volunteers.Skill', blank=True)
    required_documents = models.ManyToManyField('volunteers.DocumentType', blank=True)

    class Meta:
        ordering = ['pk']
        constraints = [
            models.UniqueConstraint(Lower('name'), models.F('event'), name='event_function_name_ci'),
            models.CheckConstraint(condition=models.Q(capacity__gte=1, capacity__lte=500), name='position_capacity_bounds'),
        ]


class EventTransition(models.Model):
    event = models.ForeignKey(Event, on_delete=models.PROTECT, related_name='transitions')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    from_status = models.CharField(max_length=20)
    to_status = models.CharField(max_length=20)
    reason = models.CharField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'pk']


class Participation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.PROTECT, related_name='participations')
    position = models.ForeignKey(EventPosition, on_delete=models.PROTECT, related_name='participations')
    profile = models.ForeignKey('accounts.VolunteerProfile', on_delete=models.PROTECT, related_name='participations')
    status = models.CharField(max_length=20, choices=[(value, value) for value in ['applied', 'invited', 'confirmed', 'waitlisted', 'declined', 'cancelled', 'rejected']], default='applied')
    expires_at = models.DateTimeField(null=True, blank=True)
    attendance = models.CharField(max_length=12, choices=[('', 'Pendiente'), ('present', 'Presente'), ('absent', 'Ausente')], blank=True)
    revision = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', 'pk']
        constraints = [models.UniqueConstraint(fields=['event', 'profile'], name='one_participation_per_event')]


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=300)
    target = models.CharField(max_length=30, blank=True, default='', db_default='', choices=[('', 'Sin enlace'), ('documents', 'Documentos'), ('participations', 'Participaciones'), ('my-requests', 'Mis solicitudes')])
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']
