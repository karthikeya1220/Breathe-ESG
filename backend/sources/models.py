import uuid
from django.conf import settings
from django.db import models


class DataSource(models.Model):
    class SourceType(models.TextChoices):
        SAP_FLAT_FILE = 'SAP_FLAT_FILE', 'SAP Flat File (MB51/ME2M)'
        UTILITY_CSV = 'UTILITY_CSV', 'Utility Portal CSV'
        TRAVEL_CSV = 'TRAVEL_CSV', 'Corporate Travel CSV (Concur/Navan)'

    class Scope(models.TextChoices):
        SCOPE_1 = 'SCOPE_1', 'Scope 1'
        SCOPE_2 = 'SCOPE_2', 'Scope 2'
        SCOPE_3 = 'SCOPE_3', 'Scope 3'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='data_sources'
    )
    source_type = models.CharField(max_length=30, choices=SourceType.choices)
    scope = models.CharField(max_length=10, choices=Scope.choices)
    display_name = models.CharField(max_length=255)
    # Source-specific config: column mappings, plant codes, meter IDs, etc.
    config = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_sources'
    )

    def __str__(self):
        return f"{self.display_name} ({self.source_type})"

    class Meta:
        ordering = ['display_name']


class IngestionJob(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        PROCESSING = 'PROCESSING', 'Processing'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    data_source = models.ForeignKey(
        DataSource,
        on_delete=models.CASCADE,
        related_name='ingestion_jobs'
    )
    # Denormalized for query performance — avoids join on every status check
    org = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='ingestion_jobs'
    )
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='triggered_jobs'
    )
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    # S3/volume path to original file — immutable after creation
    raw_file_path = models.CharField(max_length=512, blank=True)
    # SHA-256 of uploaded file; used to detect duplicate uploads
    file_hash = models.CharField(max_length=64, blank=True)
    original_filename = models.CharField(max_length=255, blank=True)
    row_count_raw = models.IntegerField(default=0)
    row_count_ok = models.IntegerField(default=0)
    row_count_failed = models.IntegerField(default=0)
    # Aggregated parse errors keyed by row number
    error_summary = models.JSONField(default=list, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Job {self.id} — {self.data_source.display_name} ({self.status})"

    class Meta:
        ordering = ['-started_at']
