from __future__ import annotations

from datetime import timedelta

import pytest
from django.conf import settings
from django.utils import timezone

from alerts.models import AlertRun
from core.tasks import rotate_deks
from integrations.models import PlatformCredential
from integrations.tasks import remind_expiring_credentials


def test_rotate_deks_updates_key(api_client, user, tenant):
    credential = PlatformCredential(
        tenant=tenant,
        provider=PlatformCredential.META,
        account_id="123",
    )
    credential.set_raw_tokens("token", "refresh")
    credential.save()
    old_version = credential.dek_key_version
    result = rotate_deks()
    credential.refresh_from_db()
    assert "rotated" in result
    assert credential.dek_key_version != old_version


@pytest.mark.django_db
def test_remind_expiring_credentials_creates_alert(tenant):
    AlertRun.objects.all().delete()
    credential = PlatformCredential(
        tenant=tenant,
        provider=PlatformCredential.META,
        account_id="acct-42",
        expires_at=timezone.now() + timedelta(days=2),
    )
    credential.set_raw_tokens("access", "refresh")
    credential.save()

    result = remind_expiring_credentials.run()

    assert result["processed"] == 1
    run = AlertRun.objects.latest("created_at")
    assert run.rule_slug == "credential_rotation_due"
    assert run.row_count == 1
    payload = run.raw_results[0]
    assert payload["provider"] == PlatformCredential.META
    assert payload["credential_ref"].startswith("ref_")
    assert payload["status"] == "expiring"


@pytest.mark.django_db
def test_remind_expiring_credentials_without_matches():
    AlertRun.objects.all().delete()

    result = remind_expiring_credentials.run()

    assert result == {"processed": 0}
    assert AlertRun.objects.count() == 0


def test_rotate_deks_schedule_present():
    schedule = settings.CELERY_BEAT_SCHEDULE
    assert "rotate-tenant-deks" in schedule
    entry = schedule["rotate-tenant-deks"]
    assert entry["task"] == "core.tasks.rotate_deks"
