# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""自动审计：通过 SQLAlchemy Session 事件捕获所有业务对象的增/改/删，写入 audit_logs。

设计要点：
- 仅当 Session 被显式启用（请求路径经 get_current_user → enable_audit）才记录，
  避免演示种子 / 后台任务 / 测试噪声。actor 取自 Session.info（同请求共享，规避线程池 contextvar 隔离）。
- before_flush 收集变更（get_history 提供旧/新值），after_flush 用 Core insert 直接写审计行
  （不触发 ORM 事件，避免递归；此时新建对象 id 已回填）。
- 仅审计业务实体，跳过 AuditLog 自身。
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import get_history

from app.models.audit import AuditLog

_SKIP_COLS = {"created_at", "updated_at"}


def _jsonval(v):
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    if isinstance(v, (list, tuple)):
        return [_jsonval(x) for x in v]
    if isinstance(v, dict):
        return {k: _jsonval(x) for k, x in v.items()}
    return str(v)


def _column_keys(obj) -> list[str]:
    mapper = inspect(type(obj)).mapper
    return [a.key for a in mapper.column_attrs]


def _snapshot(obj) -> dict:
    out = {}
    for key in _column_keys(obj):
        if key in _SKIP_COLS:
            continue
        out[key] = _jsonval(getattr(obj, key, None))
    return out


def _changes(obj) -> tuple[dict, dict]:
    before: dict = {}
    after: dict = {}
    for key in _column_keys(obj):
        if key in _SKIP_COLS:
            continue
        hist = get_history(obj, key)
        if hist.has_changes():
            before[key] = _jsonval(hist.deleted[0] if hist.deleted else None)
            after[key] = _jsonval(hist.added[0] if hist.added else None)
    return before, after


def _auditable(obj) -> bool:
    return not isinstance(obj, AuditLog)


@event.listens_for(Session, "before_flush")
def _collect(session: Session, flush_context, instances):
    if not session.info.get("audit_enabled"):
        session.info["_audit_pending"] = []
        return
    pending: list[dict] = []
    for obj in session.new:
        if _auditable(obj):
            pending.append({"action": "create", "obj": obj})
    for obj in session.dirty:
        if not _auditable(obj):
            continue
        before, after = _changes(obj)
        if before or after:
            pending.append({"action": "update", "obj": obj, "before": before, "after": after})
    for obj in session.deleted:
        if _auditable(obj):
            pending.append({"action": "delete", "obj": obj, "before": _snapshot(obj)})
    session.info["_audit_pending"] = pending


@event.listens_for(Session, "after_flush")
def _write(session: Session, flush_context):
    pending = session.info.get("_audit_pending") or []
    session.info["_audit_pending"] = []
    if not pending:
        return
    actor_id = session.info.get("audit_actor_id")
    actor_name = session.info.get("audit_actor_name")
    ip = session.info.get("audit_ip")
    reason = session.info.pop("audit_reason", None)
    now = datetime.now()
    rows = []
    for p in pending:
        obj = p["obj"]
        entity = getattr(obj, "__tablename__", obj.__class__.__name__)
        action = p["action"]
        if action == "create":
            before, after = None, _snapshot(obj)
        elif action == "delete":
            before, after = p.get("before"), None
        else:
            before, after = p.get("before"), p.get("after")
        rows.append(
            {
                "entity": entity,
                "entity_id": obj.id,
                "action": action,
                "before": before,
                "after": after,
                "reason": reason,
                "actor_id": actor_id,
                "actor_name": actor_name,
                "ip": ip,
                "created_at": now,
            }
        )
    session.connection().execute(AuditLog.__table__.insert(), rows)


# ---------------- 对外 helper ----------------

def enable_audit(db: Session, user, ip: str | None = None) -> None:
    """在请求作用域 Session 上开启审计并绑定操作人（由 get_current_user 调用）。"""
    db.info["audit_enabled"] = True
    db.info["audit_actor_id"] = getattr(user, "id", None)
    db.info["audit_actor_name"] = getattr(user, "username", None)
    db.info["audit_ip"] = ip


def set_reason(db: Session, reason: str | None) -> None:
    if reason:
        db.info["audit_reason"] = reason


def soft_delete(db: Session, obj, reason: str | None = None) -> None:
    """逻辑删除：置 is_deleted/deleted_at/deleted_by，审计由事件自动记录（action=update）。"""
    reason = reason or "逻辑删除"
    set_reason(db, reason)
    obj.is_deleted = True
    obj.deleted_at = datetime.now()
    obj.deleted_by = db.info.get("audit_actor_id")
    db.commit()
    # A3 关键变更 → 统一通知底座（惰性导入 + 吞异常，绝不影响审计主流程）
    try:
        from app.services import notify
        entity = getattr(type(obj), "__tablename__", type(obj).__name__)
        notify.notify_audit_change(
            entity=entity, action="delete", entity_id=getattr(obj, "id", None),
            reason=reason, actor=db.info.get("audit_actor_name") or "",
        )
    except Exception:  # noqa: BLE001
        pass
