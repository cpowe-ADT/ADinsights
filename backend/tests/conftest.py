from __future__ import annotations

# ruff: noqa: E402

import os
import sys
import warnings
from pathlib import Path

from django.utils.deprecation import RemovedInDjango60Warning

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
from tests.integration.gating import is_integration_test_path, should_collect_path


@pytest.fixture
def tenant(db) -> Tenant:
    return Tenant.objects.create(name="Test Tenant")


@pytest.fixture
def user(tenant) -> User:
    return User.objects.create_user(
        username="user@example.com",
        email="user@example.com",
        tenant=tenant,
        password="password123",
    )


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture(autouse=True)
def suppress_removed_in_django60_warnings():
    warnings.simplefilter("ignore", RemovedInDjango60Warning)
    yield


@pytest.fixture(autouse=True)
def reset_local_kms(monkeypatch):
    from core.crypto.kms import LocalKmsClient
    from django.conf import settings

    LocalKmsClient._store.clear()
    settings.KMS_PROVIDER = "local"
    settings.AWS_REGION = "us-east-1"
    yield


def pytest_ignore_collect(collection_path, config):  # noqa: ANN001, ARG001
    return not should_collect_path(collection_path)


def pytest_collection_modifyitems(config, items):  # noqa: ANN001
    for item in items:
        item_path = getattr(item, "path", getattr(item, "fspath", ""))
        if "integration" in item.keywords or is_integration_test_path(item_path):
            item.add_marker(pytest.mark.integration)
            continue
        item.add_marker(pytest.mark.fast)
