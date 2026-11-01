import uuid
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower


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

    class Meta:
        constraints = [models.UniqueConstraint(Lower('email'), name='unique_user_email_casefold')]


class VolunteerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='volunteer_profile')
    phone = models.CharField(max_length=20, blank=True)
    commune = models.CharField(max_length=80, blank=True)
    adult_confirmed_at = models.DateTimeField()
    privacy_accepted_at = models.DateTimeField()
    notice_version = models.CharField(max_length=30, default='development-1')
    whatsapp_opt_in_at = models.DateTimeField(null=True, blank=True)
    qualifications_revision = models.PositiveIntegerField(default=0)
    availability_revision = models.PositiveIntegerField(default=0)


class AuditEvent(models.Model):
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=80)
    resource = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class RateBucket(models.Model):
    key = models.CharField(max_length=64, unique=True)
    count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField()
