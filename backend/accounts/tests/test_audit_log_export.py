from __future__ import annotations

import csv
import io

import pytest
from django.urls import reverse

from accounts.models import AuditLog
from backend.tests.conftest import *  # noqa: F401,F403


@pytest.mark.django_db
class TestAuditLogExportCsv:
    def test_export_csv_returns_csv_with_headers_and_rows(
        self, api_client, user, tenant
    ):
        api_client.force_authenticate(user=user)

        AuditLog.objects.create(
            tenant=tenant,
            user=user,
            action="report_created",
            resource_type="report_definition",
            resource_id="rpt-001",
            metadata={"source": "manual"},
        )
        AuditLog.objects.create(
            tenant=tenant,
            user=user,
            action="user_login",
            resource_type="session",
            resource_id="sess-002",
            metadata={},
        )

        url = reverse("auditlog-export-csv")
        response = api_client.get(url)

        assert response.status_code == 200
        assert response["Content-Type"] == "text/csv"
        assert "audit_log_export.csv" in response["Content-Disposition"]

        content = b"".join(response.streaming_content).decode("utf-8")
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)

        assert rows[0] == [
            "id",
            "action",
            "resource_type",
            "resource_id",
            "user_email",
            "metadata",
            "created_at",
        ]
        assert len(rows) == 3  # header + 2 data rows
        actions = {rows[1][1], rows[2][1]}
        assert actions == {"report_created", "user_login"}

    def test_export_csv_respects_action_filter(self, api_client, user, tenant):
        api_client.force_authenticate(user=user)

        AuditLog.objects.create(
            tenant=tenant,
            user=user,
            action="report_created",
            resource_type="report_definition",
            resource_id="rpt-001",
        )
        AuditLog.objects.create(
            tenant=tenant,
            user=user,
            action="user_login",
            resource_type="session",
            resource_id="sess-002",
        )

        url = reverse("auditlog-export-csv")
        response = api_client.get(url, {"action": "report_created"})

        content = b"".join(response.streaming_content).decode("utf-8")
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)

        assert len(rows) == 2  # header + 1 filtered row
        assert rows[1][1] == "report_created"

    def test_export_csv_unauthenticated_returns_401(self, api_client):
        url = reverse("auditlog-export-csv")
        response = api_client.get(url)
        assert response.status_code == 401
