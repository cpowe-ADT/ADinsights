from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..security import OAuthProvider, TokenEncryptor, compute_expiry, generate_state

router = APIRouter(prefix="/oauth", tags=["oauth"])

token_encryptor = TokenEncryptor()
oauth_provider = OAuthProvider()


@router.get("/{platform}/authorize", response_model=schemas.OAuthAuthorizationUrl)
async def authorize(platform: str, tenant_id: int) -> schemas.OAuthAuthorizationUrl:
    state = generate_state()
    scopes = [
        "public_profile",
        "ads_read",
    ]
    if platform == "google_ads":
        scopes = [
            "https://www.googleapis.com/auth/adwords",
            "openid",
            "email",
        ]

    url = oauth_provider.build_authorization_url(platform, state, scopes)
    return schemas.OAuthAuthorizationUrl(authorization_url=url)


@router.post("/{platform}/callback", response_model=schemas.TokenResponse)
async def oauth_callback(
    platform: str,
    payload: schemas.OAuthCallbackPayload,
    tenant_id: int,
    db: Session = Depends(get_db),
) -> schemas.TokenResponse:
    tenant = db.get(models.Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    token_data = await oauth_provider.exchange_code_for_token(platform, payload.code)
    refresh_token = token_data.get("refresh_token")
    if refresh_token is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Refresh token missing")

    expires_in = token_data.get("expires_in")
    access_token = token_data.get("access_token")
    scope = token_data.get("scope")
    expiry: datetime | None = compute_expiry(expires_in) if expires_in else None

    credential = models.PlatformCredential(
        tenant=tenant,
        platform=platform,
        account_identifier=token_data.get("user_id"),
        access_token=access_token,
        refresh_token_encrypted=token_encryptor.encrypt(refresh_token),
        expires_at=expiry,
        scope=scope if isinstance(scope, str) else " ".join(scope or []),
    )

    db.add(credential)
    db.commit()
    db.refresh(credential)

    return schemas.TokenResponse(
        platform=platform,
        tenant_id=tenant.id,
        expires_at=credential.expires_at,
        scope=credential.scope,
    )
