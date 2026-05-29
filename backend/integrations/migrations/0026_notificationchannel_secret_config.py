import json

from django.db import migrations, models


SECRET_KEYS = {
    "url",
    "webhook_url",
    "headers",
    "auth_headers",
    "authorization",
    "authorization_header",
    "token",
    "auth_token",
    "bearer_token",
    "api_key",
    "secret",
}
SECRET_TYPES = {"slack", "webhook"}


def encrypt_existing_channel_secrets(apps, schema_editor):
    from accounts.models import Tenant
    from core.crypto.dek_manager import get_dek_for_tenant
    from core.crypto.fields import encrypt_value

    NotificationChannel = apps.get_model("integrations", "NotificationChannel")
    for channel in NotificationChannel.objects.filter(channel_type__in=SECRET_TYPES):
        config = dict(channel.config or {})
        secret_config = {
            key: config.pop(key)
            for key in SECRET_KEYS
            if key in config
        }
        if not secret_config:
            continue
        tenant = Tenant.objects.get(pk=channel.tenant_id)
        key, version = get_dek_for_tenant(tenant)
        encrypted = encrypt_value(json.dumps(secret_config, sort_keys=True), key)
        if encrypted is None:
            continue
        channel.config = config
        channel.secret_config_enc = encrypted.ciphertext
        channel.secret_config_nonce = encrypted.nonce
        channel.secret_config_tag = encrypted.tag
        channel.secret_dek_key_version = version
        channel.save(
            update_fields=[
                "config",
                "secret_config_enc",
                "secret_config_nonce",
                "secret_config_tag",
                "secret_dek_key_version",
            ]
        )


def decrypt_channel_secrets_for_reverse(apps, schema_editor):
    from accounts.models import Tenant
    from core.crypto.dek_manager import get_dek_for_tenant
    from core.crypto.fields import decrypt_value

    NotificationChannel = apps.get_model("integrations", "NotificationChannel")
    for channel in NotificationChannel.objects.filter(
        channel_type__in=SECRET_TYPES,
        secret_config_enc__isnull=False,
    ):
        tenant = Tenant.objects.get(pk=channel.tenant_id)
        key, _ = get_dek_for_tenant(tenant)
        raw = decrypt_value(
            channel.secret_config_enc,
            channel.secret_config_nonce,
            channel.secret_config_tag,
            key,
        )
        secret_config = json.loads(raw or "{}")
        channel.config = {**dict(channel.config or {}), **secret_config}
        channel.save(update_fields=["config"])


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0025_recommendation_dismissed_audit"),
    ]

    operations = [
        migrations.AddField(
            model_name="notificationchannel",
            name="secret_config_enc",
            field=models.BinaryField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="notificationchannel",
            name="secret_config_nonce",
            field=models.BinaryField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="notificationchannel",
            name="secret_config_tag",
            field=models.BinaryField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="notificationchannel",
            name="secret_dek_key_version",
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.RunPython(
            encrypt_existing_channel_secrets,
            decrypt_channel_secrets_for_reverse,
        ),
    ]
