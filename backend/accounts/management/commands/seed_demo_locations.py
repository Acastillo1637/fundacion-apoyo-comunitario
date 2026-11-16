"""Add explicitly synthetic reference locations to the existing community demo."""
import json
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import AuditEvent, VolunteerProfile
from .seed_community_demo import BATCH, DOMAIN, VOLUNTEERS, identifier


# Synthetic points near each commune, not geocoded homes or verified addresses.
CENTERS = {
    'Maipú': (-33.51, -70.76), 'Estación Central': (-33.46, -70.70),
    'Puente Alto': (-33.61, -70.58), 'La Florida': (-33.52, -70.60),
    'San Miguel': (-33.49, -70.65), 'Peñalolén': (-33.48, -70.54),
    'Santiago': (-33.45, -70.66), 'San Bernardo': (-33.59, -70.70),
    'Ñuñoa': (-33.46, -70.60), 'Cerrillos': (-33.50, -70.72),
    'Macul': (-33.49, -70.60),
}


class Command(BaseCommand):
    help = 'Añade referencias ficticias a perfiles del lote community-demo-v1 sin ubicación.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Solo disponible en desarrollo.')
        rows = {identifier('user', row[2]): (index, row) for index, row in enumerate(VOLUNTEERS)}
        with transaction.atomic():
            profiles = list(VolunteerProfile.objects.select_for_update().select_related('user').filter(
                user_id__in=rows, notice_version=BATCH, reference_latitude__isnull=True,
                reference_longitude__isnull=True).order_by('pk'))
            changes = []
            for profile in profiles:
                index, row = rows[profile.user_id]
                if profile.user.email != f'{row[2]}@{DOMAIN}' or profile.commune != row[3]:
                    continue
                lat, lon = CENTERS[row[3]]
                lat = Decimal(str(lat)) + Decimal(index % 3 - 1) / 100
                lon = Decimal(str(lon)) + Decimal((index // 3) % 3 - 1) / 100
                changes.append((profile, lat, lon, f'DEMO: Pasaje Encuentro Ficticio {100 + index * 17}'))
            self.stdout.write(f'Perfiles ficticios sin ubicación: {len(changes)}. No se cambian referencias existentes.')
            if not options['apply'] or not changes:
                return
            folder = settings.BASE_DIR.parent / 'backups' / 'demo-locations'
            folder.mkdir(parents=True, exist_ok=True)
            backup = folder / (timezone.now().strftime('%Y%m%dT%H%M%S%f') + '.json')
            backup.write_text(json.dumps([{'id': p.pk, 'sector': p.sector,
                'location_revision': p.location_revision, 'latitude': None, 'longitude': None}
                for p, *_ in changes], ensure_ascii=False), encoding='utf-8')
            for profile, lat, lon, sector in changes:
                profile.reference_latitude, profile.reference_longitude = lat, lon
                profile.sector = sector
                profile.location_revision += 1
                profile.save(update_fields=['reference_latitude', 'reference_longitude', 'sector', 'location_revision'])
                AuditEvent.objects.create(action='demo.location.assigned', resource=f'profile:{profile.pk}')
            self.stdout.write(self.style.SUCCESS(f'Referencias ficticias guardadas: {len(changes)}. Respaldo privado creado.'))
