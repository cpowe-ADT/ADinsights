from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class RoleBase(BaseModel):
    name: str
    description: Optional[str] = None


class RoleCreate(RoleBase):
    pass


class RoleRead(RoleBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class TenantBase(BaseModel):
    name: str


class TenantCreate(TenantBase):
    pass


class TenantRead(TenantBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None


class UserCreate(UserBase):
    password: str
    role_id: Optional[int] = None


class UserRead(UserBase):
    id: int
    tenant_id: int
    role: Optional[RoleRead]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class PlatformCredentialBase(BaseModel):
    platform: str
    account_identifier: Optional[str] = None
    scope: Optional[str] = None


class PlatformCredentialCreate(PlatformCredentialBase):
    authorization_code: str


class PlatformCredentialRead(PlatformCredentialBase):
    id: int
    tenant_id: int
    expires_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class OAuthAuthorizationUrl(BaseModel):
    authorization_url: str


class OAuthCallbackPayload(BaseModel):
    code: str
    state: str


class TokenResponse(BaseModel):
    platform: str
    tenant_id: int
    expires_at: Optional[datetime]
    scope: Optional[str]
