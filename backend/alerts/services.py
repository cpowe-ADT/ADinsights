from __future__ import annotations

import logging
import re
from contextlib import nullcontext
from datetime import date, datetime
from decimal import Decimal
from time import monotonic
from typing import Any, Iterable, Iterator, Mapping, Sequence
from uuid import UUID

import hashlib

from django.utils import timezone

from accounts.tenant_context import tenant_context
from app import alerts as alert_rules
from app.alerts import AlertEvaluator, AlertRule
from app.llm import LLMClient, LLMError, get_llm_client
from integrations.models import AlertRuleDefinition

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
_DB_RULE_SLUG_PREFIX = "tenant_alert:"
_METRIC_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_OPERATOR_SQL = {
    AlertRuleDefinition.OPERATOR_GREATER_THAN: ">",
    AlertRuleDefinition.OPERATOR_GREATER_THAN_EQUAL: ">=",
    AlertRuleDefinition.OPERATOR_LESS_THAN: "<",
    AlertRuleDefinition.OPERATOR_LESS_THAN_EQUAL: "<=",
}


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


def _metric_column(metric: str) -> str:
    metric = metric.strip()
    if not _METRIC_IDENTIFIER_RE.fullmatch(metric):
        raise ValueError(f"Unsupported alert metric identifier: {metric!r}")
    return metric


def _database_rule_slug(rule: AlertRuleDefinition) -> str:
    return f"{_DB_RULE_SLUG_PREFIX}{rule.id}"


def _database_rule_to_alert_rule(rule: AlertRuleDefinition) -> AlertRule:
    metric = _metric_column(rule.metric)
    operator = _OPERATOR_SQL[rule.comparison_operator]
    order_direction = "desc" if operator in {">", ">="} else "asc"
    sql = alert_rules._strip_sql(  # noqa: SLF001 - shared normalizer for AlertRule SQL.
        f"""
        select
            c.date_day,
            c.source_platform,
            c.ad_account_id,
            c.campaign_id,
            c.{metric} as metric_value,
            %(metric)s as metric,
            %(threshold)s as threshold,
            %(comparison_operator)s as comparison_operator,
            %(lookback_hours)s as lookback_hours
        from vw_campaign_daily c
        where c.tenant_id::text = %(tenant_id)s
          and c.date_day >= (current_timestamp - (%(lookback_hours)s * interval '1 hour'))::date
          and c.{metric} {operator} %(threshold)s
        order by c.date_day desc, metric_value {order_direction} nulls last
        limit %(limit)s
        """
    )
    return AlertRule(
        slug=_database_rule_slug(rule),
        name=rule.name,
        description=(
            f"Tenant-defined threshold alert for {rule.metric} "
            f"{rule.comparison_operator} {rule.threshold} over {rule.lookback_hours}h."
        ),
        severity=rule.severity,
        sql=sql,
        parameters={
            "tenant_id": str(rule.tenant_id),
            "metric": rule.metric,
            "threshold": rule.threshold,
            "comparison_operator": rule.comparison_operator,
            "lookback_hours": rule.lookback_hours,
        },
        tenant_id=str(rule.tenant_id),
    )


class AlertService:
    """Coordinates evaluation of alert rules and persistence of runs."""

    def __init__(
        self,
        rules: Iterable[AlertRule] | None = None,
        evaluator: AlertEvaluator | None = None,
        llm_client: LLMClient | None = None,
        include_database_rules: bool = True,
    ) -> None:
        self._rules: Sequence[AlertRule] = tuple(
            alert_rules.iter_rules() if rules is None else rules
        )
        self._evaluator = evaluator or AlertEvaluator()
        self._llm = llm_client or get_llm_client()
        self._include_database_rules = include_database_rules

    def _iter_rules(self) -> Iterator[AlertRule]:
        yield from self._rules
        if not self._include_database_rules:
            return
        queryset = AlertRuleDefinition.active_for_eval().select_related("tenant")
        for definition in queryset.order_by("tenant_id", "name"):
            try:
                yield _database_rule_to_alert_rule(definition)
            except (KeyError, ValueError):
                logger.exception(
                    "Skipping invalid alert rule definition",
                    extra={
                        "tenant_id": str(definition.tenant_id),
                        "alert_rule_definition_id": str(definition.id),
                    },
                )

    def run_cycle(self) -> list[AlertRun]:
        runs: list[AlertRun] = []
        for rule in self._iter_rules():
            run = AlertRun.objects.create(rule_slug=rule.slug, status=AlertRun.Status.STARTED)
            started = monotonic()
            try:
                context = tenant_context(rule.tenant_id) if rule.tenant_id else nullcontext()
                with context:
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
