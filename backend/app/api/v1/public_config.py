# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""免登录的公开配置：登录页与前端品牌区要用，必须在拿到 token 之前可读。"""
from fastapi import APIRouter

from app.core.config import settings
from app.core.response import ok
from app.services.login_captcha import is_login_captcha_enabled

router = APIRouter()


@router.get("")
def public_config_api():
    return ok(
        {
            "company_name": settings.COMPANY_NAME or "",
            "logo_url": settings.LOGO_URL or "",
            "login_captcha_enabled": is_login_captcha_enabled(),
            "session_expire_minutes": int(settings.ACCESS_TOKEN_EXPIRE_MINUTES),
            "remember_me_expire_minutes": int(settings.REMEMBER_ME_EXPIRE_MINUTES),
        }
    )