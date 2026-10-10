# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""演示扩展路由：验证扩展宿主热挂载 / 门控 / 迁移。

约定：扩展在自己的 router.py 里暴露一个 `router`（fastapi.APIRouter）对象；
宿主会把它挂到 `/api/extensions/{key}`，并叠加 get_current_user + require_extension 门控。
"""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.response import ok

router = APIRouter()


@router.get("/ping")
def ping():
    return ok({"ext": "demo_hello", "pong": True})


@router.get("/note-count")
def note_count(db: Session = Depends(get_db)):
    """读取扩展自建表 ext_demo_hello_note 的行数，验证幂等迁移已执行。"""
    n = db.execute(text("SELECT COUNT(*) FROM ext_demo_hello_note")).scalar()
    return ok({"count": int(n or 0)})
