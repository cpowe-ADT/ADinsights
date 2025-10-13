from __future__ import annotations

import uuid

from django.db import models


class AlertRun(models.Model):
    class Status(models.TextChoices):
        STARTED = "started", "Started"
        SUCCESS = "success", "Success"
        NO_RESULTS = "no_results", "No results"
        PARTIAL = "partial", "Partial"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rule_slug = models.CharField(max_length=128, db_index=True)
    status = models.CharField(max_length=32, choices=Status.choices)
    row_count = models.PositiveIntegerField(default=0)
    llm_summary = models.TextField(blank=True)
    raw_results = models.JSONField(default=list, blank=True)
    error_message = models.TextField(blank=True)
    duration_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["rule_slug", "-created_at"], name="alerts_rule_ts"),
        ]

    def __str__(self) -> str:  # pragma: no cover - human readable
        return f"{self.rule_slug} ({self.status})"
