"""Structured logging helpers and instrumentation for the core service."""

from __future__ import annotations

import contextvars
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from celery import Task
from django.conf import settings

from core.metrics import observe_task
from accounts.tenant_context import get_current_tenant_id

_correlation_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "correlation_id", default=None
)
_task_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "task_id", default=None
)


def emit_observability_event(
    logger: logging.Logger,
    event_name: str,
    *,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    """Emit a structured event payload with consistent event naming."""

    logger.log(level, event_name, extra={"event": event_name, **fields})


def set_correlation_id(value: Optional[str]) -> None:
    """Persist the correlation identifier for the current context."""

    _correlation_id_var.set(value)


def get_correlation_id() -> Optional[str]:
    """Return the active correlation identifier, if any."""

    return _correlation_id_var.get()


def clear_correlation_id() -> None:
    """Remove any correlation identifier bound to this context."""

    _correlation_id_var.set(None)


def set_task_id(value: Optional[str]) -> None:
    """Persist the current Celery task identifier for structured logging."""

    _task_id_var.set(value)


def get_task_id() -> Optional[str]:
    """Return the active Celery task identifier, if any."""

    return _task_id_var.get()


def clear_task_id() -> None:
    """Clear any task identifier bound to the context."""

    _task_id_var.set(None)


class JsonFormatter(logging.Formatter):
    """Render log records as structured JSON."""

    RESERVED_ATTRS: frozenset[str] = frozenset(
        {
            "args",
            "asctime",
            "created",
            "exc_info",
            "exc_text",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "message",
            "msg",
            "name",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "thread",
            "threadName",
        }
    )

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401 - interface contract
        payload: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "component": getattr(record, "component", record.name),
            "tenant_id": getattr(record, "tenant_id", None),
            "correlation_id": getattr(record, "correlation_id", None),
            "task_id": getattr(record, "task_id", None),
        }

        for key, value in record.__dict__.items():
            if key in self.RESERVED_ATTRS or key.startswith("_"):
                continue
            payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


class ContextFilter(logging.Filter):
    """Attach per-request/task context (correlation, tenant) to log records."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401 - interface contract
        correlation_id = get_correlation_id()
        if correlation_id:
            record.correlation_id = correlation_id

        tenant_id = get_current_tenant_id()
        if tenant_id:
            record.tenant_id = str(tenant_id)

        task_id = get_task_id()
        if task_id:
            record.task_id = task_id

        return True


class RequestCorrelationMiddleware:
    """Assign correlation IDs to incoming HTTP requests and responses."""

    HEADER_NAME = "X-Correlation-ID"

    def __init__(self, get_response):  # noqa: ANN001 - middleware signature
        self.get_response = get_response

    def __call__(self, request):  # noqa: ANN001 - middleware signature
        incoming = request.headers.get(self.HEADER_NAME)
        correlation_id = incoming or str(uuid.uuid4())
        set_correlation_id(correlation_id)
        try:
            response = self.get_response(request)
        finally:
            clear_correlation_id()
        response[self.HEADER_NAME] = correlation_id
        return response


class APILoggingMiddleware:
    """Middleware that emits structured access logs for API requests."""

    def __init__(self, get_response):  # noqa: ANN001 - middleware signature
        self.get_response = get_response
        self.logger = logging.getLogger("api.access")
        prefixes = getattr(settings, "API_LOGGING_PREFIXES", ("/api/",))
        self._api_prefixes: tuple[str, ...] = tuple(prefixes)

    def __call__(self, request):  # noqa: ANN001 - middleware signature
        if not request.path.startswith(self._api_prefixes):
            return self.get_response(request)

        start = time.perf_counter()
        response = self.get_response(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        resolver_match = getattr(request, "resolver_match", None)
        view_name = resolver_match.view_name if resolver_match else None
        user = getattr(request, "user", None)
        tenant_id = getattr(user, "tenant_id", None) if getattr(user, "is_authenticated", False) else None
        self.logger.info(
            "request.completed",
            extra={
                "http": {
                    "method": request.method,
                    "path": request.get_full_path(),
                    "status_code": response.status_code,
                },
                "duration_ms": duration_ms,
                "view": view_name,
                "user_id": getattr(user, "id", None) if user else None,
                "tenant_id": str(tenant_id) if tenant_id else None,
                "remote_addr": request.META.get("HTTP_X_FORWARDED_FOR")
                or request.META.get("REMOTE_ADDR"),
            },
        )
        return response


class InstrumentedTask(Task):
    """Celery task base class that emits structured lifecycle logs."""

    abstract = True
    logger = logging.getLogger("celery.tasks")

    def before_start(self, task_id, args, kwargs):  # noqa: ANN001 - celery hook
        self.request._start_time = time.perf_counter()
        set_correlation_id(task_id)
        set_task_id(task_id)
        self.logger.info(
            "task.started",
            extra=self._task_extra(task_id, args, kwargs),
        )
        super().before_start(task_id, args, kwargs)

    def after_return(self, status, retval, task_id, args, kwargs, einfo):  # noqa: ANN001 - celery hook
        start_time = getattr(self.request, "_start_time", None)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2) if start_time else None
        duration_seconds = (duration_ms / 1000) if duration_ms is not None else None
        extra = self._task_extra(task_id, args, kwargs)
        extra.update(
            {
                "status": status,
                "duration_ms": duration_ms,
            }
        )
        if einfo:
            extra["exception"] = str(einfo.exception)
            self.logger.error("task.failed", extra=extra)
        else:
            self.logger.info("task.succeeded", extra=extra)
        observe_task(self.name, status, duration_seconds)
        try:
            super().after_return(status, retval, task_id, args, kwargs, einfo)
        finally:
            clear_correlation_id()
            clear_task_id()

    def _task_extra(self, task_id, args, kwargs) -> Dict[str, Any]:  # noqa: ANN001
        return {
            "task": {
                "name": self.name,
                "id": task_id,
                "args_count": len(args),
                "kwargs_keys": sorted(kwargs.keys()),
            }
        }
