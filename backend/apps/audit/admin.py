from django.contrib import admin
from .models import AuditLog

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['action', 'user', 'organization', 'timestamp', 'notes']
    list_filter = ['action', 'organization']
    readonly_fields = ['id', 'organization', 'record', 'datasource', 'action', 'old_values', 'new_values', 'user', 'timestamp']
