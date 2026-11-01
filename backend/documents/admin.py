from django.contrib import admin
from django.utils.html import format_html

from .models import VolunteerDocument


@admin.register(VolunteerDocument)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['document_type', 'version', 'status', 'scan_status', 'uploaded_at']
    list_filter = ['status', 'scan_status', 'document_type']
    fields = ['document_type', 'version', 'effective_status', 'scan_status', 'uploaded_at', 'reviewed_at', 'expires_on', 'observation', 'download_link']
    readonly_fields = fields
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.has_perm('documents.review_volunteerdocument')

    def get_queryset(self, request):
        return super().get_queryset(request).exclude(profile__user=request.user)

    @admin.display(description='Descarga autorizada')
    def download_link(self, obj):
        return format_html('<a href="{}">Descargar archivo</a>', f'/api/documents/{obj.pk}/download/')
