from django.contrib import admin
from accounts.models import AuditEvent
from .models import DocumentType, Profession, Skill


class CatalogAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name']
    fields = ['name', 'description', 'is_active']
    list_per_page = 30

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
admin.site.register(Profession, RequirementCatalogAdmin)
