# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""RBAC 管理接口：权限点/角色维护、用户角色分配。写操作按 role.manage / user.manage 门控。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_permissions
from app.core.response import ok
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User

router = APIRouter()

_BUILTIN_ROLES = {"admin", "qc", "operator", "viewer"}


class RoleIn(BaseModel):
    code: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1, max_length=64)


class RolePermsIn(BaseModel):
    permission_codes: list[str] = Field(default_factory=list)


class UserRolesIn(BaseModel):
    role_codes: list[str] = Field(default_factory=list)


@router.get("/rbac/permissions")
def list_permissions(db: Session = Depends(get_db)):
    rows = db.scalars(select(Permission).order_by(Permission.code)).all()
    return ok([{"id": p.id, "code": p.code, "name": p.name} for p in rows])


@router.get("/rbac/roles")
def list_roles(db: Session = Depends(get_db)):
    rows = db.scalars(select(Role).order_by(Role.code)).all()
    return ok([
        {
            "id": r.id,
            "code": r.code,
            "name": r.name,
            "permissions": sorted(p.code for p in r.permissions),
        }
        for r in rows
    ])


@router.post("/rbac/roles")
def create_role(payload: RoleIn, db: Session = Depends(get_db), _=Depends(require_permissions(["role.manage"]))):
    if db.scalar(select(Role.id).where(Role.code == payload.code)):
        raise HTTPException(status_code=400, detail="角色编码已存在")
    role = Role(code=payload.code, name=payload.name)
    db.add(role)
    db.commit()
    db.refresh(role)
    return ok({"id": role.id, "code": role.code, "name": role.name})


@router.put("/rbac/roles/{role_id}/permissions")
def set_role_permissions(role_id: int, payload: RolePermsIn, db: Session = Depends(get_db), _=Depends(require_permissions(["role.manage"]))):
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    perms = db.scalars(select(Permission).where(Permission.code.in_(payload.permission_codes))).all()
    role.permissions = list(perms)
    db.commit()
    return ok({"id": role.id, "permissions": sorted(p.code for p in role.permissions)})


@router.delete("/rbac/roles/{role_id}")
def delete_role(role_id: int, db: Session = Depends(get_db), _=Depends(require_permissions(["role.manage"]))):
    role = db.get(Role, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    if role.code in _BUILTIN_ROLES:
        raise HTTPException(status_code=400, detail="内置角色不可删除")
    db.delete(role)
    db.commit()
    return ok()


@router.put("/rbac/users/{user_id}/roles")
def assign_user_roles(user_id: int, payload: UserRolesIn, db: Session = Depends(get_db), _=Depends(require_permissions(["user.manage"]))):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    roles = db.scalars(select(Role).where(Role.code.in_(payload.role_codes))).all()
    user.roles = list(roles)
    db.commit()
    return ok({"id": user.id, "roles": sorted(r.code for r in user.roles)})
