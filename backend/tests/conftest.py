from __future__ import annotations

# ruff: noqa: E402

import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
os.environ.setdefault("SECRETS_PROVIDER", "env")
os.environ.setdefault("KMS_PROVIDER", "aws")
os.environ.setdefault("KMS_KEY_ID", "test-key")

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
