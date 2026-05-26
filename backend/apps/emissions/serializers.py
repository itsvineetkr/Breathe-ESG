from rest_framework import serializers
from .models import EmissionRecord


class EmissionRecordSerializer(serializers.ModelSerializer):
    scope_display = serializers.CharField(source='get_scope_display', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    source_name = serializers.CharField(source='source.name', read_only=True)
    source_type = serializers.CharField(source='source.source_type', read_only=True)
    reviewed_by_name = serializers.SerializerMethodField()
    co2e_tonnes = serializers.FloatField(read_only=True)

    class Meta:
        model = EmissionRecord
        fields = [
            'id', 'scope', 'scope_display', 'category', 'category_display',
            'activity_date', 'activity_period_end',
            'raw_quantity', 'raw_unit',
            'normalized_quantity', 'normalized_unit',
            'emission_factor', 'emission_factor_source',
            'co2e_kg', 'co2e_tonnes',
            'location', 'vendor', 'description',
            'origin', 'destination', 'flight_class', 'distance_km',
            'source_name', 'source_type', 'source_row_number',
            'status', 'status_display', 'is_flagged', 'flag_reasons',
            'analyst_notes', 'reviewed_by_name', 'reviewed_at',
            'created_at', 'updated_at',
            # Source row data is large — only include on detail view
        ]
        read_only_fields = [
            'id', 'scope', 'category', 'activity_date', 'activity_period_end',
            'raw_quantity', 'raw_unit', 'normalized_quantity', 'normalized_unit',
            'emission_factor', 'emission_factor_source', 'co2e_kg', 'co2e_tonnes',
            'origin', 'destination', 'distance_km',
            'source_name', 'source_type', 'source_row_number',
            'reviewed_by_name', 'reviewed_at', 'created_at', 'updated_at',
        ]

    def get_reviewed_by_name(self, obj):
        if obj.reviewed_by and obj.reviewed_by.user:
            u = obj.reviewed_by.user
            return f"{u.first_name} {u.last_name}".strip() or u.email
        return None


class EmissionRecordDetailSerializer(EmissionRecordSerializer):
    """Includes source_row_data for the detail view."""
    class Meta(EmissionRecordSerializer.Meta):
        fields = EmissionRecordSerializer.Meta.fields + ['source_row_data']


class ReviewActionSerializer(serializers.Serializer):
    """Payload for approve/reject/edit actions."""
    action = serializers.ChoiceField(choices=['approve', 'reject', 'flag', 'unflag', 'add_note', 'edit_scope'])
    notes = serializers.CharField(required=False, allow_blank=True, default='')
    # For scope/category correction
    scope = serializers.ChoiceField(
        choices=EmissionRecord.SCOPE_CHOICES,
        required=False, allow_null=True
    )
    category = serializers.ChoiceField(
        choices=EmissionRecord.CATEGORY_CHOICES,
        required=False, allow_null=True
    )
    flag_reason = serializers.CharField(required=False, allow_blank=True)
