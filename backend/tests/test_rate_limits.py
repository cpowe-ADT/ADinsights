from __future__ import annotations

from django.conf import settings
from django.core.cache import cache
from django.test import override_settings
import pytest


def _throttle_settings(auth_burst: str) -> dict[str, object]:
    rest_framework = dict(settings.REST_FRAMEWORK)
    rates = dict(rest_framework.get("DEFAULT_THROTTLE_RATES", {}))
    rates.update(
        {
            "auth_burst": auth_burst,
            "auth_sustained": "100/day",
            "public": "100/min",
        }
    )
    rest_framework["DEFAULT_THROTTLE_RATES"] = rates
    return rest_framework


@pytest.mark.django_db
def test_login_endpoint_enforces_auth_throttle(api_client, user):
    cache.clear()
    with override_settings(REST_FRAMEWORK=_throttle_settings("1/min")):
        first = api_client.post(
            "/api/auth/login/",
            {"username": user.username, "password": "wrong-password"},
            format="json",
        )
        second = api_client.post(
            "/api/auth/login/",
            {"username": user.username, "password": "wrong-password"},
            format="json",
        )

    assert first.status_code in {400, 401}
    assert second.status_code == 429


@pytest.mark.django_db
def test_jwt_token_endpoint_enforces_auth_throttle(api_client, user):
    cache.clear()
    with override_settings(REST_FRAMEWORK=_throttle_settings("1/min")):
        first = api_client.post(
            "/api/token/",
            {"username": user.username, "password": "wrong-password"},
            format="json",
        )
        second = api_client.post(
            "/api/token/",
            {"username": user.username, "password": "wrong-password"},
            format="json",
        )

    assert first.status_code in {400, 401}
    assert second.status_code == 429


@pytest.mark.django_db
def test_password_reset_request_enforces_auth_throttle(api_client, user):
    cache.clear()
    with override_settings(REST_FRAMEWORK=_throttle_settings("1/min")):
        first = api_client.post(
            "/api/auth/password-reset/",
            {"email": user.email},
            format="json",
        )
        second = api_client.post(
            "/api/auth/password-reset/",
            {"email": user.email},
            format="json",
        )

    assert first.status_code == 202
    assert second.status_code == 429
