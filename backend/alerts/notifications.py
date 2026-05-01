from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

import httpx
from django.conf import settings
from django.core.mail import send_mail

from integrations.models import AlertRuleDefinition, NotificationChannel

from .models import AlertRun

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeliveryResult:
    channel_id: str
    channel_type: str
    delivered: bool
    error: str = ""


def _as_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, Iterable) and not isinstance(value, Mapping):
        return [str(part).strip() for part in value if str(part).strip()]
    return []


def _channel_url(config: Mapping[str, Any]) -> str:
    return str(config.get("url") or config.get("webhook_url") or "").strip()


def _alert_subject(definition: AlertRuleDefinition, run: AlertRun) -> str:
    return f"[ADinsights] {definition.severity.upper()} alert: {definition.name} ({run.row_count})"


def _alert_text(definition: AlertRuleDefinition, run: AlertRun) -> str:
    return "\n".join(
        [
            f"Alert: {definition.name}",
            f"Severity: {definition.severity}",
            f"Metric: {definition.metric} {definition.comparison_operator} {definition.threshold}",
            f"Rows: {run.row_count}",
            f"Run: {run.id}",
            "",
            run.llm_summary or "Alert fired without a summary.",
        ]
    )


def _alert_payload(definition: AlertRuleDefinition, run: AlertRun) -> dict[str, Any]:
    return {
        "alert_run_id": str(run.id),
        "rule_id": str(definition.id),
        "rule_name": definition.name,
        "severity": definition.severity,
        "metric": definition.metric,
        "comparison_operator": definition.comparison_operator,
        "threshold": str(definition.threshold),
        "lookback_hours": definition.lookback_hours,
        "status": run.status,
        "row_count": run.row_count,
        "summary": run.llm_summary,
        "results": run.raw_results,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }


class AlertNotificationDispatcher:
    """Delivers fired DB-backed alert runs to configured tenant channels."""

    def __init__(self, http_client=httpx, mail_sender=send_mail) -> None:
        self._http = http_client
        self._send_mail = mail_sender

    def notify(self, definition: AlertRuleDefinition, run: AlertRun) -> list[DeliveryResult]:
        results: list[DeliveryResult] = []
        channels = definition.notification_channels.filter(is_active=True).order_by("name")
        for channel in channels:
            try:
                self._deliver(channel, definition, run)
            except Exception as exc:  # pragma: no cover - defensive, per-channel isolation
                logger.warning(
                    "Alert notification delivery failed",
                    extra={
                        "tenant_id": str(definition.tenant_id),
                        "alert_rule_definition_id": str(definition.id),
                        "notification_channel_id": str(channel.id),
                        "notification_channel_type": channel.channel_type,
                    },
                    exc_info=True,
                )
                results.append(
                    DeliveryResult(
                        channel_id=str(channel.id),
                        channel_type=channel.channel_type,
                        delivered=False,
                        error=str(exc),
                    )
                )
            else:
                results.append(
                    DeliveryResult(
                        channel_id=str(channel.id),
                        channel_type=channel.channel_type,
                        delivered=True,
                    )
                )
        return results

    def _deliver(
        self,
        channel: NotificationChannel,
        definition: AlertRuleDefinition,
        run: AlertRun,
    ) -> None:
        config = channel.config or {}
        if channel.channel_type == NotificationChannel.CHANNEL_EMAIL:
            self._deliver_email(config, definition, run)
            return
        if channel.channel_type == NotificationChannel.CHANNEL_SLACK:
            self._deliver_slack(config, definition, run)
            return
        if channel.channel_type == NotificationChannel.CHANNEL_WEBHOOK:
            self._deliver_webhook(config, definition, run)
            return
        raise ValueError(f"Unsupported notification channel type: {channel.channel_type}")

    def _deliver_email(
        self,
        config: Mapping[str, Any],
        definition: AlertRuleDefinition,
        run: AlertRun,
    ) -> None:
        recipients = _as_string_list(config.get("emails") or config.get("to"))
        if not recipients:
            raise ValueError("Email notification channel requires config.emails or config.to")
        from_email = str(
            config.get("from_email")
            or getattr(settings, "DEFAULT_FROM_EMAIL", "alerts@adinsights.local")
        )
        self._send_mail(
            _alert_subject(definition, run),
            _alert_text(definition, run),
            from_email,
            recipients,
            fail_silently=False,
        )

    def _deliver_slack(
        self,
        config: Mapping[str, Any],
        definition: AlertRuleDefinition,
        run: AlertRun,
    ) -> None:
        url = _channel_url(config)
        if not url:
            raise ValueError("Slack notification channel requires config.url")
        response = self._http.post(url, json={"text": _alert_text(definition, run)}, timeout=10.0)
        response.raise_for_status()

    def _deliver_webhook(
        self,
        config: Mapping[str, Any],
        definition: AlertRuleDefinition,
        run: AlertRun,
    ) -> None:
        url = _channel_url(config)
        if not url:
            raise ValueError("Webhook notification channel requires config.url")
        headers = config.get("headers") if isinstance(config.get("headers"), Mapping) else None
        response = self._http.post(
            url,
            json=_alert_payload(definition, run),
            headers=dict(headers or {}),
            timeout=10.0,
        )
        response.raise_for_status()


__all__ = ["AlertNotificationDispatcher", "DeliveryResult"]
