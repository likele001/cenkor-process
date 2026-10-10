# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.security import decode_token
from app.crud.rbac import get_user_permission_codes
from app.models.user import User
from app.services.audit import enable_audit

security_scheme = HTTPBearer(auto_error=False)


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _authenticate_api_key(request: Request) -> bool:
    """兼容旧 X-API-Key 鉴权；API_KEY 为空时（dev）放行。"""
    if not settings.API_KEY:
        return True
    return request.headers.get("X-API-Key", "") == settings.API_KEY


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    cred: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> User:
    """Bearer Token 优先，X-API-Key 双兼容；二者皆不具备则 401。"""
    if cred and cred.credentials:
        try:
            payload = decode_token(cred.credentials)
        except JWTError:
            raise HTTPException(status_code=401, detail="登录已失效")
        user_id = payload.get("sub")
        if user_id:
            user = db.get(User, int(user_id))
            if user and user.is_active:
                request.state.token_payload = payload
                enable_audit(db, user, _client_ip(request))
                return user
    if _authenticate_api_key(request):
        enable_audit(db, None, _client_ip(request))
        return None  # type: ignore[return-value]  # API-Key 通道无 user，视为匿名放行
    raise HTTPException(status_code=401, detail="未登录")


def get_current_permissions(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[str]:
    """解析当前用户权限码，请求级缓存；未登录（匿名 API-Key）返回空。"""
    if user is None:
        return []
    cached = getattr(request.state, "permission_codes", None)
    if cached is not None:
        return cached
    codes = get_user_permission_codes(db, user.id)
    request.state.permission_codes = codes
    return codes


def require_permissions(required: list[str]):
    """需同时具备全部权限码，否则 403。"""
    def _dep(user: User = Depends(get_current_user), codes: list[str] = Depends(get_current_permissions)) -> None:
        if user is None:
            raise HTTPException(status_code=401, detail="未登录")
        if not set(required).issubset(set(codes)):
            raise HTTPException(status_code=403, detail="无权限")
    return _dep


def require_any_permissions(required: list[str]):
    """具备任一权限码即可，否则 403。"""
    def _dep(user: User = Depends(get_current_user), codes: list[str] = Depends(get_current_permissions)) -> None:
        if user is None:
            raise HTTPException(status_code=401, detail="未登录")
        if not set(required) & set(codes):
            raise HTTPException(status_code=403, detail="无权限")
    return _dep


def require_write_permission(code: str):
    """写操作门控：GET/HEAD/OPTIONS 仅需登录；其余方法必须具备 `code` 权限，否则 403。

    供 router 级别统一挂载，避免逐端点标注；登录鉴权由路由级 get_current_user 保证。
    """
    _SAFE = {"GET", "HEAD", "OPTIONS"}
    def _dep(
        request: Request,
        user: User = Depends(get_current_user),
        codes: list[str] = Depends(get_current_permissions),
    ) -> None:
        if request.method in _SAFE:
            return
        if user is None:
            raise HTTPException(status_code=401, detail="未登录")
        if code not in codes:
            raise HTTPException(status_code=403, detail="无权限")
    return _dep