# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
from fastapi import APIRouter, HTTPException

from app.core.response import ok
from app.services.captcha import create_captcha
from app.services.login_captcha import is_login_captcha_enabled

router = APIRouter()


@router.get("")
def get_captcha_api():
    """获取登录验证码（所有登录入口共用）。关闭时返回 enabled=False。"""
    if not is_login_captcha_enabled():
        return ok({"enabled": False})
    try:
        captcha_id, image_base64, expires_in = create_captcha()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"验证码生成失败，请确认已安装 Pillow：{e}")
    return ok(
        {
            "enabled": True,
            "captcha_id": captcha_id,
            "image_base64": image_base64,
            "expires_in": int(expires_in),
        }
    )