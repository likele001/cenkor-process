# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""批次库存服务：FEFO 出库、批次收货、谱系查询。

FEFO（先到期先出）：仅取 status='released' 且 qty>0 的批次，
按 expiry_at 升序（无有效期排最后）。所有扣减在调用方事务内完成。
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import BizError
from app.models.proc import LotGenealogy, StockLot


def _now() -> datetime:
    return datetime.now()


def is_lot_expired(lot: StockLot, now: datetime | None = None) -> bool:
    """已过期：设定了效期且早于当前时间。"""
    now = now or _now()
    return bool(lot.expiry_at and lot.expiry_at < now)


def days_to_expiry(lot: StockLot, now: datetime | None = None) -> int | None:
    """剩余效期天数（向下取整）；无有效期返回 None；已过期为负数。"""
    if not lot.expiry_at:
        return None
    now = now or _now()
    return (lot.expiry_at.date() - now.date()).days


def is_lot_near_expiry(lot: StockLot, now: datetime | None = None) -> bool:
    """临期：有有效期、未过期、且剩余天数 < EXPIRY_WARN_DAYS。"""
    d = days_to_expiry(lot, now)
    return d is not None and 0 <= d < settings.EXPIRY_WARN_DAYS


def assert_lot_dispensable(lot: StockLot, now: datetime | None = None) -> None:
    """投料/领料拦截：非 released 或已过期的批次禁止投入使用（A5）。"""
    now = now or _now()
    if lot.status != "released":
        raise BizError(409, f"未放行批次 {lot.lot_no}（状态 {lot.status}）禁止投料")
    if is_lot_expired(lot, now):
        raise BizError(409, f"过期批次 {lot.lot_no}（效期 {lot.expiry_at:%Y-%m-%d}）禁止投料")


def fefo_plan(db: Session, warehouse_id: int, material_id: int, need_qty: Decimal) -> dict:
    """预演 FEFO 出库方案，不改动库存。

    仅取 status='released'、qty>0 且未过期的批次（过期批次不得参与 FEFO，A5）。
    """
    if need_qty <= 0:
        raise BizError(400, "需求数量必须大于 0")

    now = _now()
    lots = db.scalars(
        select(StockLot)
        .where(
            StockLot.warehouse_id == warehouse_id,
            StockLot.material_id == material_id,
            StockLot.status == "released",
            StockLot.qty > 0,
            or_(StockLot.expiry_at.is_(None), StockLot.expiry_at >= now),
        )
        .order_by(StockLot.expiry_at.is_(None), StockLot.expiry_at.asc(), StockLot.id.asc())
    ).all()

    plan: list[dict] = []
    remaining = need_qty
    for lot in lots:
        if remaining <= 0:
            break
        take = min(lot.qty, remaining)
        plan.append(
            {
                "lot_id": lot.id,
                "lot_no": lot.lot_no,
                "expiry_at": lot.expiry_at,
                "take_qty": take,
            }
        )
        remaining -= take

    return {
        "warehouse_id": warehouse_id,
        "material_id": material_id,
        "need_qty": need_qty,
        "enough": remaining <= 0,
        "plan": plan,
    }


def fefo_issue(db: Session, warehouse_id: int, material_id: int, need_qty: Decimal) -> list[dict]:
    """按 FEFO 实际扣减库存（调用方负责事务提交/回滚）。

    返回 [{lot_id, lot_no, take_qty}]。库存不足时抛 BizError，由调用方回滚。
    加锁顺序：按 lot id 升序 FOR UPDATE，避免并发死锁（§3 闸2）。
    负库存策略（§3 闸5）：settings.ALLOW_NEGATIVE_STOCK 为真时放行缺口（挂末批），否则严格阻断。
    """
    allow_negative = settings.ALLOW_NEGATIVE_STOCK
    preview = fefo_plan(db, warehouse_id, material_id, need_qty)
    if not preview["enough"] and not allow_negative:
        raise BizError(409, f"库存不足：物料 {material_id} 在仓库 {warehouse_id} 可用量不够")

    lot_ids = sorted(p["lot_id"] for p in preview["plan"])
    locked = {
        lot.id: lot
        for lot in db.scalars(
            select(StockLot).where(StockLot.id.in_(lot_ids)).order_by(StockLot.id.asc()).with_for_update()
        ).all()
    }

    consumed: list[dict] = []
    remaining = need_qty
    for item in preview["plan"]:
        lot = locked[item["lot_id"]]
        take = item["take_qty"]
        if lot.qty < take and not allow_negative:
            raise BizError(409, f"库存不足：批次 {lot.lot_no} 可用 {lot.qty} < 需求 {take}")
        lot.qty = lot.qty - take
        if lot.qty <= 0:
            lot.status = "consumed"
        remaining -= take
        consumed.append({"lot_id": lot.id, "lot_no": lot.lot_no, "take_qty": take})

    if remaining > 0 and allow_negative:
        if not preview["plan"]:
            raise BizError(409, "该物料无可扣批次，且不允许凭空产生负库存")
        last = locked[preview["plan"][-1]["lot_id"]]
        last.qty = last.qty - remaining
        if last.qty <= 0:
            last.status = "consumed"
        consumed.append({"lot_id": last.id, "lot_no": last.lot_no, "take_qty": remaining, "negative": True})

    return consumed


def receive_lot(db: Session, payload) -> StockLot:
    """批次收货入库（幂等键：warehouse + material + lot_no）。"""
    exists = db.scalar(
        select(StockLot).where(
            StockLot.warehouse_id == payload.warehouse_id,
            StockLot.material_id == payload.material_id,
            StockLot.lot_no == payload.lot_no,
        )
    )
    if exists:
        exists.qty = exists.qty + payload.qty
        if payload.expiry_at:
            exists.expiry_at = payload.expiry_at
        if payload.status:
            exists.status = payload.status
        return exists

    lot = StockLot(
        warehouse_id=payload.warehouse_id,
        material_id=payload.material_id,
        lot_no=payload.lot_no,
        qty=payload.qty,
        uom_id=payload.uom_id,
        produced_at=payload.produced_at,
        expiry_at=payload.expiry_at,
        status=payload.status,
        supplier_lot_no=payload.supplier_lot_no,
    )
    db.add(lot)
    db.flush()
    return lot


def genealogy(db: Session, lot_id: int) -> dict:
    """查某批次的上下游谱系（父/子）。"""
    parents = db.scalars(select(LotGenealogy).where(LotGenealogy.child_lot_id == lot_id)).all()
    children = db.scalars(select(LotGenealogy).where(LotGenealogy.parent_lot_id == lot_id)).all()
    return {
        "lot_id": lot_id,
        "parents": [
            {"lot_id": g.parent_lot_id, "op_type": g.op_type, "amount": g.amount} for g in parents
        ],
        "children": [
            {"lot_id": g.child_lot_id, "op_type": g.op_type, "amount": g.amount} for g in children
        ],
    }


def _lock_lots(db: Session, lot_ids: list[int]) -> list[StockLot]:
    """按 lot id 升序 FOR UPDATE 加锁，防并发死锁（§3 闸2）。"""
    ids = sorted(set(lot_ids))
    return list(
        db.scalars(
            select(StockLot).where(StockLot.id.in_(ids)).order_by(StockLot.id.asc()).with_for_update()
        ).all()
    )


def merge_lots(db: Session, payload) -> dict:
    """合批：多个父批全量并入 1 个新子批，谱系 op_type=merge（§10）。

    约束：同物料 / 同仓库 / 同单位；子批效期取父批最早效期（保守，避免 FEFO 误判）。
    """
    ids = list(payload.lot_ids)
    if len(set(ids)) < 2:
        raise BizError(400, "合批至少需要 2 个批次")

    lots = _lock_lots(db, ids)
    if len(lots) != len(set(ids)):
        raise BizError(409, "存在无效的库存批次")
    if len({l.material_id for l in lots}) != 1:
        raise BizError(400, "合批要求所有批次为同一物料")
    if len({l.warehouse_id for l in lots}) != 1:
        raise BizError(400, "合批要求所有批次在同一仓库")
    if len({l.uom_id for l in lots}) != 1:
        raise BizError(400, "合批要求所有批次单位一致")

    parents = [(l.id, l.lot_no, Decimal(l.qty)) for l in lots]
    total = sum((q for _, _, q in parents), Decimal("0"))
    if total <= 0:
        raise BizError(400, "合批总量为 0，无可合并库存")

    first = lots[0]
    expiries = [l.expiry_at for l in lots if l.expiry_at]
    child = StockLot(
        warehouse_id=first.warehouse_id,
        material_id=first.material_id,
        lot_no=payload.lot_no or f"MG-{first.id}-{datetime.now():%Y%m%d%H%M%S}",
        qty=total,
        uom_id=first.uom_id,
        produced_at=datetime.now(),
        expiry_at=min(expiries) if expiries else None,
        status=payload.status or "released",
    )
    db.add(child)
    db.flush()

    for lot in lots:
        lot.qty = Decimal("0")
        lot.status = "consumed"

    for lot_id, _, amount in parents:
        db.add(LotGenealogy(parent_lot_id=lot_id, child_lot_id=child.id, amount=amount, op_type="merge"))

    db.commit()
    return {
        "child_lot_id": child.id,
        "child_lot_no": child.lot_no,
        "merged_qty": total,
        "expiry_at": child.expiry_at,
        "parents": [{"lot_id": i, "lot_no": n, "amount": str(a)} for i, n, a in parents],
    }


def split_lot(db: Session, lot_id: int, payload) -> dict:
    """拆批：1 个父批按 parts 拆为多个子批，谱系 op_type=split（§10）。

    父批余量保留；拆分总量超过可用量时，严格模式下阻断（可放开 ALLOW_NEGATIVE_STOCK）。
    """
    lot = db.get(StockLot, lot_id, with_for_update=True)
    if not lot:
        raise BizError(404, "批次不存在")
    if not payload.parts:
        raise BizError(400, "拆分明细不能为空")

    total = sum((Decimal(p.qty) for p in payload.parts), Decimal("0"))
    if total <= 0:
        raise BizError(400, "拆分总量必须大于 0")
    if total > lot.qty and not settings.ALLOW_NEGATIVE_STOCK:
        raise BizError(409, f"拆分总量 {total} 超过批次 {lot.lot_no} 可用量 {lot.qty}")

    stamp = datetime.now().strftime("%m%d%H%M%S")
    children = []
    for idx, part in enumerate(payload.parts, start=1):
        if Decimal(part.qty) <= 0:
            raise BizError(400, "拆分数量必须大于 0")
        child = StockLot(
            warehouse_id=lot.warehouse_id,
            material_id=lot.material_id,
            lot_no=part.lot_no or f"{lot.lot_no}-S{stamp}{idx}",
            qty=part.qty,
            uom_id=lot.uom_id,
            produced_at=lot.produced_at,
            expiry_at=part.expiry_at or lot.expiry_at,
            status=payload.status or lot.status,
            source_batch_id=lot.source_batch_id,
        )
        db.add(child)
        db.flush()
        db.add(LotGenealogy(parent_lot_id=lot.id, child_lot_id=child.id, amount=part.qty, op_type="split"))
        children.append(child)

    lot.qty = lot.qty - total
    if lot.qty <= 0:
        lot.status = "consumed"

    db.commit()
    return {
        "parent_lot_id": lot.id,
        "parent_lot_no": lot.lot_no,
        "parent_remaining": str(lot.qty),
        "children": [{"lot_id": c.id, "lot_no": c.lot_no, "qty": str(c.qty)} for c in children],
    }