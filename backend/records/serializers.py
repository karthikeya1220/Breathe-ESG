from rest_framework import serializers
from .models import EmissionRecord, RawRecord, AnalystReview


class RawRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = RawRecord
        fields = ['id', 'row_number', 'raw_data', 'parse_status', 'parse_errors', 'created_at']


class AnalystReviewSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.CharField(source='reviewer.get_full_name', read_only=True)
    reviewer_username = serializers.CharField(source='reviewer.username', read_only=True)

    class Meta:
        model = AnalystReview
        fields = ['id', 'action', 'comment', 'reviewer_name', 'reviewer_username', 'created_at']


class EmissionRecordListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for the review queue list view."""
    source_name = serializers.CharField(source='data_source.display_name', read_only=True)
    source_type = serializers.CharField(source='data_source.source_type', read_only=True)
    emission_factor_display = serializers.SerializerMethodField()

    def get_emission_factor_display(self, obj):
        if obj.emission_factor:
            return f"{obj.emission_factor.activity} ({obj.emission_factor.source})"
        return None

    class Meta:
        model = EmissionRecord
        fields = [
            'id', 'scope', 'category', 'activity_description',
            'period_start', 'period_end',
            'raw_quantity', 'raw_unit',
            'quantity_normalized', 'unit_normalized',
            'co2e_kg', 'emission_factor_display',
            'review_status', 'is_locked',
            'source_name', 'source_type',
            'created_at',
        ]


class EmissionRecordDetailSerializer(serializers.ModelSerializer):
    """Full serializer including raw record side-by-side."""
    raw_record = RawRecordSerializer(read_only=True)
    reviews = AnalystReviewSerializer(many=True, read_only=True)
    source_name = serializers.CharField(source='data_source.display_name', read_only=True)
    emission_factor_detail = serializers.SerializerMethodField()

    def get_emission_factor_detail(self, obj):
        if obj.emission_factor:
            ef = obj.emission_factor
            return {
                'id': ef.id,
                'source': ef.source,
                'activity': ef.activity,
                'factor_kg_co2e': str(ef.factor_kg_co2e),
                'unit': ef.unit,
            }
        return None

    class Meta:
        model = EmissionRecord
        fields = [
            'id', 'org', 'scope', 'category', 'activity_description',
            'period_start', 'period_end',
            'raw_quantity', 'raw_unit',
            'quantity_normalized', 'unit_normalized',
            'co2e_kg', 'emission_factor_detail', 'emission_factor_override',
            'review_status', 'is_locked', 'locked_at',
            'is_manually_edited', 'edit_history',
            'source_name', 'raw_record', 'reviews',
            'created_at',
        ]


class ReviewActionSerializer(serializers.Serializer):
    """Input serializer for POST /api/records/{id}/review/"""
    action = serializers.ChoiceField(choices=AnalystReview.Action.choices)
    comment = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, data):
        if data['action'] in ('FLAGGED', 'REJECTED') and not data.get('comment'):
            raise serializers.ValidationError(
                "A comment is required when flagging or rejecting a record."
            )
        return data
