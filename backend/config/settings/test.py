import os

# ruff: noqa: F405  # allow names brought in via star-imports in settings files

os.environ.setdefault("DJANGO_SECRET_KEY", "test")
os.environ.setdefault("CELERY_BROKER_URL", "memory://")
os.environ.setdefault("CELERY_RESULT_BACKEND", "cache+memory://")
os.environ.setdefault("KMS_KEY_ID", "test-key")
os.environ.setdefault("SECRETS_PROVIDER", "env")
os.environ.setdefault("KMS_PROVIDER", "local")
os.environ.setdefault("API_VERSION", "test")
os.environ.setdefault("DRF_THROTTLE_AUTH_BURST", "10000/min")
os.environ.setdefault("DRF_THROTTLE_AUTH_SUSTAINED", "100000/day")
os.environ.setdefault("DRF_THROTTLE_PUBLIC", "10000/min")

from .base import *  # noqa: F403,E402

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "test")
DEBUG = True
ALLOWED_HOSTS = ["*"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "memory://")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "cache+memory://")
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
KMS_PROVIDER = "local"
