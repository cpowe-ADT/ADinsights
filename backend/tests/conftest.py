from __future__ import annotations

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
