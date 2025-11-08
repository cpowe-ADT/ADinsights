from __future__ import annotations

import logging

from celery import shared_task

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

        logger.info(
            "Password reset email dispatched",
            extra={
                "token_id": token_id,
                "user_id": str(token.user_id),
                "tenant_id": tenant_id,
            },
        )
        return "sent"
