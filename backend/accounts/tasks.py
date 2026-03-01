from __future__ import annotations

import logging
from urllib.parse import urlencode

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .email import EmailPayload, send_email
from .models import PasswordResetToken
from .tenant_context import tenant_context

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def send_password_reset_email(self, token_id: str, raw_token: str) -> str:
    """Deliver password reset instructions for the given token."""

    try:
        token = PasswordResetToken.objects.select_related("user", "user__tenant").get(
            id=token_id
        )
    except PasswordResetToken.DoesNotExist:
        logger.warning("Password reset token missing", extra={"token_id": token_id})
        return "missing"

    tenant_id = str(token.user.tenant_id)

    with tenant_context(tenant_id):
        if not token.is_valid(raw_token):
            logger.info(
                "Password reset token invalid",
                extra={
                    "token_id": token_id,
                    "user_id": str(token.user_id),
                    "tenant_id": tenant_id,
                },
            )
            return "invalid"

        base_url = settings.FRONTEND_BASE_URL.rstrip("/")
        query = urlencode({"token": raw_token})
        reset_url = f"{base_url}/password-reset?{query}"
        expires_at = timezone.localtime(token.expires_at).isoformat()
        body = (
            "Hello,\n\n"
            "A request was received to reset your ADinsights password.\n"
            f"Reset your password: {reset_url}\n\n"
            f"This link expires at {expires_at}.\n"
            "If you did not request this, you can ignore this email.\n"
        )

        send_email(
            EmailPayload(
                subject="Reset your ADinsights password",
                body=body,
                to=[token.user.email],
            )
        )
        return "sent"
