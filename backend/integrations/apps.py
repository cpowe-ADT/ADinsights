from django.apps import AppConfig


class IntegrationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "integrations"

    def ready(self) -> None:
        from django.conf import settings
        from django.db import connections
        from django.db.utils import OperationalError, ProgrammingError

        if not bool(getattr(settings, "META_PAGE_INSIGHTS_ENABLED", True)):
            return

        from integrations.models import MetaMetricRegistry

        connection = connections["default"]
        try:
            table_names = set(connection.introspection.table_names())
        except (OperationalError, ProgrammingError):
            return
        if MetaMetricRegistry._meta.db_table not in table_names:
            return

        from integrations.meta_page_insights.metric_pack_loader import load_metric_pack_v1

        try:
            load_metric_pack_v1()
        except Exception:  # pragma: no cover - startup guard
            return
