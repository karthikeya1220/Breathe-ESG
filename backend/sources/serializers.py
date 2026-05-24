from rest_framework import serializers
from .models import DataSource, IngestionJob


class DataSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DataSource
        fields = [
            'id', 'source_type', 'scope', 'display_name',
            'config', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class IngestionJobSerializer(serializers.ModelSerializer):
    data_source_name = serializers.CharField(source='data_source.display_name', read_only=True)
    source_type = serializers.CharField(source='data_source.source_type', read_only=True)

    class Meta:
        model = IngestionJob
        fields = [
            'id', 'data_source', 'data_source_name', 'source_type',
            'status', 'original_filename', 'row_count_raw',
            'row_count_ok', 'row_count_failed', 'error_summary',
            'started_at', 'completed_at',
        ]
        read_only_fields = fields
