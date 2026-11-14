"""An additive, explicit synthetic scenario for manual matching demonstrations."""
from datetime import timedelta
from io import BytesIO
import json
import secrets
from uuid import NAMESPACE_URL, uuid5

from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from accounts.models import AuditEvent, User, VolunteerProfile
from activities.models import Event, EventPosition, ServiceRequest
from documents.models import VolunteerDocument
from documents.storage import private_storage, save_file
from volunteers.models import AvailabilitySlot, DocumentType, Skill, VolunteerSkill

BATCH = 'matching-map-demo-v1'
TITLE = 'DEMO — Preparación de kits comunitarios y encuentro vecinal'
PEOPLE = [
    ('Camila Antonia', 'Méndez Salinas', 'camila.matching', '-33.44', '-70.65', 2),
    ('Diego Felipe', 'Araya Contreras', 'diego.matching', '-33.46', '-70.66', 1),
    ('Valentina Isabel', 'Ríos Morales', 'valentina.matching', '-33.50', '-70.70', 0),
]


def identity(value):
    return uuid5(NAMESPACE_URL, f'fundacion:{BATCH}:{value}')


def demo_pdf():
    # A readable test sheet, explicitly not a professional certificate.
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
    writer = PdfWriter()
    page = writer.add_blank_page(width=595, height=842)
    font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
        NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
    page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'):
        DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
    content = DecodedStreamObject()
    content.set_data(b'BT /F1 18 Tf 40 770 Td (DEMO - DOCUMENTO FICTICIO SIN VALIDEZ) Tj '
        b'0 -35 Td /F1 12 Tf (Induccion sintetica para probar requisitos y matching.) Tj '
        b'0 -25 Td (No acredita formacion, identidad ni revision humana real.) Tj ET')
    page[NameObject('/Contents')] = writer._add_object(content)
    stream = BytesIO(); writer.write(stream)
    return stream.getvalue()


class Command(BaseCommand):
    help = 'Crea una convocatoria futura y tres candidatos completos; solo desarrollo, sin envíos.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Solo se permiten datos sintéticos en desarrollo.')
        if not options['apply']:
            self.stdout.write('Plan: una convocatoria abierta con dos cupos, tres voluntarios, referencias geográficas y documentos DEMO aprobados. Sin teléfonos, consentimientos WhatsApp ni envíos.')
            return
        receipt = settings.BASE_DIR.parent / 'backups' / BATCH / 'access.json'
        created_files = []
        try:
            with transaction.atomic():
                if connection.vendor == 'postgresql':
                    with connection.cursor() as cursor:
                        cursor.execute('SELECT pg_advisory_xact_lock(%s)', [942615032])
                if AuditEvent.objects.filter(action='demo.seed.completed', resource=BATCH).exists():
                    self.stdout.write(f'El lote ya existe. No se modificaron datos. Accesos privados: {receipt}')
                    return
                emails = [f'{person[2]}@demo.example.org' for person in PEOPLE]
                if User.objects.filter(email__in=emails).exists():
                    raise CommandError('Colisión con una cuenta existente. No se sobrescribe.')
                group = Group.objects.get(name='Voluntario')
                now = timezone.now()
                start = (timezone.localtime(now) + timedelta(days=7)).replace(hour=10, minute=0, second=0, microsecond=0)
                end = start + timedelta(hours=3)
                required, _ = Skill.objects.get_or_create(name='DEMO — Preparación de kits', defaults={'description':'Habilidad ficticia del escenario de matching.'})
                desired = [Skill.objects.get_or_create(name=name)[0] for name in ['DEMO — Acogida comunitaria', 'DEMO — Organización de materiales']]
                document_type, _ = DocumentType.objects.get_or_create(name='DEMO — Constancia de inducción (sin validez)', defaults={'description':'Documento sintético; no corresponde a una certificación real.'})
                source = ServiceRequest.objects.create(id=identity('request'), submission_id=identity('submission'),
                    requester_type='institution', contact_name='Contacto ficticio del escenario DEMO',
                    organization='Entidad ficticia de demostración', email='contacto.matching@demo.example.org', phone='',
                    description='Solicitud sintética para probar matching, mapas, invitaciones, cupos y reemplazos.',
                    quantity=2, starts_at=start, ends_at=end, address='Referencia pública: Plaza de Armas, Santiago. No asistir; solo DEMO.',
                    commune='Santiago', privacy_accepted_at=now, status='approved', email_verified_at=now,
                    observations='Verificación y aprobación sintéticas. No es una solicitud real.')
                event = Event.objects.create(id=identity('event'), request=source, title=TITLE,
                    public_description='Actividad ficticia para probar recomendaciones, mapa e invitaciones. No corresponde a una convocatoria real ni se debe asistir al lugar.',
                    internal_notes=f'Lote {BATCH}. Datos y aprobaciones documentales sintéticos. Sin contactos externos.',
                    starts_at=start, ends_at=end, address=source.address, commune='Santiago', status='open',
                    latitude='-33.437200', longitude='-70.650600')
                position = EventPosition.objects.create(event=event, name='Apoyo comunitario DEMO', capacity=2)
                position.required_skills.add(required); position.desired_skills.set(desired)
                position.required_documents.add(document_type)
                accounts = []
                content = demo_pdf()
                for first, last, local, lat, lon, matches in PEOPLE:
                    password = secrets.token_urlsafe(18)
                    user = User.objects.create_user(email=f'{local}@demo.example.org', password=password,
                        id=identity(local), first_name=first, last_name=last)
                    user.groups.add(group)
                    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
                    profile = VolunteerProfile.objects.create(user=user, commune='Santiago', sector='Referencia sintética DEMO',
                        reference_latitude=lat, reference_longitude=lon, adult_confirmed_at=now,
                        privacy_accepted_at=now, notice_version='synthetic-matching-demo')
                    VolunteerSkill.objects.bulk_create([VolunteerSkill(profile=profile, skill=skill) for skill in [required, *desired[:matches]]])
                    AvailabilitySlot.objects.create(profile=profile, weekday=start.weekday(), start_time=start.time(), end_time=end.time())
                    key, checksum = save_file(content, '.pdf'); created_files.append(key)
                    VolunteerDocument.objects.create(profile=profile, document_type=document_type, version=1,
                        storage_key=key, checksum=checksum, size=len(content), mime_type='application/pdf',
                        scan_status='not_scanned', status='validated', reviewed_at=now,
                        expires_on=start.date()+timedelta(days=90),
                        observation='APROBACIÓN SINTÉTICA DE DEMOSTRACIÓN. Sin revisión humana real ni validez documental.')
                    accounts.append({'name':user.get_full_name(), 'email':user.email, 'password':password, 'profile_id':profile.pk})
                receipt.parent.mkdir(parents=True, exist_ok=True)
                receipt.write_text(json.dumps({'batch':BATCH,'event_id':str(event.pk),'title':TITLE,
                    'date':start.isoformat(),'position_id':position.pk,'accounts':accounts},ensure_ascii=False,indent=2), encoding='utf-8')
                AuditEvent.objects.create(action='demo.seed.completed', resource=BATCH)
        except Exception:
            for key in created_files:
                private_storage().delete(key)
            raise
        self.stdout.write(f'Creada: {TITLE}\nFecha: {start:%d-%m-%Y %H:%M}–{end:%H:%M} (Santiago)\nTres candidatos completos, dos cupos. Accesos privados: {receipt}')
