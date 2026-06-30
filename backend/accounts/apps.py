from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    def ready(self) -> None:  # pragma: no cover - import side effects
        # Import signal handlers that register themselves with Django's signal
        # framework. The import is intentionally local to avoid triggering
        # database access at import time.
        from . import signals  # noqa: F401

        return super().ready()
