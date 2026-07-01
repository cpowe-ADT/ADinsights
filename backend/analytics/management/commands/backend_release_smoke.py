from __future__ import annotations

import json
import re
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from uuid import uuid4

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.test import Client

from core.metrics import ensure_task_queue_start_series


DEFAULT_REQUIRED_METRICS = [
    "celery_task_executions_total",
    "celery_task_retries_total",
    "celery_task_queue_starts_total",
    "celery_task_queue_wait_seconds",
    "combined_metrics_request_duration_seconds",
    "airbyte_sync_latency_seconds",
    "dbt_run_duration_seconds",
]
DEFAULT_STRICT_OBSERVABILITY_MAX_UNKNOWN_RETRY_SHARE = 0.10
DEFAULT_UNKNOWN_RETRY_REASON_LABELS = (
    "unknown",
    "airbyte_unknown_error",
    "meta_graph_unknown_error",
    "meta_page_insights_unknown",
)
STRICT_OBSERVABILITY_QUEUE_SETTINGS = (
    ("CELERY_QUEUE_SYNC", "sync"),
    ("CELERY_QUEUE_SNAPSHOT", "snapshot"),
    ("CELERY_QUEUE_SUMMARY", "summary"),
)
STRICT_OBSERVABILITY_SERIES_TASK_NAME = "backend_release_smoke.strict_observability"


@dataclass(frozen=True)
class EndpointCheck:
    path: str
    allowed_statuses: tuple[int, ...]


@dataclass(frozen=True)
class RateLimitCheck:
    name: str
    scope: str
    method: str
    path: str
    expected_prelimit_statuses: tuple[int, ...]
    payload: dict[str, object] | None = None
    extra: dict[str, str] | None = None


_SAMPLE_LINE_RE = re.compile(
    r"^(?P<name>[a-zA-Z_:][a-zA-Z0-9_:]*)"
    r"(?:\{(?P<labels>[^}]*)\})?"
    r"\s+"
    r"(?P<value>[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)"
    r"(?:\s+[0-9]+)?$"
)
_LABEL_PAIR_RE = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)="((?:[^"\\]|\\.)*)"')


def _parse_metric_samples(metrics_body: str, metric_name: str) -> list[tuple[dict[str, str], float]]:
    samples: list[tuple[dict[str, str], float]] = []
    for raw_line in metrics_body.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _SAMPLE_LINE_RE.match(line)
        if match is None or match.group("name") != metric_name:
            continue
        labels_raw = match.group("labels") or ""
        labels: dict[str, str] = {}
        for key, value in _LABEL_PAIR_RE.findall(labels_raw):
            labels[key] = bytes(value, "utf-8").decode("unicode_escape")
        samples.append((labels, float(match.group("value"))))
    return samples


def _parse_metric_label_expectation(raw: str) -> tuple[str, dict[str, str]]:
    parts = [part.strip() for part in raw.split(",") if part and part.strip()]
    if not parts:
        raise CommandError("Invalid --expect-metric-label value: empty expectation.")
    metric_name = parts[0]
    labels: dict[str, str] = {}
    for pair in parts[1:]:
        if "=" not in pair:
            raise CommandError(
                f"Invalid --expect-metric-label value '{raw}'. "
                "Use format metric_name,label=value[,label=value]."
            )
        key, value = pair.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or not value:
            raise CommandError(
                f"Invalid --expect-metric-label value '{raw}'. "
                "Use non-empty label keys and values."
            )
        labels[key] = value
    return metric_name, labels


def _resolve_client_http_host() -> str:
    allowed_hosts = getattr(settings, "ALLOWED_HOSTS", []) or []
    for raw_host in allowed_hosts:
        if not isinstance(raw_host, str):
            continue
        host = raw_host.strip()
        if not host or host == "*":
            continue
        normalized = host.lstrip(".")
        if normalized:
            return normalized
    return "localhost"


def _normalize_queue_label(queue_name: str | None) -> str:
    return (queue_name or "unknown").strip().lower() or "unknown"


def _strict_observability_queue_names() -> tuple[str, ...]:
    return tuple(
        str(getattr(settings, setting_name, default_name))
        for setting_name, default_name in STRICT_OBSERVABILITY_QUEUE_SETTINGS
    )


def _default_strict_observability_metric_labels() -> list[tuple[str, dict[str, str]]]:
    return [
        ("celery_task_queue_starts_total", {"queue_name": _normalize_queue_label(queue_name)})
        for queue_name in _strict_observability_queue_names()
    ]


def _ensure_strict_observability_series() -> None:
    ensure_task_queue_start_series(
        task_name=STRICT_OBSERVABILITY_SERIES_TASK_NAME,
        queue_names=_strict_observability_queue_names(),
    )


def _configured_rate(scope: str) -> str:
    rates = settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {})
    rate = str(rates.get(scope) or "").strip()
    if not rate:
        raise CommandError(f"No DRF throttle rate configured for scope '{scope}'.")
    return rate


def _attempts_required_for_rate(rate: str) -> int:
    try:
        num_requests_raw, _period = rate.split("/", 1)
        num_requests = int(num_requests_raw)
    except (TypeError, ValueError) as exc:
        raise CommandError(f"Throttle rate '{rate}' is invalid.") from exc
    if num_requests < 1:
        raise CommandError(f"Throttle rate '{rate}' is not bounded.")
    return num_requests + 1


def _exercise_rate_limit(
    *,
    client: Client,
    check: RateLimitCheck,
    max_attempts: int,
) -> dict[str, object]:
    rate = _configured_rate(check.scope)
    attempts_required = _attempts_required_for_rate(rate)
    result: dict[str, object] = {
        "name": check.name,
        "scope": check.scope,
        "method": check.method,
        "path": check.path,
        "configured_rate": rate,
        "attempts_required": attempts_required,
        "attempts_made": 0,
        "observed_statuses": [],
        "ok": False,
    }
    if attempts_required > max_attempts:
        result["failure"] = (
            f"Configured rate requires {attempts_required} attempts, "
            f"which exceeds max {max_attempts}."
        )
        return result

    remote_addr = f"203.0.113.{uuid4().int % 250 + 1}"
    request_extra = {
        "REMOTE_ADDR": remote_addr,
        **(check.extra or {}),
    }
    request: Callable[..., object] = getattr(client, check.method.lower())
    statuses: list[int] = []
    for index in range(attempts_required):
        response = request(check.path, check.payload or {}, **request_extra)
        status_code = int(getattr(response, "status_code"))
        statuses.append(status_code)
        if status_code == 429:
            break
        if index == 0 and status_code not in check.expected_prelimit_statuses:
            break

    result["attempts_made"] = len(statuses)
    result["observed_statuses"] = statuses
    result["ok"] = 429 in statuses
    if 429 not in statuses:
        result["failure"] = f"Expected HTTP 429, observed statuses {statuses}."
    return result


class Command(BaseCommand):
    help = "Run backend release-readiness smoke checks against core health and metrics endpoints."

    def add_arguments(self, parser) -> None:  # noqa: ANN001
        parser.add_argument(
            "--strict-external",
            action="store_true",
            help="Require /api/health/airbyte and /api/health/dbt to return 200.",
        )
        parser.add_argument(
            "--expect-metric",
            action="append",
            default=[],
            help="Metric name that must be present in /metrics/app/ output. Can be repeated.",
        )
        parser.add_argument(
            "--expect-metric-label",
            action="append",
            default=[],
            help=(
                "Required metric sample in format "
                "metric_name,label=value[,label=value]. Can be repeated."
            ),
        )
        parser.add_argument(
            "--max-unknown-retry-share",
            type=float,
            default=None,
            help=(
                "Maximum allowed share of unknown retry reasons from "
                "celery_task_retries_total (0.0-1.0)."
            ),
        )
        parser.add_argument(
            "--unknown-retry-reason",
            action="append",
            default=[],
            help=(
                "Retry reason label treated as unknown when computing unknown retry share. "
                "Can be repeated."
            ),
        )
        parser.add_argument(
            "--strict-observability",
            action="store_true",
            help=(
                "Enable strict observability checks (default queue label presence "
                "and unknown retry-share guardrail)."
            ),
        )
        parser.add_argument(
            "--check-rate-limits",
            action="store_true",
            help=(
                "Exercise configured auth and public throttles and require an HTTP 429 "
                "before the configured attempt budget is exhausted."
            ),
        )
        parser.add_argument(
            "--max-rate-limit-smoke-attempts",
            type=int,
            default=150,
            help="Maximum per-scope attempts allowed for --check-rate-limits.",
        )

    def handle(self, *args, **options):  # noqa: ANN002, ANN003
        strict_external = bool(options.get("strict_external"))
        strict_observability = bool(options.get("strict_observability"))
        check_rate_limits = bool(options.get("check_rate_limits"))
        max_rate_limit_smoke_attempts = int(options.get("max_rate_limit_smoke_attempts") or 0)
        expected_metrics = options.get("expect_metric") or DEFAULT_REQUIRED_METRICS
        expected_metrics = [metric.strip() for metric in expected_metrics if metric and metric.strip()]
        expected_metric_label_args = options.get("expect_metric_label") or []
        expected_metric_labels = [
            _parse_metric_label_expectation(raw) for raw in expected_metric_label_args
        ]
        max_unknown_retry_share = options.get("max_unknown_retry_share")
        unknown_retry_reason_labels = [
            str(reason).strip().lower()
            for reason in (options.get("unknown_retry_reason") or [])
            if str(reason).strip()
        ]

        if strict_observability:
            for metric_name in ("celery_task_queue_starts_total", "celery_task_retries_total"):
                if metric_name not in expected_metrics:
                    expected_metrics.append(metric_name)
            if not expected_metric_labels:
                expected_metric_labels = _default_strict_observability_metric_labels()
            if max_unknown_retry_share is None:
                max_unknown_retry_share = DEFAULT_STRICT_OBSERVABILITY_MAX_UNKNOWN_RETRY_SHARE
            if not unknown_retry_reason_labels:
                unknown_retry_reason_labels = list(DEFAULT_UNKNOWN_RETRY_REASON_LABELS)
        expected_metrics = list(dict.fromkeys(expected_metrics))
        unknown_retry_reason_labels = list(dict.fromkeys(unknown_retry_reason_labels))

        if max_unknown_retry_share is not None and not (0 <= max_unknown_retry_share <= 1):
            raise CommandError("--max-unknown-retry-share must be between 0.0 and 1.0.")
        if check_rate_limits and max_rate_limit_smoke_attempts < 1:
            raise CommandError("--max-rate-limit-smoke-attempts must be at least 1.")
        if max_unknown_retry_share is not None and not unknown_retry_reason_labels:
            unknown_retry_reason_labels = list(DEFAULT_UNKNOWN_RETRY_REASON_LABELS)

        if strict_observability:
            _ensure_strict_observability_series()

        external_statuses = (200,) if strict_external else (200, 502, 503)
        checks = [
            EndpointCheck(path="/api/health/", allowed_statuses=(200,)),
            EndpointCheck(path="/api/health/airbyte/", allowed_statuses=external_statuses),
            EndpointCheck(path="/api/health/dbt/", allowed_statuses=external_statuses),
            EndpointCheck(path="/api/timezone/", allowed_statuses=(200,)),
            EndpointCheck(path="/metrics/app/", allowed_statuses=(200,)),
        ]

        client = Client()
        http_host = _resolve_client_http_host()
        defaults = getattr(client, "defaults", None)
        if isinstance(defaults, dict):
            defaults.setdefault("HTTP_HOST", http_host)
        failures: list[str] = []
        results: list[dict[str, object]] = []
        metrics_body = ""

        for check in checks:
            response = client.get(check.path)
            payload: dict[str, object] | None = None
            with suppress(Exception):
                payload = response.json()  # type: ignore[assignment]
            status_payload = payload.get("status") if isinstance(payload, dict) else None
            ok = response.status_code in check.allowed_statuses
            results.append(
                {
                    "path": check.path,
                    "status_code": response.status_code,
                    "allowed_statuses": list(check.allowed_statuses),
                    "status": status_payload,
                    "ok": ok,
                }
            )
            if not ok:
                failures.append(
                    f"{check.path} returned {response.status_code}; expected one of {check.allowed_statuses}."
                )
            if check.path == "/metrics/app/" and response.status_code == 200:
                metrics_body = response.content.decode("utf-8")

        rate_limit_results: list[dict[str, object]] = []
        if check_rate_limits:
            rate_limit_checks = [
                RateLimitCheck(
                    name="auth_burst_token_obtain",
                    scope="auth_burst",
                    method="POST",
                    path="/api/token/",
                    payload={
                        "username": f"throttle-smoke-{uuid4()}",
                        "password": "not-a-real-password",
                    },
                    expected_prelimit_statuses=(400, 401),
                ),
                RateLimitCheck(
                    name="public_health_version",
                    scope="public",
                    method="GET",
                    path="/api/health/version/",
                    expected_prelimit_statuses=(200,),
                ),
            ]
            for rate_limit_check in rate_limit_checks:
                result = _exercise_rate_limit(
                    client=client,
                    check=rate_limit_check,
                    max_attempts=max_rate_limit_smoke_attempts,
                )
                rate_limit_results.append(result)
                if not result["ok"]:
                    failures.append(
                        f"Rate-limit smoke '{rate_limit_check.name}' failed: "
                        f"{result.get('failure')}"
                    )

        missing_metrics = [name for name in expected_metrics if name not in metrics_body]
        for metric in missing_metrics:
            failures.append(f"/metrics/app/ missing required metric '{metric}'.")

        missing_metric_labels: list[dict[str, object]] = []
        for metric_name, labels in expected_metric_labels:
            samples = _parse_metric_samples(metrics_body, metric_name)
            has_match = any(
                all(sample_labels.get(key) == value for key, value in labels.items())
                for sample_labels, _value in samples
            )
            if not has_match:
                missing_metric_labels.append(
                    {
                        "metric_name": metric_name,
                        "labels": labels,
                    }
                )
                failures.append(
                    f"/metrics/app/ missing required metric sample '{metric_name}' with labels {labels}."
                )

        unknown_retry_share: float | None = None
        unknown_retry_count: float = 0.0
        retry_total: float = 0.0
        if max_unknown_retry_share is not None:
            retry_samples = _parse_metric_samples(metrics_body, "celery_task_retries_total")
            retry_total = sum(value for _labels, value in retry_samples)
            unknown_reason_set = set(unknown_retry_reason_labels)
            unknown_retries = sum(
                value
                for labels, value in retry_samples
                if labels.get("reason", "").strip().lower() in unknown_reason_set
            )
            unknown_retry_count = unknown_retries
            if retry_total > 0:
                unknown_retry_share = unknown_retries / retry_total
                if unknown_retry_share > max_unknown_retry_share:
                    failures.append(
                        "Unknown retry reason share "
                        f"{unknown_retry_share:.4f} exceeds allowed "
                        f"{max_unknown_retry_share:.4f} for labels {unknown_retry_reason_labels}."
                    )

        summary = {
            "ok": not failures,
            "strict_external": strict_external,
            "strict_observability": strict_observability,
            "http_host": http_host,
            "checks": results,
            "expected_metrics": expected_metrics,
            "expected_metric_labels": [
                {"metric_name": metric_name, "labels": labels}
                for metric_name, labels in expected_metric_labels
            ],
            "missing_metrics": missing_metrics,
            "missing_metric_labels": missing_metric_labels,
            "max_unknown_retry_share": max_unknown_retry_share,
            "unknown_retry_share": unknown_retry_share,
            "unknown_retry_reason_labels": unknown_retry_reason_labels,
            "unknown_retry_count": unknown_retry_count,
            "retry_total": retry_total,
            "rate_limit_checks": rate_limit_results,
        }
        self.stdout.write(json.dumps(summary, indent=2, sort_keys=True))

        if failures:
            raise CommandError("; ".join(failures))
