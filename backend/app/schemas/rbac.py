# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
from pydantic import BaseModel, Field


class PermissionOut(BaseModel):
    id: int
    code: str
    name: str


class RoleOut(BaseModel):
    id: int
    code: str
    name: str
    permissions: list[str] = []


class RoleIn(BaseModel):
    code: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1, max_length=64)
    permissions: list[str] = []


class RoleUpdateIn(BaseModel):
    name: str | None = Field(None, max_length=64)
    permissions: list[str] | None = None


class AssignRolesIn(BaseModel):
    role_codes: list[str] = []
