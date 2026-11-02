"""Explicit, repeat-safe synthetic data for the shared development environment."""
from datetime import datetime, time, timedelta
import json
import secrets
from uuid import NAMESPACE_URL, uuid5

from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from accounts.models import AuditEvent, RequesterProfile, User, VolunteerProfile
from activities.models import Event, EventPosition, EventTransition, Notification, Participation, RequestTransition, ServiceRequest
from volunteers.models import AvailabilitySlot, Profession, Skill, VolunteerProfession, VolunteerSkill


BATCH = 'community-demo-v1'
DOMAIN = 'demo.example.org'
VOLUNTEERS = [
    ('Camila Ignacia', 'Rojas Fuentes', 'camila.rojas', 'Maipú', 'Trabajo social'),
    ('Diego Andrés', 'Muñoz Araya', 'diego.munoz', 'Estación Central', 'Técnico en mantenimiento'),
    ('Valentina Paz', 'Soto Contreras', 'valentina.soto', 'Puente Alto', 'Educación diferencial'),
    ('Nicolás Ignacio', 'Herrera Díaz', 'nicolas.herrera', 'La Florida', 'Administración'),
    ('Francisca Belén', 'Morales Vega', 'francisca.morales', 'San Miguel', 'Diseño gráfico'),
    ('Matías Alejandro', 'Castro Navarro', 'matias.castro', 'Maipú', 'Ingeniería en informática'),
    ('Javiera Constanza', 'Pérez Leiva', 'javiera.perez', 'Peñalolén', 'Pedagogía'),
    ('Sebastián Felipe', 'Torres Silva', 'sebastian.torres', 'Santiago', 'Técnico en electricidad'),
    ('Catalina Antonia', 'Vargas Riquelme', 'catalina.vargas', 'Puente Alto', 'Trabajo social'),
    ('Felipe Esteban', 'González Bravo', 'felipe.gonzalez', 'San Bernardo', 'Administración'),
    ('Daniela Andrea', 'Sepúlveda Reyes', 'daniela.sepulveda', 'La Florida', 'Enfermería'),
    ('Tomás Vicente', 'Espinoza Lagos', 'tomas.espinoza', 'Ñuñoa', 'Fotografía'),
    ('Paula Fernanda', 'Carrasco Molina', 'paula.carrasco', 'Peñalolén', 'Psicología'),
    ('Ignacio Javier', 'Alarcón Vidal', 'ignacio.alarcon', 'Cerrillos', 'Técnico en logística'),
    ('Antonia Josefa', 'Reyes Cortés', 'antonia.reyes', 'Macul', 'Pedagogía'),
    ('Cristóbal Andrés', 'Vera Salazar', 'cristobal.vera', 'Santiago', 'Técnico en construcción'),
    ('Marcela Alejandra', 'Navarrete Mena', 'marcela.navarrete', 'San Miguel', 'Administración'),
    ('Rodrigo Patricio', 'Valenzuela Pinto', 'rodrigo.valenzuela', 'Maipú', 'Técnico en mantenimiento'),
]
REQUESTERS = [
    ('Verónica Isabel', 'Fuentes Muñoz', 'veronica.fuentes', 'La Florida', 'institution', 'Agrupación Vecinal Encuentro Sur'),
    ('Andrés Felipe', 'Molina Rivas', 'andres.molina', 'Maipú', 'company', 'Servicios y Oficios El Encuentro'),
    ('Claudia Patricia', 'Sanhueza Ortiz', 'claudia.sanhueza', 'Puente Alto', 'institution', 'Red Comunitaria Barrio Abierto'),
]
SKILLS = ['Recreación', 'Pintura', 'Fotografía', 'Apoyo logístico', 'Acompañamiento comunitario', 'Apoyo escolar']
EVENTS = [
    ('Recuperación de espacios verdes en el barrio', 'Maipú', 0, 9, 13, 'open', 'Pintura',
     'Jornada comunitaria para recuperar jardineras, pintar bancas y ordenar un espacio de encuentro vecinal. Se trabajará en equipos con materiales proporcionados por la organización.'),
    ('Lectura y juegos para compartir en familia', 'Puente Alto', 1, 10, 13, 'open', 'Recreación',
     'Encuentro de lectura compartida y juegos cooperativos para familias del sector. Buscamos apoyo en la preparación de materiales, acogida y acompañamiento de las dinámicas.'),
    ('Encuentro de acompañamiento a personas mayores', 'La Florida', 7, 9, 13, 'open', 'Acompañamiento comunitario',
     'Mañana de conversación, actividades recreativas y orientación comunitaria para personas mayores. Las tareas son de acompañamiento y coordinación, sin prestaciones clínicas.'),
    ('Clasificación y preparación de kits comunitarios', 'Estación Central', 8, 15, 18, 'open', 'Apoyo logístico',
     'Organización de insumos y preparación de kits de apoyo para iniciativas barriales. Se requiere atención al detalle y disposición para trabajar de manera colaborativa.'),
    ('Taller de apoyo escolar y hábitos de estudio', 'Peñalolén', 14, 10, 13, 'draft', 'Apoyo escolar',
     'Preparación de un espacio de apoyo escolar con actividades de organización del estudio y lectura. La coordinación definirá los requisitos antes de abrir la convocatoria.'),
    ('Jornada de limpieza y encuentro vecinal', 'San Miguel', -14, 9, 13, 'finished', 'Apoyo logístico',
     'Actividad comunitaria de limpieza de espacios compartidos y encuentro entre vecinos. Los equipos colaboraron en la organización de materiales y el cierre de la jornada.'),
]


def identifier(kind, value):
    return uuid5(NAMESPACE_URL, f'fundacion:{BATCH}:{kind}:{value}')


class Command(BaseCommand):
    help = 'Prepara datos ficticios verosimiles; solo escribe con --apply y DEBUG activo.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Los datos de demostracion solo se crean en desarrollo.')
        if AuditEvent.objects.filter(action='demo.seed.completed', resource=BATCH).exists():
            self.stdout.write('El lote de demostracion ya existe. No se duplico ni modifico nada.')
            return
        if not options['apply']:
            self.stdout.write('Plan: 18 voluntarios, 3 solicitantes, 1 coordinadora, 6 eventos y 2 solicitudes adicionales. Sin envios externos.')
            self.stdout.write('Las credenciales aleatorias se guardaran solo en backups/. Usa --apply para crear los datos.')
            return
        receipt_dir = settings.BASE_DIR.parent / 'backups' / f'demo-community-{timezone.now():%Y%m%dT%H%M%S}'
        with transaction.atomic():
            if connection.vendor == 'postgresql':
                with connection.cursor() as cursor:
                    cursor.execute('SELECT pg_advisory_xact_lock(%s)', [942615031])
            if AuditEvent.objects.filter(action='demo.seed.completed', resource=BATCH).exists():
                self.stdout.write('El lote ya fue creado por otra sesion. Sin cambios.')
                return
            now = timezone.now()
            today = timezone.localdate()
            saturday = today + timedelta(days=(5 - today.weekday()) % 7 or 7)
            rows = [(*row[:4], 'Voluntario') for row in VOLUNTEERS] + [(*row[:4], 'Solicitante') for row in REQUESTERS]
            rows.append(('Carolina Beatriz', 'Valdés Pizarro', 'carolina.valdes', 'Santiago', 'Secretaría'))
            emails = [f'{row[2]}@{DOMAIN}' for row in rows]
            if User.objects.filter(email__in=emails).exists():
                raise CommandError('Hay una cuenta con un correo reservado del lote. No se sobrescribio nada.')
            users, credentials = [], []
            self.stdout.write('Preparando cuentas ficticias y credenciales privadas...')
            self.stdout.flush()
            for first, last, local, commune, role in rows:
                password = secrets.token_urlsafe(24)
                user = User(id=identifier('user', local), email=f'{local}@{DOMAIN}', first_name=first, last_name=last, is_active=True, is_staff=False)
                user.set_password(password)
                users.append(user)
                credentials.append({'name': user.get_full_name(), 'email': user.email, 'password': password, 'role': role})
            User.objects.bulk_create(users)
            groups = {name: Group.objects.get(name=name) for name in ['Voluntario', 'Solicitante', 'Secretaría']}
            User.groups.through.objects.bulk_create([User.groups.through(user_id=user.pk, group_id=groups[row[4]].pk) for user, row in zip(users, rows)])
            EmailAddress.objects.bulk_create([EmailAddress(user=user, email=user.email, verified=True, primary=True) for user in users])
            coordinator = users[-1]
            profiles = [VolunteerProfile(user=user, commune=row[3], phone='', adult_confirmed_at=now,
                privacy_accepted_at=now, notice_version=BATCH) for user, row in zip(users[:18], VOLUNTEERS)]
            VolunteerProfile.objects.bulk_create(profiles)
            self.stdout.write('Cuentas creadas. Preparando perfiles y disponibilidad...')
            self.stdout.flush()
            skills = {}
            for name in SKILLS:
                skill, _ = Skill.objects.get_or_create(name=name)
                if not skill.is_active:
                    raise CommandError('Un catalogo necesario esta inactivo. No se modificaron datos existentes.')
                skills[name] = skill
            requirements = {skill.pk: skill.required_documents.exists() for skill in skills.values()}
            professions = {name: Profession.objects.get_or_create(name=name)[0] for name in {row[4] for row in VOLUNTEERS}}
            declarations, availability = [], []
            declared_names, profile_slots, commitments = {}, {}, []
            for index, (profile, row) in enumerate(zip(profiles, VOLUNTEERS)):
                chosen = {SKILLS[index % len(SKILLS)], SKILLS[(index + 1) % len(SKILLS)], 'Apoyo logístico'}
                declared_names[profile.pk] = chosen
                declarations += [VolunteerSkill(profile=profile, skill=skills[name]) for name in chosen]
                VolunteerProfession.objects.create(profile=profile, profession=professions[row[4]])
                days = [[5, 6], [1, 3, 5], [0, 2, 4, 5, 6]][index % 3]
                start, end = [(time(8, 30), time(14)), (time(14), time(19)), (time(8, 30), time(19)), (time(9), time(18))][index % 4]
                profile_slots[profile.pk] = [AvailabilitySlot(profile=profile, weekday=day, start_time=start, end_time=end) for day in days]
                availability += profile_slots[profile.pk]
            VolunteerSkill.objects.bulk_create(declarations)
            AvailabilitySlot.objects.bulk_create(availability)
            owners = []
            for user, row in zip(users[18:21], REQUESTERS):
                owners.append(RequesterProfile.objects.create(user=user, commune=row[3], requester_type=row[4], organization=row[5],
                    phone='+56 0 0000 0000', adult_confirmed_at=now, privacy_accepted_at=now, representative_confirmed_at=now, notice_version=BATCH))
            event_results = []
            for index, (title, commune, offset, start_hour, end_hour, status, skill_name, description) in enumerate(EVENTS):
                day = saturday + timedelta(days=offset)
                start = timezone.make_aware(datetime.combine(day, time(start_hour)))
                end = timezone.make_aware(datetime.combine(day, time(end_hour)))
                owner = owners[index % len(owners)]
                source = ServiceRequest.objects.create(id=identifier('request', index), submission_id=identifier('submission', index), requester=owner,
                    requester_type=owner.requester_type, contact_name=owner.user.get_full_name(), organization=owner.organization,
                    email=owner.user.email, phone=owner.phone, description=description, quantity=5, starts_at=start, ends_at=end,
                    address=f'Espacio comunitario de {commune}; ubicacion referencial de demostracion', commune=commune,
                    observations=f'Datos sinteticos de presentacion. Lote {BATCH}. Sin personas beneficiarias reales.',
                    email_verified_at=now, privacy_accepted_at=now, status='approved', revision=2)
                source.skills.add(skills[skill_name])
                RequestTransition.objects.bulk_create([
                    RequestTransition(request=source, actor=coordinator, from_status='pending', to_status='in_review', reason='Escenario de demostracion: antecedentes revisados.'),
                    RequestTransition(request=source, actor=coordinator, from_status='in_review', to_status='approved', reason='Escenario de demostracion: solicitud aprobada.')])
                event = Event.objects.create(id=identifier('event', index), request=source, title=title, public_description=description,
                    starts_at=start, ends_at=end, address=source.address, commune=commune, status=status,
                    internal_notes=f'Escenario ficticio para demostracion. Lote {BATCH}. No representa una actividad ni una alianza real.', revision=0 if status == 'draft' else 1)
                main = EventPosition.objects.create(event=event, name='Apoyo a la actividad', capacity=2)
                main.required_skills.add(skills[skill_name])
                support = EventPosition.objects.create(event=event, name='Acogida y organización de materiales', capacity=3)
                if status != 'draft':
                    EventTransition.objects.create(event=event, actor=coordinator, from_status='draft', to_status='open', reason='Publicacion ficticia para demostracion.')
                    if status == 'finished':
                        EventTransition.objects.create(event=event, actor=coordinator, from_status='open', to_status='finished', reason='Escenario historico de demostracion.')
                    used = set()
                    for position, assignment, state in [(main, 'primary', 'confirmed'), (main, 'primary', 'confirmed'),
                            (main, 'backup', 'confirmed'), (main, 'primary', 'waitlisted'),
                            (support, 'primary', 'applied'), (support, 'primary', 'invited'), (support, 'primary', 'confirmed')]:
                        # All these profiles belong to this new, synthetic batch.
                        # Compare the same required skill, schedule and primary-overlap rules in memory.
                        required = skill_name if position.pk == main.pk else None
                        pool = [profile for profile in profiles if profile.pk not in used
                            and (not required or (required in declared_names[profile.pk] and not requirements[skills[required].pk]))
                            and any(slot.weekday == day.weekday() and slot.start_time <= start.time() and slot.end_time >= end.time() for slot in profile_slots[profile.pk])
                            and not any(profile.pk == person and begin < end and finish > start for person, begin, finish in commitments)]
                        if not pool:
                            continue
                        profile = pool[0]
                        used.add(profile.pk)
                        if status == 'finished' and (assignment == 'backup' or state != 'confirmed'):
                            continue
                        Participation.objects.create(event=event, position=position, profile=profile, assignment=assignment, status=state,
                            expires_at=min(now + timedelta(hours=48), start) if state == 'invited' else None,
                            attendance='present' if status == 'finished' and assignment == 'primary' and state == 'confirmed' else '')
                        if assignment == 'primary' and state == 'confirmed':
                            commitments.append((profile.pk, start, end))
                    if index == 0:
                        cancelled = event.participations.filter(assignment='primary', status='confirmed').first()
                        if cancelled:
                            cancelled.status = 'cancelled'
                            cancelled.revision += 1
                            cancelled.save(update_fields=['status', 'revision'])
                    if status == 'open':
                        for participation in event.participations.filter(status='invited').select_related('profile'):
                            Notification.objects.create(user=participation.profile.user, target='participations',
                                message=f'Tienes una invitacion para {event.title}. Escenario de demostracion: revisala desde tu espacio.')
                event_results.append({'title': title, 'date': str(day), 'status': status, 'participants': event.participations.count()})
                self.stdout.write(f'Escenario preparado: {title}')
                self.stdout.flush()
            for index, state in enumerate(['pending', 'in_review'], 6):
                owner = owners[index % len(owners)]
                start = timezone.make_aware(datetime.combine(saturday + timedelta(days=21 + index), time(10)))
                item = ServiceRequest.objects.create(id=identifier('request', index), submission_id=identifier('submission', index), requester=owner,
                    requester_type=owner.requester_type, organization=owner.organization, contact_name=owner.user.get_full_name(),
                    email=owner.user.email, phone=owner.phone, description=['Apoyo para organizar una jornada de intercambio de libros y materiales escolares.',
                    'Colaboración en la preparación de un encuentro barrial de oficios y emprendimientos.'][index - 6],
                    quantity=4 + index - 6, starts_at=start, ends_at=start + timedelta(hours=3), address='Centro comunitario; ubicacion referencial',
                    commune=owner.commune, status=state, revision=int(state == 'in_review'), email_verified_at=now,
                    privacy_accepted_at=now, observations=f'Solicitud sintetica del lote {BATCH}.')
                if state == 'in_review':
                    RequestTransition.objects.create(request=item, actor=coordinator, from_status='pending', to_status='in_review', reason='Escenario de revision de demostracion.')
            receipt_dir.mkdir(parents=True, exist_ok=False)
            access = receipt_dir / 'access.json'
            access.write_text(json.dumps({'synthetic': True, 'batch': BATCH, 'accounts': credentials}, ensure_ascii=False, indent=2), encoding='utf-8')
            (receipt_dir / 'manifest.json').write_text(json.dumps({'batch': BATCH, 'synthetic': True, 'events': event_results}, ensure_ascii=False, indent=2), encoding='utf-8')
            AuditEvent.objects.create(actor=None, action='demo.seed.completed', resource=BATCH)
        self.stdout.write(self.style.SUCCESS('Creados: 22 usuarios ficticios, 6 eventos y 8 solicitudes, con perfiles y participaciones.'))
        self.stdout.write(f'Credenciales privadas (no publicarlas): {receipt_dir / "access.json"}')
        self.stdout.write(json.dumps(event_results, ensure_ascii=True))
