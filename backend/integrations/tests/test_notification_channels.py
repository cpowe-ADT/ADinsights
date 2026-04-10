from __future__ import annotations

import pytest
from rest_framework import status

from accounts.models import Role, assign_role
from integrations.models import AlertRuleDefinition, NotificationChannel


@pytest.fixture
def admin_user(user):
    assign_role(user, Role.ADMIN)
    return user


@pytest.fixture
def channel(tenant):
    return NotificationChannel.objects.create(
        tenant=tenant,
        name="Team Email",
        channel_type=NotificationChannel.CHANNEL_EMAIL,
        config={"emails": "a@example.com,b@example.com"},
    )


@pytest.fixture
def alert_rule(tenant):
    return AlertRuleDefinition.objects.create(
        tenant=tenant,
        name="High Spend",
        metric="spend",
        comparison_operator="gt",
        threshold=1000,
        lookback_hours=24,
        severity="high",
    )


class TestNotificationChannelModel:
    def test_create_channel(self, tenant):
        ch = NotificationChannel.objects.create(
            tenant=tenant,
            name="Slack Alerts",
            channel_type=NotificationChannel.CHANNEL_SLACK,
            config={"url": "https://hooks.slack.com/services/xxx"},
        )
        assert ch.pk is not None
        assert ch.channel_type == "slack"
        assert ch.is_active is True

    def test_str(self, channel):
        assert "Team Email" in str(channel)
        assert "email" in str(channel)


class TestNotificationChannelAPI:
    endpoint = "/api/notification-channels/"

    def test_list_requires_auth(self, api_client):
        resp = api_client.get(self.endpoint)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_channels(self, api_client, admin_user, channel):
        api_client.force_authenticate(user=admin_user)
        resp = api_client.get(self.endpoint)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        results = data if isinstance(data, list) else data.get("results", data)
        assert len(results) == 1
        assert results[0]["name"] == "Team Email"

    def test_create_channel(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        payload = {
            "name": "Webhook Alerts",
            "channel_type": "webhook",
            "config": {"url": "https://example.com/hook"},
        }
        resp = api_client.post(self.endpoint, payload, format="json")
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.json()["name"] == "Webhook Alerts"
        assert resp.json()["channel_type"] == "webhook"

    def test_update_channel(self, api_client, admin_user, channel):
        api_client.force_authenticate(user=admin_user)
        resp = api_client.patch(
            f"{self.endpoint}{channel.pk}/",
            {"name": "Updated Name"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["name"] == "Updated Name"

    def test_delete_channel(self, api_client, admin_user, channel):
        api_client.force_authenticate(user=admin_user)
        resp = api_client.delete(f"{self.endpoint}{channel.pk}/")
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        assert not NotificationChannel.objects.filter(pk=channel.pk).exists()

    def test_tenant_isolation(self, api_client, admin_user, channel, db):
        from accounts.models import Tenant, User

        other_tenant = Tenant.objects.create(name="Other Tenant")
        other_user = User.objects.create_user(
            username="other@example.com",
            email="other@example.com",
            tenant=other_tenant,
        )
        other_user.set_password("password123")
        other_user.save()
        assign_role(other_user, Role.ADMIN)

        api_client.force_authenticate(user=other_user)
        resp = api_client.get(self.endpoint)
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        results = data if isinstance(data, list) else data.get("results", data)
        assert len(results) == 0


class TestAlertRuleNotificationChannels:
    def test_m2m_assignment(self, alert_rule, channel):
        alert_rule.notification_channels.add(channel)
        assert channel in alert_rule.notification_channels.all()
        assert alert_rule in channel.alert_rules.all()

    def test_m2m_clear(self, alert_rule, channel):
        alert_rule.notification_channels.add(channel)
        alert_rule.notification_channels.clear()
        assert alert_rule.notification_channels.count() == 0
