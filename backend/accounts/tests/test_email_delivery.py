from __future__ import annotations

from accounts.email import EmailPayload, send_email


def test_ses_send_uses_configuration_set(settings, monkeypatch):
    captured: dict[str, object] = {}

    class FakeSesClient:
        def send_email(self, **kwargs):  # noqa: ANN003 - boto-style kwargs
            captured.update(kwargs)
            return {"MessageId": "abc123"}

    settings.EMAIL_PROVIDER = "ses"
    settings.EMAIL_FROM_ADDRESS = "no-reply@adtelligent.net"
    settings.SES_EXPECTED_FROM_DOMAIN = "adtelligent.net"
    settings.SES_CONFIGURATION_SET = "adinsights-prod"
    settings.AWS_REGION = "us-east-1"
    settings.AWS_ACCESS_KEY_ID = None
    settings.AWS_SECRET_ACCESS_KEY = None
    settings.AWS_SESSION_TOKEN = None
    monkeypatch.setattr("accounts.email.boto3.client", lambda *args, **kwargs: FakeSesClient())

    status = send_email(
        EmailPayload(
            subject="Subject",
            body="Body",
            to=["user@example.com"],
        )
    )

    assert status == "sent"
    assert captured["ConfigurationSetName"] == "adinsights-prod"
    assert captured["Source"] == "no-reply@adtelligent.net"


def test_ses_send_skips_when_from_domain_mismatch(settings, monkeypatch):
    called = {"client": False}

    def fake_client(*args, **kwargs):  # noqa: ANN002, ANN003 - boto patch helper
        called["client"] = True
        raise AssertionError("SES client should not be called for invalid from domain")

    settings.EMAIL_PROVIDER = "ses"
    settings.EMAIL_FROM_ADDRESS = "no-reply@example.com"
    settings.SES_EXPECTED_FROM_DOMAIN = "adtelligent.net"
    settings.AWS_REGION = "us-east-1"
    monkeypatch.setattr("accounts.email.boto3.client", fake_client)

    status = send_email(
        EmailPayload(
            subject="Subject",
            body="Body",
            to=["user@example.com"],
        )
    )

    assert status == "skipped"
    assert called["client"] is False

