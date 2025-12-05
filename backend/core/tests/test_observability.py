from __future__ import annotations

import logging

from accounts.tenant_context import tenant_context
from core.observability import (
    ContextFilter,
    clear_correlation_id,
    clear_task_id,
    set_correlation_id,
    set_task_id,
)


def test_context_filter_attaches_ids():
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="hello",
        args=(),
        exc_info=None,
    )
    set_correlation_id("corr-123")
    set_task_id("task-456")
    try:
        with tenant_context("tenant-abc"):
            context_filter = ContextFilter()
            assert context_filter.filter(record) is True
            assert record.correlation_id == "corr-123"
            assert record.task_id == "task-456"
            assert record.tenant_id == "tenant-abc"
    finally:
        clear_correlation_id()
        clear_task_id()
