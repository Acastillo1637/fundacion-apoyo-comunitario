from django.contrib import admin
from accounts.models import AuditEvent
from .models import DocumentType, Profession, Skill


class CatalogAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name']
    fields = ['name', 'description', 'is_active']
    list_per_page = 30

    def get_readonly_fields(self, request, obj=None):
        from .signals import DEGREE_NAME, SKILL_DOCUMENTS
        if obj is None:
            return []
        key = obj.name.strip().casefold()
        protected = {DEGREE_NAME.casefold()} | {name.casefold()
            for documents in SKILL_DOCUMENTS.values() for name, _ in documents}
        if isinstance(obj, DocumentType) and key in protected:
            return ['name', 'is_active']
        if isinstance(obj, Skill) and key in SKILL_DOCUMENTS:
            return ['name']
        if isinstance(obj, Profession) and obj.kind == Profession.Kind.OTHER:
            return ['name', 'kind']
        return []

    def has_delete_permission(self, request, obj=None):
        # La desactivación conserva las declaraciones y referencias históricas.
        return False

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        AuditEvent.objects.create(
            actor=request.user,
            action='catalog.updated' if change else 'catalog.created',
            resource=f'{obj._meta.label_lower}:{obj.pk}',
        )


class RequirementCatalogAdmin(CatalogAdmin):
    fields = CatalogAdmin.fields + ['required_documents']
    filter_horizontal = ['required_documents']


admin.site.register(DocumentType, CatalogAdmin)
admin.site.register(Skill, RequirementCatalogAdmin)


@admin.register(Profession)
class ProfessionAdmin(RequirementCatalogAdmin):
    fields = RequirementCatalogAdmin.fields + ['kind']
