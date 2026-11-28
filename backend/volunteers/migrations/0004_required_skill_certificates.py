from django.db import migrations


def apply_rules(apps, schema_editor):
    alias = schema_editor.connection.alias
    Skill = apps.get_model('volunteers', 'Skill')
    DocumentType = apps.get_model('volunteers', 'DocumentType')
    rules = {
        'Primeros auxilios': [('Certificado de primeros auxilios', False)],
        'Apoyo escolar': [('Certificado de antecedentes', True),
            ('Consulta de inhabilidades para trabajar con menores de edad', True)],
    }
    for name, documents in rules.items():
        skill = Skill.objects.using(alias).filter(name__iexact=name).first()
        if skill is None:
            continue
        for title, safeguarding in documents:
            document, _ = DocumentType.objects.using(alias).get_or_create(name__iexact=title, defaults={'name': title})
            if safeguarding:
                DocumentType.objects.using(alias).filter(pk=document.pk).update(requires_safeguarding_review=True)
            skill.required_documents.add(document)


class Migration(migrations.Migration):
    dependencies = [('volunteers', '0003_documenttype_requires_safeguarding_review'),
                    ('documents', '0002_volunteerdocument_safeguarding_confirmed')]
    operations = [migrations.RunPython(apply_rules, migrations.RunPython.noop)]
