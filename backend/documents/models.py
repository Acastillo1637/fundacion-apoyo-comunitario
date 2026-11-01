import uuid

from django.db import models
from django.utils import timezone


class VolunteerDocument(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pendiente'
        VALIDATED = 'validated', 'Validado'
        REJECTED = 'rejected', 'Rechazado'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey('accounts.VolunteerProfile', on_delete=models.PROTECT, related_name='documents')
    document_type = models.ForeignKey('volunteers.DocumentType', on_delete=models.PROTECT, verbose_name='tipo documental')
    version = models.PositiveIntegerField()
    storage_key = models.CharField(max_length=80, unique=True)
    size = models.PositiveIntegerField()
    mime_type = models.CharField(max_length=40)
    checksum = models.CharField(max_length=64)
    scan_status = models.CharField(max_length=20, choices=[('clean', 'Analizado: sin detección'), ('not_scanned', 'Sin análisis antimalware')])
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewer = models.ForeignKey('accounts.User', on_delete=models.PROTECT, null=True, blank=True)
    observation = models.CharField(max_length=1000, blank=True)
    expires_on = models.DateField('válido hasta', null=True, blank=True)

    class Meta:
        ordering = ['-uploaded_at', '-pk']
        permissions = [('review_volunteerdocument', 'Puede revisar documentos de voluntarios')]
        constraints = [
            models.UniqueConstraint(fields=['profile', 'document_type', 'version'], name='document_version_once'),
            models.CheckConstraint(condition=models.Q(version__gte=1), name='document_positive_version'),
        ]

    @property
    def effective_status(self):
        if self.status == self.Status.VALIDATED and self.expires_on and self.expires_on < timezone.localdate():
            return 'expired'
        return self.status

    def __str__(self):
        return f'{self.document_type} · versión {self.version}'
