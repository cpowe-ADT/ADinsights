from __future__ import annotations

import json
from datetime import datetime, timezone as dt_timezone
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from accounts.models import AuditLog
from analytics.reporting_availability import build_report_data_availability
from analytics.reporting_preview import build_widget_preview
from integrations.models import (
    MetaConnection,
    MetaInsightPoint,
    MetaPage,
    MetaPost,
    MetaPostInsightPoint,
)


def _create_page(*, tenant, user, page_id: str = "page-123") -> MetaPage:
    connection = MetaConnection(
        tenant=tenant,
        user=user,
        app_scoped_user_id=f"{page_id}-user",
        scopes=["pages_show_list", "pages_read_engagement"],
        is_active=True,
    )
    connection.set_raw_token("meta-user-token")
    connection.save()
    page = MetaPage(
        tenant=tenant,
        connection=connection,
        page_id=page_id,
        name="Students' Loan Bureau",
        can_analyze=True,
        is_default=True,
    )
    page.set_raw_page_token("page-token")
    page.save()
    return page


def _metric_availability_by_key(dataset: dict) -> dict[str, dict]:
    return {
        str(metric["key"]): metric
        for metric in dataset["metric_availability"]["metrics"]
    }


@pytest.mark.django_db
def test_import_meta_organic_csv_upserts_page_and_post_reporting_rows(
    tmp_path, tenant, user
):
    _create_page(tenant=tenant, user=user)
    csv_path = tmp_path / "meta-organic.csv"
    csv_path.write_text(
        "\n".join(
            [
                "Date,Page ID,Page Reach,Page Impressions,Post ID,Post Message,Post Impressions,Post Reach,Post Clicks,Post Reactions,Post Comments,Post Shares",
                '2026-05-15,page-123,"1,234",234,page-123_1,Manual import post,55,44,,7,2,1',
                "2026-05-16,page-123,,345,,,,,,,",
            ]
        ),
        encoding="utf-8",
    )
    output = StringIO()

    call_command(
        "import_meta_organic_csv",
        "--tenant-id",
        str(tenant.id),
        "--file",
        str(csv_path),
        stdout=output,
    )

    payload = json.loads(output.getvalue())
    assert payload["schema_version"] == "meta_organic_csv_import.v1"
    assert payload["stored_aggregate_only"] is True
    assert payload["no_live_provider_calls"] is True
    assert payload["summary"] == {
        "page_count": 1,
        "page_points_created": 3,
        "page_points_updated": 0,
        "post_count": 1,
        "post_points_created": 5,
        "post_points_updated": 0,
        "posts_created": 1,
        "posts_updated": 0,
        "rows_seen": 2,
        "rows_skipped_no_metrics": 0,
    }
    assert MetaInsightPoint.all_objects.filter(
        tenant=tenant,
        metric_key="page_reach",
        value_num=1234,
    ).exists()
    assert MetaInsightPoint.all_objects.filter(
        tenant=tenant,
        metric_key="page_impressions",
        value_num=345,
    ).exists()
    assert not MetaPostInsightPoint.all_objects.filter(
        tenant=tenant, metric_key="post_clicks"
    ).exists()
    post = MetaPost.all_objects.get(tenant=tenant, post_id="page-123_1")
    assert post.message == "Manual import post"
    assert MetaPostInsightPoint.all_objects.filter(
        tenant=tenant,
        post=post,
        metric_key="post_impressions",
        value_num=55,
    ).exists()
    assert MetaPostInsightPoint.all_objects.filter(
        tenant=tenant,
        post=post,
        metric_key="post_reach",
        value_num=44,
    ).exists()

    availability = build_report_data_availability(
        tenant=tenant,
        params={
            "date_range": "custom",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
            "page_id": "page-123",
        },
    )
    page_metrics = _metric_availability_by_key(
        availability["datasets"]["organic_facebook_page"]
    )
    assert page_metrics["page_reach"]["availability_state"] == "available"
    assert page_metrics["page_reach"]["row_count"] == 1
    assert page_metrics["page_impressions"]["availability_state"] == "available"
    assert page_metrics["page_impressions"]["row_count"] == 2
    post_metrics = _metric_availability_by_key(
        availability["datasets"]["organic_facebook_posts"]
    )
    assert post_metrics["post_impressions"]["availability_state"] == "available"
    assert post_metrics["post_reach"]["availability_state"] == "available"

    page_preview = build_widget_preview(
        tenant=tenant,
        payload={
            "page_id": "page-123",
            "widget": {
                "id": "organic_page_imported",
                "type": "line_chart",
                "dataset": "organic_facebook_page",
                "metrics": ["page_reach", "page_impressions"],
                "dimensions": ["date"],
                "filters": {
                    "date_range": "custom",
                    "start_date": "2026-05-01",
                    "end_date": "2026-05-31",
                },
                "coverage_policy": "render_with_warning",
            },
        },
    )
    assert page_preview["data"]["rows"] == [
        {"date": "2026-05-15", "page_reach": 1234.0, "page_impressions": 234.0},
        {"date": "2026-05-16", "page_reach": None, "page_impressions": 345.0},
    ]

    post_preview = build_widget_preview(
        tenant=tenant,
        payload={
            "page_id": "page-123",
            "widget": {
                "id": "organic_posts_imported",
                "type": "data_table",
                "dataset": "organic_facebook_page",
                "metrics": [
                    "post_impressions",
                    "post_reach",
                    "post_reactions",
                    "post_comments",
                    "post_shares",
                ],
                "dimensions": ["post"],
                "filters": {
                    "date_range": "custom",
                    "start_date": "2026-05-01",
                    "end_date": "2026-05-31",
                },
                "coverage_policy": "render_with_warning",
                "visual": {"row_limit": 10},
            },
        },
    )
    assert post_preview["data"]["rows"] == [
        {
            "post": "page-123_1",
            "date": "2026-05-15",
            "content": "Manual import post",
            "post_impressions": 55.0,
            "post_reach": 44.0,
            "post_reactions": 7.0,
            "post_comments": 2.0,
            "post_shares": 1.0,
        }
    ]


@pytest.mark.django_db
def test_import_meta_organic_csv_dry_run_validates_without_writes(
    tmp_path, tenant, user
):
    _create_page(tenant=tenant, user=user)
    csv_path = tmp_path / "meta-organic-dry-run.csv"
    csv_path.write_text(
        "\n".join(
            [
                "date,page_id,page_reach,post_id,post_message,post_reactions",
                "2026-05-15,page-123,123,page-123_1,Dry run post,7",
            ]
        ),
        encoding="utf-8",
    )
    output = StringIO()

    call_command(
        "import_meta_organic_csv",
        "--tenant-id",
        str(tenant.id),
        "--file",
        str(csv_path),
        "--dry-run",
        stdout=output,
    )

    payload = json.loads(output.getvalue())
    assert payload["schema_version"] == "meta_organic_csv_import.v1"
    assert payload["dry_run"] is True
    assert payload["stored_aggregate_only"] is True
    assert payload["no_live_provider_calls"] is True
    assert payload["summary"] == {
        "page_count": 1,
        "page_points_created": 1,
        "page_points_updated": 0,
        "post_count": 1,
        "post_points_created": 1,
        "post_points_updated": 0,
        "posts_created": 1,
        "posts_updated": 0,
        "rows_seen": 1,
        "rows_skipped_no_metrics": 0,
    }
    assert not MetaInsightPoint.all_objects.filter(tenant=tenant).exists()
    assert not MetaPost.all_objects.filter(tenant=tenant).exists()
    assert not MetaPostInsightPoint.all_objects.filter(tenant=tenant).exists()
    assert not AuditLog.all_objects.filter(
        tenant=tenant, action="meta_organic_csv_imported"
    ).exists()


@pytest.mark.django_db
def test_import_meta_organic_csv_updates_existing_points_without_zeroing_blanks(
    tmp_path, tenant, user
):
    page = _create_page(tenant=tenant, user=user)
    end_time = datetime(2026, 5, 15, 12, tzinfo=dt_timezone.utc)
    MetaInsightPoint.all_objects.create(
        tenant=tenant,
        page=page,
        metric_key="page_media_view",
        period="day",
        end_time=end_time,
        value_num=100,
    )
    csv_path = tmp_path / "meta-organic-update.csv"
    csv_path.write_text(
        "date,page_id,page_impressions,page_reach\n2026-05-15,page-123,200,\n",
        encoding="utf-8",
    )
    output = StringIO()

    call_command(
        "import_meta_organic_csv",
        "--tenant-id",
        str(tenant.id),
        "--file",
        str(csv_path),
        stdout=output,
    )

    payload = json.loads(output.getvalue())
    assert payload["summary"]["page_points_created"] == 1
    assert payload["summary"]["page_points_updated"] == 0
    assert (
        MetaInsightPoint.all_objects.get(
            tenant=tenant,
            page=page,
            metric_key="page_media_view",
        ).value_num
        == 100
    )
    assert (
        MetaInsightPoint.all_objects.get(
            tenant=tenant,
            page=page,
            metric_key="page_impressions",
        ).value_num
        == 200
    )
    assert not MetaInsightPoint.all_objects.filter(
        tenant=tenant,
        page=page,
        metric_key="page_reach",
    ).exists()


@pytest.mark.django_db
def test_import_meta_organic_csv_source_keys_do_not_clear_permission_gated_products(
    tmp_path, tenant, user
):
    _create_page(tenant=tenant, user=user)
    csv_path = tmp_path / "meta-organic-source-key.csv"
    csv_path.write_text(
        "\n".join(
            [
                "date,page_id,page_media_view,post_id,post_message,post_media_view",
                "2026-05-15,page-123,777,page-123_1,Source metric post,55",
            ]
        ),
        encoding="utf-8",
    )

    call_command(
        "import_meta_organic_csv",
        "--tenant-id",
        str(tenant.id),
        "--file",
        str(csv_path),
    )

    post = MetaPost.all_objects.get(tenant=tenant, post_id="page-123_1")
    assert MetaInsightPoint.all_objects.filter(
        tenant=tenant,
        metric_key="page_media_view",
        value_num=777,
    ).exists()
    assert not MetaInsightPoint.all_objects.filter(
        tenant=tenant,
        metric_key="page_impressions",
    ).exists()
    assert MetaPostInsightPoint.all_objects.filter(
        tenant=tenant,
        post=post,
        metric_key="post_media_view",
        value_num=55,
    ).exists()
    assert not MetaPostInsightPoint.all_objects.filter(
        tenant=tenant,
        post=post,
        metric_key="post_impressions",
    ).exists()

    availability = build_report_data_availability(
        tenant=tenant,
        params={
            "date_range": "custom",
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
            "page_id": "page-123",
        },
    )
    page_metrics = _metric_availability_by_key(
        availability["datasets"]["organic_facebook_page"]
    )
    assert page_metrics["page_impressions"]["availability_state"] == "permission_gated"
    assert page_metrics["page_impressions"]["row_count"] == 0
    post_metrics = _metric_availability_by_key(
        availability["datasets"]["organic_facebook_posts"]
    )
    assert post_metrics["post_impressions"]["availability_state"] == "permission_gated"
    assert post_metrics["post_impressions"]["row_count"] == 0


@pytest.mark.django_db
def test_import_meta_organic_csv_rejects_missing_or_cross_tenant_page(
    tmp_path, tenant, user
):
    _create_page(tenant=tenant, user=user, page_id="owned-page")
    csv_path = tmp_path / "meta-organic-cross-tenant.csv"
    csv_path.write_text(
        "date,page_id,page_impressions\n2026-05-15,other-page,200\n", encoding="utf-8"
    )

    with pytest.raises(CommandError, match="was not found for this tenant"):
        call_command(
            "import_meta_organic_csv",
            "--tenant-id",
            str(tenant.id),
            "--file",
            str(csv_path),
        )

    assert MetaInsightPoint.all_objects.filter(tenant=tenant).count() == 0


@pytest.mark.django_db
def test_import_meta_organic_csv_rejects_invalid_metric_values(tmp_path, tenant, user):
    _create_page(tenant=tenant, user=user)
    for index, metric_value in enumerate(["nope", "NaN", "Infinity"], start=15):
        csv_path = tmp_path / f"meta-organic-invalid-{index}.csv"
        csv_path.write_text(
            "date,page_id,page_impressions\n"
            f"2026-05-{index},page-123,{metric_value}\n",
            encoding="utf-8",
        )

        with pytest.raises(CommandError, match="must be numeric"):
            call_command(
                "import_meta_organic_csv",
                "--tenant-id",
                str(tenant.id),
                "--file",
                str(csv_path),
            )

    assert MetaInsightPoint.all_objects.filter(tenant=tenant).count() == 0
