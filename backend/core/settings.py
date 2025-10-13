"""Django settings for the ads reporting backend."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import environ
from celery.schedules import crontab

from backend.config.logging import build_logging_config

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
    DJANGO_LOG_LEVEL=(str, "INFO"),
    APP_VERSION=(str, "0.0.0-dev"),
)

ENV_FILE = BASE_DIR / ".env"
if ENV_FILE.exists():
    environ.Env.read_env(ENV_FILE)


def _optional(value: str | None) -> str | None:
    return value or None

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")
API_VERSION = env("API_VERSION")

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
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "accounts.middleware.TenantMiddleware",
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
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_SCHEMA_CLASS": "rest_framework.schemas.openapi.AutoSchema",
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
CELERY_TASK_DEFAULT_QUEUE = "default"
CELERY_BEAT_SCHEDULE = {
    "alerts-quarter-hourly": {
        "task": "alerts.tasks.run_alert_cycle",
        "schedule": crontab(minute="*/15"),
    }
}

SECRETS_PROVIDER = env("SECRETS_PROVIDER")
KMS_PROVIDER = env("KMS_PROVIDER")
KMS_KEY_ID = env("KMS_KEY_ID")
AWS_REGION = _optional(env("AWS_REGION", default=None))
AWS_ACCESS_KEY_ID = _optional(env("AWS_ACCESS_KEY_ID", default=None))
AWS_SECRET_ACCESS_KEY = _optional(env("AWS_SECRET_ACCESS_KEY", default=None))
AWS_SESSION_TOKEN = _optional(env("AWS_SESSION_TOKEN", default=None))

TENANT_SETTING_KEY = "app.tenant_id"

AIRBYTE_API_URL = _optional(env("AIRBYTE_API_URL", default=None))
AIRBYTE_API_TOKEN = _optional(env("AIRBYTE_API_TOKEN", default=None))
AIRBYTE_USERNAME = _optional(env("AIRBYTE_USERNAME", default=None))
AIRBYTE_PASSWORD = _optional(env("AIRBYTE_PASSWORD", default=None))
LLM_API_URL = _optional(env("LLM_API_URL", default=None))
LLM_API_KEY = _optional(env("LLM_API_KEY", default=None))
LLM_MODEL = env("LLM_MODEL", default="gpt-5-codex")
LLM_TIMEOUT = env.float("LLM_TIMEOUT")
APP_VERSION = env("APP_VERSION")
