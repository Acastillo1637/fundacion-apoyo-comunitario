"""Keep the mandatory credential even through admin forms and M2M edits."""
from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver

from .models import DocumentType, Profession, Skill

DEGREE_NAME = 'Respaldo de título profesional'
SKILL_DOCUMENTS = {
    'primeros auxilios': [('Certificado de primeros auxilios', False)],
    'apoyo escolar': [('Certificado de antecedentes', True),
        ('Consulta de inhabilidades para trabajar con menores de edad', True)],
}


def ensure_degree(profession, using):
    if profession.kind == Profession.Kind.OTHER:
        return
    document, _ = DocumentType.objects.using(using).get_or_create(
        name__iexact=DEGREE_NAME, defaults={'name': DEGREE_NAME,
            'description': 'Título profesional o técnico correspondiente a la formación declarada.'})
    if not profession.required_documents.filter(pk=document.pk).exists():
        profession.required_documents.add(document)


@receiver(post_save, sender=Profession)
def profession_saved(sender, instance, using, raw=False, **kwargs):
    if not raw:
        ensure_degree(instance, using)


def ensure_skill_requirements(skill, using):
    for name, safeguarding in SKILL_DOCUMENTS.get(skill.name.strip().casefold(), []):
        document, _ = DocumentType.objects.using(using).get_or_create(name__iexact=name,
            defaults={'name': name, 'requires_safeguarding_review': safeguarding})
        if safeguarding and not document.requires_safeguarding_review:
            DocumentType.objects.using(using).filter(pk=document.pk).update(requires_safeguarding_review=True)
        if not skill.required_documents.filter(pk=document.pk).exists():
            skill.required_documents.add(document)


@receiver(post_save, sender=Skill)
def skill_saved(sender, instance, using, raw=False, **kwargs):
    if not raw:
        ensure_skill_requirements(instance, using)


@receiver(m2m_changed, sender=Skill.required_documents.through)
def skill_requirements_changed(sender, instance, action, reverse, using, **kwargs):
    if action == 'pre_clear' and reverse:
        instance._safeguarding_skill_ids = list(instance.skill_set.values_list('pk', flat=True))
    if action not in ['post_remove', 'post_clear']:
        return
    if reverse:
        ids = kwargs.get('pk_set') if action == 'post_remove' else getattr(instance, '_safeguarding_skill_ids', [])
        for skill in Skill.objects.using(using).filter(pk__in=ids):
            ensure_skill_requirements(skill, using)
    else:
        ensure_skill_requirements(instance, using)


@receiver(m2m_changed, sender=Profession.required_documents.through)
def profession_requirements_changed(sender, instance, action, reverse, using, **kwargs):
    if action == 'pre_clear' and reverse:
        instance._degree_profession_ids = list(instance.profession_set.values_list('pk', flat=True))
    if action not in ['post_remove', 'post_clear']:
        return
    if reverse:
        ids = kwargs.get('pk_set') if action == 'post_remove' else getattr(instance, '_degree_profession_ids', [])
        for profession in Profession.objects.using(using).filter(pk__in=ids):
            ensure_degree(profession, using)
    else:
        ensure_degree(instance, using)
