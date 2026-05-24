from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    """
    Append-only audit log. Nothing is ever deleted from this table.
    Fires on: ingestion job state changes, record approvals, factor overrides, manual edits.
    bigserial PK (auto BigAutoField) — sequential for easy chronological querying.
    The application layer CANNOT override created_at (auto_now_add=True).
    """
    org = models.ForeignKey(
        'organizations.Organization',
        on_delete=models.CASCADE,
        related_name='audit_events'
    )
    # Null for system-triggered events (scheduled jobs, background tasks)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_events'
    )
    # e.g. JOB_STARTED, RECORD_APPROVED, FACTOR_OVERRIDDEN, RECORD_REJECTED
    event_type = models.CharField(max_length=100)
    # e.g. "IngestionJob", "EmissionRecord"
    object_type = models.CharField(max_length=50)
    # UUID of the affected object
    object_id = models.CharField(max_length=36)
    # Full before/after state for mutations
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.event_type} on {self.object_type}:{self.object_id}"

    class Meta:
        ordering = ['-created_at']
        # Never allow deletion
        default_permissions = ('add', 'view')
