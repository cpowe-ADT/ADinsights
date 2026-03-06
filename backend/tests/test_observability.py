from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from core.observability import (
    InstrumentedTask,
    extract_task_queue_name,
    extract_task_queue_wait_seconds,
)


def test_extract_task_queue_name_prefers_delivery_info():
    request = SimpleNamespace(
        delivery_info={"routing_key": "snapshot"},
        headers={"routing_key": "sync"},
    )

    assert extract_task_queue_name(request, default_queue="default") == "snapshot"


def test_extract_task_queue_wait_seconds_reads_header_timestamp():
    published_at = datetime(2026, 3, 6, 10, 0, tzinfo=timezone.utc)
    request = SimpleNamespace(headers={"sent_at": published_at.isoformat()}, properties={})

    wait_seconds = extract_task_queue_wait_seconds(
        request,
        now=published_at + timedelta(seconds=5),
    )

    assert wait_seconds == pytest.approx(5.0)


def test_extract_task_queue_wait_seconds_reads_properties_timestamp():
    published_at = datetime(2026, 3, 6, 9, 0, tzinfo=timezone.utc)
    request = SimpleNamespace(headers={}, properties={"timestamp": int(published_at.timestamp())})

    wait_seconds = extract_task_queue_wait_seconds(
        request,
        now=published_at + timedelta(seconds=2),
    )

    assert wait_seconds == pytest.approx(2.0)


def test_instrumented_task_before_start_records_queue_context(monkeypatch):
    captured: dict[str, object] = {}

    def fake_observe_queue_start(*, task_name: str, queue_name: str | None, queue_wait_seconds: float | None):
        captured["task_name"] = task_name
        captured["queue_name"] = queue_name
        captured["queue_wait_seconds"] = queue_wait_seconds

    monkeypatch.setattr("core.observability.observe_task_queue_start", fake_observe_queue_start)
    monkeypatch.setattr("core.observability.observe_task", lambda *args, **kwargs: None)

    sent_at = datetime.now(tz=timezone.utc) - timedelta(seconds=1)
    
    class DummyTask(InstrumentedTask):
        name = "dummy.instrumented.task"
        request = SimpleNamespace(
            delivery_info={"routing_key": "sync"},
            headers={"sent_at": sent_at.isoformat()},
            properties={},
        )

    task = DummyTask()

    task.before_start("task-123", (), {})
    task.after_return("SUCCESS", None, "task-123", (), {}, None)

    assert task.request._queue_name == "sync"
    assert captured["task_name"] == "dummy.instrumented.task"
    assert captured["queue_name"] == "sync"
    assert isinstance(captured["queue_wait_seconds"], float)
