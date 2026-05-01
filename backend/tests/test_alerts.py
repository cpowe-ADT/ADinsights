from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.models import Tenant
from accounts.tenant_context import get_current_tenant_id
from alerts.models import AlertRun
from alerts.services import AlertService
from alerts.tasks import run_alert_cycle
from app import alerts as alert_rules
from app.llm import LLMError
from integrations.models import AlertRuleDefinition


def list_results(response):
    payload = response.json()
    if isinstance(payload, dict) and "results" in payload:
        return payload["results"]
    return payload


@dataclass
class StubEvaluator:
    rows: list[dict[str, object]]

    def run(self, rule):  # noqa: D401, ANN001 - signature dictated by service
        return list(self.rows)


class StubLLM:
    def __init__(self, summary: str = "summary") -> None:
        self.summary = summary
        self.called_with = None
        self.fallback_called = False

    def summarize(self, rule, rows):  # noqa: D401, ANN001 - external API
        self.called_with = (rule.slug, list(rows))
        return self.summary

    def fallback_summary(self, rows):  # noqa: D401, ANN001 - external API
        self.fallback_called = True
        return "fallback"


def _make_alert_definition(
    tenant,
    *,
    name="High CPA",
    metric="cpa",
    is_active=True,
    paused_until=None,
):
    return AlertRuleDefinition.objects.create(
        tenant=tenant,
        name=name,
        metric=metric,
        comparison_operator=AlertRuleDefinition.OPERATOR_GREATER_THAN,
        threshold=15,
        lookback_hours=6,
        is_active=is_active,
        paused_until=paused_until,
    )


@pytest.mark.django_db
def test_alert_service_persists_successful_run():
    rule = next(alert_rules.iter_rules())
    evaluator = StubEvaluator(rows=[{"campaign_id": "123", "ctr": 0.01}])
    llm = StubLLM(summary="Actionable summary")

    service = AlertService(rules=[rule], evaluator=evaluator, llm_client=llm)
    runs = service.run_cycle()

    assert len(runs) == 1
    run = runs[0]
    run.refresh_from_db()

    assert run.status == AlertRun.Status.SUCCESS
    assert run.row_count == 1
    assert run.llm_summary == "Actionable summary"
    assert run.raw_results != evaluator.rows
    assert run.raw_results[0]["campaign_ref"].startswith("ref_")
    assert "campaign_id" not in run.raw_results[0]
    assert run.raw_results[0]["ctr"] == evaluator.rows[0]["ctr"]
    assert run.error_message == ""
    assert run.completed_at is not None
    assert llm.called_with[0] == rule.slug
    assert llm.called_with[1] == run.raw_results


@pytest.mark.django_db
def test_alert_service_handles_llm_failure():
    rule = next(alert_rules.iter_rules())
    evaluator = StubEvaluator(rows=[{"ad_account_id": "acct", "spend": 500}])

    class FailingLLM(StubLLM):
        def summarize(self, rule, rows):  # noqa: D401, ANN001 - external API
            raise LLMError("provider unavailable")

    llm = FailingLLM()

    service = AlertService(rules=[rule], evaluator=evaluator, llm_client=llm)
    runs = service.run_cycle()
    run = runs[0]

    assert run.status == AlertRun.Status.PARTIAL
    assert run.llm_summary == "fallback"
    assert run.error_message == "provider unavailable"
    assert run.row_count == 1
    assert llm.fallback_called is True
    assert run.raw_results[0]["ad_account_ref"].startswith("ref_")
    assert "ad_account_id" not in run.raw_results[0]


@pytest.mark.django_db
def test_alert_service_handles_no_results():
    rule = next(alert_rules.iter_rules())
    evaluator = StubEvaluator(rows=[])
    llm = StubLLM()

    service = AlertService(rules=[rule], evaluator=evaluator, llm_client=llm)
    run = service.run_cycle()[0]

    assert run.status == AlertRun.Status.NO_RESULTS
    assert "No rows" in run.llm_summary
    assert run.row_count == 0
    assert llm.called_with is None
    assert run.raw_results == []


@pytest.mark.django_db
def test_alert_service_records_failures():
    rule = next(alert_rules.iter_rules())

    class ExplodingEvaluator(StubEvaluator):
        def run(self, rule):  # noqa: D401, ANN001 - external API
            raise RuntimeError("warehouse offline")

    evaluator = ExplodingEvaluator(rows=[])
    llm = StubLLM()

    service = AlertService(rules=[rule], evaluator=evaluator, llm_client=llm)
    run = service.run_cycle()[0]

    assert run.status == AlertRun.Status.FAILED
    assert run.row_count == 0
    assert run.raw_results == []
    assert "warehouse offline" in run.error_message
    assert llm.called_with is None


@pytest.mark.django_db
def test_alert_service_evaluates_active_database_rules(tenant):
    active_rule = _make_alert_definition(tenant, name="Active CPA")
    future_pause = timezone.now() + timedelta(hours=1)
    paused_rule = _make_alert_definition(
        tenant,
        name="Paused CPA",
        is_active=False,
        paused_until=future_pause,
    )
    evaluator = StubEvaluator(rows=[])
    service = AlertService(rules=[], evaluator=evaluator, llm_client=StubLLM())

    runs = service.run_cycle()

    assert [run.rule_slug for run in runs] == [f"tenant_alert:{active_rule.id}"]
    assert AlertRun.objects.filter(rule_slug=f"tenant_alert:{active_rule.id}").exists()
    assert not AlertRun.objects.filter(rule_slug=f"tenant_alert:{paused_rule.id}").exists()


@pytest.mark.django_db
def test_alert_service_auto_resumes_expired_database_rule_pause(tenant):
    expired_pause = timezone.now() - timedelta(minutes=5)
    rule = _make_alert_definition(
        tenant,
        name="Expired pause",
        is_active=False,
        paused_until=expired_pause,
    )
    service = AlertService(rules=[], evaluator=StubEvaluator(rows=[]), llm_client=StubLLM())

    runs = service.run_cycle()

    assert [run.rule_slug for run in runs] == [f"tenant_alert:{rule.id}"]
    rule.refresh_from_db()
    assert rule.is_active is True
    assert rule.paused_until is None


@pytest.mark.django_db
def test_alert_service_sets_tenant_context_for_database_rules(tenant):
    other_tenant = Tenant.objects.create(name="Other Tenant")
    first_rule = _make_alert_definition(tenant, name="Tenant A CPA")
    second_rule = _make_alert_definition(other_tenant, name="Tenant B CPA")

    class TenantRecordingEvaluator(StubEvaluator):
        def __init__(self):
            super().__init__(rows=[])
            self.calls = []

        def run(self, rule):  # noqa: D401, ANN001 - signature dictated by service
            self.calls.append((rule.slug, rule.parameters["tenant_id"], get_current_tenant_id()))
            return []

    evaluator = TenantRecordingEvaluator()
    service = AlertService(rules=[], evaluator=evaluator, llm_client=StubLLM())

    service.run_cycle()

    assert sorted(evaluator.calls) == sorted(
        [
            (
                f"tenant_alert:{first_rule.id}",
                str(first_rule.tenant_id),
                str(first_rule.tenant_id),
            ),
            (
                f"tenant_alert:{second_rule.id}",
                str(second_rule.tenant_id),
                str(second_rule.tenant_id),
            ),
        ]
    )
    assert get_current_tenant_id() is None


@pytest.mark.django_db
def test_alert_service_notifies_channels_for_fired_database_rule(tenant):
    rule = _make_alert_definition(tenant, name="High Spend", metric="spend")
    evaluator = StubEvaluator(rows=[{"campaign_id": "cmp_1", "spend": 2500}])

    class StubNotifier:
        def __init__(self):
            self.calls = []

        def notify(self, definition, run):  # noqa: D401, ANN001 - service collaborator
            self.calls.append((definition.id, run.rule_slug, run.row_count))
            return []

    notifier = StubNotifier()
    service = AlertService(
        rules=[],
        evaluator=evaluator,
        llm_client=StubLLM(summary="Spend alert fired."),
        notifier=notifier,
    )

    runs = service.run_cycle()

    assert runs[0].status == AlertRun.Status.SUCCESS
    assert notifier.calls == [(rule.id, f"tenant_alert:{rule.id}", 1)]


@pytest.mark.django_db
def test_alert_service_does_not_notify_no_result_database_rule(tenant):
    _make_alert_definition(tenant, name="Quiet CPA")

    class StubNotifier:
        def notify(self, definition, run):  # noqa: D401, ANN001 - service collaborator
            raise AssertionError("no-result alerts should not notify")

    service = AlertService(
        rules=[],
        evaluator=StubEvaluator(rows=[]),
        llm_client=StubLLM(),
        notifier=StubNotifier(),
    )

    run = service.run_cycle()[0]

    assert run.status == AlertRun.Status.NO_RESULTS


@pytest.mark.django_db
def test_alert_service_persists_run_when_notifier_fails(tenant):
    rule = _make_alert_definition(tenant, name="High Spend", metric="spend")

    class FailingNotifier:
        def notify(self, definition, run):  # noqa: D401, ANN001 - service collaborator
            raise RuntimeError("notification provider down")

    service = AlertService(
        rules=[],
        evaluator=StubEvaluator(rows=[{"campaign_id": "cmp_1", "spend": 2500}]),
        llm_client=StubLLM(summary="Spend alert fired."),
        notifier=FailingNotifier(),
    )

    run = service.run_cycle()[0]

    assert run.rule_slug == f"tenant_alert:{rule.id}"
    assert run.status == AlertRun.Status.SUCCESS
    run.refresh_from_db()
    assert run.row_count == 1


@pytest.mark.django_db
def test_alert_history_api_returns_runs(api_client, user):
    AlertRun.objects.create(
        rule_slug="campaign_ctr_drop",
        status=AlertRun.Status.SUCCESS,
        row_count=2,
        llm_summary="Summary",
        raw_results=[{"campaign_id": "123"}],
        error_message="",
        duration_ms=1500,
    )

    api_client.force_authenticate(user=user)
    response = api_client.get("/api/alerts/runs/")
    api_client.force_authenticate(user=None)

    assert response.status_code == 200
    payload = list_results(response)
    assert payload
    first = payload[0]
    assert first["rule_slug"] == "campaign_ctr_drop"
    assert first["status"] == AlertRun.Status.SUCCESS
    assert first["row_count"] == 2
    assert first["rule_name"]


@pytest.mark.django_db
def test_alert_history_api_resolves_database_rule_runs(api_client, user, tenant):
    rule = _make_alert_definition(tenant, name="Tenant CPA Alert")
    AlertRun.objects.create(
        rule_slug=f"tenant_alert:{rule.id}",
        status=AlertRun.Status.NO_RESULTS,
        row_count=0,
        llm_summary="No rows",
        raw_results=[],
        error_message="",
        duration_ms=15,
    )

    api_client.force_authenticate(user=user)
    response = api_client.get("/api/alerts/runs/")
    api_client.force_authenticate(user=None)

    assert response.status_code == 200
    first = list_results(response)[0]
    assert first["rule_slug"] == f"tenant_alert:{rule.id}"
    assert first["rule_name"] == "Tenant CPA Alert"
    assert first["severity"] == rule.severity
    assert "Tenant-defined threshold alert" in first["rule_description"]


@pytest.mark.django_db
def test_celery_task_uses_service(monkeypatch):
    rule = next(alert_rules.iter_rules())
    fake_run = AlertRun(
        rule_slug=rule.slug,
        status=AlertRun.Status.SUCCESS,
        row_count=1,
        duration_ms=10,
    )

    class StubService:
        def run_cycle(self):
            return [fake_run]

    monkeypatch.setattr("alerts.tasks.AlertService", StubService)

    result = run_alert_cycle.run()
    assert result == [
        {
            "id": str(fake_run.id),
            "rule": rule.slug,
            "status": fake_run.status,
            "row_count": fake_run.row_count,
            "duration_ms": fake_run.duration_ms,
        }
    ]
