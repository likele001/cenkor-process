# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""库存：批次查询、收货、FEFO 预演、谱系。"""
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.response import ok
from app.models.proc import StockLot
from app.schemas.proc import LotMergeIn, LotReceiptIn, LotSplitIn, StockLotOut
from app.services import stock_service

router = APIRouter()


def _lot_out(lot: StockLot) -> StockLotOut:
    """序列化批次并回填效期只读字段（days_to_expiry / expired / near_expiry）。"""
    out = StockLotOut.model_validate(lot)
    out.days_to_expiry = stock_service.days_to_expiry(lot)
    out.expired = stock_service.is_lot_expired(lot)
    out.near_expiry = stock_service.is_lot_near_expiry(lot)
    return out


@router.get("/stock/lots")
def list_lots(
    warehouse_id: int | None = None,
    material_id: int | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    stmt = select(StockLot).where(StockLot.is_deleted.is_(False))
    if warehouse_id is not None:
        stmt = stmt.where(StockLot.warehouse_id == warehouse_id)
    if material_id is not None:
        stmt = stmt.where(StockLot.material_id == material_id)
    if status:
        stmt = stmt.where(StockLot.status == status)
    rows = db.scalars(stmt.order_by(StockLot.expiry_at.is_(None), StockLot.expiry_at.asc(), StockLot.id.asc())).all()
    return ok([_lot_out(r) for r in rows])


@router.post("/stock/lots")
def receive_lot(payload: LotReceiptIn, db: Session = Depends(get_db)):
    lot = stock_service.receive_lot(db, payload)
    db.commit()
    db.refresh(lot)
    return ok(_lot_out(lot))


@router.get("/stock/fefo-preview")
def fefo_preview(warehouse_id: int, material_id: int, qty: Decimal, db: Session = Depends(get_db)):
    return ok(stock_service.fefo_plan(db, warehouse_id, material_id, qty))


@router.get("/stock/genealogy/{lot_id}")
def lot_genealogy(lot_id: int, db: Session = Depends(get_db)):
    return ok(stock_service.genealogy(db, lot_id))


@router.post("/stock/lots/merge")
def merge_lots(payload: LotMergeIn, db: Session = Depends(get_db)):
    """合批：多个父批全量并入一个新子批（谱系 op_type=merge）。"""
    return ok(stock_service.merge_lots(db, payload))


@router.post("/stock/lots/{lot_id}/split")
def split_lot(lot_id: int, payload: LotSplitIn, db: Session = Depends(get_db)):
    """拆批：一个父批按明细拆为多个子批（谱系 op_type=split）。"""
    return ok(stock_service.split_lot(db, lot_id, payload))