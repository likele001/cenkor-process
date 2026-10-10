# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""审计日志查询（只读，需 audit.view）。审计表 append-only，无写端点。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_permissions
from app.core.response import ok
from app.models.audit import AuditLog

router = APIRouter()


@router.get("/audits")
def list_audits(
    entity: str | None = None,
    entity_id: int | None = None,
    action: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    _=Depends(require_permissions(["audit.view"])),
):
    stmt = select(AuditLog)
    if entity:
        stmt = stmt.where(AuditLog.entity == entity)
    if entity_id is not None:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    rows = db.scalars(stmt.order_by(AuditLog.id.desc()).limit(min(max(limit, 1), 500))).all()
    return ok([
        {
            "id": a.id,
            "entity": a.entity,
            "entity_id": a.entity_id,
            "action": a.action,
            "before": a.before,
            "after": a.after,
            "reason": a.reason,
            "actor_id": a.actor_id,
            "actor_name": a.actor_name,
            "ip": a.ip,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in rows
    ])
