# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""统一通知底座（A7，精简版）。

区别于 CenkorMES 的 notify_dispatcher（深度绑定工单/工资等业务与短信/邮件渠道）：
这里只提供「站内 + WebSocket 实时 + 日志」三合一的最小投递，并预留外部渠道 hook。
- send(): 结构化投递一条通知，落内存收件箱 + 经 ws_hub 实时推送；
- notify_expiry_warning()/notify_audit_change(): 领域封装，供 A5 临期、A3 关键变更调用；
- external_hook: 可注入的外部渠道发送函数（短信/邮件/IM），默认 None，异常不影响主流程。
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Callable

from app.services.ws_hub import ws_hub

logger = logging.getLogger("cenkor-process.notify")

_recent: list[dict] = []
_MAX_RECENT = 200

# 可选外部渠道发送函数：签名 (payload: dict) -> None；抛错被吞，不影响站内/实时
external_hook: Callable[[dict], None] | None = None

LEVELS = ("info", "warning", "critical")


@dataclass
class Notification:
    event: str
    title: str
    body: str = ""
    level: str = "info"
    channel: str = "dashboard"
    data: dict = field(default_factory=dict)
    created_at: str = ""


def send(
    *,
    event: str,
    title: str,
    body: str = "",
    level: str = "info",
    channel: str = "dashboard",
    data: dict | None = None,
) -> dict:
    """投递一条通知：内存收件箱 + WebSocket 实时推送 + 日志。绝不抛出。"""
    if level not in LEVELS:
        level = "info"
    n = Notification(
        event=event,
        title=title,
        body=body,
        level=level,
        channel=channel,
        data=data or {},
        created_at=datetime.now().isoformat(timespec="seconds"),
    )
    payload = asdict(n)
    _recent.append(payload)
    if len(_recent) > _MAX_RECENT:
        del _recent[:-_MAX_RECENT]
    logger.info("[notify][%s][%s] %s | %s", level, event, title, body)
    try:
        ws_hub.publish({"type": "notification", **payload})
        ws_hub.publish_refresh([channel], reason=event)
        if external_hook is not None:
            external_hook(payload)
    except Exception as exc:  # noqa: BLE001 - 推送/外发失败不得影响业务
        logger.debug("notify push skipped: %s", exc)
    return payload


def recent(limit: int = 50) -> list[dict]:
    """返回最近的收件箱（倒序，最新在前）。"""
    return list(reversed(_recent[-limit:]))


def notify_expiry_warning(lots) -> dict | None:
    """A5 临期预警：把临期/过期批次聚合成一条 warning 通知。"""
    items = []
    for lot in lots:
        dte = getattr(lot, "expiry_at", None)
        items.append(
            {
                "lot_id": lot.id,
                "lot_no": lot.lot_no,
                "material_id": lot.material_id,
                "qty": str(lot.qty),
                "expiry_at": dte.isoformat() if isinstance(dte, datetime) else (str(dte) if dte else None),
            }
        )
    if not items:
        return None
    return send(
        event="expiry_warning",
        title=f"效期预警：{len(items)} 个批次临期/过期",
        body="存在临近或超过保质期的库存批次，请优先处理。",
        level="warning",
        channel="stock",
        data={"lots": items},
    )


def notify_audit_change(*, entity: str, action: str, entity_id: Any = None, reason: str = "", actor: str = "") -> dict:
    """A3 关键变更：投递一条变更通知（软删/发布/改版等），供实时看板感知。"""
    return send(
        event="audit_change",
        title=f"{entity} #{entity_id} {action}",
        body=reason,
        level="info",
        channel="audit",
        data={"entity": entity, "action": action, "entity_id": entity_id, "reason": reason, "actor": actor},
    )
