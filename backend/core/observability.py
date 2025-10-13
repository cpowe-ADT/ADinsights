"""Structured logging helpers and instrumentation for the core service."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict

from celery import Task
from django.conf import settings


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
        }

        for key, value in record.__dict__.items():
            if key in self.RESERVED_ATTRS or key.startswith("_"):
                continue
            payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


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
        self.logger.info(
            "task.started",
            extra=self._task_extra(task_id, args, kwargs),
        )
        super().before_start(task_id, args, kwargs)

    def after_return(self, status, retval, task_id, args, kwargs, einfo):  # noqa: ANN001 - celery hook
        start_time = getattr(self.request, "_start_time", None)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2) if start_time else None
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
        super().after_return(status, retval, task_id, args, kwargs, einfo)

    def _task_extra(self, task_id, args, kwargs) -> Dict[str, Any]:  # noqa: ANN001
        return {
            "task": {
                "name": self.name,
                "id": task_id,
                "args_count": len(args),
                "kwargs_keys": sorted(kwargs.keys()),
            }
        }

