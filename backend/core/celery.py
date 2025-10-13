from __future__ import annotations

import os

from celery import Celery

from core.observability import InstrumentedTask

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

app = Celery("core")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.Task = InstrumentedTask
app.autodiscover_tasks()
