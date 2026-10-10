# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)
    captcha_id: str = Field("", max_length=64)
    captcha_code: str = Field("", max_length=8)
    remember_me: bool = False


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 0
    remember_me: bool = False


class MeOut(BaseModel):
    id: int
    username: str
    full_name: str | None
    phone: str | None = None
    email: str | None = None
    is_superuser: bool
    roles: list[str]
    permissions: list[str]


class CaptchaOut(BaseModel):
    enabled: bool
    captcha_id: str | None = None
    image_base64: str | None = None
    expires_in: int | None = None


class PublicConfigOut(BaseModel):
    company_name: str
    logo_url: str
    login_captcha_enabled: bool
    session_expire_minutes: int
    remember_me_expire_minutes: int


class ProfileUpdateIn(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    email: str | None = None


class ChangePasswordIn(BaseModel):
    old_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=1, max_length=128)