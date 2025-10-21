from __future__ import annotations

# ruff: noqa: E402

import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")
os.environ.update(
    {
        "DJANGO_SECRET_KEY": "test-secret-key",
        "CELERY_BROKER_URL": "memory://",
        "CELERY_RESULT_BACKEND": "cache+memory://",
        "SECRETS_PROVIDER": "env",
        "KMS_PROVIDER": "local",
        "KMS_KEY_ID": "test-key",
        "AWS_REGION": "us-east-1",
        "AIRBYTE_API_URL": "http://localhost:8001",
        "AIRBYTE_API_TOKEN": "test-token",
        "API_VERSION": "test-version",
    }
)

import django

django.setup()

import pytest
from rest_framework.test import APIClient

from accounts.models import Tenant, User


@pytest.fixture
def tenant(db) -> Tenant:
    return Tenant.objects.create(name="Test Tenant")


@pytest.fixture
def user(tenant) -> User:
    user = User.objects.create_user(
        username="user@example.com",
        email="user@example.com",
        tenant=tenant,
    )
    user.set_password("password123")
    user.save()
    return user


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture(autouse=True)
def reset_local_kms(monkeypatch):
    from core.crypto.kms import LocalKmsClient
    from django.conf import settings

    LocalKmsClient._store.clear()
    settings.KMS_PROVIDER = "local"
    settings.AWS_REGION = "us-east-1"
    yield
