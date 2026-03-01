from __future__ import annotations

from django.test import override_settings


@override_settings(
    CORS_ALLOW_ALL_ORIGINS=False,
    CORS_ALLOWED_ORIGINS=["https://app.adinsights.local"],
    CORS_ALLOWED_METHODS=["GET", "POST", "OPTIONS"],
    CORS_ALLOWED_HEADERS=["authorization", "content-type", "x-tenant-id"],
    CORS_ALLOW_CREDENTIALS=True,
    CORS_PREFLIGHT_MAX_AGE=600,
)
def test_cors_allows_configured_origin(api_client):
    response = api_client.get("/api/health/", HTTP_ORIGIN="https://app.adinsights.local")

    assert response.status_code == 200
    assert response["Access-Control-Allow-Origin"] == "https://app.adinsights.local"
    assert response["Access-Control-Allow-Credentials"] == "true"


@override_settings(
    CORS_ALLOW_ALL_ORIGINS=False,
    CORS_ALLOWED_ORIGINS=["https://app.adinsights.local"],
    CORS_ALLOWED_METHODS=["GET", "POST", "OPTIONS"],
    CORS_ALLOWED_HEADERS=["authorization", "content-type", "x-tenant-id"],
    CORS_ALLOW_CREDENTIALS=True,
    CORS_PREFLIGHT_MAX_AGE=600,
)
def test_cors_blocks_unconfigured_preflight_origin(api_client):
    response = api_client.options(
        "/api/health/",
        HTTP_ORIGIN="https://evil.example.com",
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS="Authorization,Content-Type",
    )

    assert response.status_code == 403
    assert "Access-Control-Allow-Origin" not in response


@override_settings(
    CORS_ALLOW_ALL_ORIGINS=False,
    CORS_ALLOWED_ORIGINS=["https://app.adinsights.local"],
    CORS_ALLOWED_METHODS=["GET", "POST", "OPTIONS"],
    CORS_ALLOWED_HEADERS=["authorization", "content-type", "x-tenant-id"],
    CORS_ALLOW_CREDENTIALS=True,
    CORS_PREFLIGHT_MAX_AGE=600,
)
def test_cors_preflight_returns_allow_headers_for_configured_origin(api_client):
    response = api_client.options(
        "/api/health/",
        HTTP_ORIGIN="https://app.adinsights.local",
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS="Authorization,Content-Type,X-Tenant-Id",
    )

    assert response.status_code == 204
    assert response["Access-Control-Allow-Origin"] == "https://app.adinsights.local"
    assert response["Access-Control-Allow-Methods"] == "GET, POST, OPTIONS"
    assert response["Access-Control-Allow-Headers"] == "authorization, content-type, x-tenant-id"
    assert response["Access-Control-Max-Age"] == "600"

