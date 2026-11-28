from django.test import TestCase

from .models import DocumentType, Profession, Skill
from .tests import make_profile


class CredentialRulesTests(TestCase):
    def test_new_profession_keeps_title_after_requirement_edits(self):
        profession = Profession.objects.create(name='Diseño gráfico')
        title = profession.required_documents.get()
        self.assertEqual(title.name, 'Respaldo de título profesional')
        for change in [lambda: profession.required_documents.clear(),
                       lambda: profession.required_documents.remove(title),
                       lambda: profession.required_documents.set([]),
                       lambda: title.profession_set.clear()]:
            change()
            self.assertTrue(profession.required_documents.filter(pk=title.pk).exists())

    def test_safety_skills_keep_required_certificates(self):
        for name, count in [('Primeros auxilios', 1), ('Apoyo escolar', 2)]:
            skill, _ = Skill.objects.get_or_create(name=name)
            skill.required_documents.clear()
            self.assertEqual(skill.required_documents.count(), count)
            for document in skill.required_documents.all():
                document.skill_set.remove(skill)
                self.assertTrue(skill.required_documents.filter(pk=document.pk).exists())

    def test_other_trade_requires_text_and_persists_without_degree(self):
        profile = make_profile('oficio@example.org')
        self.client.force_login(profile.user)
        other, _ = Profession.objects.get_or_create(name='Otro oficio', defaults={'kind': 'other'})
        data = {'revision': 0, 'skills': [], 'professions': [other.pk], 'without_university_degree': True}
        self.assertEqual(self.client.put('/api/volunteer/qualifications/', data, content_type='application/json').status_code, 400)
        data['other_trade'] = 'Carpintería'
        self.assertEqual(self.client.put('/api/volunteer/qualifications/', data, content_type='application/json').status_code, 200)
        restored = self.client.get('/api/volunteer/qualifications/').json()
        self.assertEqual(restored['other_trade'], 'Carpintería')
        self.assertTrue(restored['without_university_degree'])
        self.assertFalse(other.required_documents.exists())
        career = Profession.objects.create(name='Trabajo social')
        data.update(revision=1, professions=[career.pk])
        self.assertEqual(self.client.put('/api/volunteer/qualifications/', data, content_type='application/json').status_code, 400)

