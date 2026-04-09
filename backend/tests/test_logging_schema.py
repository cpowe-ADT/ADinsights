from __future__ import annotations

import json
import logging

from config.logging import build_logging_config
from core.observability import JsonFormatter


def test_json_formatter_includes_required_fields():
    record = logging.LogRecord(
        name="api.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="request.completed",
        args=(),
        exc_info=None,
    )
    formatter = JsonFormatter()
    payload = json.loads(formatter.format(record))

    assert payload["timestamp"]
    assert payload["level"] == "INFO"
    assert payload["message"] == "request.completed"
    assert payload["component"] == "api.access"
    assert payload["tenant_id"] is None
    assert payload["correlation_id"] is None
    assert payload["task_id"] is None


def test_logging_config_suppresses_httpx_info_logs():
    payload = build_logging_config("INFO")

    assert payload["loggers"]["httpx"]["level"] == "WARNING"
    assert payload["loggers"]["httpx"]["propagate"] is False
    assert payload["loggers"]["httpcore"]["level"] == "WARNING"
    assert payload["loggers"]["httpcore"]["propagate"] is False
