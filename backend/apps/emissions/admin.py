from django.contrib import admin
from .models import EmissionRecord

@admin.register(EmissionRecord)
class EmissionRecordAdmin(admin.ModelAdmin):
    list_display = ['organization', 'scope', 'category', 'activity_date', 'co2e_kg', 'status', 'is_flagged']
    list_filter = ['scope', 'category', 'status', 'is_flagged', 'organization']
    search_fields = ['description', 'location', 'vendor']
