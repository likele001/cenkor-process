# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""批次服务：创建批次 + 批次产出入账（单事务原子）。

对齐计划 §9：
  - 扣原料批 / 产出批入库 / 副产品入库 / 谱系关联 / 工序推进 —— 同一 DB 事务；
  - 所有库存写前 FOR UPDATE，加锁按 lot id 升序，防并发死锁；
  - 称重超差默认阻断（严格模式），可显式放开为「记录 deviated 后继续」；
  - 库存不足明确报错，绝不静默改数。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import BizError
from app.models.proc import (
    Batch,
    BatchOperation,
    DispenseRecord,
    LotGenealogy,
    Material,
    Recipe,
    StockLot,
)
from app.services import recipe_service
from app.services.stock_service import assert_lot_dispensable, fefo_plan

HUNDRED = Decimal("100")


def next_batch_no(db: Session, when: datetime | None = None) -> str:
    when = when or datetime.now()
    prefix = f"PB{when:%Y%m%d}"
    count = db.scalar(
        select(func.count(Batch.id)).where(Batch.batch_no.like(f"{prefix}%"))
    ) or 0
    return f"{prefix}{count + 1:04d}"


def create_batch(db: Session, payload) -> Batch:
    recipe = db.get(Recipe, payload.recipe_id)
    if not recipe:
        raise BizError(404, "配方不存在")
    if recipe.status != "released":
        raise BizError(400, f"配方 {recipe.code} 未发布，不能投产")

    uom_id = payload.uom_id or recipe.base_uom_id
    batch = Batch(
        batch_no=next_batch_no(db),
        recipe_id=recipe.id,
        recipe_version=recipe.version,
        recipe_snapshot=recipe_service.recipe_snapshot(db, recipe),
        product_material_id=recipe.product_material_id,
        planned_qty=payload.planned_qty,
        uom_id=uom_id,
        planned_date=payload.planned_date,
        status="released",
        note=payload.note,
    )
    db.add(batch)
    db.flush()

    op = BatchOperation(
        batch_id=batch.id,
        seq=1,
        name="配料",
        op_type="dispense",
        planned_qty=payload.planned_qty,
        uom_id=uom_id,
        status="pending",
    )
    db.add(op)
    db.commit()
    db.refresh(batch)
    return batch


def _tol_ok(planned: Decimal, actual: Decimal, tol_pct: Decimal) -> bool:
    if planned <= 0:
        return True
    diff = abs(actual - planned) / planned * HUNDRED
    return diff <= tol_pct


def _resolve_allocations(db: Session, dispenses, warehouse_id: int | None, auto_issue: bool):
    """把配料行解析为 (dispense, lot_id, take_qty) 分配清单，不写库。"""
    allocations: list[tuple] = []
    for d in dispenses:
        if d.lot_id:
            allocations.append((d, d.lot_id, d.actual_qty))
        elif auto_issue and warehouse_id:
            preview = fefo_plan(db, warehouse_id, d.material_id, d.actual_qty)
            if not preview["enough"] and not settings.ALLOW_NEGATIVE_STOCK:
                raise BizError(409, f"库存不足：物料 {d.material_id} 在仓库 {warehouse_id} 可用量不够")
            for item in preview["plan"]:
                allocations.append((d, item["lot_id"], item["take_qty"]))
            # 放开负库存时，把缺口挂到末批，避免「产出多、投入少」的静默不一致
            shortfall = d.actual_qty - sum((item["take_qty"] for item in preview["plan"]), Decimal("0"))
            if shortfall > 0 and settings.ALLOW_NEGATIVE_STOCK:
                if not preview["plan"]:
                    raise BizError(409, "该物料无可扣批次，且不允许凭空产生负库存")
                allocations.append((d, preview["plan"][-1]["lot_id"], shortfall))
        else:
            raise BizError(400, f"配料行 material_id={d.material_id} 未指定批次，且未开启自动发料")
    return allocations


def complete_batch(db: Session, batch_id: int, payload) -> dict:
    try:
        batch = db.get(Batch, batch_id, with_for_update=True)
        if not batch:
            raise BizError(404, "批次不存在")
        if batch.status in ("completed", "closed"):
            raise BizError(409, f"批次已 {batch.status}，不可重复过账")

        # ⓪ 配方快照一致性：实投物料须落在发布快照内，防止按「改动后的配方」过账（§3 闸4）
        if batch.recipe_snapshot and payload.dispenses and not payload.allow_unplanned:
            planned_materials = {int(c["material_id"]) for c in batch.recipe_snapshot.get("components", [])}
            unplanned = sorted({d.material_id for d in payload.dispenses if d.material_id not in planned_materials})
            if unplanned:
                raise BizError(409, f"实投含快照外物料 {unplanned}，已阻断（可放开 allow_unplanned 记录后继续）")

        # ① 称重容差校验
        deviations = []
        for d in payload.dispenses:
            if not _tol_ok(d.planned_qty, d.actual_qty, d.tol_pct):
                deviations.append(
                    {
                        "material_id": d.material_id,
                        "planned_qty": str(d.planned_qty),
                        "actual_qty": str(d.actual_qty),
                        "tol_pct": str(d.tol_pct),
                    }
                )
        if deviations and not payload.allow_deviation:
            raise BizError(409, f"称重超差 {len(deviations)} 项，已阻断过账（可放开 allow_deviation 记录后继续）")

        # ② 解析分配 + 按 lot id 升序加锁
        allocations = _resolve_allocations(db, payload.dispenses, payload.warehouse_id, payload.auto_issue)
        lot_ids = sorted({lot_id for _, lot_id, _ in allocations})
        locked = {
            lot.id: lot
            for lot in db.scalars(
                select(StockLot).where(StockLot.id.in_(lot_ids)).order_by(StockLot.id.asc()).with_for_update()
            ).all()
        }
        if len(locked) != len(lot_ids):
            raise BizError(409, "存在无效的库存批次")

        # ③ 扣减原料批（投料拦截：过期/未放行批次禁止使用；不足即回滚）
        for _, lot_id, take in allocations:
            lot = locked[lot_id]
            assert_lot_dispensable(lot)
            if lot.qty < take and not settings.ALLOW_NEGATIVE_STOCK:
                raise BizError(409, f"库存不足：批次 {lot.lot_no} 可用 {lot.qty} < 需扣 {take}")
            lot.qty = lot.qty - take
            if lot.qty <= 0:
                lot.status = "consumed"

        # ④ 产成品批入库（效期由物料保质期推算）
        product = db.get(Material, batch.product_material_id)
        now = datetime.now()
        out_warehouse = payload.warehouse_id or (locked[lot_ids[0]].warehouse_id if lot_ids else None)
        if out_warehouse is None:
            raise BizError(400, "缺少产出仓库：请在 payload 指定 warehouse_id")
        produced_lot = StockLot(
            warehouse_id=out_warehouse,
            material_id=batch.product_material_id,
            lot_no=f"{batch.batch_no}-FG",
            qty=payload.produced_qty,
            uom_id=batch.uom_id,
            produced_at=now,
            expiry_at=(now + timedelta(days=product.shelf_life_days))
            if product and product.shelf_life_days
            else None,
            status="received",
            source_batch_id=batch.id,
        )
        db.add(produced_lot)
        db.flush()

        # ⑤ 副产品 / 废料批入库
        for bp in payload.byproduct:
            bp_wh = bp.warehouse_id or payload.warehouse_id
            if bp_wh is None:
                raise BizError(400, "副产品缺少 warehouse_id")
            db.add(
                StockLot(
                    warehouse_id=bp_wh,
                    material_id=bp.material_id,
                    lot_no=f"{batch.batch_no}-BP{bp.material_id}",
                    qty=bp.qty,
                    uom_id=bp.uom_id,
                    produced_at=now,
                    status=bp.status,
                    source_batch_id=batch.id,
                )
            )

        # ⑥ 谱系关联（父批 -> 成品批）
        for d, lot_id, take in allocations:
            db.add(
                LotGenealogy(
                    parent_lot_id=lot_id,
                    child_lot_id=produced_lot.id,
                    amount=take,
                    op_type="consume",
                    op_batch_id=batch.id,
                )
            )

        # ⑦ 配料记录
        for d in payload.dispenses:
            db.add(
                DispenseRecord(
                    batch_id=batch.id,
                    component_id=d.component_id,
                    material_id=d.material_id,
                    lot_id=d.lot_id,
                    planned_qty=d.planned_qty,
                    actual_qty=d.actual_qty,
                    uom_id=d.uom_id,
                    tol_pct=d.tol_pct,
                    deviated=not _tol_ok(d.planned_qty, d.actual_qty, d.tol_pct),
                    operator_id=d.operator_id,
                )
            )

        # ⑧ 批次收尾 + 工序推进
        batch.produced_qty = payload.produced_qty
        batch.yield_pct = (payload.produced_qty / batch.planned_qty * HUNDRED).quantize(Decimal("0.0001")) if batch.planned_qty else None
        batch.status = "completed"
        batch.completed_at = now
        op = db.scalars(
            select(BatchOperation).where(BatchOperation.batch_id == batch.id).order_by(BatchOperation.seq.asc())
        ).first()
        if op:
            op.status = "done"
            op.actual_qty = payload.produced_qty
            op.ended_at = now

        db.commit()
        return {
            "batch_id": batch.id,
            "batch_no": batch.batch_no,
            "status": batch.status,
            "produced_lot_id": produced_lot.id,
            "produced_lot_no": produced_lot.lot_no,
            "consumed": [{"lot_id": lid, "take_qty": str(t)} for _, lid, t in allocations],
            "deviations": deviations,
        }
    except Exception:
        db.rollback()
        raise


def release_batch(db: Session, batch_id: int) -> Batch:
    """发布批次：冻结配方快照（不可变），此后配方改动不影响在制批次（§3 闸4）。"""
    batch = db.get(Batch, batch_id, with_for_update=True)
    if not batch:
        raise BizError(404, "批次不存在")
    if batch.status in ("completed", "closed"):
        raise BizError(409, f"批次已 {batch.status}，不可再发布")

    recipe = db.get(Recipe, batch.recipe_id)
    if not recipe:
        raise BizError(404, "配方不存在")
    if recipe.status != "released":
        raise BizError(400, f"配方 {recipe.code} 未发布，不能投产")

    batch.recipe_version = recipe.version
    batch.recipe_snapshot = recipe_service.recipe_snapshot(db, recipe)
    batch.status = "released"
    db.commit()
    db.refresh(batch)
    return batch


def dispense_plan(db: Session, batch_id: int) -> dict:
    """应投清单：按批次「冻结快照」把成分缩放到该批次计划批量。

    与实时配方无关 —— 配方后续被改，本接口结果不变。
    """
    batch = db.get(Batch, batch_id)
    if not batch:
        raise BizError(404, "批次不存在")
    snap = batch.recipe_snapshot
    if not snap:
        raise BizError(409, "批次无配方快照，请先调用 POST /v1/batches/{id}/release")

    yield_factor = Decimal(snap.get("yield_pct") or "100") / HUNDRED
    if yield_factor <= 0:
        raise BizError(400, "收率必须大于 0")

    lines = []
    for c in snap.get("components", []):
        planned = (batch.planned_qty * (Decimal(c["ratio_pct"]) / HUNDRED) / yield_factor).quantize(Decimal("0.0001"))
        lines.append(
            {
                "component_id": c.get("component_id"),
                "material_id": c["material_id"],
                "uom_id": c["uom_id"],
                "ratio_pct": Decimal(c["ratio_pct"]),
                "tol_pct": Decimal(c["tol_pct"]),
                "planned_qty": planned,
                "is_key": bool(c.get("is_key", False)),
            }
        )

    return {
        "batch_id": batch.id,
        "batch_no": batch.batch_no,
        "recipe_id": snap.get("recipe_id"),
        "recipe_version": snap.get("version"),
        "planned_qty": batch.planned_qty,
        "yield_pct": Decimal(snap.get("yield_pct") or "100"),
        "lines": lines,
    }