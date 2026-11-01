from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Crea grupos base sin asignar usuarios ni permisos globales.'

    @transaction.atomic
    def handle(self, *args, **options):
        Group.objects.get_or_create(name='Voluntario')
        permission = Permission.objects.get(content_type__app_label='accounts', codename='view_volunteerprofile')
        for name in ['Secretaría', 'Administrador general']:
            group, _ = Group.objects.get_or_create(name=name)
            group.permissions.add(permission)
        catalogs = Permission.objects.filter(
            content_type__app_label='volunteers',
            content_type__model__in=['skill', 'profession', 'documenttype'],
            codename__in=[f'{operation}_{model}' for operation in ['add', 'change', 'view'] for model in ['skill', 'profession', 'documenttype']],
        )
        Group.objects.get(name='Administrador general').permissions.add(*catalogs)
        self.stdout.write(self.style.SUCCESS('Roles base creados. Nuevos módulos agregarán permisos explícitos.'))
