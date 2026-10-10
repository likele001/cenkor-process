# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""登录验证码开关与校验（开关来自 config，默认关闭以对齐 CenkorMES）。"""
from fastapi import HTTPException

from app.core.config import settings
from app.services.captcha import verify_captcha


def is_login_captcha_enabled() -> bool:
    return bool(settings.LOGIN_CAPTCHA_ENABLED)


def assert_login_captcha(captcha_id: str | None, captcha_code: str | None) -> None:
    if not is_login_captcha_enabled():
        return
    if not captcha_id or not captcha_code:
        raise HTTPException(status_code=400, detail="请输入验证码")
    if not verify_captcha(captcha_id, captcha_code):
        raise HTTPException(status_code=400, detail="验证码错误或已过期")