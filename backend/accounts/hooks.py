from __future__ import annotations

from urllib.parse import urlencode

from django.conf import settings
from django.utils import timezone

from .email import EmailPayload, send_email
from .models import Invitation


def _build_invite_url(token: str) -> str:
    base_url = settings.FRONTEND_BASE_URL.rstrip("/")
    query = urlencode({"token": token})
    return f"{base_url}/invite?{query}"


def send_invitation_email(invitation: Invitation, *, is_resend: bool = False) -> None:
    subject = "Your ADinsights invite"
    tenant_name = invitation.tenant.name
    expires_at = timezone.localtime(invitation.expires_at).isoformat()
    invite_url = _build_invite_url(invitation.token)
    resend_note = "This is a refreshed invite link.\n\n" if is_resend else ""
    body = (
        "Hello,\n\n"
        f"You have been invited to {tenant_name} in ADinsights.\n"
        f"{resend_note}"
        f"Accept your invite: {invite_url}\n\n"
        f"This link expires at {expires_at}.\n"
    )

    send_email(
        EmailPayload(
            subject=subject,
            body=body,
            to=[invitation.email],
        )
    )
