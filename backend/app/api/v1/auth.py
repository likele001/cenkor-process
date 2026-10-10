# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.core.response import ok
from app.core.security import create_access_token, token_expire_minutes
from app.crud.rbac import get_user_permission_codes, get_user_role_codes
from app.crud.user import authenticate, change_user_password
from app.schemas.auth import ChangePasswordIn, LoginIn, MeOut, ProfileUpdateIn
from app.services.login_captcha import assert_login_captcha
from app.services.login_ratelimit import is_login_blocked, record_login_failure, reset_login_failures

router = APIRouter()


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/login")
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)):
    ip = _client_ip(request)
    if is_login_blocked(ip):
        raise HTTPException(status_code=429, detail="登录失败次数过多，请稍后再试")
    assert_login_captcha(payload.captcha_id, payload.captcha_code)
    user = authenticate(db, payload.username, payload.password)
    if not user:
        record_login_failure(ip)
        raise HTTPException(status_code=400, detail="账号或密码错误")
    reset_login_failures(ip)
    minutes = token_expire_minutes(payload.remember_me)
    token = create_access_token(
        {"sub": str(user.id), "username": user.username},
        expires_minutes=minutes,
    )
    return ok(
        {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": minutes * 60,
            "remember_me": payload.remember_me,
        }
    )


@router.get("/me")
def me(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    roles = get_user_role_codes(db, user.id)
    permissions = get_user_permission_codes(db, user.id)
    return ok(
        MeOut(
            id=user.id,
            username=user.username,
            full_name=user.full_name,
            phone=user.phone,
            email=user.email,
            is_superuser=user.is_superuser,
            roles=roles,
            permissions=permissions,
        ).model_dump()
    )


@router.put("/profile")
def update_profile(
    payload: ProfileUpdateIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    allowed = {"full_name", "phone", "email"}
    changed = False
    for key, value in payload.model_dump().items():
        if key in allowed and value is not None:
            setattr(user, key, value)
            changed = True
    if not changed:
        raise HTTPException(status_code=400, detail="无修改内容")
    db.commit()
    db.refresh(user)
    return ok(MeOut(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        phone=user.phone,
        email=user.email,
        is_superuser=user.is_superuser,
        roles=get_user_role_codes(db, user.id),
        permissions=get_user_permission_codes(db, user.id),
    ).model_dump())


@router.put("/password")
def change_password_api(
    payload: ChangePasswordIn,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if not user:
        raise HTTPException(status_code=401, detail="未登录")
    try:
        change_user_password(db, user, payload.old_password, payload.new_password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()
    return ok()