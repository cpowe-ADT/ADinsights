from __future__ import annotations

from django.apps import AppConfig


class ContentOpsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "content_ops"
    verbose_name = "Content Operations"
