from __future__ import annotations

import logging
from dataclasses import dataclass
from email.utils import parseaddr
from typing import Sequence

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailPayload:
    subject: str
    body: str
    to: Sequence[str]


def send_email(payload: EmailPayload) -> str:
    provider = getattr(settings, "EMAIL_PROVIDER", "log")
    provider_value = provider.lower() if isinstance(provider, str) else "log"

    if provider_value == "ses":
        return _send_via_ses(payload)

    return _log_email(payload, provider_value)


def _log_email(payload: EmailPayload, provider: str) -> str:
    logger.info(
        "email.delivery.skipped",
        extra={
            "provider": provider,
            "subject": payload.subject,
            "recipient_count": len(payload.to),
        },
    )
    return "logged"


def _send_via_ses(payload: EmailPayload) -> str:
    from_address = getattr(settings, "EMAIL_FROM_ADDRESS", None)
    if not from_address:
        logger.warning(
            "email.delivery.missing_from_address",
            extra={"provider": "ses", "recipient_count": len(payload.to)},
        )
        return "skipped"

    expected_domain = getattr(settings, "SES_EXPECTED_FROM_DOMAIN", None)
    sender_email = parseaddr(from_address)[1]
    sender_domain = sender_email.rsplit("@", 1)[-1].lower() if "@" in sender_email else ""
    if expected_domain and sender_domain != expected_domain.lower():
        logger.warning(
            "email.delivery.invalid_from_domain",
            extra={
                "provider": "ses",
                "configured_domain": expected_domain,
                "from_domain": sender_domain or None,
                "recipient_count": len(payload.to),
            },
        )
        return "skipped"

    region = getattr(settings, "AWS_REGION", None)
    if not region:
        logger.warning(
            "email.delivery.missing_region",
            extra={"provider": "ses", "recipient_count": len(payload.to)},
        )
        return "skipped"

    client_kwargs: dict[str, str] = {"region_name": region}
    if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
        client_kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
        client_kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
        if settings.AWS_SESSION_TOKEN:
            client_kwargs["aws_session_token"] = settings.AWS_SESSION_TOKEN

    client = boto3.client("ses", **client_kwargs)

    send_kwargs = {
        "Source": from_address,
        "Destination": {"ToAddresses": list(payload.to)},
        "Message": {
            "Subject": {"Data": payload.subject, "Charset": "UTF-8"},
            "Body": {"Text": {"Data": payload.body, "Charset": "UTF-8"}},
        },
    }
    configuration_set = getattr(settings, "SES_CONFIGURATION_SET", None)
    if configuration_set:
        send_kwargs["ConfigurationSetName"] = configuration_set

    try:
        client.send_email(**send_kwargs)
    except (BotoCoreError, ClientError) as exc:
        logger.error(
            "email.delivery.failed",
            extra={"provider": "ses", "recipient_count": len(payload.to)},
            exc_info=exc,
        )
        return "error"

    logger.info(
        "email.delivery.sent",
        extra={"provider": "ses", "recipient_count": len(payload.to)},
    )
    return "sent"
