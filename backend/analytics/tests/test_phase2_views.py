import pytest
from django.urls import reverse
from rest_framework import status
from analytics.models import DashboardDefinition, ReportDefinition

@pytest.fixture
def other_tenant(db):
    from accounts.models import Tenant
    return Tenant.objects.create(name="Other Tenant")

@pytest.fixture
def other_user(other_tenant):
    from accounts.models import User
    return User.objects.create_user(
        username="other@example.com",
        email="other@example.com",
        tenant=other_tenant,
        password="password123"  # pragma: allowlist secret
    )

@pytest.mark.django_db
class TestRecentDashboardsView:
    url = reverse("dashboard-recent")

    def test_recent_dashboards_requires_authentication(self, api_client):
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_recent_dashboards_empty_state(self, api_client, user):
        api_client.force_authenticate(user=user)
        response = api_client.get(self.url)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == []

    def test_recent_dashboards_returns_user_reports(self, api_client, user, tenant):
        api_client.force_authenticate(user=user)

        # Create some dashboards
        DashboardDefinition.objects.create(
            tenant=tenant, name="Report 1", created_by=user, is_active=True
        )
        r2 = DashboardDefinition.objects.create(
            tenant=tenant, name="Report 2", created_by=user, is_active=True
        )

        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert len(data) == 2
        # Ordered by updated_at desc, so r2 should be first
        assert data[0]["name"] == "Report 2"
        assert data[0]["id"] == str(r2.id)
        assert data[0]["route"] == f"/dashboards/saved/{r2.id}"
        assert data[1]["name"] == "Report 1"

    def test_recent_dashboards_limit(self, api_client, user, tenant):
        api_client.force_authenticate(user=user)

        for i in range(5):
            DashboardDefinition.objects.create(
                tenant=tenant, name=f"Report {i}", created_by=user, is_active=True
            )

        # Default limit is 3
        response = api_client.get(self.url)
        assert len(response.json()) == 3

        # Custom limit
        response = api_client.get(self.url, {"limit": 2})
        assert len(response.json()) == 2

        response = api_client.get(self.url, {"limit": 10})
        assert len(response.json()) == 5

    def test_recent_dashboards_tenant_isolation(self, api_client, user, tenant, other_user, other_tenant):
        # Create dashboard for tenant 1
        DashboardDefinition.objects.create(
            tenant=tenant, name="T1 Report", created_by=user, is_active=True
        )
        # Create dashboard for tenant 2
        DashboardDefinition.objects.create(
            tenant=other_tenant, name="T2 Report", created_by=other_user, is_active=True
        )

        # Check tenant 1 sees only their dashboard
        api_client.force_authenticate(user=user)
        response = api_client.get(self.url)
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "T1 Report"

        # Check tenant 2 sees only their dashboard
        api_client.force_authenticate(user=other_user)
        response = api_client.get(self.url)
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "T2 Report"


@pytest.mark.django_db
class TestPageInsightsDashboardDefinitionCRUD:
    """Verify DashboardDefinition CRUD with template_key=meta_page_insights."""

    list_url = reverse("dashboard-definition-list")

    PAGE_INSIGHTS_FILTERS = {
        "page_id": "123456789",
        "date_preset": "last_28d",
        "metric": "page_post_engagements",
        "period": "day",
    }

    def _detail_url(self, pk):
        return reverse("dashboard-definition-detail", args=[pk])

    def test_create_page_insights_definition(self, api_client, user, tenant):
        api_client.force_authenticate(user=user)
        payload = {
            "name": "My Page View",
            "description": "Saved page overview filters",
            "template_key": "meta_page_insights",
            "filters": self.PAGE_INSIGHTS_FILTERS,
            "layout": {},
            "default_metric": "spend",
            "is_active": True,
        }
        response = api_client.post(self.list_url, payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["template_key"] == "meta_page_insights"
        assert data["filters"]["page_id"] == "123456789"
        assert data["name"] == "My Page View"

    def test_list_filters_by_template_key(self, api_client, user, tenant):
        api_client.force_authenticate(user=user)
        DashboardDefinition.objects.create(
            tenant=tenant,
            name="Campaign Dashboard",
            template_key=DashboardDefinition.TEMPLATE_META_CAMPAIGN_PERFORMANCE,
            created_by=user,
        )
        DashboardDefinition.objects.create(
            tenant=tenant,
            name="Page View 1",
            template_key=DashboardDefinition.TEMPLATE_META_PAGE_INSIGHTS,
            filters=self.PAGE_INSIGHTS_FILTERS,
            created_by=user,
        )
        response = api_client.get(self.list_url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        results = data if isinstance(data, list) else data.get("results", data)
        assert len(results) == 2

    def test_read_page_insights_definition(self, api_client, user, tenant):
        api_client.force_authenticate(user=user)
        dashboard = DashboardDefinition.objects.create(
            tenant=tenant,
            name="Page View Read",
            template_key=DashboardDefinition.TEMPLATE_META_PAGE_INSIGHTS,
            filters=self.PAGE_INSIGHTS_FILTERS,
            created_by=user,
        )
        response = api_client.get(self._detail_url(dashboard.pk))
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["template_key"] == "meta_page_insights"

    def test_update_page_insights_definition(self, api_client, user, tenant):
        api_client.force_authenticate(user=user)
        dashboard = DashboardDefinition.objects.create(
            tenant=tenant,
            name="Page View Update",
            template_key=DashboardDefinition.TEMPLATE_META_PAGE_INSIGHTS,
            filters=self.PAGE_INSIGHTS_FILTERS,
            created_by=user,
        )
        response = api_client.patch(
            self._detail_url(dashboard.pk),
            {"name": "Updated Name", "filters": {**self.PAGE_INSIGHTS_FILTERS, "period": "week"}},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["name"] == "Updated Name"
        assert response.json()["filters"]["period"] == "week"

    def test_delete_page_insights_definition(self, api_client, user, tenant):
        api_client.force_authenticate(user=user)
        dashboard = DashboardDefinition.objects.create(
            tenant=tenant,
            name="Page View Delete",
            template_key=DashboardDefinition.TEMPLATE_META_PAGE_INSIGHTS,
            filters=self.PAGE_INSIGHTS_FILTERS,
            created_by=user,
        )
        response = api_client.delete(self._detail_url(dashboard.pk))
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not DashboardDefinition.objects.filter(pk=dashboard.pk).exists()


@pytest.mark.django_db
class TestReportScheduleFields:
    list_url = reverse("report-definition-list")

    def _detail_url(self, pk):
        return reverse("report-definition-detail", args=[pk])

    def _toggle_url(self, pk):
        return reverse("report-definition-toggle-schedule", args=[pk])

    def test_create_report_with_schedule_fields(self, api_client, user, tenant):
        api_client.force_authenticate(user=user)
        payload = {
            "name": "Scheduled Report",
            "description": "A report with schedule",
            "schedule_enabled": True,
            "schedule_cron": "0 8 * * 1",
            "delivery_emails": ["team@example.com", "boss@example.com"],
        }
        response = api_client.post(self.list_url, payload, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["schedule_enabled"] is True
        assert data["schedule_cron"] == "0 8 * * 1"
        assert data["delivery_emails"] == ["team@example.com", "boss@example.com"]
        assert data["last_scheduled_at"] is None

    def test_toggle_schedule_action(self, api_client, user, tenant):
        api_client.force_authenticate(user=user)
        report = ReportDefinition.objects.create(
            tenant=tenant,
            name="Toggle Test",
            created_by=user,
            schedule_enabled=False,
        )
        # Enable
        response = api_client.post(
            self._toggle_url(report.pk), {"enabled": True}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["schedule_enabled"] is True

        # Disable
        response = api_client.post(
            self._toggle_url(report.pk), {"enabled": False}, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["schedule_enabled"] is False

    def test_schedule_fields_in_get_response(self, api_client, user, tenant):
        api_client.force_authenticate(user=user)
        report = ReportDefinition.objects.create(
            tenant=tenant,
            name="Get Test",
            created_by=user,
            schedule_enabled=True,
            schedule_cron="30 9 * * *",
            delivery_emails=["a@b.com"],
        )
        response = api_client.get(self._detail_url(report.pk))
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["schedule_enabled"] is True
        assert data["schedule_cron"] == "30 9 * * *"
        assert data["delivery_emails"] == ["a@b.com"]
        assert "last_scheduled_at" in data
