import uuid
from django.conf import settings
from django.db import models


class RawRecord(models.Model):
    """
    One row per parsed row from the source file.
    NEVER mutated after creation — this is the ground truth of what arrived.
    """
    class ParseStatus(models.TextChoices):
        OK = 'OK', 'OK'
        PARSE_ERROR = 'PARSE_ERROR', 'Parse Error'
        VALIDATION_ERROR = 'VALIDATION_ERROR', 'Validation Error'
        SKIPPED = 'SKIPPED', 'Skipped'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ingestion_job = models.ForeignKey(
        'sources.IngestionJob',
        on_delete=models.CASCADE,
        related_name='raw_records'
    )
    # Denormalized for direct filtering without join chain
    org = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='raw_records'
    )
    row_number = models.IntegerField(help_text="Line number in source file (1-indexed)")
    # Exact key-value dict of the parsed CSV row — never transformed
    raw_data = models.JSONField()
    parse_status = models.CharField(
        max_length=20,
        choices=ParseStatus.choices,
        default=ParseStatus.OK
    )
    # Array of {field, message} error objects
    parse_errors = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Row {self.row_number} — Job {self.ingestion_job_id} ({self.parse_status})"

    class Meta:
        ordering = ['ingestion_job', 'row_number']


class EmissionRecord(models.Model):
    """
    Normalized, scope-tagged, unit-converted emission record.
    One row per valid RawRecord.
    """
    class Scope(models.TextChoices):
        SCOPE_1 = 'SCOPE_1', 'Scope 1'
        SCOPE_2 = 'SCOPE_2', 'Scope 2'
        SCOPE_3 = 'SCOPE_3', 'Scope 3'

    class ReviewStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        FLAGGED = 'FLAGGED', 'Flagged'
        REJECTED = 'REJECTED', 'Rejected'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    org = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='emission_records'
    )
    # One-to-one with RawRecord; nullable for manually entered records
    raw_record = models.OneToOneField(
        RawRecord,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='emission_record'
    )
    data_source = models.ForeignKey(
        'sources.DataSource',
        on_delete=models.CASCADE,
        related_name='emission_records'
    )
    # Record-level scope can differ from DataSource default (e.g., SAP file with mixed rows)
    scope = models.CharField(max_length=10, choices=Scope.choices)
    # GHG Protocol category string, e.g. "Stationary combustion", "Purchased electricity"
    category = models.CharField(max_length=100)
    activity_description = models.CharField(max_length=255)

    # Billing / activity period (explicit dates, not snapped to calendar month)
    period_start = models.DateField()
    period_end = models.DateField()

    # Raw quantity exactly as it appeared in the source
    raw_quantity = models.DecimalField(max_digits=18, decimal_places=6)
    raw_unit = models.CharField(max_length=50)

    # Converted to canonical unit (litres for fuel, kWh for energy, km for distance)
    quantity_normalized = models.DecimalField(max_digits=18, decimal_places=6)
    unit_normalized = models.CharField(max_length=20)

    # Computed kg CO₂e; null until emission factor applied
    co2e_kg = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    emission_factor = models.ForeignKey(
        'factors.EmissionFactor',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='emission_records'
    )
    # Stored if analyst manually overrides the factor
    emission_factor_override = models.JSONField(null=True, blank=True)

    review_status = models.CharField(
        max_length=10,
        choices=ReviewStatus.choices,
        default=ReviewStatus.PENDING
    )
    # True after analyst approval — blocks all further field mutations
    is_locked = models.BooleanField(default=False)
    locked_at = models.DateTimeField(null=True, blank=True)
    locked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='locked_records'
    )
    is_manually_edited = models.BooleanField(default=False)
    # Array of {field, old_value, new_value, user, timestamp}
    edit_history = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.activity_description} — {self.co2e_kg} kg CO₂e ({self.review_status})"

    class Meta:
        ordering = ['-created_at']


class AnalystReview(models.Model):
    """
    Append-only action log for analyst decisions.
    review_status on EmissionRecord = current state.
    This table = the history of how we got there.
    """
    class Action(models.TextChoices):
        APPROVED = 'APPROVED', 'Approved'
        FLAGGED = 'FLAGGED', 'Flagged'
        REJECTED = 'REJECTED', 'Rejected'
        EDITED = 'EDITED', 'Edited'
        NOTE_ADDED = 'NOTE_ADDED', 'Note Added'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    emission_record = models.ForeignKey(
        EmissionRecord,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    org = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='analyst_reviews'
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    action = models.CharField(max_length=15, choices=Action.choices)
    # Required for FLAGGED and REJECTED
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action} by {self.reviewer} on {self.emission_record_id}"

    class Meta:
        ordering = ['-created_at']
