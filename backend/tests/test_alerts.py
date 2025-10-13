from __future__ import annotations

from dataclasses import dataclass

import pytest

from alerts.models import AlertRun
from alerts.services import AlertService
from alerts.tasks import run_alert_cycle
from app import alerts as alert_rules
from app.llm import LLMError


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
    payload = response.json()
    assert payload
    first = payload[0]
    assert first["rule_slug"] == "campaign_ctr_drop"
    assert first["status"] == AlertRun.Status.SUCCESS
    assert first["row_count"] == 2
    assert first["rule_name"]


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
