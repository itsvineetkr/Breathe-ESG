from rest_framework import serializers
from .models import DataSource


class DataSourceSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.SerializerMethodField()
    source_type_display = serializers.CharField(source='get_source_type_display', read_only=True)

    class Meta:
        model = DataSource
        fields = [
            'id', 'name', 'source_type', 'source_type_display',
            'original_filename', 'uploaded_by_name', 'uploaded_at',
            'status', 'total_rows', 'parsed_rows', 'failed_rows',
            'flagged_rows', 'field_mapping_override',
        ]
        read_only_fields = [
            'id', 'uploaded_by_name', 'uploaded_at', 'status',
            'total_rows', 'parsed_rows', 'failed_rows', 'flagged_rows',
        ]

    def get_uploaded_by_name(self, obj):
        if obj.uploaded_by and obj.uploaded_by.user:
            u = obj.uploaded_by.user
            return f"{u.first_name} {u.last_name}".strip() or u.email
        return None


class DataSourceUploadSerializer(serializers.Serializer):
    """Used for the file upload endpoint."""
    name = serializers.CharField(max_length=255)
    source_type = serializers.ChoiceField(choices=DataSource.SOURCE_TYPE_CHOICES)
    file = serializers.FileField()
    field_mapping_override = serializers.JSONField(required=False, default=dict)
