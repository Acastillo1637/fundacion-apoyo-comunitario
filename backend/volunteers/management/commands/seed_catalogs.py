from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from volunteers.models import DocumentType, Profession, Skill


class Command(BaseCommand):
    help = 'Añade ejemplos editables en desarrollo, sin usuarios ni datos personales.'

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Los catálogos de ejemplo solo se cargan en desarrollo.')
        for name in ['Recreación', 'Fotografía', 'Pintura', 'Primeros auxilios']:
            Skill.objects.get_or_create(name__iexact=name, defaults={'name': name})
        document, _ = DocumentType.objects.get_or_create(name__iexact='Respaldo de título profesional', defaults={'name': 'Respaldo de título profesional'})
        profession, created = Profession.objects.get_or_create(name__iexact='Enfermería', defaults={'name': 'Enfermería'})
        if created:
            profession.required_documents.add(document)
        Profession.objects.get_or_create(name__iexact='Otro oficio', defaults={'name': 'Otro oficio'})
        self.stdout.write(self.style.SUCCESS('Ejemplos cargados. Son editables; la fundación debe definir los requisitos reales.'))
