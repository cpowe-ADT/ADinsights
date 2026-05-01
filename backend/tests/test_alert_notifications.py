from __future__ import annotations

import httpx
import pytest

from alerts.models import AlertRun
from alerts.notifications import AlertNotificationDispatcher
from integrations.models import AlertRuleDefinition, NotificationChannel


def _make_rule(tenant, *, name="High Spend"):
    return AlertRuleDefinition.objects.create(
        tenant=tenant,
        name=name,
        metric="spend",
        comparison_operator=AlertRuleDefinition.OPERATOR_GREATER_THAN,
        threshold=1000,
        lookback_hours=24,
        severity=AlertRuleDefinition.SEVERITY_HIGH,
    )


def _make_run(rule):
    return AlertRun.objects.create(
        rule_slug=f"tenant_alert:{rule.id}",
        status=AlertRun.Status.SUCCESS,
        row_count=1,
        llm_summary="Spend crossed the configured threshold.",
        raw_results=[{"campaign_ref": "ref_abc123", "spend": 2500}],
        error_message="",
        duration_ms=25,
    )


class FakeResponse:
    def __init__(self, status_code=200):
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "failed",
                request=httpx.Request("POST", "https://example.com"),
                response=httpx.Response(self.status_code),
            )


class FakeHttpClient:
    def __init__(self, status_code=200):
        self.status_code = status_code
        self.posts = []

    def post(self, url, **kwargs):  # noqa: D401, ANN001 - httpx-compatible fake
        self.posts.append((url, kwargs))
        return FakeResponse(self.status_code)


@pytest.mark.django_db
def test_alert_notification_dispatcher_sends_email(tenant):
    rule = _make_rule(tenant)
    run = _make_run(rule)
    channel = NotificationChannel.objects.create(
        tenant=tenant,
        name="Email",
        channel_type=NotificationChannel.CHANNEL_EMAIL,
        config={"emails": "ops@example.com, analyst@example.com"},
    )
    rule.notification_channels.add(channel)
    sent = []

    def fake_send_mail(subject, message, from_email, recipient_list, fail_silently):
        sent.append((subject, message, from_email, recipient_list, fail_silently))
        return 1

    dispatcher = AlertNotificationDispatcher(mail_sender=fake_send_mail)

    results = dispatcher.notify(rule, run)

    assert [result.delivered for result in results] == [True]
    subject, message, _from_email, recipients, fail_silently = sent[0]
    assert "High Spend" in subject
    assert "Spend crossed the configured threshold." in message
    assert recipients == ["ops@example.com", "analyst@example.com"]
    assert fail_silently is False


@pytest.mark.django_db
def test_alert_notification_dispatcher_posts_slack_and_webhook(tenant):
    rule = _make_rule(tenant)
    run = _make_run(rule)
    slack_channel = NotificationChannel.objects.create(
        tenant=tenant,
        name="Slack",
        channel_type=NotificationChannel.CHANNEL_SLACK,
        config={"url": "https://hooks.slack.test/services/abc"},
    )
    webhook_channel = NotificationChannel.objects.create(
        tenant=tenant,
        name="Webhook",
        channel_type=NotificationChannel.CHANNEL_WEBHOOK,
        config={
            "url": "https://alerts.example.com/hook",
            "headers": {"X-Alert-Token": "redacted"},
        },
    )
    rule.notification_channels.add(slack_channel, webhook_channel)
    http_client = FakeHttpClient()
    dispatcher = AlertNotificationDispatcher(http_client=http_client)

    results = dispatcher.notify(rule, run)

    assert [result.delivered for result in results] == [True, True]
    slack_url, slack_kwargs = http_client.posts[0]
    webhook_url, webhook_kwargs = http_client.posts[1]
    assert slack_url == "https://hooks.slack.test/services/abc"
    assert "High Spend" in slack_kwargs["json"]["text"]
    assert webhook_url == "https://alerts.example.com/hook"
    assert webhook_kwargs["headers"] == {"X-Alert-Token": "redacted"}
    assert webhook_kwargs["json"]["alert_run_id"] == str(run.id)
    assert webhook_kwargs["json"]["results"] == run.raw_results


@pytest.mark.django_db
def test_alert_notification_dispatcher_skips_inactive_channels(tenant):
    rule = _make_rule(tenant)
    run = _make_run(rule)
    channel = NotificationChannel.objects.create(
        tenant=tenant,
        name="Inactive Slack",
        channel_type=NotificationChannel.CHANNEL_SLACK,
        config={"url": "https://hooks.slack.test/services/abc"},
        is_active=False,
    )
    rule.notification_channels.add(channel)
    http_client = FakeHttpClient()
    dispatcher = AlertNotificationDispatcher(http_client=http_client)

    results = dispatcher.notify(rule, run)

    assert results == []
    assert http_client.posts == []


@pytest.mark.django_db
def test_alert_notification_dispatcher_records_channel_failure(tenant):
    rule = _make_rule(tenant)
    run = _make_run(rule)
    channel = NotificationChannel.objects.create(
        tenant=tenant,
        name="Broken Webhook",
        channel_type=NotificationChannel.CHANNEL_WEBHOOK,
        config={},
    )
    rule.notification_channels.add(channel)
    dispatcher = AlertNotificationDispatcher()

    results = dispatcher.notify(rule, run)

    assert len(results) == 1
    assert results[0].delivered is False
    assert "requires config.url" in results[0].error
