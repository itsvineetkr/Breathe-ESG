"""
ingestion/models.py

DataSource represents a single file upload event.
One upload → one DataSource → many EmissionRecords.

The raw_file is always preserved so we can re-parse if the normalization logic
changes (e.g., we add a new unit conversion). This is important for audit
defensibility — we can always show "here is the exact file the analyst uploaded."
"""

import uuid
from django.db import models
from apps.accounts.models import Organization, UserProfile


class DataSource(models.Model):
    SOURCE_SAP = 'SAP'
    SOURCE_UTILITY = 'UTILITY'
    SOURCE_TRAVEL = 'TRAVEL'
    SOURCE_TYPE_CHOICES = [
        (SOURCE_SAP, 'SAP Flat File (MB51/ME2M)'),
        (SOURCE_UTILITY, 'Utility Portal CSV'),
        (SOURCE_TRAVEL, 'Travel Platform CSV (Navan/Concur)'),
    ]

    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='datasources'
    )
    source_type = models.CharField(max_length=10, choices=SOURCE_TYPE_CHOICES)
    name = models.CharField(
        max_length=255,
        help_text="Human-readable name for this upload, set by user."
    )
    raw_file = models.FileField(
        upload_to='uploads/%Y/%m/',
        help_text="Original file preserved for audit and re-parsing."
    )
    original_filename = models.CharField(max_length=255, blank=True)

    uploaded_by = models.ForeignKey(
        UserProfile, on_delete=models.SET_NULL, null=True, related_name='uploads'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PROCESSING)

    # Parse statistics — shown in the uploads list
    total_rows = models.IntegerField(default=0)
    parsed_rows = models.IntegerField(default=0)
    failed_rows = models.IntegerField(default=0)
    flagged_rows = models.IntegerField(default=0)

    # Per-upload field mapping override (takes precedence over org-level)
    # Allows one-off header fixes without changing org-wide config.
    field_mapping_override = models.JSONField(
        default=dict,
        help_text="Per-upload custom field mapping overrides."
    )

    # Detailed parse log for debugging: [{row: N, error: "..."}, ...]
    parse_log = models.JSONField(default=list)

    def __str__(self):
        return f"{self.name} ({self.source_type}) — {self.organization.name}"

    class Meta:
        ordering = ['-uploaded_at']
