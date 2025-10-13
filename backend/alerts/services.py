from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal
from time import monotonic
from typing import Any, Iterable, Mapping, Sequence
from uuid import UUID

import hashlib

from django.utils import timezone

from app import alerts as alert_rules
from app.alerts import AlertEvaluator, AlertRule
from app.llm import LLMClient, LLMError, get_llm_client

from .models import AlertRun

logger = logging.getLogger(__name__)


_IDENTIFIER_KEYS: frozenset[str] = frozenset(
    {
        "ad_account_id",
        "campaign_id",
        "adset_id",
        "ad_id",
        "creative_id",
    }
)


def _mask_identifier(value: Any) -> str:
    if value is None:
        return "ref_unknown"
    digest = hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:10]
    return f"ref_{digest}"


def _normalise_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return value


def _sanitise_row(row: Mapping[str, Any]) -> dict[str, Any]:
    sanitised: dict[str, Any] = {}
    for key, value in row.items():
        if key == "tenant_id":
            continue
        if key in _IDENTIFIER_KEYS or key.endswith("_id"):
            masked_key = key[:-3] + "_ref" if key.endswith("_id") else f"{key}_ref"
            sanitised[masked_key] = _mask_identifier(value)
            continue
        sanitised[key] = _normalise_value(value)
    return sanitised


def _sanitise_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    sanitised_rows: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, Mapping):
            sanitised_rows.append(_sanitise_row(row))
    return sanitised_rows


class AlertService:
    """Coordinates evaluation of alert rules and persistence of runs."""

    def __init__(
        self,
        rules: Iterable[AlertRule] | None = None,
        evaluator: AlertEvaluator | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        self._rules: Sequence[AlertRule] = tuple(rules or alert_rules.iter_rules())
        self._evaluator = evaluator or AlertEvaluator()
        self._llm = llm_client or get_llm_client()

    def run_cycle(self) -> list[AlertRun]:
        runs: list[AlertRun] = []
        for rule in self._rules:
            run = AlertRun.objects.create(rule_slug=rule.slug, status=AlertRun.Status.STARTED)
            started = monotonic()
            try:
                rows = self._evaluator.run(rule)
                sanitised_rows = _sanitise_rows(rows)
                run.row_count = len(rows)
                run.raw_results = sanitised_rows
                run.error_message = ""

                if not rows:
                    run.status = AlertRun.Status.NO_RESULTS
                    run.llm_summary = "No rows matched this alert during the cycle."
                else:
                    try:
                        summary = self._llm.summarize(rule, sanitised_rows)
                    except LLMError as exc:
                        logger.warning("LLM summary failed for %s: %s", rule.slug, exc)
                        run.status = AlertRun.Status.PARTIAL
                        run.llm_summary = self._llm.fallback_summary(sanitised_rows)
                        run.error_message = str(exc)
                    else:
                        run.status = AlertRun.Status.SUCCESS
                        run.llm_summary = summary
            except Exception as exc:  # pragma: no cover - defensive catch-all
                logger.exception("Alert rule %s failed", rule.slug)
                run.status = AlertRun.Status.FAILED
                run.row_count = 0
                run.raw_results = []
                run.llm_summary = "Alert execution failed before summarisation."
                run.error_message = str(exc)
            finally:
                run.duration_ms = int((monotonic() - started) * 1000)
                run.completed_at = timezone.now()
                run.save(
                    update_fields=[
                        "status",
                        "row_count",
                        "raw_results",
                        "llm_summary",
                        "error_message",
                        "duration_ms",
                        "completed_at",
                    ]
                )
                runs.append(run)
        return runs


__all__ = ["AlertService"]
