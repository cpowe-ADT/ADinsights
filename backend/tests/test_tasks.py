from __future__ import annotations

from core.tasks import rotate_deks
from integrations.models import PlatformCredential


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
