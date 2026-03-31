"""Django settings for the ads reporting backend."""

from __future__ import annotations

from datetime import timedelta
import logging
from pathlib import Path
from urllib.parse import urlsplit

import environ
from celery.schedules import crontab
from kombu import Queue
from django.core.exceptions import ImproperlyConfigured

from config.logging import build_logging_config
from core.crypto.kms import validate_kms_configuration

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env if present.
env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    TIME_ZONE=(str, "America/Jamaica"),
    API_VERSION=(str, "dev"),
    SECRETS_PROVIDER=(str, "env"),
    KMS_PROVIDER=(str, "aws"),
    LLM_TIMEOUT=(float, 10.0),
    ENABLE_TENANCY=(bool, True),
    DJANGO_LOG_LEVEL=(str, "INFO"),
    APP_VERSION=(str, "0.0.0-dev"),
    METRICS_SNAPSHOT_TTL=(int, 300),
    METRICS_SNAPSHOT_STALE_TTL_SECONDS=(int, 3600),
    METRICS_SNAPSHOT_SYNC_LOCK_TTL_SECONDS=(int, 900),
    ENABLE_FAKE_ADAPTER=(bool, False),
    ENABLE_WAREHOUSE_ADAPTER=(bool, False),
    ENABLE_DEMO_ADAPTER=(bool, False),
    ENABLE_UPLOAD_ADAPTER=(bool, True),
    ENABLE_DEMO_GENERATION=(bool, True),
    DEMO_SEED_DIR=(str, ""),
    CREDENTIAL_ROTATION_REMINDER_DAYS=(int, 7),
    EMAIL_PROVIDER=(str, "log"),
    EMAIL_FROM_ADDRESS=(str, "no-reply@adinsights.local"),
    SES_CONFIGURATION_SET=(str, ""),
    SES_EXPECTED_FROM_DOMAIN=(str, ""),
    FRONTEND_BASE_URL=(str, "http://localhost:5173"),
    META_APP_ID=(str, ""),
    META_APP_SECRET=(str, ""),
    META_OAUTH_REDIRECT_URI=(str, ""),
    META_LOGIN_CONFIG_ID=(str, ""),
    META_LOGIN_CONFIG_REQUIRED=(bool, True),
    META_OAUTH_SCOPES=(
        list,
        [
            "ads_management",
            "pages_show_list",
            "pages_read_engagement",
            "pages_manage_ads",
            "pages_manage_metadata",
            "pages_messaging",
            "ads_read",
            "business_management",
            "catalog_management",
        ],
    ),
    META_PAGE_INSIGHTS_OAUTH_SCOPES=(
        list,
        [
            "pages_show_list",
            "pages_read_engagement",
            "pages_manage_metadata",
        ],
    ),
    META_GRAPH_API_VERSION=(str, "v24.0"),
    META_GRAPH_TIMEOUT_SECONDS=(float, 10.0),
    META_GRAPH_MAX_ATTEMPTS=(int, 5),
    META_PAGE_INSIGHTS_ENABLED=(bool, True),
    META_PAGE_INSIGHTS_METRIC_PACK_PATH=(str, ""),
    META_PAGE_INSIGHTS_BACKFILL_DAYS=(int, 90),
    META_PAGE_INSIGHTS_INCREMENTAL_LOOKBACK_DAYS=(int, 3),
    META_PAGE_INSIGHTS_POST_RECENCY_DAYS=(int, 28),
    META_PAGE_INSIGHTS_METRIC_CHUNK_SIZE=(int, 10),
    META_PAGE_INSIGHTS_TIMEOUT_SECONDS=(float, 20.0),
    META_PAGE_INSIGHTS_MAX_ATTEMPTS=(int, 5),
    META_PAGE_INSIGHTS_NIGHTLY_HOUR=(int, 3),
    META_PAGE_INSIGHTS_NIGHTLY_MINUTE=(int, 10),
    META_POST_INSIGHTS_NIGHTLY_HOUR=(int, 3),
    META_POST_INSIGHTS_NIGHTLY_MINUTE=(int, 20),
    CORS_ALLOW_ALL_ORIGINS=(bool, False),
    CORS_ALLOWED_ORIGINS=(list, []),
    CORS_ALLOWED_METHODS=(
        list,
        ["DELETE", "GET", "OPTIONS", "PATCH", "POST", "PUT"],
    ),
    CORS_ALLOWED_HEADERS=(
        list,
        [
            "accept",
            "accept-language",
            "authorization",
            "content-type",
            "origin",
            "x-correlation-id",
            "x-requested-with",
            "x-tenant-id",
        ],
    ),
    CORS_ALLOW_CREDENTIALS=(bool, True),
    CORS_PREFLIGHT_MAX_AGE=(int, 86400),
    AIRBYTE_DEFAULT_WORKSPACE_ID=(str, ""),
    AIRBYTE_DEFAULT_DESTINATION_ID=(str, ""),
    AIRBYTE_SOURCE_DEFINITION_META=(str, ""),
    AIRBYTE_RECONCILE_STALE_MINUTES=(int, 120),
    AIRBYTE_RECONCILE_FORCE_STALE_FAILURE=(bool, False),
    AIRBYTE_SYNC_HEALTH_REFRESH_MINUTE=(int, 40),
    GOOGLE_ADS_SYNC_ENGINE_DEFAULT=(str, "sdk"),
    GOOGLE_ADS_PARITY_ENABLED=(bool, True),
    GOOGLE_ADS_PARITY_SPEND_MAX_DELTA_PCT=(float, 1.0),
    GOOGLE_ADS_PARITY_CLICKS_MAX_DELTA_PCT=(float, 2.0),
    GOOGLE_ADS_PARITY_CONVERSIONS_MAX_DELTA_PCT=(float, 2.0),
    GOOGLE_ADS_TODAY_CACHE_TTL_SECONDS=(int, 300),
    DRF_THROTTLE_AUTH_BURST=(str, "10/min"),
    DRF_THROTTLE_AUTH_SUSTAINED=(str, "100/day"),
    DRF_THROTTLE_PUBLIC=(str, "120/min"),
    CELERY_TASK_DEFAULT_QUEUE=(str, "default"),
    CELERY_QUEUE_SYNC=(str, "sync"),
    CELERY_QUEUE_SNAPSHOT=(str, "snapshot"),
    CELERY_QUEUE_SUMMARY=(str, "summary"),
    CELERY_WORKER_CONCURRENCY=(int, 4),
    CELERY_WORKER_CONCURRENCY_BUDGET=(int, 7),
    CELERY_WORKER_MAX_CONCURRENCY_PER_PROFILE=(int, 16),
    CELERY_WORKER_MAX_PREFETCH_MULTIPLIER=(int, 4),
    CELERY_WORKER_SYNC_MAX_TO_BACKGROUND_RATIO=(int, 4),
    CELERY_WORKER_PREFETCH_MULTIPLIER=(int, 1),
    CELERY_WORKER_MAX_TASKS_PER_CHILD=(int, 200),
    CELERY_WORKER_MAX_MEMORY_PER_CHILD=(int, 0),
    CELERY_WORKER_MAX_MEMORY_PER_CHILD_KB=(int, 0),
    CELERY_WORKER_SYNC_QUEUES=(list, ["default", "sync"]),
    CELERY_WORKER_SYNC_CONCURRENCY=(int, 4),
    CELERY_WORKER_SYNC_PREFETCH_MULTIPLIER=(int, 1),
    CELERY_WORKER_SYNC_MAX_TASKS_PER_CHILD=(int, 200),
    CELERY_WORKER_SNAPSHOT_QUEUES=(list, ["snapshot"]),
    CELERY_WORKER_SNAPSHOT_CONCURRENCY=(int, 2),
    CELERY_WORKER_SNAPSHOT_PREFETCH_MULTIPLIER=(int, 1),
    CELERY_WORKER_SNAPSHOT_MAX_TASKS_PER_CHILD=(int, 100),
    CELERY_WORKER_SUMMARY_QUEUES=(list, ["summary"]),
    CELERY_WORKER_SUMMARY_CONCURRENCY=(int, 1),
    CELERY_WORKER_SUMMARY_PREFETCH_MULTIPLIER=(int, 1),
    CELERY_WORKER_SUMMARY_MAX_TASKS_PER_CHILD=(int, 100),
    CELERY_TASK_ACKS_LATE=(bool, True),
    CELERY_TASK_REJECT_ON_WORKER_LOST=(bool, True),
    CELERY_TASK_TRACK_STARTED=(bool, True),
    CELERY_TASK_ALWAYS_EAGER=(bool, False),
    CELERY_TASK_EAGER_PROPAGATES=(bool, True),
)

ENV_FILE = BASE_DIR / ".env"
if ENV_FILE.exists():
    environ.Env.read_env(ENV_FILE)


def _optional(value: str | None) -> str | None:
    return value or None


def _origin_from_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlsplit(value)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def _normalize_queue_list(values: list[str], *, default: tuple[str, ...]) -> tuple[str, ...]:
    normalized = [value.strip() for value in values if isinstance(value, str) and value.strip()]
    if not normalized:
        return default
    return tuple(dict.fromkeys(normalized))


SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")
ENABLE_TENANCY = env.bool("ENABLE_TENANCY", default=True)
API_VERSION = env("API_VERSION")
METRICS_SNAPSHOT_TTL = env.int("METRICS_SNAPSHOT_TTL")
METRICS_SNAPSHOT_STALE_TTL_SECONDS = max(env.int("METRICS_SNAPSHOT_STALE_TTL_SECONDS"), 1)
METRICS_SNAPSHOT_SYNC_LOCK_TTL_SECONDS = max(env.int("METRICS_SNAPSHOT_SYNC_LOCK_TTL_SECONDS"), 1)
# In local DEBUG sessions, keep demo/fake adapters on by default so dashboard
# toggles always have a working non-live data source unless explicitly disabled.
ENABLE_FAKE_ADAPTER = env.bool("ENABLE_FAKE_ADAPTER", default=DEBUG)
ENABLE_WAREHOUSE_ADAPTER = env.bool("ENABLE_WAREHOUSE_ADAPTER", default=False)
ENABLE_DEMO_ADAPTER = env.bool("ENABLE_DEMO_ADAPTER", default=DEBUG)
ENABLE_UPLOAD_ADAPTER = env.bool("ENABLE_UPLOAD_ADAPTER", default=True)
ENABLE_DEMO_GENERATION = env.bool("ENABLE_DEMO_GENERATION", default=True)
DEMO_SEED_DIR = _optional(env("DEMO_SEED_DIR", default=""))
CREDENTIAL_ROTATION_REMINDER_DAYS = env.int("CREDENTIAL_ROTATION_REMINDER_DAYS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "alerts",
    "accounts",
    "integrations",
    "analytics",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "core.cors.CORSMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "middleware.tenant.TenantHeaderMiddleware",
    "accounts.middleware.TenantMiddleware",
    "core.observability.RequestCorrelationMiddleware",
    "core.observability.APILoggingMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = env("TIME_ZONE")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "accounts.authentication.ServiceAccountAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 100,
    "DEFAULT_FILTER_BACKENDS": (
        "core.filters.ScopeFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_SCHEMA_CLASS": "rest_framework.schemas.openapi.AutoSchema",
    "DEFAULT_THROTTLE_RATES": {
        "auth_burst": env("DRF_THROTTLE_AUTH_BURST"),
        "auth_sustained": env("DRF_THROTTLE_AUTH_SUSTAINED"),
        "public": env("DRF_THROTTLE_PUBLIC"),
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

LOGGING = build_logging_config(env("DJANGO_LOG_LEVEL"))

CELERY_BROKER_URL = env("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND")
CELERY_TASK_DEFAULT_QUEUE = env("CELERY_TASK_DEFAULT_QUEUE", default="default")
CELERY_QUEUE_SYNC = env("CELERY_QUEUE_SYNC", default="sync")
CELERY_QUEUE_SNAPSHOT = env("CELERY_QUEUE_SNAPSHOT", default="snapshot")
CELERY_QUEUE_SUMMARY = env("CELERY_QUEUE_SUMMARY", default="summary")
CELERY_WORKER_CONCURRENCY = max(env.int("CELERY_WORKER_CONCURRENCY", default=4), 1)
CELERY_WORKER_CONCURRENCY_BUDGET = max(
    env.int("CELERY_WORKER_CONCURRENCY_BUDGET", default=7),
    3,
)
CELERY_WORKER_MAX_CONCURRENCY_PER_PROFILE = max(
    env.int("CELERY_WORKER_MAX_CONCURRENCY_PER_PROFILE", default=16),
    1,
)
CELERY_WORKER_MAX_PREFETCH_MULTIPLIER = max(
    env.int("CELERY_WORKER_MAX_PREFETCH_MULTIPLIER", default=4),
    1,
)
CELERY_WORKER_SYNC_MAX_TO_BACKGROUND_RATIO = max(
    env.int("CELERY_WORKER_SYNC_MAX_TO_BACKGROUND_RATIO", default=4),
    1,
)
CELERY_WORKER_PREFETCH_MULTIPLIER = max(
    env.int("CELERY_WORKER_PREFETCH_MULTIPLIER", default=1), 1
)
CELERY_WORKER_MAX_TASKS_PER_CHILD = max(
    env.int("CELERY_WORKER_MAX_TASKS_PER_CHILD", default=200), 1
)
CELERY_WORKER_MAX_MEMORY_PER_CHILD = max(
    env.int(
        "CELERY_WORKER_MAX_MEMORY_PER_CHILD",
        default=env.int("CELERY_WORKER_MAX_MEMORY_PER_CHILD_KB", default=0),
    ),
    0,
)
CELERY_WORKER_SYNC_QUEUES = _normalize_queue_list(
    env.list("CELERY_WORKER_SYNC_QUEUES", default=[CELERY_TASK_DEFAULT_QUEUE, CELERY_QUEUE_SYNC]),
    default=(CELERY_TASK_DEFAULT_QUEUE, CELERY_QUEUE_SYNC),
)
CELERY_WORKER_SYNC_CONCURRENCY = max(
    env.int("CELERY_WORKER_SYNC_CONCURRENCY", default=CELERY_WORKER_CONCURRENCY),
    1,
)
CELERY_WORKER_SYNC_PREFETCH_MULTIPLIER = max(
    env.int("CELERY_WORKER_SYNC_PREFETCH_MULTIPLIER", default=CELERY_WORKER_PREFETCH_MULTIPLIER),
    1,
)
CELERY_WORKER_SYNC_MAX_TASKS_PER_CHILD = max(
    env.int("CELERY_WORKER_SYNC_MAX_TASKS_PER_CHILD", default=CELERY_WORKER_MAX_TASKS_PER_CHILD),
    1,
)
CELERY_WORKER_SNAPSHOT_QUEUES = _normalize_queue_list(
    env.list("CELERY_WORKER_SNAPSHOT_QUEUES", default=[CELERY_QUEUE_SNAPSHOT]),
    default=(CELERY_QUEUE_SNAPSHOT,),
)
CELERY_WORKER_SNAPSHOT_CONCURRENCY = max(
    env.int("CELERY_WORKER_SNAPSHOT_CONCURRENCY", default=2),
    1,
)
CELERY_WORKER_SNAPSHOT_PREFETCH_MULTIPLIER = max(
    env.int("CELERY_WORKER_SNAPSHOT_PREFETCH_MULTIPLIER", default=1),
    1,
)
CELERY_WORKER_SNAPSHOT_MAX_TASKS_PER_CHILD = max(
    env.int("CELERY_WORKER_SNAPSHOT_MAX_TASKS_PER_CHILD", default=100),
    1,
)
CELERY_WORKER_SUMMARY_QUEUES = _normalize_queue_list(
    env.list("CELERY_WORKER_SUMMARY_QUEUES", default=[CELERY_QUEUE_SUMMARY]),
    default=(CELERY_QUEUE_SUMMARY,),
)
CELERY_WORKER_SUMMARY_CONCURRENCY = max(
    env.int("CELERY_WORKER_SUMMARY_CONCURRENCY", default=1),
    1,
)
CELERY_WORKER_SUMMARY_PREFETCH_MULTIPLIER = max(
    env.int("CELERY_WORKER_SUMMARY_PREFETCH_MULTIPLIER", default=1),
    1,
)
CELERY_WORKER_SUMMARY_MAX_TASKS_PER_CHILD = max(
    env.int("CELERY_WORKER_SUMMARY_MAX_TASKS_PER_CHILD", default=100),
    1,
)
CELERY_TASK_ACKS_LATE = env.bool("CELERY_TASK_ACKS_LATE", default=True)
CELERY_TASK_REJECT_ON_WORKER_LOST = env.bool(
    "CELERY_TASK_REJECT_ON_WORKER_LOST", default=True
)
CELERY_TASK_TRACK_STARTED = env.bool("CELERY_TASK_TRACK_STARTED", default=True)
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_TASK_EAGER_PROPAGATES = env.bool("CELERY_TASK_EAGER_PROPAGATES", default=True)
AIRBYTE_RECONCILE_STALE_MINUTES = env.int("AIRBYTE_RECONCILE_STALE_MINUTES", default=120)
AIRBYTE_RECONCILE_FORCE_STALE_FAILURE = env.bool("AIRBYTE_RECONCILE_FORCE_STALE_FAILURE", default=False)
AIRBYTE_SYNC_HEALTH_REFRESH_MINUTE = env.int("AIRBYTE_SYNC_HEALTH_REFRESH_MINUTE", default=40)
CELERY_TASK_ROUTES = {
    "core.tasks.sync_meta_metrics": {"queue": CELERY_QUEUE_SYNC},
    "core.tasks.sync_google_metrics": {"queue": CELERY_QUEUE_SYNC},
    "integrations.tasks.sync_*": {"queue": CELERY_QUEUE_SYNC},
    "integrations.tasks.evaluate_*": {"queue": CELERY_QUEUE_SYNC},
    "integrations.tasks.trigger_scheduled_airbyte_syncs": {"queue": CELERY_QUEUE_SYNC},
    "integrations.tasks.remind_expiring_credentials": {"queue": CELERY_QUEUE_SYNC},
    "integrations.tasks.refresh_*": {"queue": CELERY_QUEUE_SYNC},
    "analytics.sync_metrics_snapshots": {"queue": CELERY_QUEUE_SNAPSHOT},
    "analytics.tasks.sync_metrics_snapshots": {"queue": CELERY_QUEUE_SNAPSHOT},
    "analytics.ai_daily_summary": {"queue": CELERY_QUEUE_SUMMARY},
    "analytics.run_report_export_job": {"queue": CELERY_QUEUE_SUMMARY},
}
CELERY_TASK_QUEUES = (
    Queue(CELERY_TASK_DEFAULT_QUEUE),
    Queue(CELERY_QUEUE_SYNC),
    Queue(CELERY_QUEUE_SNAPSHOT),
    Queue(CELERY_QUEUE_SUMMARY),
)
CELERY_BEAT_SCHEDULE = {
    "alerts-quarter-hourly": {
        "task": "alerts.tasks.run_alert_cycle",
        "schedule": crontab(minute="*/15"),
    },
    "airbyte-scheduled-syncs-hourly": {
        "task": "integrations.tasks.trigger_scheduled_airbyte_syncs",
        "schedule": crontab(minute=0, hour="6-22"),
        "options": {"queue": CELERY_QUEUE_SYNC},
    },
    "airbyte-sync-health-refresh-hourly": {
        "task": "integrations.tasks.refresh_airbyte_sync_health",
        "schedule": crontab(minute=AIRBYTE_SYNC_HEALTH_REFRESH_MINUTE, hour="6-22"),
        "options": {"queue": CELERY_QUEUE_SYNC},
    },
    "credential-rotation-reminders": {
        "task": "integrations.tasks.remind_expiring_credentials",
        "schedule": crontab(hour=2, minute=0),
        "options": {"queue": CELERY_QUEUE_SYNC},
    },
    "meta-credential-lifecycle-hourly": {
        "task": "integrations.tasks.refresh_meta_tokens",
        "schedule": crontab(minute=0, hour="6-22"),
        "options": {"queue": CELERY_QUEUE_SYNC},
    },
    "meta-sync-accounts-hourly": {
        "task": "integrations.tasks.sync_meta_accounts",
        "schedule": crontab(minute=0, hour="6-22"),
        "options": {"queue": CELERY_QUEUE_SYNC},
    },
    "meta-sync-insights-hourly": {
        "task": "integrations.tasks.sync_meta_insights_incremental",
        "schedule": crontab(minute=0, hour="6-22"),
        "options": {"queue": CELERY_QUEUE_SYNC},
    },
    "google-ads-sdk-sync-hourly": {
        "task": "integrations.tasks.sync_google_ads_sdk_incremental",
        "schedule": crontab(minute=0, hour="6-22"),
        "options": {"queue": CELERY_QUEUE_SYNC},
    },
    "google-ads-sdk-finalize-daily": {
        "task": "integrations.tasks.sync_google_ads_sdk_finalize_daily",
        "schedule": crontab(hour=5, minute=0),
        "options": {"queue": CELERY_QUEUE_SYNC},
    },
    "google-ads-refresh-tokens-hourly": {
        "task": "integrations.tasks.refresh_google_ads_tokens",
        "schedule": crontab(minute=10, hour="6-22"),
        "options": {"queue": CELERY_QUEUE_SYNC},
    },
    "google-ads-parity-daily": {
        "task": "integrations.tasks.evaluate_google_ads_parity",
        "schedule": crontab(hour=5, minute=40),
        "options": {"queue": CELERY_QUEUE_SYNC},
    },
    "meta-sync-hierarchy-daily": {
        "task": "integrations.tasks.sync_meta_hierarchy",
        "schedule": crontab(hour=2, minute=15),
        "options": {"queue": CELERY_QUEUE_SYNC},
    },
    "meta-page-insights-nightly": {
        "task": "integrations.tasks.sync_meta_page_insights",
        "schedule": crontab(
            hour=env.int("META_PAGE_INSIGHTS_NIGHTLY_HOUR", default=3),
            minute=env.int("META_PAGE_INSIGHTS_NIGHTLY_MINUTE", default=10),
        ),
        "options": {"queue": CELERY_QUEUE_SYNC},
    },
    "meta-post-insights-nightly": {
        "task": "integrations.tasks.sync_meta_post_insights",
        "schedule": crontab(
            hour=env.int("META_POST_INSIGHTS_NIGHTLY_HOUR", default=3),
            minute=env.int("META_POST_INSIGHTS_NIGHTLY_MINUTE", default=20),
        ),
        "options": {"queue": CELERY_QUEUE_SYNC},
    },
    "meta-sync-pages-hourly": {
        "task": "integrations.tasks.sync_meta_pages",
        "schedule": crontab(minute=5, hour="6-22"),
        "options": {"queue": CELERY_QUEUE_SYNC},
    },
    "meta-discover-page-metrics-daily": {
        "task": "integrations.tasks.discover_supported_metrics",
        "schedule": crontab(hour=4, minute=0),
        "options": {"queue": CELERY_QUEUE_SYNC},
    },
    "meta-page-posts-hourly": {
        "task": "integrations.tasks.sync_page_posts",
        "schedule": crontab(minute=15, hour="6-22"),
        "options": {"queue": CELERY_QUEUE_SYNC},
    },
    "meta-page-insights-hourly": {
        "task": "integrations.tasks.sync_page_insights",
        "schedule": crontab(minute=20, hour="6-22"),
        "options": {"queue": CELERY_QUEUE_SYNC},
    },
    "meta-post-insights-hourly": {
        "task": "integrations.tasks.sync_post_insights",
        "schedule": crontab(minute=25, hour="6-22"),
        "options": {"queue": CELERY_QUEUE_SYNC},
    },
    "rotate-tenant-deks": {
        "task": "core.tasks.rotate_deks",
        "schedule": crontab(hour=1, minute=30, day_of_week="sun"),
    },
    "metrics-snapshot-sync": {
        "task": "analytics.sync_metrics_snapshots",
        "schedule": crontab(minute="*/30"),
        "options": {"queue": CELERY_QUEUE_SNAPSHOT},
    },
    "ai-daily-summary": {
        "task": "analytics.ai_daily_summary",
        "schedule": crontab(hour=6, minute=10),
        "options": {"queue": CELERY_QUEUE_SUMMARY},
    },
}


def _validate_celery_runtime_configuration() -> None:
    queue_settings = {
        "CELERY_TASK_DEFAULT_QUEUE": CELERY_TASK_DEFAULT_QUEUE,
        "CELERY_QUEUE_SYNC": CELERY_QUEUE_SYNC,
        "CELERY_QUEUE_SNAPSHOT": CELERY_QUEUE_SNAPSHOT,
        "CELERY_QUEUE_SUMMARY": CELERY_QUEUE_SUMMARY,
    }
    normalized_queues: dict[str, str] = {}
    for key, value in queue_settings.items():
        queue_name = str(value or "").strip()
        if not queue_name:
            raise ImproperlyConfigured(f"{key} must be non-empty.")
        normalized_queues[key] = queue_name

    queue_values = list(normalized_queues.values())
    if len(set(queue_values)) != len(queue_values):
        raise ImproperlyConfigured("Celery queue names must be distinct.")

    if CELERY_WORKER_CONCURRENCY < 1:
        raise ImproperlyConfigured("CELERY_WORKER_CONCURRENCY must be >= 1.")
    if CELERY_WORKER_PREFETCH_MULTIPLIER < 1:
        raise ImproperlyConfigured("CELERY_WORKER_PREFETCH_MULTIPLIER must be >= 1.")
    if CELERY_WORKER_MAX_TASKS_PER_CHILD < 1:
        raise ImproperlyConfigured("CELERY_WORKER_MAX_TASKS_PER_CHILD must be >= 1.")
    if CELERY_WORKER_MAX_MEMORY_PER_CHILD < 0:
        raise ImproperlyConfigured("CELERY_WORKER_MAX_MEMORY_PER_CHILD must be >= 0.")
    if CELERY_WORKER_CONCURRENCY_BUDGET < 3:
        raise ImproperlyConfigured("CELERY_WORKER_CONCURRENCY_BUDGET must be >= 3.")
    if CELERY_WORKER_MAX_CONCURRENCY_PER_PROFILE < 1:
        raise ImproperlyConfigured("CELERY_WORKER_MAX_CONCURRENCY_PER_PROFILE must be >= 1.")
    if CELERY_WORKER_MAX_PREFETCH_MULTIPLIER < 1:
        raise ImproperlyConfigured("CELERY_WORKER_MAX_PREFETCH_MULTIPLIER must be >= 1.")
    if CELERY_WORKER_SYNC_MAX_TO_BACKGROUND_RATIO < 1:
        raise ImproperlyConfigured("CELERY_WORKER_SYNC_MAX_TO_BACKGROUND_RATIO must be >= 1.")
    if not 0 <= AIRBYTE_SYNC_HEALTH_REFRESH_MINUTE <= 59:
        raise ImproperlyConfigured("AIRBYTE_SYNC_HEALTH_REFRESH_MINUTE must be between 0 and 59.")
    if AIRBYTE_RECONCILE_STALE_MINUTES < 1:
        raise ImproperlyConfigured("AIRBYTE_RECONCILE_STALE_MINUTES must be >= 1.")
    worker_profiles = {
        "CELERY_WORKER_SYNC": {
            "queues": CELERY_WORKER_SYNC_QUEUES,
            "required_queue": CELERY_QUEUE_SYNC,
            "concurrency": CELERY_WORKER_SYNC_CONCURRENCY,
            "prefetch_multiplier": CELERY_WORKER_SYNC_PREFETCH_MULTIPLIER,
            "max_tasks_per_child": CELERY_WORKER_SYNC_MAX_TASKS_PER_CHILD,
        },
        "CELERY_WORKER_SNAPSHOT": {
            "queues": CELERY_WORKER_SNAPSHOT_QUEUES,
            "required_queue": CELERY_QUEUE_SNAPSHOT,
            "concurrency": CELERY_WORKER_SNAPSHOT_CONCURRENCY,
            "prefetch_multiplier": CELERY_WORKER_SNAPSHOT_PREFETCH_MULTIPLIER,
            "max_tasks_per_child": CELERY_WORKER_SNAPSHOT_MAX_TASKS_PER_CHILD,
        },
        "CELERY_WORKER_SUMMARY": {
            "queues": CELERY_WORKER_SUMMARY_QUEUES,
            "required_queue": CELERY_QUEUE_SUMMARY,
            "concurrency": CELERY_WORKER_SUMMARY_CONCURRENCY,
            "prefetch_multiplier": CELERY_WORKER_SUMMARY_PREFETCH_MULTIPLIER,
            "max_tasks_per_child": CELERY_WORKER_SUMMARY_MAX_TASKS_PER_CHILD,
        },
    }

    known_queues = set(queue_values)
    for profile_name, profile in worker_profiles.items():
        queues = tuple(profile["queues"])
        if not queues:
            raise ImproperlyConfigured(f"{profile_name}_QUEUES must include at least one queue.")
        if profile["required_queue"] not in queues:
            raise ImproperlyConfigured(
                f"{profile_name}_QUEUES must include {profile['required_queue']!r}."
            )
        for queue_name in queues:
            if queue_name not in known_queues:
                raise ImproperlyConfigured(
                    f"{profile_name}_QUEUES references unknown queue {queue_name!r}."
                )
        if int(profile["concurrency"]) < 1:
            raise ImproperlyConfigured(f"{profile_name}_CONCURRENCY must be >= 1.")
        if int(profile["concurrency"]) > CELERY_WORKER_MAX_CONCURRENCY_PER_PROFILE:
            raise ImproperlyConfigured(
                f"{profile_name}_CONCURRENCY must be <= {CELERY_WORKER_MAX_CONCURRENCY_PER_PROFILE}."
            )
        if int(profile["prefetch_multiplier"]) < 1:
            raise ImproperlyConfigured(
                f"{profile_name}_PREFETCH_MULTIPLIER must be >= 1."
            )
        if int(profile["prefetch_multiplier"]) > CELERY_WORKER_MAX_PREFETCH_MULTIPLIER:
            raise ImproperlyConfigured(
                f"{profile_name}_PREFETCH_MULTIPLIER must be <= {CELERY_WORKER_MAX_PREFETCH_MULTIPLIER}."
            )
        if int(profile["max_tasks_per_child"]) < 1:
            raise ImproperlyConfigured(
                f"{profile_name}_MAX_TASKS_PER_CHILD must be >= 1."
            )

    total_profile_concurrency = (
        CELERY_WORKER_SYNC_CONCURRENCY
        + CELERY_WORKER_SNAPSHOT_CONCURRENCY
        + CELERY_WORKER_SUMMARY_CONCURRENCY
    )
    if total_profile_concurrency > CELERY_WORKER_CONCURRENCY_BUDGET:
        raise ImproperlyConfigured(
            "Combined worker profile concurrency exceeds CELERY_WORKER_CONCURRENCY_BUDGET."
        )
    background_profile_concurrency = (
        CELERY_WORKER_SNAPSHOT_CONCURRENCY + CELERY_WORKER_SUMMARY_CONCURRENCY
    )
    if CELERY_WORKER_SYNC_CONCURRENCY > (
        background_profile_concurrency * CELERY_WORKER_SYNC_MAX_TO_BACKGROUND_RATIO
    ):
        raise ImproperlyConfigured(
            "CELERY_WORKER_SYNC_CONCURRENCY exceeds fairness ratio versus snapshot/summary workers."
        )

    for route_name, route in CELERY_TASK_ROUTES.items():
        queue_name = str((route or {}).get("queue") or "").strip()
        if queue_name and queue_name not in known_queues:
            raise ImproperlyConfigured(
                f"CELERY_TASK_ROUTES[{route_name!r}] references unknown queue {queue_name!r}."
            )

    for schedule_name, entry in CELERY_BEAT_SCHEDULE.items():
        options = (entry or {}).get("options")
        if not isinstance(options, dict):
            continue
        queue_name = str(options.get("queue") or "").strip()
        if queue_name and queue_name not in known_queues:
            raise ImproperlyConfigured(
                f"CELERY_BEAT_SCHEDULE[{schedule_name!r}] references unknown queue {queue_name!r}."
            )


_validate_celery_runtime_configuration()

SECRETS_PROVIDER = env("SECRETS_PROVIDER")
KMS_PROVIDER = env("KMS_PROVIDER")
KMS_KEY_ID = env("KMS_KEY_ID")
AWS_REGION = _optional(env("AWS_REGION", default=None))
AWS_ACCESS_KEY_ID = _optional(env("AWS_ACCESS_KEY_ID", default=None))
AWS_SECRET_ACCESS_KEY = _optional(env("AWS_SECRET_ACCESS_KEY", default=None))
AWS_SESSION_TOKEN = _optional(env("AWS_SESSION_TOKEN", default=None))
validate_kms_configuration(KMS_PROVIDER, KMS_KEY_ID, AWS_REGION)

CORS_ALLOW_ALL_ORIGINS = env.bool("CORS_ALLOW_ALL_ORIGINS", default=False)
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
_frontend_origin = _origin_from_url(env("FRONTEND_BASE_URL"))
if _frontend_origin and _frontend_origin not in CORS_ALLOWED_ORIGINS:
    CORS_ALLOWED_ORIGINS.append(_frontend_origin)
CORS_ALLOWED_METHODS = [method.upper() for method in env.list("CORS_ALLOWED_METHODS")]
CORS_ALLOWED_HEADERS = [header.lower() for header in env.list("CORS_ALLOWED_HEADERS")]
CORS_ALLOW_CREDENTIALS = env.bool("CORS_ALLOW_CREDENTIALS", default=True)
CORS_PREFLIGHT_MAX_AGE = env.int("CORS_PREFLIGHT_MAX_AGE", default=86400)

TENANT_SETTING_KEY = "app.tenant_id"

AIRBYTE_API_URL = _optional(env("AIRBYTE_API_URL", default=None))
AIRBYTE_API_TOKEN = _optional(env("AIRBYTE_API_TOKEN", default=None))
AIRBYTE_USERNAME = _optional(env("AIRBYTE_USERNAME", default=None))
AIRBYTE_PASSWORD = _optional(env("AIRBYTE_PASSWORD", default=None))
AIRBYTE_WEBHOOK_SECRET = _optional(env("AIRBYTE_WEBHOOK_SECRET", default=None))
AIRBYTE_WEBHOOK_SECRET_REQUIRED = env.bool("AIRBYTE_WEBHOOK_SECRET_REQUIRED", default=True)
LLM_API_URL = _optional(env("LLM_API_URL", default=None))
LLM_API_KEY = _optional(env("LLM_API_KEY", default=None))
LLM_MODEL = env("LLM_MODEL", default="gpt-5.1")
LLM_TIMEOUT = env.float("LLM_TIMEOUT")
APP_VERSION = env("APP_VERSION")
EMAIL_PROVIDER = env("EMAIL_PROVIDER")
EMAIL_FROM_ADDRESS = env("EMAIL_FROM_ADDRESS")
SES_CONFIGURATION_SET = _optional(env("SES_CONFIGURATION_SET", default=None))
SES_EXPECTED_FROM_DOMAIN = _optional(env("SES_EXPECTED_FROM_DOMAIN", default=None))
FRONTEND_BASE_URL = env("FRONTEND_BASE_URL")
GOOGLE_ADS_CLIENT_ID = _optional(env("GOOGLE_ADS_CLIENT_ID", default=None))
GOOGLE_ADS_CLIENT_SECRET = _optional(env("GOOGLE_ADS_CLIENT_SECRET", default=None))
GOOGLE_ADS_DEVELOPER_TOKEN = _optional(env("GOOGLE_ADS_DEVELOPER_TOKEN", default=None))
GOOGLE_ADS_OAUTH_REDIRECT_URI = _optional(env("GOOGLE_ADS_OAUTH_REDIRECT_URI", default=None))
GOOGLE_ADS_OAUTH_SCOPES = env.list(
    "GOOGLE_ADS_OAUTH_SCOPES",
    default=[
        "https://www.googleapis.com/auth/adwords",
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
    ],
)
GOOGLE_ADS_LOGIN_CUSTOMER_ID = _optional(env("GOOGLE_ADS_LOGIN_CUSTOMER_ID", default=None))
GOOGLE_ADS_START_DATE = env("GOOGLE_ADS_START_DATE", default="2024-01-01")
GOOGLE_ADS_CONVERSION_WINDOW_DAYS = env.int("GOOGLE_ADS_CONVERSION_WINDOW_DAYS", default=30)
GOOGLE_ADS_LOOKBACK_WINDOW_DAYS = env.int("GOOGLE_ADS_LOOKBACK_WINDOW_DAYS", default=3)
GOOGLE_ANALYTICS_CLIENT_ID = _optional(env("GOOGLE_ANALYTICS_CLIENT_ID", default=None))
GOOGLE_ANALYTICS_CLIENT_SECRET = _optional(
    env("GOOGLE_ANALYTICS_CLIENT_SECRET", default=None)
)
GOOGLE_ANALYTICS_OAUTH_REDIRECT_URI = _optional(
    env("GOOGLE_ANALYTICS_OAUTH_REDIRECT_URI", default=None)
)
GOOGLE_ANALYTICS_OAUTH_SCOPES = env.list(
    "GOOGLE_ANALYTICS_OAUTH_SCOPES",
    default=[
        "https://www.googleapis.com/auth/analytics.readonly",
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
    ],
)
GOOGLE_ADS_SYNC_ENGINE_DEFAULT = env("GOOGLE_ADS_SYNC_ENGINE_DEFAULT", default="sdk").strip().lower()
if GOOGLE_ADS_SYNC_ENGINE_DEFAULT not in {"sdk", "airbyte"}:
    GOOGLE_ADS_SYNC_ENGINE_DEFAULT = "sdk"
GOOGLE_ADS_PARITY_ENABLED = env.bool("GOOGLE_ADS_PARITY_ENABLED", default=True)
GOOGLE_ADS_PARITY_SPEND_MAX_DELTA_PCT = env.float("GOOGLE_ADS_PARITY_SPEND_MAX_DELTA_PCT", default=1.0)
GOOGLE_ADS_PARITY_CLICKS_MAX_DELTA_PCT = env.float("GOOGLE_ADS_PARITY_CLICKS_MAX_DELTA_PCT", default=2.0)
GOOGLE_ADS_PARITY_CONVERSIONS_MAX_DELTA_PCT = env.float(
    "GOOGLE_ADS_PARITY_CONVERSIONS_MAX_DELTA_PCT",
    default=2.0,
)
GOOGLE_ADS_TODAY_CACHE_TTL_SECONDS = env.int("GOOGLE_ADS_TODAY_CACHE_TTL_SECONDS", default=300)
META_APP_ID = _optional(env("META_APP_ID", default=None))
META_APP_SECRET = _optional(env("META_APP_SECRET", default=None))
META_OAUTH_REDIRECT_URI = _optional(env("META_OAUTH_REDIRECT_URI", default=None))
META_LOGIN_CONFIG_ID = _optional(env("META_LOGIN_CONFIG_ID", default=None))
META_LOGIN_CONFIG_REQUIRED = env.bool("META_LOGIN_CONFIG_REQUIRED", default=True)
META_OAUTH_SCOPES = env.list("META_OAUTH_SCOPES")
META_PAGE_INSIGHTS_OAUTH_SCOPES = env.list("META_PAGE_INSIGHTS_OAUTH_SCOPES")
META_GRAPH_API_VERSION = env("META_GRAPH_API_VERSION", default="v24.0")
META_GRAPH_TIMEOUT_SECONDS = env.float("META_GRAPH_TIMEOUT_SECONDS", default=10.0)
META_GRAPH_MAX_ATTEMPTS = env.int("META_GRAPH_MAX_ATTEMPTS", default=5)
META_PAGE_INSIGHTS_ENABLED = env.bool("META_PAGE_INSIGHTS_ENABLED", default=True)
META_PAGE_INSIGHTS_METRIC_PACK_PATH = _optional(
    env("META_PAGE_INSIGHTS_METRIC_PACK_PATH", default=None)
)
META_PAGE_INSIGHTS_BACKFILL_DAYS = env.int("META_PAGE_INSIGHTS_BACKFILL_DAYS", default=90)
META_PAGE_INSIGHTS_INCREMENTAL_LOOKBACK_DAYS = env.int(
    "META_PAGE_INSIGHTS_INCREMENTAL_LOOKBACK_DAYS",
    default=3,
)
META_PAGE_INSIGHTS_POST_RECENCY_DAYS = env.int("META_PAGE_INSIGHTS_POST_RECENCY_DAYS", default=28)
META_PAGE_INSIGHTS_METRIC_CHUNK_SIZE = env.int("META_PAGE_INSIGHTS_METRIC_CHUNK_SIZE", default=10)
META_PAGE_INSIGHTS_TIMEOUT_SECONDS = env.float("META_PAGE_INSIGHTS_TIMEOUT_SECONDS", default=20.0)
META_PAGE_INSIGHTS_MAX_ATTEMPTS = env.int("META_PAGE_INSIGHTS_MAX_ATTEMPTS", default=5)
META_PAGE_INSIGHTS_NIGHTLY_HOUR = env.int("META_PAGE_INSIGHTS_NIGHTLY_HOUR", default=3)
META_PAGE_INSIGHTS_NIGHTLY_MINUTE = env.int("META_PAGE_INSIGHTS_NIGHTLY_MINUTE", default=10)
META_POST_INSIGHTS_NIGHTLY_HOUR = env.int("META_POST_INSIGHTS_NIGHTLY_HOUR", default=3)
META_POST_INSIGHTS_NIGHTLY_MINUTE = env.int("META_POST_INSIGHTS_NIGHTLY_MINUTE", default=20)
AIRBYTE_DEFAULT_WORKSPACE_ID = _optional(env("AIRBYTE_DEFAULT_WORKSPACE_ID", default=None))
AIRBYTE_DEFAULT_DESTINATION_ID = _optional(env("AIRBYTE_DEFAULT_DESTINATION_ID", default=None))
AIRBYTE_SOURCE_DEFINITION_META = _optional(env("AIRBYTE_SOURCE_DEFINITION_META", default=None))
AIRBYTE_SOURCE_DEFINITION_GOOGLE = _optional(env("AIRBYTE_SOURCE_DEFINITION_GOOGLE", default=None))

SENTRY_DSN = _optional(env("SENTRY_DSN", default=None))
SENTRY_ENVIRONMENT = env("SENTRY_ENVIRONMENT", default="development")
SENTRY_TRACES_SAMPLE_RATE = env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.0)

if SENTRY_DSN:
    try:  # pragma: no cover - optional dependency
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.django import DjangoIntegration
    except ImportError:  # pragma: no cover - defensive fallback
        logging.getLogger(__name__).warning(
            "SENTRY_DSN set but sentry-sdk is not installed."
        )
    else:
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            environment=SENTRY_ENVIRONMENT,
            release=APP_VERSION,
            send_default_pii=False,
            traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
            integrations=[DjangoIntegration(), CeleryIntegration()],
        )
