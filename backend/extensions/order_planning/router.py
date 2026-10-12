# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""订单与生产计划扩展（order_planning）后端路由。

商业纪律：
- 本插件只建 ``ext_op_*`` 表；对核心 ``materials/recipes/stock_lots/batches`` 一律**只读**。
- 「计划↔批次」关系用映射表 ``ext_op_plan_batches`` 表达，**不给核心 batches 加列**。
- 计划下达时通过核心 ``batch_service.create_batch`` 生成**核心生产批次**（单一真相在核心，插件不另立批次账）。

约定：扩展在自己的 router.py 暴露 ``router``；宿主挂到 ``/api/extensions/order_planning`` 并叠加
``get_current_user`` + ``require_extension`` 门控。此处再叠加写权限门控（GET 仅需登录）。
"""
from __future__ import annotations

import logging
import os
import sys
import threading
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.db import get_db, SessionLocal
from app.core.deps import get_current_user, require_write_permission
from app.core.errors import BizError
from app.core.response import ok
from app.models.proc import Material, Recipe, StockLot
from app.models.user import User
from app.services.batch_service import create_batch
from app.services.recipe_service import scale_components
from app.services.stock_service import assert_lot_dispensable, fefo_plan, is_lot_expired

router = APIRouter(dependencies=[Depends(require_write_permission("ext.order_planning.manage"))])


# ---------- 通用小工具 ----------


def _jsonify(row) -> dict:
    out = {}
    for k, v in dict(row).items():
        if isinstance(v, Decimal):
            out[k] = str(v)
        elif isinstance(v, (datetime, date)):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def _rows(db: Session, sql: str, **params) -> list[dict]:
    return [_jsonify(r) for r in db.execute(text(sql), params).mappings().all()]


def _scalar(db: Session, sql: str, **params):
    return db.execute(text(sql), params).scalar()


def _next_no(db: Session, table: str, col: str, prefix: str) -> str:
    day = datetime.now().strftime("%Y%m%d")
    pfx = f"{day}"
    cnt = _scalar(db, f"SELECT COUNT(*) FROM {table} WHERE {col} LIKE :p", p=f"{prefix}{pfx}%") or 0
    return f"{prefix}{pfx}{cnt + 1:04d}"


def _validate_material(db: Session, material_id: int) -> Material:
    m = db.get(Material, material_id)
    if not m:
        raise BizError(400, f"成品物料不存在: material_id={material_id}")
    return m


# ---------- 销售订单 ----------


@router.get("/orders")
def list_orders(
    db: Session = Depends(get_db),
    status: str | None = Query(None),
    keyword: str | None = Query(None),
    offset: int = 0,
    limit: int = 50,
):
    where = ["o.is_deleted = 0"]
    params: dict = {"off": offset, "lim": min(max(limit, 1), 200)}
    if status:
        where.append("o.status = :st")
        params["st"] = status
    if keyword:
        where.append("(o.order_no LIKE :kw OR o.customer_name LIKE :kw)")
        params["kw"] = f"%{keyword}%"
    sql = "SELECT o.* FROM ext_op_orders o WHERE " + " AND ".join(where) + " ORDER BY o.id DESC LIMIT :off, :lim"
    return ok(_rows(db, sql, **params))


@router.get("/orders/{oid}")
def get_order(oid: int, db: Session = Depends(get_db)):
    order = _rows(db, "SELECT * FROM ext_op_orders WHERE id=:id AND is_deleted=0", id=oid)
    if not order:
        raise BizError(404, "订单不存在")
    items = _rows(
        db,
        "SELECT it.*, m.code AS material_code, m.name AS material_name "
        "FROM ext_op_order_items it LEFT JOIN materials m ON m.id = it.material_id "
        "WHERE it.order_id=:id ORDER BY it.id ASC",
        id=oid,
    )
    plans = _rows(db, "SELECT * FROM ext_op_plans WHERE order_id=:id AND is_deleted=0 ORDER BY id ASC", id=oid)
    return ok({"order": order[0], "items": items, "plans": plans})


@router.post("/orders")
def create_order(payload: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    customer_name = (payload.get("customer_name") or "").strip()
    if not customer_name:
        raise BizError(400, "客户名称必填")
    items = payload.get("items") or []
    if not items:
        raise BizError(400, "订单至少需要一行明细")

    order_no = payload.get("order_no") or _next_no(db, "ext_op_orders", "order_no", "SO")
    if _scalar(db, "SELECT COUNT(*) FROM ext_op_orders WHERE order_no=:n", n=order_no):
        raise BizError(409, f"订单号已存在: {order_no}")

    db.execute(
        text(
            "INSERT INTO ext_op_orders (order_no, customer_name, customer_code, status, order_date, due_date, remark, created_by) "
            "VALUES (:order_no, :customer_name, :customer_code, 'draft', :order_date, :due_date, :remark, :created_by)"
        ),
        {
            "order_no": order_no,
            "customer_name": customer_name,
            "customer_code": payload.get("customer_code"),
            "order_date": payload.get("order_date"),
            "due_date": payload.get("due_date"),
            "remark": payload.get("remark"),
            "created_by": user.id if user else None,
        },
    )
    oid = int(db.execute(text("SELECT LAST_INSERT_ID()")).scalar())

    for it in items:
        mat = _validate_material(db, int(it["material_id"]))
        qty = Decimal(str(it["qty"]))
        if qty <= 0:
            raise BizError(400, "订单行数量必须大于 0")
        db.execute(
            text(
                "INSERT INTO ext_op_order_items (order_id, material_id, spec, qty, uom_id, due_date) "
                "VALUES (:order_id, :material_id, :spec, :qty, :uom_id, :due_date)"
            ),
            {
                "order_id": oid,
                "material_id": mat.id,
                "spec": it.get("spec"),
                "qty": qty,
                "uom_id": int(it["uom_id"] or mat.base_uom_id),
                "due_date": it.get("due_date"),
            },
        )
    db.commit()
    return ok({"id": oid, "order_no": order_no})


@router.put("/orders/{oid}")
def update_order(oid: int, payload: dict = Body(...), db: Session = Depends(get_db)):
    row = _rows(db, "SELECT * FROM ext_op_orders WHERE id=:id AND is_deleted=0", id=oid)
    if not row:
        raise BizError(404, "订单不存在")
    if row[0]["status"] != "draft":
        raise BizError(409, "仅草稿订单可编辑")
    db.execute(
        text("UPDATE ext_op_orders SET customer_name=:cn, customer_code=:cc, due_date=:dd, remark=:rm WHERE id=:id"),
        {
            "cn": payload.get("customer_name", row[0].get("customer_name")),
            "cc": payload.get("customer_code"),
            "dd": payload.get("due_date"),
            "rm": payload.get("remark"),
            "id": oid,
        },
    )
    db.commit()
    return ok({"id": oid})


@router.post("/orders/{oid}/confirm")
def confirm_order(oid: int, db: Session = Depends(get_db)):
    row = _rows(db, "SELECT status FROM ext_op_orders WHERE id=:id AND is_deleted=0", id=oid)
    if not row:
        raise BizError(404, "订单不存在")
    if row[0]["status"] != "draft":
        raise BizError(409, "仅草稿可确认")
    db.execute(text("UPDATE ext_op_orders SET status='confirmed' WHERE id=:id"), {"id": oid})
    db.commit()
    return ok({"id": oid, "status": "confirmed"})


@router.post("/orders/{oid}/cancel")
def cancel_order(oid: int, db: Session = Depends(get_db)):
    row = _rows(db, "SELECT status FROM ext_op_orders WHERE id=:id AND is_deleted=0", id=oid)
    if not row:
        raise BizError(404, "订单不存在")
    if row[0]["status"] in ("shipped", "closed"):
        raise BizError(409, "已发货/已关闭订单不可取消")
    db.execute(text("UPDATE ext_op_orders SET status='cancelled' WHERE id=:id"), {"id": oid})
    db.commit()
    return ok({"id": oid, "status": "cancelled"})


# ---------- 生产计划 ----------


@router.get("/plans")
def list_plans(
    db: Session = Depends(get_db),
    status: str | None = Query(None),
    source_type: str | None = Query(None),
    order_id: int | None = Query(None),
    offset: int = 0,
    limit: int = 50,
):
    where = ["p.is_deleted = 0"]
    params: dict = {"off": offset, "lim": min(max(limit, 1), 200)}
    if status:
        where.append("p.status = :st")
        params["st"] = status
    if source_type:
        where.append("p.source_type = :st2")
        params["st2"] = source_type
    if order_id:
        where.append("p.order_id = :oid")
        params["oid"] = order_id
    sql = (
        "SELECT p.*, m.code AS material_code, m.name AS material_name, r.code AS recipe_code "
        "FROM ext_op_plans p "
        "LEFT JOIN materials m ON m.id = p.material_id "
        "LEFT JOIN recipes r ON r.id = p.recipe_id "
        "WHERE " + " AND ".join(where) + " ORDER BY p.id DESC LIMIT :off, :lim"
    )
    return ok(_rows(db, sql, **params))


@router.get("/plans/{pid}")
def get_plan(pid: int, db: Session = Depends(get_db)):
    rows = _rows(db, "SELECT * FROM ext_op_plans WHERE id=:id AND is_deleted=0", id=pid)
    if not rows:
        raise BizError(404, "计划不存在")
    batches = _rows(
        db,
        "SELECT pb.*, b.batch_no, b.status AS batch_status, b.produced_qty "
        "FROM ext_op_plan_batches pb LEFT JOIN batches b ON b.id = pb.batch_id WHERE pb.plan_id=:id ORDER BY pb.id ASC",
        id=pid,
    )
    return ok({"plan": rows[0], "batches": batches})


def _plan_common(db: Session, payload: dict, user) -> dict:
    source_type = (payload.get("source_type") or "mto").lower()
    if source_type not in ("mto", "mts"):
        raise BizError(400, "source_type 须为 mto / mts")
    recipe_id = int(payload["recipe_id"])
    recipe = db.get(Recipe, recipe_id)
    if not recipe:
        raise BizError(400, "配方不存在")
    if recipe.status != "released":
        raise BizError(400, f"配方 {recipe.code} 未发布，不能排产")
    mat = _validate_material(db, int(payload["material_id"]))
    planned_qty = Decimal(str(payload["planned_qty"]))
    if planned_qty <= 0:
        raise BizError(400, "计划数量必须大于 0")

    order_id = payload.get("order_id")
    order_item_id = payload.get("order_item_id")
    if order_id and not _rows(db, "SELECT id FROM ext_op_orders WHERE id=:id AND is_deleted=0", id=int(order_id)):
        raise BizError(400, "关联订单不存在")

    return {
        "source_type": source_type,
        "order_id": int(order_id) if order_id else None,
        "order_item_id": int(order_item_id) if order_item_id else None,
        "material_id": mat.id,
        "recipe_id": recipe.id,
        "planned_qty": planned_qty,
        "uom_id": int(payload.get("uom_id") or recipe.base_uom_id),
        "warehouse_id": int(payload["warehouse_id"]) if payload.get("warehouse_id") else None,
        "due_date": payload.get("due_date"),
        "remark": payload.get("remark"),
        "created_by": user.id if user else None,
    }


@router.post("/plans")
def create_plan(payload: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    data = _plan_common(db, payload, user)
    plan_no = payload.get("plan_no") or _next_no(db, "ext_op_plans", "plan_no", "MP")
    if _scalar(db, "SELECT COUNT(*) FROM ext_op_plans WHERE plan_no=:n", n=plan_no):
        raise BizError(409, f"计划单号已存在: {plan_no}")
    db.execute(
        text(
            "INSERT INTO ext_op_plans (plan_no, source_type, order_id, order_item_id, material_id, recipe_id, "
            "planned_qty, uom_id, warehouse_id, due_date, status, remark, created_by) "
            "VALUES (:plan_no, :source_type, :order_id, :order_item_id, :material_id, :recipe_id, "
            ":planned_qty, :uom_id, :warehouse_id, :due_date, 'draft', :remark, :created_by)"
        ),
        {"plan_no": plan_no, **data},
    )
    pid = int(db.execute(text("SELECT LAST_INSERT_ID()")).scalar())
    db.commit()
    return ok({"id": pid, "plan_no": plan_no})


@router.put("/plans/{pid}")
def update_plan(pid: int, payload: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = _rows(db, "SELECT status FROM ext_op_plans WHERE id=:id AND is_deleted=0", id=pid)
    if not rows:
        raise BizError(404, "计划不存在")
    if rows[0]["status"] != "draft":
        raise BizError(409, "仅草稿计划可编辑")
    data = _plan_common(db, payload, user)
    data.pop("created_by", None)
    sets = ", ".join(f"{k}=:{k}" for k in data)
    db.execute(text(f"UPDATE ext_op_plans SET {sets} WHERE id=:id"), {**data, "id": pid})
    db.commit()
    return ok({"id": pid})


def _kitting_lines(db: Session, recipe_id: int, planned_qty: Decimal, wh: int) -> tuple[list, bool]:
    scaled = scale_components(db, recipe_id, planned_qty)
    lines = []
    short = False
    for c in scaled["components"]:
        need = Decimal(str(c["planned_qty"]))
        fp = fefo_plan(db, wh, int(c["material_id"]), need)
        avail = sum((Decimal(str(p["take_qty"])) for p in fp["plan"]), Decimal("0"))
        gap = need - avail
        if not fp["enough"]:
            short = True
        lines.append(
            {
                "material_id": c["material_id"],
                "uom_id": c["uom_id"],
                "need_qty": str(need),
                "available_qty": str(avail),
                "shortage_qty": str(gap if gap > 0 else Decimal("0")),
                "enough": fp["enough"],
            }
        )
    return lines, short


@router.get("/plans/{pid}/kitting")
def plan_kitting(pid: int, db: Session = Depends(get_db), warehouse_id: int | None = Query(None)):
    rows = _rows(db, "SELECT * FROM ext_op_plans WHERE id=:id AND is_deleted=0", id=pid)
    if not rows:
        raise BizError(404, "计划不存在")
    plan = rows[0]
    wh = int(warehouse_id) if warehouse_id else (int(plan["warehouse_id"]) if plan["warehouse_id"] else None)
    if not wh:
        raise BizError(400, "缺少仓库：请在计划或查询参数提供 warehouse_id")
    lines, short = _kitting_lines(db, int(plan["recipe_id"]), Decimal(str(plan["planned_qty"])), wh)
    return ok({"plan_id": pid, "warehouse_id": wh, "enough": not short, "lines": lines})


@router.post("/plans/{pid}/release")
def release_plan(
    pid: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    force: bool = Query(False, description="忽略齐套缺口强行下达"),
    warehouse_id: int | None = Query(None),
):
    """计划下达：齐套校验（不足默认阻断）→ 调用核心 create_batch 生成核心批次 → 记映射 → 计划转 released。"""
    rows = _rows(db, "SELECT * FROM ext_op_plans WHERE id=:id AND is_deleted=0", id=pid)
    if not rows:
        raise BizError(404, "计划不存在")
    plan = rows[0]
    if plan["status"] != "draft":
        raise BizError(409, f"计划状态为 {plan['status']}，不可重复下达")

    wh = int(warehouse_id) if warehouse_id else (int(plan["warehouse_id"]) if plan["warehouse_id"] else None)
    if not wh:
        raise BizError(400, "缺少产出/投料仓库，下达失败")

    lines, short = _kitting_lines(db, int(plan["recipe_id"]), Decimal(str(plan["planned_qty"])), wh)
    shortage = [ln for ln in lines if not ln["enough"]]
    if shortage and not force:
        raise BizError(409, f"齐套不足，缺料 {len(shortage)} 项：{[s['material_id'] for s in shortage]}（可加 ?force=true 强行下达）")

    payload = SimpleNamespace(
        recipe_id=int(plan["recipe_id"]),
        planned_qty=Decimal(str(plan["planned_qty"])),
        uom_id=int(plan["uom_id"]),
        planned_date=None,
        note=f"由计划 {plan['plan_no']} 下达",
    )
    batch = create_batch(db, payload)

    db.execute(
        text("INSERT INTO ext_op_plan_batches (plan_id, batch_id, planned_qty) VALUES (:p, :b, :q)"),
        {"p": pid, "b": batch.id, "q": Decimal(str(plan["planned_qty"]))},
    )
    db.execute(text("UPDATE ext_op_plans SET status='released' WHERE id=:id"), {"id": pid})
    if plan["order_id"]:
        db.execute(
            text("UPDATE ext_op_orders SET status='released' WHERE id=:id AND status IN ('draft','confirmed')"),
            {"id": int(plan["order_id"])},
        )
    db.commit()
    return ok({"plan_id": pid, "batch_id": batch.id, "batch_no": batch.batch_no, "status": "released"})


@router.get("/plans/{pid}/batches")
def plan_batches(pid: int, db: Session = Depends(get_db)):
    return ok(
        _rows(
            db,
            "SELECT pb.*, b.batch_no, b.status AS batch_status, b.produced_qty, b.planned_qty AS batch_planned_qty "
            "FROM ext_op_plan_batches pb LEFT JOIN batches b ON b.id = pb.batch_id WHERE pb.plan_id=:id ORDER BY pb.id ASC",
            id=pid,
        )
    )


# ---------- 成品分配 / 发货 ----------


@router.get("/orders/{oid}/allocatable-lots")
def allocatable_lots(oid: int, db: Session = Depends(get_db)):
    items = _rows(db, "SELECT id, material_id, qty, delivered_qty FROM ext_op_order_items WHERE order_id=:id", id=oid)
    if not items:
        raise BizError(404, "订单无明细")
    result = []
    for it in items:
        lots = db.scalars(
            select(StockLot)
            .where(StockLot.material_id == int(it["material_id"]), StockLot.status == "released", StockLot.qty > 0)
            .order_by(StockLot.expiry_at.is_(None), StockLot.expiry_at.asc(), StockLot.id.asc())
        ).all()
        usable = [
            {"lot_id": l.id, "lot_no": l.lot_no, "qty": str(l.qty), "expiry_at": l.expiry_at.isoformat() if l.expiry_at else None}
            for l in lots
            if not is_lot_expired(l)
        ]
        result.append({"order_item_id": it["id"], "material_id": it["material_id"], "need": it["qty"], "lots": usable})
    return ok(result)


@router.post("/orders/{oid}/allocate")
def allocate_order(oid: int, payload: list[dict] = Body(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not payload:
        raise BizError(400, "分配明细为空")
    created = []
    for a in payload:
        item_id = int(a["order_item_id"])
        lot_id = int(a["lot_id"])
        qty = Decimal(str(a["qty"]))
        if qty <= 0:
            raise BizError(400, "分配数量必须大于 0")
        item = _rows(db, "SELECT material_id, order_id FROM ext_op_order_items WHERE id=:id", id=item_id)
        if not item or int(item[0]["order_id"]) != oid:
            raise BizError(400, f"订单行 {item_id} 不属于订单 {oid}")
        lot = db.get(StockLot, lot_id)
        if not lot:
            raise BizError(400, f"批次 {lot_id} 不存在")
        if int(item[0]["material_id"]) != lot.material_id:
            raise BizError(400, f"批次 {lot.lot_no} 物料与订单行不一致")
        if qty > lot.qty:
            raise BizError(409, f"批次 {lot.lot_no} 可用 {lot.qty} < 分配 {qty}")
        db.execute(
            text("INSERT INTO ext_op_allocations (order_item_id, lot_id, qty, created_by) VALUES (:i, :l, :q, :c)"),
            {"i": item_id, "l": lot_id, "q": qty, "c": user.id if user else None},
        )
        created.append(int(db.execute(text("SELECT LAST_INSERT_ID()")).scalar()))
    db.commit()
    return ok({"created": created})


@router.post("/allocations/{aid}/ship")
def ship_allocation(aid: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """确认发货：走核心出库纪律（行锁+合规门控）扣减批次库存、累加订单行已发量、回算订单状态。"""
    row = _rows(db, "SELECT * FROM ext_op_allocations WHERE id=:id", id=aid)
    if not row:
        raise BizError(404, "分配记录不存在")
    alloc = row[0]
    if str(alloc["shipped"]) in ("1", "True"):
        raise BizError(409, "该分配已发货")
    # 出库过账走核心纪律：行锁 + 合规门控（未放行/过期批次禁止出库），审计由 ORM 事件自动记录
    lot = db.scalars(
        select(StockLot).where(StockLot.id == int(alloc["lot_id"])).with_for_update()
    ).first()
    qty = Decimal(str(alloc["qty"]))
    if not lot:
        raise BizError(400, "关联批次不存在")
    assert_lot_dispensable(lot)
    if lot.qty < qty:
        raise BizError(409, f"批次 {lot.lot_no} 可用 {lot.qty} < 发货 {qty}")
    lot.qty = lot.qty - qty
    if lot.qty <= 0:
        lot.status = "consumed"

    item_id = int(alloc["order_item_id"])
    db.execute(text("UPDATE ext_op_order_items SET delivered_qty = delivered_qty + :q WHERE id=:id"), {"q": qty, "id": item_id})
    db.execute(text("UPDATE ext_op_allocations SET shipped=1, shipped_at=NOW() WHERE id=:id"), {"id": aid})

    order_id = int(_rows(db, "SELECT order_id FROM ext_op_order_items WHERE id=:id", id=item_id)[0]["order_id"])
    stats = _rows(db, "SELECT qty, delivered_qty FROM ext_op_order_items WHERE order_id=:id", id=order_id)
    total_need = sum((Decimal(str(s["qty"])) for s in stats), Decimal("0"))
    total_done = sum((Decimal(str(s["delivered_qty"])) for s in stats), Decimal("0"))
    if total_done >= total_need:
        new_status = "shipped"
    elif total_done > 0:
        new_status = "partial_shipped"
    else:
        new_status = "released"
    db.execute(
        text("UPDATE ext_op_orders SET status=:st WHERE id=:id AND status NOT IN ('closed','cancelled')"),
        {"st": new_status, "id": order_id},
    )
    db.commit()
    try:
        from app.services import notify
        notify.send(
            event="order_planning_shipped",
            title=f"订单 #{order_id} 发货 {qty}（批次 {lot.lot_no}）",
            body=f"分配 #{aid} 已出库，订单状态：{new_status}。",
            level="info",
            channel="production",
            data={"order_id": order_id, "allocation_id": aid, "lot_no": lot.lot_no, "qty": str(qty)},
        )
    except Exception:  # noqa: BLE001 - 通知失败不影响发货主流程
        pass
    return ok({"id": aid, "order_id": order_id, "order_status": new_status})


@router.get("/orders/{oid}/allocations")
def list_allocations(oid: int, db: Session = Depends(get_db)):
    return ok(
        _rows(
            db,
            "SELECT a.*, l.lot_no, i.material_id FROM ext_op_allocations a "
            "LEFT JOIN ext_op_order_items i ON i.id = a.order_item_id "
            "LEFT JOIN stock_lots l ON l.id = a.lot_id "
            "WHERE i.order_id=:id ORDER BY a.id ASC",
            id=oid,
        )
    )


# ---------- 安全库存备货策略（MTS 驱动源） ----------


def _on_hand(db: Session, material_id: int, warehouse_id: int) -> Decimal:
    """某成品物料在指定仓库的可用库存：status=released、qty>0、未过期、未软删。"""
    val = _scalar(
        db,
        "SELECT COALESCE(SUM(qty), 0) FROM stock_lots "
        "WHERE material_id=:m AND warehouse_id=:w AND status='released' AND qty > 0 AND is_deleted = 0 "
        "AND (expiry_at IS NULL OR expiry_at >= NOW())",
        m=material_id,
        w=warehouse_id,
    )
    return Decimal(str(val or 0))


def _released_recipe_for(db: Session, material_id: int):
    """取该成品物料最近一个已发布配方（MTS 备货排产用），无则 None。"""
    rows = _rows(
        db,
        "SELECT id, code, name, base_uom_id FROM recipes "
        "WHERE product_material_id=:m AND status='released' AND is_deleted = 0 "
        "ORDER BY id DESC LIMIT 1",
        m=material_id,
    )
    return rows[0] if rows else None


@router.get("/safety-stock")
def list_safety_stock(db: Session = Depends(get_db)):
    rows = _rows(
        db,
        "SELECT ss.*, m.code AS material_code, m.name AS material_name, w.name AS warehouse_name "
        "FROM ext_op_safety_stock ss "
        "LEFT JOIN materials m ON m.id = ss.material_id "
        "LEFT JOIN warehouses w ON w.id = ss.warehouse_id "
        "ORDER BY ss.id DESC",
    )
    for r in rows:
        r["on_hand"] = str(_on_hand(db, int(r["material_id"]), int(r["warehouse_id"])))
    return ok(rows)


@router.put("/safety-stock")
def upsert_safety_stock(payload: dict = Body(...), db: Session = Depends(get_db)):
    material_id = int(payload["material_id"])
    warehouse_id = int(payload["warehouse_id"])
    min_qty = Decimal(str(payload.get("min_qty") or 0))
    max_qty = Decimal(str(payload.get("max_qty") or 0))
    if min_qty < 0 or max_qty < 0:
        raise BizError(400, "min_qty / max_qty 不能为负")
    if max_qty < min_qty:
        raise BizError(400, "max_qty 不能小于 min_qty")
    _validate_material(db, material_id)
    if not _rows(db, "SELECT id FROM warehouses WHERE id=:id", id=warehouse_id):
        raise BizError(400, f"仓库不存在: warehouse_id={warehouse_id}")
    remark = payload.get("remark")
    existed = _rows(
        db, "SELECT id FROM ext_op_safety_stock WHERE material_id=:m AND warehouse_id=:w",
        m=material_id, w=warehouse_id,
    )
    if existed:
        db.execute(
            text("UPDATE ext_op_safety_stock SET min_qty=:min, max_qty=:max, remark=:rm WHERE id=:id"),
            {"min": min_qty, "max": max_qty, "rm": remark, "id": int(existed[0]["id"])},
        )
        sid = int(existed[0]["id"])
    else:
        db.execute(
            text("INSERT INTO ext_op_safety_stock (material_id, warehouse_id, min_qty, max_qty, remark) "
                 "VALUES (:m, :w, :min, :max, :rm)"),
            {"m": material_id, "w": warehouse_id, "min": min_qty, "max": max_qty, "rm": remark},
        )
        sid = int(db.execute(text("SELECT LAST_INSERT_ID()")).scalar())
    db.commit()
    return ok({"id": sid, "material_id": material_id, "warehouse_id": warehouse_id})


@router.delete("/safety-stock/{sid}")
def delete_safety_stock(sid: int, db: Session = Depends(get_db)):
    if not _rows(db, "SELECT id FROM ext_op_safety_stock WHERE id=:id", id=sid):
        raise BizError(404, "安全库存策略不存在")
    db.execute(text("DELETE FROM ext_op_safety_stock WHERE id=:id"), {"id": sid})
    db.commit()
    return ok({"id": sid})


def _build_mts_suggestions(db: Session) -> list[dict]:
    """按安全库存策略实时算备货建议：on_hand < min_qty → 建议补到 max_qty。"""
    rules = _rows(db, "SELECT * FROM ext_op_safety_stock ORDER BY id ASC")
    suggestions = []
    for r in rules:
        mid, wid = int(r["material_id"]), int(r["warehouse_id"])
        on_hand = _on_hand(db, mid, wid)
        min_qty = Decimal(str(r["min_qty"]))
        max_qty = Decimal(str(r["max_qty"]))
        if on_hand >= min_qty:
            continue
        suggested = max_qty - on_hand
        if suggested <= 0:
            continue
        recipe = _released_recipe_for(db, mid)
        mat = _rows(db, "SELECT code, name, base_uom_id FROM materials WHERE id=:id AND is_deleted=0", id=mid)
        suggestions.append(
            {
                "material_id": mid,
                "material_code": mat[0]["code"] if mat else None,
                "material_name": mat[0]["name"] if mat else None,
                "warehouse_id": wid,
                "on_hand": str(on_hand),
                "min_qty": str(min_qty),
                "max_qty": str(max_qty),
                "suggested_qty": str(suggested),
                "recipe_id": int(recipe["id"]) if recipe else None,
                "recipe_code": recipe["code"] if recipe else None,
                "uom_id": (int(recipe["base_uom_id"]) if recipe else (mat[0]["base_uom_id"] if mat else None)),
                "can_plan": bool(recipe),
            }
        )
    return suggestions


@router.get("/mts-suggestions")
def mts_suggestions(db: Session = Depends(get_db)):
    items = _build_mts_suggestions(db)
    return ok({"count": len(items), "items": items})


@router.post("/generate-mts")
def generate_mts(payload: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """把备货建议批量落成草稿 MTS 计划（不自动下达，仍需人工齐套/下达）。"""
    items = payload.get("items") or []
    if not items:
        raise BizError(400, "items 为空")
    created = []
    for it in items:
        recipe = db.get(Recipe, int(it["recipe_id"]))
        if not recipe:
            raise BizError(400, f"配方不存在: recipe_id={it['recipe_id']}")
        body = {
            "source_type": "mts",
            "recipe_id": int(it["recipe_id"]),
            "material_id": int(it["material_id"]),
            "planned_qty": str(it["qty"]),
            "uom_id": it.get("uom_id"),
            "warehouse_id": int(it["warehouse_id"]),
            "remark": it.get("remark") or "安全库存备货建议自动生成",
        }
        data = _plan_common(db, body, user)
        plan_no = _next_no(db, "ext_op_plans", "plan_no", "MP")
        db.execute(
            text("INSERT INTO ext_op_plans (plan_no, source_type, order_id, order_item_id, material_id, recipe_id, "
                 "planned_qty, uom_id, warehouse_id, due_date, status, remark, created_by) "
                 "VALUES (:plan_no, :source_type, :order_id, :order_item_id, :material_id, :recipe_id, "
                 ":planned_qty, :uom_id, :warehouse_id, :due_date, 'draft', :remark, :created_by)"),
            {"plan_no": plan_no, **data},
        )
        pid = int(db.execute(text("SELECT LAST_INSERT_ID()")).scalar())
        created.append({"id": pid, "plan_no": plan_no, "material_id": data["material_id"], "planned_qty": str(data["planned_qty"])})
    db.commit()
    return ok({"created": created, "count": len(created)})


# ---------- 计划生命周期回算 & 软删除 ----------


@router.post("/plans/{pid}/sync-status")
def sync_plan_status(pid: int, db: Session = Depends(get_db)):
    """按关联核心批次的进度回算计划状态：released → in_production → completed。"""
    rows = _rows(db, "SELECT * FROM ext_op_plans WHERE id=:id AND is_deleted=0", id=pid)
    if not rows:
        raise BizError(404, "计划不存在")
    plan = rows[0]
    if plan["status"] not in ("released", "in_production", "completed"):
        raise BizError(409, f"计划状态 {plan['status']} 无需回算")
    bs = _rows(
        db,
        "SELECT b.status, b.planned_qty, COALESCE(b.produced_qty,0) AS produced_qty "
        "FROM ext_op_plan_batches pb LEFT JOIN batches b ON b.id = pb.batch_id WHERE pb.plan_id=:id",
        id=pid,
    )
    if not bs:
        return ok({"plan_id": pid, "status": plan["status"], "message": "无关联批次"})
    total_planned = sum((Decimal(str(x["planned_qty"])) for x in bs), Decimal("0"))
    total_produced = sum((Decimal(str(x["produced_qty"])) for x in bs), Decimal("0"))
    all_closed = all(str(x["status"]) in ("completed", "closed") for x in bs)
    if (total_planned > 0 and total_produced >= total_planned) or all_closed:
        new_status = "completed"
    elif total_produced > 0 or any(str(x["status"]) in ("in_progress", "completed", "closed") for x in bs):
        new_status = "in_production"
    else:
        new_status = "released"
    if new_status != plan["status"]:
        db.execute(text("UPDATE ext_op_plans SET status=:st WHERE id=:id"), {"st": new_status, "id": pid})
        db.commit()
    return ok({"plan_id": pid, "status": new_status, "produced": str(total_produced), "planned": str(total_planned)})


@router.delete("/orders/{oid}")
def delete_order(oid: int, db: Session = Depends(get_db)):
    row = _rows(db, "SELECT status FROM ext_op_orders WHERE id=:id AND is_deleted=0", id=oid)
    if not row:
        raise BizError(404, "订单不存在")
    if row[0]["status"] not in ("draft", "confirmed", "cancelled"):
        raise BizError(409, "已下达/发货的订单不可删除")
    db.execute(text("UPDATE ext_op_orders SET is_deleted=1 WHERE id=:id"), {"id": oid})
    db.commit()
    return ok({"id": oid})


@router.delete("/plans/{pid}")
def delete_plan(pid: int, db: Session = Depends(get_db)):
    row = _rows(db, "SELECT status FROM ext_op_plans WHERE id=:id AND is_deleted=0", id=pid)
    if not row:
        raise BizError(404, "计划不存在")
    if row[0]["status"] != "draft":
        raise BizError(409, "仅草稿计划可删除")
    db.execute(text("UPDATE ext_op_plans SET is_deleted=1 WHERE id=:id"), {"id": pid})
    db.commit()
    return ok({"id": pid})


# ---------- 备货预警：扫描 + 主动通知（无 Celery，用守护线程周期扫描） ----------

_MTS_SCAN_HOURS = float(os.getenv("ORDER_PLANNING_MTS_SCAN_HOURS", "6"))


def _scan_and_alert() -> dict:
    """扫描安全库存备货建议，低于再订货点则投递一条汇总预警（站内 + WebSocket）。"""
    db = SessionLocal()
    try:
        items = _build_mts_suggestions(db)
    finally:
        db.close()
    if not items:
        return {"count": 0, "alerted": False}
    preview = [
        {
            "material_code": it.get("material_code"),
            "material_name": it.get("material_name"),
            "warehouse_id": it["warehouse_id"],
            "on_hand": it["on_hand"],
            "min_qty": it["min_qty"],
            "suggested_qty": it["suggested_qty"],
        }
        for it in items[:20]
    ]
    try:
        from app.services import notify
        notify.send(
            event="order_planning_low_stock",
            title=f"备货预警：{len(items)} 个成品低于安全库存",
            body="以下成品现有可用库存低于再订货点，建议按备货建议生成 MTS 计划补货。",
            level="warning",
            channel="production",
            data={"count": len(items), "items": preview},
        )
    except Exception as exc:  # noqa: BLE001 - 通知失败不影响扫描
        logging.getLogger("order_planning").warning("备货预警投递失败: %s", exc)
    return {"count": len(items), "alerted": True}


@router.post("/safety-stock/scan-alert")
def safety_stock_scan_alert():
    """手动触发一次备货扫描并投递预警（供前端按钮 / 外部定时任务调用）。"""
    return ok(_scan_and_alert())


def _mts_scan_loop(stop: "threading.Event", gen: int) -> None:
    log = logging.getLogger("order_planning")
    interval = _MTS_SCAN_HOURS * 3600
    while not stop.wait(interval):
        reg = getattr(sys, "_op_mts_scan", None) or {}
        if reg.get("gen") != gen:
            log.debug("备货扫描线程已被新版本取代，退出 (gen=%s)", gen)
            return
        try:
            r = _scan_and_alert()
            if r["count"]:
                log.info("备货扫描：命中 %s 项，已投递预警", r["count"])
        except Exception as exc:  # noqa: BLE001
            log.warning("备货扫描异常: %s", exc)


def start_mts_scan_thread() -> None:
    """启动/替换备货扫描守护线程（进程级单例，热重载不泄漏重复线程）。

    ORDER_PLANNING_MTS_SCAN_HOURS<=0 可关闭自动扫描（仅保留手动 scan-alert 端点）。
    """
    if _MTS_SCAN_HOURS <= 0:
        return
    reg = getattr(sys, "_op_mts_scan", None)
    if reg is None:
        reg = {}
        sys._op_mts_scan = reg
    old_stop = reg.get("stop")
    if old_stop is not None:
        old_stop.set()  # 通知旧线程退出
    gen = int(reg.get("gen", 0)) + 1
    reg["gen"] = gen
    stop = threading.Event()
    reg["stop"] = stop
    t = threading.Thread(target=_mts_scan_loop, args=(stop, gen), name=f"op-mts-scan-{gen}", daemon=True)
    reg["thread"] = t
    t.start()


# 挂载/热重载时自动确保扫描线程在位（进程级单例，重复 import 只会替换旧线程）
try:
    start_mts_scan_thread()
except Exception as exc:  # noqa: BLE001 - 线程启动失败不得影响路由挂载
    logging.getLogger("order_planning").warning("备货扫描线程启动失败: %s", exc)
