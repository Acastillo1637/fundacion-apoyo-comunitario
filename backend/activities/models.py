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
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)
    is_remote = models.BooleanField(default=False, db_default=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    revision = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['starts_at', 'pk']
        constraints = [models.CheckConstraint(condition=models.Q(ends_at__gt=models.F('starts_at')), name='event_positive_duration'),
            models.CheckConstraint(condition=(models.Q(latitude__isnull=True, longitude__isnull=True) |
                models.Q(latitude__isnull=False, longitude__isnull=False, latitude__gte=-90, latitude__lte=90,
                         longitude__gte=-180, longitude__lte=180)), name='event_coordinates_valid'),
            models.CheckConstraint(condition=models.Q(is_remote=False)|models.Q(latitude__isnull=True, longitude__isnull=True), name='remote_event_no_coordinates')]


class EventPosition(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='positions')
    name = models.CharField(max_length=100)
    capacity = models.PositiveIntegerField()
    required_skills = models.ManyToManyField('volunteers.Skill', blank=True)
    desired_skills = models.ManyToManyField('volunteers.Skill', blank=True, related_name='desirable_positions')
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


class EventChange(models.Model):
    event = models.ForeignKey(Event, on_delete=models.PROTECT, related_name='changes')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    revision = models.PositiveIntegerField()
    reason = models.CharField(max_length=1000)
    fields_changed = models.JSONField(default=list)
    before_public = models.JSONField(default=dict)
    after_public = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        constraints = [models.UniqueConstraint(fields=['event', 'revision'], name='event_change_revision_once')]


class Participation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.PROTECT, related_name='participations')
    position = models.ForeignKey(EventPosition, on_delete=models.PROTECT, related_name='participations')
    profile = models.ForeignKey('accounts.VolunteerProfile', on_delete=models.PROTECT, related_name='participations')
    assignment = models.CharField(max_length=10, choices=[('primary', 'Titular'), ('backup', 'Respaldo')], default='primary', db_default='primary')
    status = models.CharField(max_length=20, choices=[(value, value) for value in ['applied', 'invited', 'confirmed', 'waitlisted', 'declined', 'cancelled', 'rejected']], default='applied')
    expires_at = models.DateTimeField(null=True, blank=True)
    attendance = models.CharField(max_length=12, choices=[('', 'Pendiente'), ('present', 'Presente'), ('absent', 'Ausente')], blank=True)
    revision = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', 'pk']
        constraints = [models.UniqueConstraint(fields=['event', 'profile'], name='one_participation_per_event'),
                       models.CheckConstraint(condition=models.Q(assignment__in=['primary', 'backup']), name='participation_assignment_valid')]


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=300)
    target = models.CharField(max_length=30, blank=True, default='', db_default='', choices=[('', 'Sin enlace'), ('documents', 'Documentos'), ('participations', 'Participaciones'), ('my-requests', 'Mis solicitudes'), ('privacy-requests','Solicitudes de privacidad')])
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']


class MatchingPolicy(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    skills_weight = models.PositiveSmallIntegerField(default=60)
    experience_weight = models.PositiveSmallIntegerField(default=15)
    distance_weight = models.PositiveSmallIntegerField(default=25)
    distance_limit_km = models.PositiveSmallIntegerField(default=50)
    experience_target = models.PositiveSmallIntegerField(default=5)
    revision = models.PositiveIntegerField(default=0)
    geocoding_enabled = models.BooleanField(default=False)
    geocoding_policy_accepted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(id=1), name='matching_policy_singleton'),
            models.CheckConstraint(condition=models.Q(skills_weight=100-models.F('experience_weight')-models.F('distance_weight')), name='matching_weights_total_100'),
            models.CheckConstraint(condition=models.Q(distance_limit_km__gte=1, distance_limit_km__lte=500), name='matching_distance_bounds'),
            models.CheckConstraint(condition=models.Q(experience_target__gte=1, experience_target__lte=100), name='matching_experience_bounds'),
        ]


class ContactInvitation(models.Model):
    STATUS = [('pending_contact', 'Pendiente de contacto'), ('contact_started', 'Contacto iniciado'),
              ('sent', 'Enviada: confirmación manual'), ('accepted', 'Aceptada: respuesta registrada'),
              ('declined', 'Rechazada'), ('no_response', 'Sin respuesta'), ('cancelled', 'Cancelada')]
    event = models.ForeignKey(Event, on_delete=models.PROTECT, related_name='contacts')
    position = models.ForeignKey(EventPosition, on_delete=models.PROTECT)
    profile = models.ForeignKey('accounts.VolunteerProfile', on_delete=models.PROTECT, related_name='contacts')
    status = models.CharField(max_length=20, choices=STATUS, default='pending_contact')
    revision = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['event', 'profile'], name='one_contact_per_event_profile')]
        ordering = ['-updated_at', 'pk']


class MatchingPolicyChange(models.Model):
    policy = models.ForeignKey(MatchingPolicy, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    revision = models.PositiveIntegerField()
    reason = models.CharField(max_length=500)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['policy', 'revision'], name='matching_policy_revision_once')]


class ContactChange(models.Model):
    contact = models.ForeignKey(ContactInvitation, on_delete=models.PROTECT, related_name='changes')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20)
    note = models.CharField(max_length=500, blank=True)
    action = models.CharField(max_length=30)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']


class GeocodingGate(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    next_request_at = models.DateTimeField()


class GeocodingResult(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    results = models.JSONField(default=list)
    expires_at = models.DateTimeField(db_index=True)
