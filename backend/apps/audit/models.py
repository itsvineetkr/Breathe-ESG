"""
audit/models.py

AuditLog records every state-changing action in the system.
This is the "who did what to which record and when" table.

We capture:
- File uploads (datasource-level)
- Record approvals, rejections, edits
- Flag additions and removals
- Analyst notes

old_values / new_values let us reconstruct the record's state at any point in time.
These are stored as JSON so we don't need to normalize the audit schema per record type.

Important: AuditLog entries are NEVER deleted. Soft-delete only for records/datasources.
"""

import uuid
from django.db import models
from apps.accounts.models import Organization, UserProfile
from apps.emissions.models import EmissionRecord
from apps.ingestion.models import DataSource


class AuditLog(models.Model):
    ACTION_UPLOAD = 'upload'
    ACTION_PARSE_COMPLETE = 'parse_complete'
    ACTION_APPROVE = 'approve'
    ACTION_REJECT = 'reject'
    ACTION_EDIT = 'edit'
    ACTION_FLAG = 'flag'
    ACTION_UNFLAG = 'unflag'
    ACTION_NOTE = 'add_note'
    ACTION_SCOPE_CHANGE = 'scope_change'

    ACTION_CHOICES = [
        (ACTION_UPLOAD, 'File Uploaded'),
        (ACTION_PARSE_COMPLETE, 'Parse Completed'),
        (ACTION_APPROVE, 'Record Approved'),
        (ACTION_REJECT, 'Record Rejected'),
        (ACTION_EDIT, 'Record Edited'),
        (ACTION_FLAG, 'Record Flagged'),
        (ACTION_UNFLAG, 'Record Unflagged'),
        (ACTION_NOTE, 'Note Added'),
        (ACTION_SCOPE_CHANGE, 'Scope/Category Changed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name='audit_logs'
    )

    # Either a record action or a datasource action (one will be null)
    record = models.ForeignKey(
        EmissionRecord, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='audit_logs'
    )
    datasource = models.ForeignKey(
        DataSource, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='audit_logs'
    )

    action = models.CharField(max_length=30, choices=ACTION_CHOICES)

    # Snapshot of what changed — for edits: {'status': 'pending_review'} → {'status': 'approved'}
    old_values = models.JSONField(default=dict)
    new_values = models.JSONField(default=dict)

    user = models.ForeignKey(
        UserProfile, null=True, on_delete=models.SET_NULL, related_name='audit_entries'
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.action} by {self.user} at {self.timestamp}"

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['organization', 'timestamp']),
            models.Index(fields=['record', 'timestamp']),
        ]
