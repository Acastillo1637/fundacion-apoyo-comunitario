import uuid
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('El correo es obligatorio.')
        user = self.model(email=self.normalize_email(email).lower(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if not extra_fields['is_staff'] or not extra_fields['is_superuser']:
            raise ValueError('Un superusuario requiere ambos privilegios.')
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None
    email = models.EmailField(unique=True)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    objects = UserManager()
    management_revision = models.PositiveIntegerField(default=0)
    session_version = models.PositiveIntegerField(default=0)

    class Meta:
        permissions = [('manage_accounts', 'Puede administrar cuentas desde el portal')]
        constraints = [models.UniqueConstraint(Lower('email'), name='unique_user_email_casefold')]


class AccountManagementGuard(models.Model):
    # Un único bloqueo serializa decisiones de acceso y protección del último administrador.
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)


class AccountChange(models.Model):
    actor = models.ForeignKey(User, on_delete=models.PROTECT, related_name='account_changes_made')
    target = models.ForeignKey(User, on_delete=models.PROTECT, related_name='account_changes_received')
    action = models.CharField(max_length=40)
    reason = models.CharField(max_length=1000)
    fields_changed = models.JSONField(default=list)
    before_access = models.JSONField(default=dict)
    after_access = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']


class VolunteerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='volunteer_profile')
    phone = models.CharField(max_length=20, blank=True)
    commune = models.CharField(max_length=80, blank=True)
    sector = models.CharField(max_length=80, blank=True, db_default='')
    reference_latitude = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    reference_longitude = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    location_revision = models.PositiveIntegerField(default=0, db_default=0)
    adult_confirmed_at = models.DateTimeField()
    privacy_accepted_at = models.DateTimeField()
    notice_version = models.CharField(max_length=30, default='development-1')
    whatsapp_opt_in_at = models.DateTimeField(null=True, blank=True)
    qualifications_revision = models.PositiveIntegerField(default=0)
    availability_revision = models.PositiveIntegerField(default=0)
    is_restricted = models.BooleanField(default=False)
    restriction_reason = models.CharField(max_length=1000, blank=True)
    restriction_expires_at = models.DateTimeField(null=True, blank=True)
    restriction_revision = models.PositiveIntegerField(default=0, db_default=0)

    class Meta:
        constraints = [models.CheckConstraint(condition=(
            models.Q(reference_latitude__isnull=True, reference_longitude__isnull=True) |
            models.Q(reference_latitude__isnull=False, reference_longitude__isnull=False,
                     reference_latitude__gte=-90, reference_latitude__lte=90,
                     reference_longitude__gte=-180, reference_longitude__lte=180)), name='volunteer_reference_valid')]

    @property
    def participation_restricted(self):
        return self.is_restricted and (self.restriction_expires_at is None or self.restriction_expires_at > timezone.now())


class RequesterProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='requester_profile')
    requester_type = models.CharField(max_length=20, choices=[('person', 'Persona'), ('company', 'Empresa'), ('institution', 'Institución')])
    organization = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=20)
    commune = models.CharField(max_length=80, blank=True)
    privacy_accepted_at = models.DateTimeField()
    adult_confirmed_at = models.DateTimeField()
    representative_confirmed_at = models.DateTimeField(null=True, blank=True)
    notice_version = models.CharField(max_length=30, default='development-1')
    revision = models.PositiveIntegerField(default=0)


class AuditEvent(models.Model):
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=80)
    resource = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class RateBucket(models.Model):
    key = models.CharField(max_length=64, unique=True)
    count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField()


class PendingEmailChange(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='pending_email_change')
    email = models.EmailField()
    nonce = models.UUIDField(default=uuid.uuid4)
    created_at = models.DateTimeField(default=timezone.now)


class PrivacyRequest(models.Model):
    owner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='privacy_requests')
    kind = models.CharField(max_length=20, choices=[('access','Acceso a mis datos'), ('rectification','Rectificación'), ('deletion','Eliminación'), ('other','Otra solicitud de privacidad')])
    note = models.CharField(max_length=1000)
    status = models.CharField(max_length=20, default='pending', choices=[('pending','Pendiente'), ('in_review','En revisión'), ('answered','Respuesta registrada'), ('rejected','Rechazada con motivo')])
    response = models.CharField(max_length=2000, blank=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='privacy_reviews')
    revision = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at','pk']


class PrivacyRequestChange(models.Model):
    request = models.ForeignKey(PrivacyRequest, on_delete=models.PROTECT, related_name='changes')
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    from_status = models.CharField(max_length=20)
    to_status = models.CharField(max_length=20)
    response = models.CharField(max_length=2000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
