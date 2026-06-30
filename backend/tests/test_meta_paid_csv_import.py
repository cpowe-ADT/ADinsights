from __future__ import annotations

import json
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from accounts.models import AuditLog
from analytics.models import AdAccount, Campaign, RawPerformanceRecord
from analytics.reporting_availability import build_report_data_availability
from analytics.reporting_preview import build_widget_preview


def _create_account(*, tenant, external_id: str = "act_791712443035541") -> AdAccount:
    account_id = external_id[4:] if external_id.startswith("act_") else external_id
    return AdAccount.objects.create(
        tenant=tenant,
        external_id=external_id,
        account_id=account_id,
        name="Students' Loan Bureau (SLB)",
        currency="JMD",
    )


def _metric_availability_by_key(dataset_payload):
    return {
        row["key"]: row for row in dataset_payload["metric_availability"]["metrics"]
    }


@pytest.mark.django_db
def test_import_meta_paid_csv_upserts_campaign_rows_and_feeds_paid_preview(
    tmp_path, tenant
):
    _create_account(tenant=tenant)
    csv_path = tmp_path / "meta-paid.csv"
    csv_path.write_text(
        "\n".join(
            [
                "Date,Account ID,Campaign ID,Campaign Name,Spend,Impressions,Reach,Clicks,Conversions,Currency",
                '2026-05-01,act_791712443035541,cmp-1,SLB Paid Search,"1,200.50","10,000","8,000",400,12,JMD',
                "2026-05-02,791712443035541,cmp-1,SLB Paid Search,100,2000,1500,50,3,JMD",
            ]
        ),
        encoding="utf-8",
    )
    output = StringIO()

    call_command(
        "import_meta_paid_csv",
        "--tenant-id",
        str(tenant.id),
        "--file",
        str(csv_path),
        stdout=output,
    )

    payload = json.loads(output.getvalue())
    assert payload["schema_version"] == "meta_paid_csv_import.v1"
    assert payload["stored_aggregate_only"] is True
    assert payload["no_live_provider_calls"] is True
    assert payload["summary"] == {
        "account_count": 1,
        "campaign_count": 1,
        "campaigns_created": 1,
        "campaigns_updated": 0,
        "records_created": 2,
        "records_updated": 0,
        "rows_seen": 2,
        "rows_skipped_no_metrics": 0,
    }
    assert Campaign.all_objects.filter(
        tenant=tenant,
        external_id="cmp-1",
        name="SLB Paid Search",
        account_external_id="act_791712443035541",
    ).exists()
    records = RawPerformanceRecord.all_objects.filter(tenant=tenant).order_by("date")
    assert records.count() == 2
    assert all(record.source == "meta" for record in records)
    assert all(
        record.raw_payload["source"] == "manual_meta_paid_csv" for record in records
    )
    assert records[0].spend == Decimal("1200.50")
    assert records[0].impressions == 10000
    assert records[0].reach == 8000
    assert records[0].clicks == 400
    assert records[0].cpc == Decimal("3.00125")

    kpi_preview = build_widget_preview(
        tenant=tenant,
        payload={
            "account_id": "act_791712443035541",
            "widget": {
                "id": "paid_summary",
                "type": "kpi",
                "dataset": "paid_meta_ads",
                "metrics": ["spend", "impressions", "reach", "clicks"],
                "dimensions": [],
                "filters": {
                    "date_range": "custom",
                    "start_date": "2026-05-01",
                    "end_date": "2026-05-02",
                },
                "coverage_policy": "render_with_warning",
            },
        },
    )
    metric_values = {row["key"]: row["value"] for row in kpi_preview["data"]["metrics"]}
    assert metric_values == {
        "spend": 1300.5,
        "impressions": 12000.0,
        "reach": 9500.0,
        "clicks": 450.0,
    }
    assert kpi_preview["coverage"]["coverage_status"] == "fresh"

    assert kpi_preview["coverage"]["row_count"] == 1

    table_preview = build_widget_preview(
        tenant=tenant,
        payload={
            "account_id": "act_791712443035541",
            "widget": {
                "id": "paid_top_campaigns",
                "type": "data_table",
                "dataset": "paid_meta_ads",
                "metrics": ["spend", "impressions", "reach", "clicks"],
                "dimensions": ["campaign"],
                "filters": {
                    "date_range": "custom",
                    "start_date": "2026-05-01",
                    "end_date": "2026-05-02",
                },
                "coverage_policy": "render_with_warning",
                "visual": {"row_limit": 10},
            },
        },
    )
    assert table_preview["data"]["rows"][0]["campaign"] == "SLB Paid Search"
    assert table_preview["data"]["rows"][0]["spend"] == 1300.5

    audit = AuditLog.all_objects.get(
        tenant=tenant,
        action="meta_paid_csv_imported",
        resource_type="ad_account",
    )
    assert audit.metadata["redacted"] is True
    serialized = json.dumps({**payload, "audit": audit.metadata}, default=str).lower()
    assert "act_791712443035541" not in serialized
    assert "791712443035541" not in serialized
    assert "raw_payload" not in serialized


@pytest.mark.django_db
def test_import_meta_paid_csv_dry_run_validates_without_writes(tmp_path, tenant):
    _create_account(tenant=tenant)
    csv_path = tmp_path / "meta-paid-dry-run.csv"
    csv_path.write_text(
        "\n".join(
            [
                "date,account_id,record_id,campaign_id,campaign_name,spend,impressions,reach,clicks",
                "2026-05-01,act_791712443035541,row-1,cmp-1,SLB Paid Search,150,1000,900,50",
            ]
        ),
        encoding="utf-8",
    )
    output = StringIO()

    call_command(
        "import_meta_paid_csv",
        "--tenant-id",
        str(tenant.id),
        "--file",
        str(csv_path),
        "--dry-run",
        stdout=output,
    )

    payload = json.loads(output.getvalue())
    assert payload["schema_version"] == "meta_paid_csv_import.v1"
    assert payload["dry_run"] is True
    assert payload["stored_aggregate_only"] is True
    assert payload["no_live_provider_calls"] is True
    assert payload["summary"] == {
        "account_count": 1,
        "campaign_count": 1,
        "campaigns_created": 1,
        "campaigns_updated": 0,
        "records_created": 1,
        "records_updated": 0,
        "rows_seen": 1,
        "rows_skipped_no_metrics": 0,
    }
    assert not Campaign.all_objects.filter(tenant=tenant).exists()
    assert not RawPerformanceRecord.all_objects.filter(tenant=tenant).exists()
    assert not AuditLog.all_objects.filter(
        tenant=tenant, action="meta_paid_csv_imported"
    ).exists()


@pytest.mark.django_db
def test_import_meta_paid_csv_updates_existing_rows_without_zeroing_blanks(
    tmp_path, tenant
):
    account = _create_account(tenant=tenant)
    campaign = Campaign.all_objects.create(
        tenant=tenant,
        ad_account=account,
        external_id="cmp-1",
        name="SLB Paid Search",
        platform="meta",
        account_external_id=account.external_id,
        currency="JMD",
    )
    RawPerformanceRecord.all_objects.create(
        tenant=tenant,
        ad_account=account,
        campaign=campaign,
        source="meta",
        external_id="manual-paid:row-1",
        date="2026-05-01",
        level="campaign",
        spend=Decimal("100"),
        impressions=1000,
        reach=900,
        clicks=50,
    )
    csv_path = tmp_path / "meta-paid-update.csv"
    csv_path.write_text(
        "date,account_id,record_id,campaign_id,campaign_name,spend,impressions,reach,clicks\n"
        "2026-05-01,act_791712443035541,row-1,cmp-1,SLB Paid Search,150,,950,\n",
        encoding="utf-8",
    )
    output = StringIO()

    call_command(
        "import_meta_paid_csv",
        "--tenant-id",
        str(tenant.id),
        "--file",
        str(csv_path),
        stdout=output,
    )

    payload = json.loads(output.getvalue())
    assert payload["summary"]["records_created"] == 0
    assert payload["summary"]["records_updated"] == 1
    record = RawPerformanceRecord.all_objects.get(
        tenant=tenant,
        external_id="manual-paid:row-1",
    )
    assert record.spend == Decimal("150")
    assert record.impressions == 1000
    assert record.reach == 950
    assert record.clicks == 50


@pytest.mark.django_db
def test_import_meta_paid_csv_blank_new_metrics_render_null_in_paid_preview(
    tmp_path, tenant
):
    _create_account(tenant=tenant)
    csv_path = tmp_path / "meta-paid-partial.csv"
    csv_path.write_text(
        "date,account_id,record_id,campaign_id,campaign_name,spend,impressions,reach,clicks,conversions,currency\n"
        "2026-05-01,act_791712443035541,row-1,cmp-1,SLB Paid Search,250.25,1000,,,,JMD\n",
        encoding="utf-8",
    )

    call_command(
        "import_meta_paid_csv",
        "--tenant-id",
        str(tenant.id),
        "--file",
        str(csv_path),
        stdout=StringIO(),
    )

    record = RawPerformanceRecord.all_objects.get(
        tenant=tenant,
        external_id="manual-paid:row-1",
    )
    assert record.clicks == 0
    assert record.raw_payload["metric_columns"] == ["impressions", "spend"]

    kpi_preview = build_widget_preview(
        tenant=tenant,
        payload={
            "account_id": "act_791712443035541",
            "widget": {
                "id": "paid_partial_summary",
                "type": "kpi",
                "dataset": "paid_meta_ads",
                "metrics": [
                    "spend",
                    "impressions",
                    "reach",
                    "clicks",
                    "conversions",
                    "ctr",
                    "cpc",
                    "frequency",
                ],
                "dimensions": [],
                "filters": {
                    "date_range": "custom",
                    "start_date": "2026-05-01",
                    "end_date": "2026-05-01",
                },
                "coverage_policy": "render_with_warning",
            },
        },
    )

    metric_values = {row["key"]: row["value"] for row in kpi_preview["data"]["metrics"]}
    assert metric_values == {
        "spend": 250.25,
        "impressions": 1000.0,
        "reach": None,
        "clicks": None,
        "conversions": None,
        "ctr": None,
        "cpc": None,
        "frequency": None,
    }
    assert kpi_preview["coverage"]["coverage_status"] == "fresh"

    availability = build_report_data_availability(
        tenant=tenant,
        params={
            "template_key": "slb_monthly_social_report",
            "start_date": "2026-05-01",
            "end_date": "2026-05-01",
            "account_id": "act_791712443035541",
        },
    )
    paid_metrics = _metric_availability_by_key(
        availability["datasets"]["paid_meta_ads"]
    )
    assert paid_metrics["spend"]["availability_state"] == "available"
    assert paid_metrics["impressions"]["availability_state"] == "available"
    assert paid_metrics["reach"]["availability_state"] == "callable_no_data"
    assert paid_metrics["clicks"]["availability_state"] == "callable_no_data"
    assert paid_metrics["conversions"]["availability_state"] == "callable_no_data"
    assert paid_metrics["ctr"]["availability_state"] == "callable_no_data"
    assert paid_metrics["cpc"]["availability_state"] == "callable_no_data"
    assert paid_metrics["cpm"]["availability_state"] == "available"
    assert paid_metrics["frequency"]["availability_state"] == "callable_no_data"


@pytest.mark.django_db
def test_import_meta_paid_csv_endpoint_only_rows_are_partial_coverage(
    tmp_path, tenant
):
    _create_account(tenant=tenant)
    csv_path = tmp_path / "meta-paid-endpoint-only.csv"
    csv_path.write_text(
        "\n".join(
            [
                "date,account_id,record_id,campaign_id,campaign_name,spend,impressions,currency",
                "2026-05-01,act_791712443035541,row-1,cmp-1,SLB Paid Search,100,1000,JMD",
                "2026-05-31,act_791712443035541,row-31,cmp-1,SLB Paid Search,200,2000,JMD",
            ]
        ),
        encoding="utf-8",
    )

    call_command(
        "import_meta_paid_csv",
        "--tenant-id",
        str(tenant.id),
        "--file",
        str(csv_path),
        stdout=StringIO(),
    )

    kpi_preview = build_widget_preview(
        tenant=tenant,
        payload={
            "account_id": "act_791712443035541",
            "widget": {
                "id": "paid_may_summary",
                "type": "kpi",
                "dataset": "paid_meta_ads",
                "metrics": ["spend", "impressions"],
                "dimensions": [],
                "filters": {
                    "date_range": "custom",
                    "start_date": "2026-05-01",
                    "end_date": "2026-05-31",
                },
                "coverage_policy": "render_with_warning",
            },
        },
    )

    assert kpi_preview["coverage"]["coverage_status"] == "partial"
    assert kpi_preview["coverage"]["coverage_note"] == (
        "Direct Meta stored snapshot is missing 29 requested days "
        "from 2026-05-02 through 2026-05-30."
    )
    assert kpi_preview["coverage"]["coverage_gap"] == {
        "requested_day_count": 31,
        "covered_day_count": 2,
        "missing_day_count": 29,
        "missing_start_date": "2026-05-02",
        "missing_end_date": "2026-05-30",
        "missing_dates": [
            "2026-05-02",
            "2026-05-03",
            "2026-05-04",
            "2026-05-05",
            "2026-05-06",
            "2026-05-07",
            "2026-05-08",
            "2026-05-09",
            "2026-05-10",
            "2026-05-11",
            "2026-05-12",
            "2026-05-13",
            "2026-05-14",
            "2026-05-15",
            "2026-05-16",
            "2026-05-17",
            "2026-05-18",
            "2026-05-19",
            "2026-05-20",
            "2026-05-21",
            "2026-05-22",
            "2026-05-23",
            "2026-05-24",
            "2026-05-25",
            "2026-05-26",
            "2026-05-27",
            "2026-05-28",
            "2026-05-29",
            "2026-05-30",
        ],
        "missing_dates_truncated": False,
        "has_leading_gap": False,
        "has_trailing_gap": False,
    }

    availability = build_report_data_availability(
        tenant=tenant,
        params={
            "template_key": "slb_monthly_social_report",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
            "account_id": "act_791712443035541",
        },
    )
    paid = availability["datasets"]["paid_meta_ads"]
    assert paid["coverage_status"] == "partial"
    assert paid["coverage_note"] == (
        "Stored rows are missing 29 requested days "
        "from 2026-05-02 through 2026-05-30."
    )
    assert paid["coverage_gap"]["missing_day_count"] == 29
    assert availability["eligible_for_report_export"] is True


@pytest.mark.django_db
def test_import_meta_paid_csv_rejects_missing_or_cross_tenant_account(tmp_path, tenant):
    _create_account(tenant=tenant)
    csv_path = tmp_path / "meta-paid-cross-tenant.csv"
    csv_path.write_text(
        "date,account_id,campaign_id,spend\n2026-05-01,act_other,cmp-1,10\n",
        encoding="utf-8",
    )

    with pytest.raises(CommandError, match="was not found for this tenant"):
        call_command(
            "import_meta_paid_csv",
            "--tenant-id",
            str(tenant.id),
            "--file",
            str(csv_path),
        )

    assert RawPerformanceRecord.all_objects.filter(tenant=tenant).count() == 0


@pytest.mark.django_db
def test_import_meta_paid_csv_rejects_multi_day_rows(tmp_path, tenant):
    _create_account(tenant=tenant)
    csv_path = tmp_path / "meta-paid-monthly.csv"
    csv_path.write_text(
        "date_start,date_stop,account_id,campaign_id,spend\n"
        "2026-05-01,2026-05-31,act_791712443035541,cmp-1,100\n",
        encoding="utf-8",
    )

    with pytest.raises(CommandError, match="must be daily rows"):
        call_command(
            "import_meta_paid_csv",
            "--tenant-id",
            str(tenant.id),
            "--file",
            str(csv_path),
        )

    assert RawPerformanceRecord.all_objects.filter(tenant=tenant).count() == 0


@pytest.mark.django_db
def test_import_meta_paid_csv_rejects_invalid_metric_values(tmp_path, tenant):
    _create_account(tenant=tenant)
    for index, metric_value in enumerate(["nope", "NaN", "Infinity"], start=1):
        csv_path = tmp_path / f"meta-paid-invalid-{index}.csv"
        csv_path.write_text(
            "date,account_id,campaign_id,spend\n"
            f"2026-05-0{index},act_791712443035541,cmp-1,{metric_value}\n",
            encoding="utf-8",
        )

        with pytest.raises(CommandError, match="must be numeric"):
            call_command(
                "import_meta_paid_csv",
                "--tenant-id",
                str(tenant.id),
                "--file",
                str(csv_path),
            )

    assert RawPerformanceRecord.all_objects.filter(tenant=tenant).count() == 0
