from __future__ import annotations

from datetime import datetime, timezone as dt_timezone

import pytest

from analytics.snapshots import SnapshotMetrics
from analytics.summaries import build_daily_summary_payload, summarize_daily_metrics
from analytics.tasks import generate_daily_summaries_for_tenants
from accounts.models import AuditLog


def test_build_daily_summary_payload_sorts_parishes():
    metrics = SnapshotMetrics(
        tenant_id="tenant-1",
        generated_at=datetime(2024, 9, 1, tzinfo=dt_timezone.utc),
        campaign_metrics={
            "summary": {
                "currency": "JMD",
                "totalSpend": 120.5,
                "totalImpressions": 2000,
                "totalClicks": 150,
                "totalConversions": 12,
                "averageRoas": 3.4,
            }
        },
        creative_metrics=[],
        budget_metrics=[],
        parish_metrics=[
            {"parish": "Kingston", "spend": 80},
            {"parish": "St James", "spend": 30},
            {"parish": "St Ann", "spend": 10},
        ],
    )

    payload = build_daily_summary_payload(metrics)

    assert payload["currency"] == "JMD"
    assert payload["top_parishes"][0]["parish"] == "Kingston"
    assert payload["top_parishes"][1]["parish"] == "St James"
    assert payload["totals"]["spend"] == 120.5


def test_summarize_daily_metrics_fallback(monkeypatch):
    payload = {
        "currency": "USD",
        "totals": {
            "spend": 10.0,
            "impressions": 100,
            "clicks": 5,
            "conversions": 1,
            "average_roas": 2.5,
        },
        "top_parishes": [{"parish": "Kingston"}],
    }

    class DisabledClient:
        def is_enabled(self):  # noqa: D401
            return False

    monkeypatch.setattr("analytics.summaries.get_llm_client", lambda: DisabledClient())

    summary = summarize_daily_metrics(payload)
    assert "Daily performance summary" in summary
    assert "Kingston" in summary


@pytest.mark.django_db
def test_generate_daily_summaries_for_tenants(monkeypatch, tenant):
    metrics = SnapshotMetrics(
        tenant_id=str(tenant.id),
        generated_at=datetime(2024, 9, 1, tzinfo=dt_timezone.utc),
        campaign_metrics={
            "summary": {
                "currency": "USD",
                "totalSpend": 10,
                "totalImpressions": 100,
                "totalClicks": 5,
                "totalConversions": 1,
                "averageRoas": 2.5,
            }
        },
        creative_metrics=[],
        budget_metrics=[],
        parish_metrics=[{"parish": "Kingston", "spend": 10}],
    )

    monkeypatch.setattr("analytics.tasks.fetch_snapshot_metrics", lambda tenant_id: metrics)
    monkeypatch.setattr("analytics.tasks.summarize_daily_metrics", lambda payload: "Summary")

    outcomes = generate_daily_summaries_for_tenants([str(tenant.id)])

    assert outcomes[0].tenant_id == str(tenant.id)
    assert outcomes[0].summary == "Summary"
    audit = AuditLog.objects.get(action="daily_summary_email_stubbed")
    assert audit.tenant_id == tenant.id
    assert audit.resource_type == "daily_summary"
