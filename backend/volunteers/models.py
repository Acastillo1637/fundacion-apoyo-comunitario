from django.db import models
from django.db.models.functions import Lower


class CatalogEntry(models.Model):
    name = models.CharField('nombre', max_length=100)
    description = models.CharField('descripción', max_length=500, blank=True)
    is_active = models.BooleanField('activo', default=True)

    class Meta:
        abstract = True
        ordering = ['name', 'pk']
        constraints = [
            models.UniqueConstraint(Lower('name'), name='%(app_label)s_%(class)s_name_ci'),
            models.CheckConstraint(condition=~models.Q(name=''), name='%(app_label)s_%(class)s_name_nonempty'),
        ]

    def __str__(self):
        return self.name


class DocumentType(CatalogEntry):
    class Meta(CatalogEntry.Meta):
        verbose_name = 'tipo documental'
        verbose_name_plural = 'tipos documentales'


class Skill(CatalogEntry):
    required_documents = models.ManyToManyField(DocumentType, blank=True, verbose_name='requisitos documentales')

    class Meta(CatalogEntry.Meta):
        verbose_name = 'habilidad'
        verbose_name_plural = 'habilidades'


class Profession(CatalogEntry):
    required_documents = models.ManyToManyField(DocumentType, blank=True, verbose_name='requisitos documentales')

    class Meta(CatalogEntry.Meta):
        verbose_name = 'profesión u oficio'
        verbose_name_plural = 'profesiones y oficios'


class VolunteerSkill(models.Model):
    profile = models.ForeignKey('accounts.VolunteerProfile', on_delete=models.CASCADE, related_name='declared_skills')
    skill = models.ForeignKey(Skill, on_delete=models.PROTECT)
    declared_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['profile', 'skill'], name='volunteer_skill_once')]


class VolunteerProfession(models.Model):
    profile = models.ForeignKey('accounts.VolunteerProfile', on_delete=models.CASCADE, related_name='declared_professions')
    profession = models.ForeignKey(Profession, on_delete=models.PROTECT)
    declared_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['profile', 'profession'], name='volunteer_profession_once')]


class AvailabilitySlot(models.Model):
    DAYS = [(0, 'Lunes'), (1, 'Martes'), (2, 'Miércoles'), (3, 'Jueves'), (4, 'Viernes'), (5, 'Sábado'), (6, 'Domingo')]
    profile = models.ForeignKey('accounts.VolunteerProfile', on_delete=models.CASCADE, related_name='availability_slots')
    weekday = models.PositiveSmallIntegerField(choices=DAYS)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ['weekday', 'start_time']
        constraints = [
            models.CheckConstraint(condition=models.Q(weekday__gte=0, weekday__lte=6), name='availability_valid_weekday'),
            models.CheckConstraint(condition=models.Q(start_time__lt=models.F('end_time')), name='availability_positive_duration'),
            models.UniqueConstraint(fields=['profile', 'weekday', 'start_time', 'end_time'], name='availability_slot_once'),
        ]


class UnavailableDate(models.Model):
    profile = models.ForeignKey('accounts.VolunteerProfile', on_delete=models.CASCADE, related_name='unavailable_dates')
    date = models.DateField()

    class Meta:
        ordering = ['date']
        constraints = [models.UniqueConstraint(fields=['profile', 'date'], name='unavailable_date_once')]
