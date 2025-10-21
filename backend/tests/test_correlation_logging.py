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
