from __future__ import annotations

import importlib

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
        ch = NotificationChannel(
            tenant=tenant,
            name="Slack Alerts",
            channel_type=NotificationChannel.CHANNEL_SLACK,
            config={},
        )
        ch.set_secret_config({"url": "https://hooks.slack.com/services/xxx"})
        ch.save()
        assert ch.pk is not None
        assert ch.channel_type == "slack"
        assert ch.is_active is True
        assert ch.config == {}
        assert ch.has_secret_config is True
        assert ch.decrypt_secret_config()["url"] == "https://hooks.slack.com/services/xxx"

    def test_model_extracts_plaintext_secret_configuration(self, tenant):
        channel = NotificationChannel.objects.create(
            tenant=tenant,
            name="Direct Webhook",
            channel_type=NotificationChannel.CHANNEL_WEBHOOK,
            config={
                "url": "https://hooks.example.test/direct",
                "auth_token": "direct-token",
                "label": "safe",
            },
        )

        assert channel.config == {"label": "safe"}
        assert channel.has_secret_config is True
        assert channel.decrypt_secret_config() == {
            "auth_token": "direct-token",
            "url": "https://hooks.example.test/direct",
        }
        channel.config = {
            "url": "https://hooks.example.test/replaced",
            "label": "updated",
        }
        channel.save(update_fields=["config"])
        channel.refresh_from_db()
        assert channel.config == {"label": "updated"}
        assert channel.decrypt_secret_config()["url"] == "https://hooks.example.test/replaced"

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
            "secret_config": {"url": "https://example.com/hook"},
        }
        resp = api_client.post(self.endpoint, payload, format="json")
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.json()["name"] == "Webhook Alerts"
        assert resp.json()["channel_type"] == "webhook"
        assert resp.json()["config"] == {}
        assert resp.json()["credentials_configured"] is True
        assert resp.json()["masked_destination"] == "Webhook configured"
        assert "secret_config" not in resp.json()
        stored = NotificationChannel.objects.get(name="Webhook Alerts")
        assert stored.decrypt_secret_config()["url"] == "https://example.com/hook"

    def test_legacy_config_secret_is_encrypted_and_redacted(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        resp = api_client.post(
            self.endpoint,
            {
                "name": "Legacy Slack",
                "channel_type": "slack",
                "config": {"url": "https://hooks.slack.test/secret", "label": "#alerts"},
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.json()["config"] == {"label": "#alerts"}
        assert "secret" not in str(resp.json())
        stored = NotificationChannel.objects.get(name="Legacy Slack")
        assert stored.config == {"label": "#alerts"}
        assert stored.decrypt_secret_config()["url"] == "https://hooks.slack.test/secret"

    def test_response_redacts_residual_plaintext_destination_config(self, api_client, admin_user, tenant):
        channel = NotificationChannel.objects.create(
            tenant=tenant,
            name="Unmigrated Webhook",
            channel_type=NotificationChannel.CHANNEL_WEBHOOK,
            config={"label": "operations"},
        )
        NotificationChannel.all_objects.filter(pk=channel.pk).update(
            config={
                "url": "https://hooks.example.test/secret",
                "headers": {"Authorization": "Bearer hidden"},
                "auth_token": "hidden-token",
                "label": "operations",
            },
        )
        api_client.force_authenticate(user=admin_user)

        response = api_client.get(self.endpoint)

        assert response.status_code == status.HTTP_200_OK
        results = response.json()
        results = results if isinstance(results, list) else results["results"]
        payload = next(row for row in results if row["name"] == "Unmigrated Webhook")
        assert payload["config"] == {"label": "operations"}
        assert "hidden" not in str(payload)

    def test_update_channel(self, api_client, admin_user, channel):
        api_client.force_authenticate(user=admin_user)
        resp = api_client.patch(
            f"{self.endpoint}{channel.pk}/",
            {"name": "Updated Name"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["name"] == "Updated Name"

    def test_update_preserves_or_clears_encrypted_destination(self, api_client, admin_user, tenant):
        secret_channel = NotificationChannel(
            tenant=tenant,
            name="Webhook",
            channel_type=NotificationChannel.CHANNEL_WEBHOOK,
        )
        secret_channel.set_secret_config({"url": "https://example.com/hook"})
        secret_channel.save()
        api_client.force_authenticate(user=admin_user)

        updated = api_client.patch(
            f"{self.endpoint}{secret_channel.pk}/",
            {"name": "Renamed"},
            format="json",
        )
        assert updated.status_code == status.HTTP_200_OK
        secret_channel.refresh_from_db()
        assert secret_channel.decrypt_secret_config()["url"] == "https://example.com/hook"

        cleared = api_client.patch(
            f"{self.endpoint}{secret_channel.pk}/",
            {"clear_secret_config": True, "is_active": False},
            format="json",
        )
        assert cleared.status_code == status.HTTP_200_OK
        assert cleared.json()["credentials_configured"] is False
        secret_channel.refresh_from_db()
        assert secret_channel.has_secret_config is False

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


@pytest.mark.django_db
def test_notification_channel_secret_data_migration_encrypts_plaintext_config(tenant):
    channel = NotificationChannel.objects.create(
        tenant=tenant,
        name="Migration Webhook",
        channel_type=NotificationChannel.CHANNEL_WEBHOOK,
        config={"label": "safe label"},
    )
    NotificationChannel.all_objects.filter(pk=channel.pk).update(
        config={
            "url": "https://hooks.example.test/migrate",
            "auth_token": "migration-token",
            "label": "safe label",
        },
    )
    migration = importlib.import_module("integrations.migrations.0026_notificationchannel_secret_config")

    class RuntimeApps:
        @staticmethod
        def get_model(app_label, model_name):
            assert (app_label, model_name) == ("integrations", "NotificationChannel")
            return NotificationChannel

    migration.encrypt_existing_channel_secrets(RuntimeApps(), None)

    channel.refresh_from_db()
    assert channel.config == {"label": "safe label"}
    assert channel.has_secret_config is True
    assert channel.decrypt_secret_config() == {
        "auth_token": "migration-token",
        "url": "https://hooks.example.test/migrate",
    }


class TestAlertRuleNotificationChannels:
    def test_m2m_assignment(self, alert_rule, channel):
        alert_rule.notification_channels.add(channel)
        assert channel in alert_rule.notification_channels.all()
        assert alert_rule in channel.alert_rules.all()

    def test_m2m_clear(self, alert_rule, channel):
        alert_rule.notification_channels.add(channel)
        alert_rule.notification_channels.clear()
        assert alert_rule.notification_channels.count() == 0
