# Settings for tests. Wildcard import is intentional for Django settings.
from .base import *  # noqa: F403
import os

# ruff: noqa: F405  # allow names originating from the wildcard import

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "test")
DEBUG = True
ALLOWED_HOSTS = ["*"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "memory://")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "cache+memory://")
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
