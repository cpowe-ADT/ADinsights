from __future__ import annotations

import logging

from .models import Invitation

logger = logging.getLogger(__name__)


def send_invitation_email(invitation: Invitation) -> None:
    """Placeholder hook for sending invitation emails.

    Real deployments should replace this function with an integration that
    delivers the invite token via email or another delivery mechanism.
    """

    logger.info(
        "Invitation issued",
        extra={
            "tenant_id": str(invitation.tenant_id),
            "email": invitation.email,
            "token": invitation.token,
            "expires_at": invitation.expires_at.isoformat(),
        },
    )
