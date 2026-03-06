from __future__ import annotations

import json
import re
from contextlib import suppress
from dataclasses import dataclass

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.test import Client


DEFAULT_REQUIRED_METRICS = [
    "celery_task_executions_total",
    "celery_task_retries_total",
    "celery_task_queue_starts_total",
    "celery_task_queue_wait_seconds",
    "combined_metrics_request_duration_seconds",
    "airbyte_sync_latency_seconds",
    "dbt_run_duration_seconds",
]
DEFAULT_STRICT_OBSERVABILITY_METRIC_LABELS = [
    ("celery_task_queue_starts_total", {"queue_name": "sync"}),
    ("celery_task_queue_starts_total", {"queue_name": "snapshot"}),
    ("celery_task_queue_starts_total", {"queue_name": "summary"}),
]
DEFAULT_STRICT_OBSERVABILITY_MAX_UNKNOWN_RETRY_SHARE = 0.10
DEFAULT_UNKNOWN_RETRY_REASON_LABELS = (
    "unknown",
    "airbyte_unknown_error",
    "meta_graph_unknown_error",
    "meta_page_insights_unknown",
)


@dataclass(frozen=True)
class EndpointCheck:
    path: str
    allowed_statuses: tuple[int, ...]


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

    def handle(self, *args, **options):  # noqa: ANN002, ANN003
        strict_external = bool(options.get("strict_external"))
        strict_observability = bool(options.get("strict_observability"))
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
                expected_metric_labels = list(DEFAULT_STRICT_OBSERVABILITY_METRIC_LABELS)
            if max_unknown_retry_share is None:
                max_unknown_retry_share = DEFAULT_STRICT_OBSERVABILITY_MAX_UNKNOWN_RETRY_SHARE
            if not unknown_retry_reason_labels:
                unknown_retry_reason_labels = list(DEFAULT_UNKNOWN_RETRY_REASON_LABELS)
        expected_metrics = list(dict.fromkeys(expected_metrics))
        unknown_retry_reason_labels = list(dict.fromkeys(unknown_retry_reason_labels))

        if max_unknown_retry_share is not None and not (0 <= max_unknown_retry_share <= 1):
            raise CommandError("--max-unknown-retry-share must be between 0.0 and 1.0.")
        if max_unknown_retry_share is not None and not unknown_retry_reason_labels:
            unknown_retry_reason_labels = list(DEFAULT_UNKNOWN_RETRY_REASON_LABELS)

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
        }
        self.stdout.write(json.dumps(summary, indent=2, sort_keys=True))

        if failures:
            raise CommandError("; ".join(failures))
