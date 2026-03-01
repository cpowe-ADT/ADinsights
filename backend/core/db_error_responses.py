from __future__ import annotations

import logging
from typing import Any

from django.db import DatabaseError, OperationalError, ProgrammingError
from rest_framework import status
from rest_framework.response import Response

SCHEMA_OUT_OF_DATE_CODE = "schema_out_of_date"
SCHEMA_OUT_OF_DATE_DETAIL = "Database schema is out of date. Run backend migrations."


def is_schema_out_of_date_error(exc: Exception) -> bool:
    """Return True when a DB exception indicates missing columns/tables in current schema."""
    if not isinstance(exc, (DatabaseError, OperationalError, ProgrammingError)):
        return False

    message = str(exc).strip().lower()
    if not message:
        return False

    if "no such table" in message or "no such column" in message:
        return True

    if "undefinedtable" in message or "undefinedcolumn" in message:
        return True

    if "does not exist" in message and (
        " relation " in f" {message} "
        or " table " in f" {message} "
        or " column " in f" {message} "
        or "relation" in message
        or "column" in message
    ):
        return True

    return False


def schema_out_of_date_response(
    *,
    exc: Exception,
    logger: logging.Logger,
    endpoint: str,
    tenant_id: Any,
) -> Response | None:
    """Return a standardized 503 response when schema drift is detected."""
    if not is_schema_out_of_date_error(exc):
        return None

    logger.warning(
        "api.schema_out_of_date",
        extra={
            "endpoint": endpoint,
            "tenant_id": str(tenant_id) if tenant_id is not None else None,
            "exception_class": exc.__class__.__name__,
        },
    )

    return Response(
        {
            "detail": SCHEMA_OUT_OF_DATE_DETAIL,
            "code": SCHEMA_OUT_OF_DATE_CODE,
        },
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )
