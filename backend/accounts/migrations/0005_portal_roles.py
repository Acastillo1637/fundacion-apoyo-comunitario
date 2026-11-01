from django.db import migrations


def assign_legacy_volunteers(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    User = apps.get_model('accounts', 'User')
    Profile = apps.get_model('accounts', 'VolunteerProfile')
    alias = schema_editor.connection.alias
    volunteer, _ = Group.objects.using(alias).get_or_create(name='Voluntario')
    Group.objects.using(alias).get_or_create(name='Solicitante')
    # Preserve real volunteers while avoiding accidental staff volunteer spaces.
    for user in User.objects.using(alias).filter(pk__in=Profile.objects.using(alias).values('user_id'), is_staff=False, is_superuser=False):
        if not user.groups.exists() and not user.user_permissions.exists():
            user.groups.add(volunteer)


class Migration(migrations.Migration):
    dependencies = [('accounts', '0004_requesterprofile')]
    operations = [migrations.RunPython(assign_legacy_volunteers, migrations.RunPython.noop)]
