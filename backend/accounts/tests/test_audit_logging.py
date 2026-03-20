import pytest
from django.urls import reverse
from rest_framework import status

from accounts.audit import log_audit_event
from accounts.models import Tenant, User

@pytest.fixture
def other_tenant(db):
    return Tenant.objects.create(name="Other Tenant")

@pytest.fixture
def other_user(other_tenant):
    return User.objects.create_user(
        username="other@example.com",
        email="other@example.com",
        tenant=other_tenant,
        password="password123"
    )

@pytest.mark.django_db
class TestAuditLogging:
    def test_log_audit_event_helper(self, tenant, user):
        metadata = {"key": "value"}
        event = log_audit_event(
            tenant=tenant,
            user=user,
            action="test_action",
            resource_type="test_resource",
            resource_id="123",
            metadata=metadata
        )
        
        assert event.tenant == tenant
        assert event.user == user
        assert event.action == "test_action"
        assert event.resource_type == "test_resource"
        assert event.resource_id == "123"
        assert event.metadata == metadata

    def test_log_audit_event_with_request(self, tenant, user):
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.get("/", HTTP_USER_AGENT="test-agent")
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        
        event = log_audit_event(
            tenant=tenant,
            user=user,
            action="request_action",
            resource_type="request_resource",
            resource_id="456",
            request=request
        )
        
        assert event.metadata["actor_ip"] == "192.168.1.1"
        assert event.metadata["user_agent"] == "test-agent"

    def test_list_audit_logs_tenant_isolation(self, api_client, tenant, user, other_tenant, other_user):
        # Create logs for both tenants
        log_audit_event(tenant=tenant, user=user, action="action_t1", resource_type="r1", resource_id="1")
        log_audit_event(tenant=other_tenant, user=other_user, action="action_t2", resource_type="r2", resource_id="2")
        
        url = reverse("auditlog-list")
        
        # Authenticate as user from tenant 1
        api_client.force_authenticate(user=user)
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["action"] == "action_t1"
        assert response.data["results"][0]["tenant"] == tenant.id

        # Authenticate as user from tenant 2
        api_client.force_authenticate(user=other_user)
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["action"] == "action_t2"
        assert response.data["results"][0]["tenant"] == other_tenant.id

    def test_audit_log_filtering(self, api_client, tenant, user):
        log_audit_event(tenant=tenant, user=user, action="login", resource_type="auth", resource_id="1")
        log_audit_event(tenant=tenant, user=user, action="logout", resource_type="auth", resource_id="1")
        log_audit_event(tenant=tenant, user=user, action="create", resource_type="report", resource_id="2")
        
        url = reverse("auditlog-list")
        api_client.force_authenticate(user=user)
        
        # Filter by action
        response = api_client.get(url, {"action": "login"})
        assert response.data["count"] == 1
        assert response.data["results"][0]["action"] == "login"
        
        # Filter by resource_type
        response = api_client.get(url, {"resource_type": "report"})
        assert response.data["count"] == 1
        assert response.data["results"][0]["resource_type"] == "report"
        
        # Combined filter
        response = api_client.get(url, {"action": "logout", "resource_type": "auth"})
        assert response.data["count"] == 1
        assert response.data["results"][0]["action"] == "logout"
