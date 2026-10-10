# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""通知中心 & 预警（A7）：站内收件箱、临期预警扫描并推送、测试投递。

与 A5 联动：/alerts/expiry 扫描临期/过期批次并经统一通知底座推送；
与 A3 联动：关键变更可用 notify.notify_audit_change 走同一通道（由各端点调用）。
"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import require_permissions
from app.core.response import ok
from app.models.proc import StockLot
from app.services import notify, stock_service

router = APIRouter()


@router.get("/notifications/recent")
def list_notifications(limit: int = 50):
    """最近站内通知（倒序）。"""
    return ok(notify.recent(limit=limit))


@router.get("/alerts/expiry")
def expiry_alerts(db: Session = Depends(get_db)):
    """扫描未删除批次中的临期/过期项，聚合为一条 warning 通知并推送。"""
    lots = db.scalars(select(StockLot).where(StockLot.is_deleted.is_(False))).all()
    flagged = [lot for lot in lots if stock_service.is_lot_expired(lot) or stock_service.is_lot_near_expiry(lot)]
    payload = notify.notify_expiry_warning(flagged)
    items = [
        {
            "lot_id": lot.id,
            "lot_no": lot.lot_no,
            "material_id": lot.material_id,
            "qty": str(lot.qty),
            "expiry_at": lot.expiry_at.isoformat() if lot.expiry_at else None,
            "days_to_expiry": stock_service.days_to_expiry(lot),
            "expired": stock_service.is_lot_expired(lot),
            "near_expiry": stock_service.is_lot_near_expiry(lot),
        }
        for lot in flagged
    ]
    return ok({"count": len(items), "lots": items, "notification": payload})


@router.post("/notifications/test")
def push_test(title: str = "测试通知", body: str = "", level: str = "info", channel: str = "dashboard", _=Depends(require_permissions(["setting.manage"]))):
    """向所有已连接客户端投递一条测试通知（需 setting.manage）。"""
    payload = notify.send(event="test", title=title, body=body, level=level, channel=channel)
    return ok(payload)
