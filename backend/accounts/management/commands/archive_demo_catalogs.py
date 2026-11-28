"""Retire synthetic catalogues without deleting users, files or audit history."""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F
from uuid import NAMESPACE_URL, uuid5

from accounts.models import AuditEvent
from activities.models import Event
from volunteers.models import DocumentType, Skill


class Command(BaseCommand):
    help = 'Desactiva entradas DEMO para que no se ofrezcan en las selecciones nuevas. Conserva usuarios e historial.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        skills = Skill.objects.filter(name__istartswith='DEMO — ', is_active=True)
        documents = DocumentType.objects.filter(name__istartswith='DEMO — ', is_active=True)
        batch = 'matching-map-demo-v1'
        event_id = uuid5(NAMESPACE_URL, f'fundacion:{batch}:event')
        events = Event.objects.filter(pk=event_id, title__startswith='DEMO — ', status__in=['draft', 'open'])
        if not AuditEvent.objects.filter(action='demo.seed.completed', resource=batch).exists():
            events = events.none()
        plan = f'{skills.count()} habilidades, {documents.count()} tipos documentales DEMO y {events.count()} convocatoria sintética. Se conservan todas las cuentas, archivos e historial.'
        if not options['apply']:
            self.stdout.write('Vista previa: '+plan)
            return
        with transaction.atomic():
            for event in events.select_for_update():
                event.participations.filter(status__in=['applied', 'invited', 'confirmed', 'waitlisted']).update(status='cancelled', revision=F('revision')+1)
                event.status = 'cancelled'
                event.revision += 1
                event.save(update_fields=['status', 'revision'])
                AuditEvent.objects.create(action='event.demo.archived', resource=f'event:{event.pk}')
            skill_ids = list(skills.select_for_update().values_list('pk', flat=True))
            document_ids = list(documents.select_for_update().values_list('pk', flat=True))
            skills.update(is_active=False)
            documents.update(is_active=False)
            if skill_ids or document_ids:
                AuditEvent.objects.create(action='catalog.demo.archived',
                    resource=f'skills:{skill_ids};documents:{document_ids}')
        self.stdout.write('Archivadas: '+plan)
