from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    def ready(self) -> None:  # pragma: no cover - import side effects
        # Import signal handlers that register themselves with Django's signal
        # framework. The import is intentionally local to avoid triggering
        # database access at import time.
        from . import signals  # noqa: F401

        # Optionally provision a default admin for local/dev when explicitly allowed.
        # This is gated by the ALLOW_DEFAULT_ADMIN env var to avoid surprises.
        try:
            from .dev_admin import ensure_default_admin

            ensure_default_admin()
        except Exception:  # pragma: no cover - defensive guard for startup
            # Never fail app startup due to optional dev admin provisioning
            pass

        return super().ready()
