from __future__ import annotations

import logging
import uuid

import pytest


class _ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.mark.django_db
def test_correlation_id_propagates_from_header(api_client):
    handler = _ListHandler()
    logger = logging.getLogger("api.access")
    logger.addHandler(handler)
    logger.setLevel("INFO")

    response = api_client.get(
        "/api/health/",
        HTTP_X_CORRELATION_ID="req-12345",
    )

    assert response.status_code == 200
    assert response["X-Correlation-ID"] == "req-12345"

    try:
        record = next(r for r in handler.records if r.getMessage() == "request.completed")
    finally:
        logger.removeHandler(handler)
    assert getattr(record, "correlation_id", None) == "req-12345"


@pytest.mark.django_db
def test_correlation_id_generated_when_missing(api_client):
    handler = _ListHandler()
    logger = logging.getLogger("api.access")
    logger.addHandler(handler)
    logger.setLevel("INFO")

    response = api_client.get("/api/health/")

    assert response.status_code == 200
    generated = response["X-Correlation-ID"]
    assert generated
    uuid.UUID(generated)  # raises if invalid

    try:
        record = next(r for r in handler.records if r.getMessage() == "request.completed")
    finally:
        logger.removeHandler(handler)
    assert getattr(record, "correlation_id", None) == generated


@pytest.mark.django_db
def test_access_log_includes_runtime_context_markers(api_client, user):
    api_client.force_authenticate(user=user)
    handler = _ListHandler()
    logger = logging.getLogger("api.access")
    logger.addHandler(handler)
    logger.setLevel("INFO")

    response = api_client.post(
        "/api/integrations/meta/oauth/start/",
        {"runtime_context": {"dataset_source": "demo"}},
        format="json",
        HTTP_ORIGIN="http://localhost:5175",
    )

    assert response.status_code in {200, 503}
    try:
        record = next(r for r in handler.records if r.getMessage() == "request.completed")
    finally:
        logger.removeHandler(handler)

    runtime = getattr(record, "runtime", None)
    assert isinstance(runtime, dict)
    assert runtime.get("origin") == "http://localhost:5175"
    assert runtime.get("dataset_markers", {}).get("dataset_source") == "demo"
