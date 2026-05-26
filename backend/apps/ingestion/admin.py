from django.contrib import admin
from .models import DataSource

@admin.register(DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display = ['name', 'source_type', 'organization', 'status', 'total_rows', 'flagged_rows', 'uploaded_at']
    list_filter = ['source_type', 'status', 'organization']
