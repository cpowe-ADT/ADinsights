from __future__ import annotations

from io import StringIO
import json

import pytest
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from core.metrics import observe_task_queue_start, observe_task_retry, reset_metrics


class _DummyResponse:
    def __init__(self, *, status_code: int, body: str = "", payload: dict[str, object] | None = None):
        self.status_code = status_code
        self.content = body.encode("utf-8")
        self._payload = payload or {}

    def json(self) -> dict[str, object]:
        return self._payload


class _DummyClient:
    def __init__(self, *, metrics_body: str, external_status: int = 200):
        self._metrics_body = metrics_body
        self._external_status = external_status

    def get(self, path: str, *_args, **_kwargs) -> _DummyResponse:
        if path == "/metrics/app/":
            return _DummyResponse(status_code=200, body=self._metrics_body)
        if path == "/api/health/":
            return _DummyResponse(status_code=200, payload={"status": "ok"})
        if path == "/api/timezone/":
            return _DummyResponse(status_code=200, payload={"timezone": "America/Jamaica"})
        if path in {"/api/health/airbyte/", "/api/health/dbt/"}:
            return _DummyResponse(status_code=self._external_status, payload={"status": "degraded"})
        return _DummyResponse(status_code=404, payload={"status": "error"})


class _DummyRateLimitClient(_DummyClient):
    def __init__(self, *, metrics_body: str, external_status: int = 200):
        super().__init__(metrics_body=metrics_body, external_status=external_status)
        self._auth_attempts = 0
        self._public_attempts = 0

    def get(self, path: str, *_args, **_kwargs) -> _DummyResponse:
        if path == "/api/health/version/":
            self._public_attempts += 1
            return _DummyResponse(status_code=429 if self._public_attempts > 1 else 200)
        return super().get(path, *_args, **_kwargs)

    def post(self, path: str, *_args, **_kwargs) -> _DummyResponse:
        if path == "/api/token/":
            self._auth_attempts += 1
            return _DummyResponse(status_code=429 if self._auth_attempts > 1 else 401)
        return _DummyResponse(status_code=404, payload={"status": "error"})


class _DummyClientWithDefaults(_DummyClient):
    def __init__(self, *, metrics_body: str, external_status: int = 200):
        super().__init__(metrics_body=metrics_body, external_status=external_status)
        self.defaults: dict[str, str] = {}


def _rest_framework_with_rates(**rates: str) -> dict[str, object]:
    rest_framework = dict(settings.REST_FRAMEWORK)
    throttle_rates = dict(rest_framework.get("DEFAULT_THROTTLE_RATES", {}))
    throttle_rates.update(rates)
    rest_framework["DEFAULT_THROTTLE_RATES"] = throttle_rates
    return rest_framework


@pytest.mark.django_db
def test_backend_release_smoke_command_passes_with_default_tolerances():
    stdout = StringIO()
    call_command("backend_release_smoke", stdout=stdout)
    payload = json.loads(stdout.getvalue())
    assert payload["ok"] is True
    assert payload["missing_metrics"] == []


@pytest.mark.django_db
def test_backend_release_smoke_command_fails_on_missing_metric():
    with pytest.raises(CommandError):
        call_command("backend_release_smoke", "--expect-metric", "definitely_missing_metric")


def test_backend_release_smoke_resolves_http_host_from_allowed_hosts(monkeypatch):
    from analytics.management.commands import backend_release_smoke as command_module

    monkeypatch.setattr(command_module.settings, "ALLOWED_HOSTS", ["api.adinsights.local"], raising=False)

    assert command_module._resolve_client_http_host() == "api.adinsights.local"


def test_backend_release_smoke_resolves_http_host_from_wildcard_only(monkeypatch):
    from analytics.management.commands import backend_release_smoke as command_module

    monkeypatch.setattr(command_module.settings, "ALLOWED_HOSTS", ["*"], raising=False)

    assert command_module._resolve_client_http_host() == "localhost"


@pytest.mark.django_db
def test_backend_release_smoke_sets_http_host_on_client_defaults(monkeypatch):
    from analytics.management.commands import backend_release_smoke as command_module

    metrics_body = "celery_task_executions_total{task_name=\"a\",status=\"success\"} 1\n"
    dummy_client = _DummyClientWithDefaults(metrics_body=metrics_body)
    monkeypatch.setattr(command_module, "Client", lambda: dummy_client)
    monkeypatch.setattr(command_module.settings, "ALLOWED_HOSTS", ["internal.adinsights.local"], raising=False)

    with pytest.raises(CommandError):
        call_command("backend_release_smoke", "--expect-metric", "definitely_missing_metric")

    assert dummy_client.defaults.get("HTTP_HOST") == "internal.adinsights.local"


@pytest.mark.django_db
def test_backend_release_smoke_command_strict_external_fails_without_external_success():
    with pytest.raises(CommandError):
        call_command("backend_release_smoke", "--strict-external")


@pytest.mark.django_db
def test_backend_release_smoke_command_validates_metric_label_expectation(monkeypatch):
    from analytics.management.commands import backend_release_smoke as command_module

    metrics_body = (
        'celery_task_queue_starts_total{task_name="a",queue_name="sync"} 1\n'
        'celery_task_retries_total{task_name="a",reason="airbyte_client_error"} 1\n'
    )
    monkeypatch.setattr(
        command_module,
        "Client",
        lambda: _DummyClient(metrics_body=metrics_body),
    )

    stdout = StringIO()
    call_command(
        "backend_release_smoke",
        "--expect-metric",
        "celery_task_queue_starts_total",
        "--expect-metric-label",
        "celery_task_queue_starts_total,queue_name=sync",
        stdout=stdout,
    )
    payload = json.loads(stdout.getvalue())
    assert payload["ok"] is True
    assert payload["missing_metric_labels"] == []


@pytest.mark.django_db
def test_backend_release_smoke_command_checks_rate_limits(monkeypatch):
    from analytics.management.commands import backend_release_smoke as command_module

    metrics_body = "celery_task_executions_total{task_name=\"a\",status=\"success\"} 1\n"
    dummy_client = _DummyRateLimitClient(metrics_body=metrics_body)
    monkeypatch.setattr(command_module, "Client", lambda: dummy_client)

    with override_settings(
        REST_FRAMEWORK=_rest_framework_with_rates(
            auth_burst="1/min",
            auth_sustained="100/day",
            public="1/min",
        )
    ):
        stdout = StringIO()
        call_command(
            "backend_release_smoke",
            "--expect-metric",
            "celery_task_executions_total",
            "--check-rate-limits",
            stdout=stdout,
        )

    payload = json.loads(stdout.getvalue())
    assert payload["ok"] is True
    assert [check["name"] for check in payload["rate_limit_checks"]] == [
        "auth_burst_token_obtain",
        "public_health_version",
    ]
    assert all(check["ok"] for check in payload["rate_limit_checks"])
    assert dummy_client._auth_attempts == 2
    assert dummy_client._public_attempts == 2


@pytest.mark.django_db
def test_backend_release_smoke_command_fails_when_rate_limit_budget_too_large(monkeypatch):
    from analytics.management.commands import backend_release_smoke as command_module

    metrics_body = "celery_task_executions_total{task_name=\"a\",status=\"success\"} 1\n"
    monkeypatch.setattr(
        command_module,
        "Client",
        lambda: _DummyRateLimitClient(metrics_body=metrics_body),
    )

    with override_settings(
        REST_FRAMEWORK=_rest_framework_with_rates(
            auth_burst="10/min",
            auth_sustained="100/day",
            public="1/min",
        )
    ):
        with pytest.raises(CommandError, match="exceeds max"):
            call_command(
                "backend_release_smoke",
                "--expect-metric",
                "celery_task_executions_total",
                "--check-rate-limits",
                "--max-rate-limit-smoke-attempts",
                "2",
            )


@pytest.mark.django_db
def test_backend_release_smoke_command_fails_on_missing_metric_label(monkeypatch):
    from analytics.management.commands import backend_release_smoke as command_module

    metrics_body = 'celery_task_queue_starts_total{task_name="a",queue_name="sync"} 1\n'
    monkeypatch.setattr(
        command_module,
        "Client",
        lambda: _DummyClient(metrics_body=metrics_body),
    )

    with pytest.raises(CommandError):
        call_command(
            "backend_release_smoke",
            "--expect-metric",
            "celery_task_queue_starts_total",
            "--expect-metric-label",
            "celery_task_queue_starts_total,queue_name=snapshot",
        )


@pytest.mark.django_db
def test_backend_release_smoke_command_fails_when_unknown_retry_share_too_high(monkeypatch):
    from analytics.management.commands import backend_release_smoke as command_module

    metrics_body = (
        'celery_task_retries_total{task_name="a",reason="unknown"} 3\n'
        'celery_task_retries_total{task_name="a",reason="airbyte_client_error"} 1\n'
    )
    monkeypatch.setattr(
        command_module,
        "Client",
        lambda: _DummyClient(metrics_body=metrics_body),
    )

    with pytest.raises(CommandError):
        call_command(
            "backend_release_smoke",
            "--expect-metric",
            "celery_task_retries_total",
            "--max-unknown-retry-share",
            "0.5",
        )


@pytest.mark.django_db
def test_backend_release_smoke_command_allows_unknown_retry_share_within_threshold(monkeypatch):
    from analytics.management.commands import backend_release_smoke as command_module

    metrics_body = (
        'celery_task_retries_total{task_name="a",reason="unknown"} 1\n'
        'celery_task_retries_total{task_name="a",reason="airbyte_client_error"} 3\n'
    )
    monkeypatch.setattr(
        command_module,
        "Client",
        lambda: _DummyClient(metrics_body=metrics_body),
    )

    stdout = StringIO()
    call_command(
        "backend_release_smoke",
        "--expect-metric",
        "celery_task_retries_total",
        "--max-unknown-retry-share",
        "0.5",
        stdout=stdout,
    )
    payload = json.loads(stdout.getvalue())
    assert payload["ok"] is True
    assert payload["unknown_retry_share"] == pytest.approx(0.25)


@pytest.mark.django_db
def test_backend_release_smoke_command_treats_airbyte_unknown_reason_as_unknown(monkeypatch):
    from analytics.management.commands import backend_release_smoke as command_module

    metrics_body = (
        'celery_task_retries_total{task_name="a",reason="airbyte_unknown_error"} 2\n'
        'celery_task_retries_total{task_name="a",reason="airbyte_client_error"} 1\n'
    )
    monkeypatch.setattr(
        command_module,
        "Client",
        lambda: _DummyClient(metrics_body=metrics_body),
    )

    with pytest.raises(CommandError):
        call_command(
            "backend_release_smoke",
            "--expect-metric",
            "celery_task_retries_total",
            "--max-unknown-retry-share",
            "0.5",
        )


@pytest.mark.django_db
def test_backend_release_smoke_command_supports_custom_unknown_retry_reason_labels(monkeypatch):
    from analytics.management.commands import backend_release_smoke as command_module

    metrics_body = (
        'celery_task_retries_total{task_name="a",reason="custom_unknown_retry"} 1\n'
        'celery_task_retries_total{task_name="a",reason="airbyte_client_error"} 3\n'
    )
    monkeypatch.setattr(
        command_module,
        "Client",
        lambda: _DummyClient(metrics_body=metrics_body),
    )

    stdout = StringIO()
    call_command(
        "backend_release_smoke",
        "--expect-metric",
        "celery_task_retries_total",
        "--max-unknown-retry-share",
        "0.5",
        "--unknown-retry-reason",
        "custom_unknown_retry",
        stdout=stdout,
    )
    payload = json.loads(stdout.getvalue())
    assert payload["ok"] is True
    assert payload["unknown_retry_share"] == pytest.approx(0.25)
    assert payload["unknown_retry_reason_labels"] == ["custom_unknown_retry"]


@pytest.mark.django_db
def test_backend_release_smoke_command_strict_observability_passes(monkeypatch):
    from analytics.management.commands import backend_release_smoke as command_module

    metrics_body = (
        'celery_task_queue_starts_total{task_name="a",queue_name="sync"} 1\n'
        'celery_task_queue_starts_total{task_name="a",queue_name="snapshot"} 1\n'
        'celery_task_queue_starts_total{task_name="a",queue_name="summary"} 1\n'
        'celery_task_retries_total{task_name="a",reason="airbyte_client_error"} 3\n'
    )
    monkeypatch.setattr(
        command_module,
        "Client",
        lambda: _DummyClient(metrics_body=metrics_body),
    )

    stdout = StringIO()
    call_command(
        "backend_release_smoke",
        "--strict-observability",
        "--expect-metric",
        "celery_task_queue_starts_total",
        "--expect-metric",
        "celery_task_retries_total",
        stdout=stdout,
    )
    payload = json.loads(stdout.getvalue())
    assert payload["ok"] is True
    assert payload["strict_observability"] is True
    assert payload["missing_metric_labels"] == []
    assert payload["unknown_retry_share"] == pytest.approx(0.0)
    assert "airbyte_unknown_error" in payload["unknown_retry_reason_labels"]


@pytest.mark.django_db
def test_backend_release_smoke_command_strict_observability_fails_missing_queue_label(monkeypatch):
    from analytics.management.commands import backend_release_smoke as command_module

    metrics_body = (
        'celery_task_queue_starts_total{task_name="a",queue_name="sync"} 1\n'
        'celery_task_queue_starts_total{task_name="a",queue_name="summary"} 1\n'
        'celery_task_retries_total{task_name="a",reason="airbyte_client_error"} 1\n'
    )
    monkeypatch.setattr(
        command_module,
        "Client",
        lambda: _DummyClient(metrics_body=metrics_body),
    )

    with pytest.raises(CommandError):
        call_command(
            "backend_release_smoke",
            "--strict-observability",
            "--expect-metric",
            "celery_task_queue_starts_total",
            "--expect-metric",
            "celery_task_retries_total",
        )


@pytest.mark.django_db
def test_backend_release_smoke_command_strict_observability_fails_unknown_retry_share(monkeypatch):
    from analytics.management.commands import backend_release_smoke as command_module

    metrics_body = (
        'celery_task_queue_starts_total{task_name="a",queue_name="sync"} 1\n'
        'celery_task_queue_starts_total{task_name="a",queue_name="snapshot"} 1\n'
        'celery_task_queue_starts_total{task_name="a",queue_name="summary"} 1\n'
        'celery_task_retries_total{task_name="a",reason="unknown"} 2\n'
        'celery_task_retries_total{task_name="a",reason="airbyte_client_error"} 1\n'
    )
    monkeypatch.setattr(
        command_module,
        "Client",
        lambda: _DummyClient(metrics_body=metrics_body),
    )

    with pytest.raises(CommandError):
        call_command(
            "backend_release_smoke",
            "--strict-observability",
            "--expect-metric",
            "celery_task_queue_starts_total",
            "--expect-metric",
            "celery_task_retries_total",
        )


@pytest.mark.django_db
def test_backend_release_smoke_command_strict_observability_fails_unknown_retry_share_end_to_end():
    reset_metrics()
    observe_task_queue_start(task_name="analytics.sync_metrics_snapshots", queue_name="sync", queue_wait_seconds=0.1)
    observe_task_queue_start(
        task_name="analytics.sync_metrics_snapshots",
        queue_name="snapshot",
        queue_wait_seconds=0.1,
    )
    observe_task_queue_start(
        task_name="analytics.sync_metrics_snapshots",
        queue_name="summary",
        queue_wait_seconds=0.1,
    )
    observe_task_retry(task_name="core.tasks.sync_meta_metrics", reason="airbyte_unknown_error")
    observe_task_retry(task_name="core.tasks.sync_meta_metrics", reason="airbyte_client_error")

    with pytest.raises(CommandError, match="Unknown retry reason share"):
        call_command(
            "backend_release_smoke",
            "--strict-observability",
            "--expect-metric",
            "celery_task_queue_starts_total",
            "--expect-metric",
            "celery_task_retries_total",
            "--max-unknown-retry-share",
            "0.4",
        )
