from datetime import datetime, timezone
from django.db import migrations


def initialize(apps, schema_editor):
    alias = schema_editor.connection.alias
    apps.get_model('activities', 'MatchingPolicy').objects.using(alias).get_or_create(pk=1)
    apps.get_model('activities', 'GeocodingGate').objects.using(alias).get_or_create(
        pk=1, defaults={'next_request_at':datetime(1970, 1, 1, tzinfo=timezone.utc)})


class Migration(migrations.Migration):
    dependencies = [('activities', '0007_contactchange_contactinvitation_geocodinggate_and_more')]
    operations = [migrations.RunPython(initialize, migrations.RunPython.noop)]
