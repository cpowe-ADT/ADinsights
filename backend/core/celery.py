from __future__ import annotations

import os
from datetime import datetime, timezone

from celery import Celery
from celery.signals import before_task_publish

from core.observability import InstrumentedTask

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

app = Celery("core")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.Task = InstrumentedTask
app.autodiscover_tasks()


@before_task_publish.connect
def stamp_task_published_at(headers=None, **_kwargs):  # noqa: ANN001
    """Attach publish time so workers can measure real queue wait latency."""

    if isinstance(headers, dict):
        headers.setdefault("published_at", datetime.now(tz=timezone.utc).isoformat())
