import pytest
from django.urls import reverse
from rest_framework import status
from analytics.models import ReportDefinition

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
        
        # Create some reports
        ReportDefinition.objects.create(
            tenant=tenant, name="Report 1", created_by=user, is_active=True
        )
        r2 = ReportDefinition.objects.create(
            tenant=tenant, name="Report 2", created_by=user, is_active=True
        )
        
        response = api_client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert len(data) == 2
        # Ordered by updated_at desc, so r2 should be first
        assert data[0]["name"] == "Report 2"
        assert data[0]["id"] == f"report-{r2.id}"
        assert data[0]["route"] == f"/reports/{r2.id}"
        assert data[1]["name"] == "Report 1"

    def test_recent_dashboards_limit(self, api_client, user, tenant):
        api_client.force_authenticate(user=user)
        
        for i in range(5):
            ReportDefinition.objects.create(
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
        # Create report for tenant 1
        ReportDefinition.objects.create(
            tenant=tenant, name="T1 Report", created_by=user, is_active=True
        )
        # Create report for tenant 2
        ReportDefinition.objects.create(
            tenant=other_tenant, name="T2 Report", created_by=other_user, is_active=True
        )
        
        # Check tenant 1 sees only their report
        api_client.force_authenticate(user=user)
        response = api_client.get(self.url)
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "T1 Report"
        
        # Check tenant 2 sees only their report
        api_client.force_authenticate(user=other_user)
        response = api_client.get(self.url)
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "T2 Report"
