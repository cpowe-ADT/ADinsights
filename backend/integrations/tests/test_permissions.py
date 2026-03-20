import pytest
from django.urls import reverse
from rest_framework import status
from accounts.models import Role

@pytest.fixture
def viewer_user(tenant):
    from accounts.models import User, assign_role
    user = User.objects.create_user(
        username="viewer@example.com",
        email="viewer@example.com",
        tenant=tenant,
        password="password123"
    )
    assign_role(user, Role.VIEWER)
    return user

@pytest.fixture
def admin_user(tenant):
    from accounts.models import User, assign_role
    user = User.objects.create_user(
        username="admin@example.com",
        email="admin@example.com",
        tenant=tenant,
        password="password123"
    )
    assign_role(user, Role.ADMIN)
    return user

@pytest.mark.django_db
class TestIntegrationPermissions:
    def test_airbyte_connection_create_denied_for_viewer(self, api_client, viewer_user):
        api_client.force_authenticate(user=viewer_user)
        url = reverse("airbyte-connection-list")
        data = {"name": "Test Connection", "workspace_id": "ws1", "destination_id": "dest1"}
        
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "User is missing the required privilege: 'workspace_manage'" in str(response.data.get("detail", ""))

    def test_airbyte_connection_create_allowed_for_admin(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        url = reverse("airbyte-connection-list")
        data = {
            "name": "Test Connection", 
            "workspace_id": "ws1", 
            "destination_id": "dest1",
            "source_definition_id": "def1",
            "connection_id": "550e8400-e29b-41d4-a716-446655440000"
        }
        
        # We expect 201 or 400 (validation error), but NOT 403
        response = api_client.post(url, data)
        assert response.status_code != status.HTTP_403_FORBIDDEN

    def test_budget_create_denied_for_viewer(self, api_client, viewer_user):
        api_client.force_authenticate(user=viewer_user)
        url = reverse("campaignbudget-list")
        data = {"name": "Test Budget", "amount": 1000}
        
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "User is missing the required privilege: 'budget_edit'" in str(response.data.get("detail", ""))
