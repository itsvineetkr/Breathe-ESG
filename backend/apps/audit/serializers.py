from rest_framework import serializers
from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    record_id = serializers.UUIDField(source='record.id', read_only=True)
    datasource_name = serializers.CharField(source='datasource.name', read_only=True, allow_null=True)

    class Meta:
        model = AuditLog
        fields = [
            'id', 'action', 'action_display',
            'record_id', 'datasource_name',
            'old_values', 'new_values',
            'user_name', 'timestamp', 'notes',
        ]

    def get_user_name(self, obj):
        if obj.user and obj.user.user:
            u = obj.user.user
            return f"{u.first_name} {u.last_name}".strip() or u.email
        return 'System'
