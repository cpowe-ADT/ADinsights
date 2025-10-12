from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..security import hash_password

router = APIRouter(prefix="/rbac", tags=["rbac"])


def _get_role(db: Session, role_id: int) -> models.Role:
    role = db.get(models.Role, role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    return role


def _get_tenant(db: Session, tenant_id: int) -> models.Tenant:
    tenant = db.get(models.Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return tenant


@router.post("/tenants", response_model=schemas.TenantRead, status_code=status.HTTP_201_CREATED)
def create_tenant(payload: schemas.TenantCreate, db: Session = Depends(get_db)):
    tenant = models.Tenant(name=payload.name)
    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    admin_role = db.query(models.Role).filter(models.Role.name == "admin").one_or_none()
    if admin_role is None:
        admin_role = models.Role(name="admin", description="Tenant administrator")
        db.add(admin_role)
        db.commit()
        db.refresh(admin_role)

    return tenant


@router.post("/tenants/{tenant_id}/users", response_model=schemas.UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    tenant_id: int,
    payload: schemas.UserCreate,
    db: Session = Depends(get_db),
):
    tenant = _get_tenant(db, tenant_id)
    role = None
    if payload.role_id is not None:
        role = _get_role(db, payload.role_id)

    user = models.User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        tenant=tenant,
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/roles", response_model=schemas.RoleRead, status_code=status.HTTP_201_CREATED)
def create_role(payload: schemas.RoleCreate, db: Session = Depends(get_db)):
    role = models.Role(name=payload.name, description=payload.description)
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


@router.post("/users/{user_id}/role/{role_id}", response_model=schemas.UserRead)
def assign_role(user_id: int, role_id: int, db: Session = Depends(get_db)):
    user = db.get(models.User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    role = _get_role(db, role_id)
    user.role = role
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
