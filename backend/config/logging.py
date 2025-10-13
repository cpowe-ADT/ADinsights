"""Logging configuration helpers for the backend service."""

from __future__ import annotations

import logging
from typing import Any

DEFAULT_LOG_LEVEL = "INFO"


def _normalize_level(level: str) -> str:
    """Return a valid logging level name, defaulting to ``INFO`` when unknown."""

    if not level:
        return DEFAULT_LOG_LEVEL

    normalized = level.upper()
    # ``logging.getLevelNamesMapping`` is available on Python 3.11+ and provides
    # a canonical registry of valid level names without reaching into the
    # logging module's internals.
    level_names = logging.getLevelNamesMapping()
    if normalized in level_names:
        return normalized
    return DEFAULT_LOG_LEVEL


def build_logging_config(level: str = DEFAULT_LOG_LEVEL) -> dict[str, Any]:
    """Produce a ``dictConfig`` logging payload that emits JSON to stdout."""

    log_level = _normalize_level(level)

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": "core.observability.JsonFormatter",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "json",
            }
        },
        "loggers": {
            "": {"handlers": ["console"], "level": log_level},
            "django": {"handlers": ["console"], "level": log_level},
            "django.request": {
                "handlers": ["console"],
                "level": log_level,
                "propagate": False,
            },
            "api.access": {
                "handlers": ["console"],
                "level": log_level,
                "propagate": False,
            },
            "celery.tasks": {
                "handlers": ["console"],
                "level": log_level,
                "propagate": False,
            },
        },
    }

