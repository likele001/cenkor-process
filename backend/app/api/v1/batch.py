# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""批次：创建、查询、产出入账（原子过账）。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import BizError
from app.core.response import ok
from app.models.proc import Batch, BatchOperation, DispenseRecord
from app.schemas.proc import BatchCompleteIn, BatchIn, BatchOut
from app.services import batch_service

router = APIRouter()


@router.get("/batches")
def list_batches(db: Session = Depends(get_db)):
    rows = db.scalars(select(Batch).where(Batch.is_deleted.is_(False)).order_by(Batch.id.desc())).all()
    return ok([BatchOut.model_validate(r) for r in rows])


@router.post("/batches")
def create_batch(payload: BatchIn, db: Session = Depends(get_db)):
    batch = batch_service.create_batch(db, payload)
    return ok(BatchOut.model_validate(batch))


@router.get("/batches/{batch_id}")
def get_batch(batch_id: int, db: Session = Depends(get_db)):
    batch = db.get(Batch, batch_id)
    if not batch or batch.is_deleted:
        raise BizError(404, "批次不存在")
    ops = db.scalars(
        select(BatchOperation).where(BatchOperation.batch_id == batch_id).order_by(BatchOperation.seq.asc())
    ).all()
    dispenses = db.scalars(
        select(DispenseRecord).where(DispenseRecord.batch_id == batch_id).order_by(DispenseRecord.id.asc())
    ).all()
    data = BatchOut.model_validate(batch).model_dump()
    data["operations"] = [
        {
            "id": o.id,
            "seq": o.seq,
            "name": o.name,
            "op_type": o.op_type,
            "status": o.status,
            "temp_c": str(o.temp_c) if o.temp_c is not None else None,
            "duration_min": o.duration_min,
        }
        for o in ops
    ]
    data["dispenses"] = [
        {
            "id": d.id,
            "material_id": d.material_id,
            "lot_id": d.lot_id,
            "planned_qty": str(d.planned_qty),
            "actual_qty": str(d.actual_qty),
            "tol_pct": str(d.tol_pct),
            "deviated": d.deviated,
        }
        for d in dispenses
    ]
    return ok(data)


@router.post("/batches/{batch_id}/complete")
def complete_batch(batch_id: int, payload: BatchCompleteIn, db: Session = Depends(get_db)):
    return ok(batch_service.complete_batch(db, batch_id, payload))


@router.post("/batches/{batch_id}/release")
def release_batch(batch_id: int, db: Session = Depends(get_db)):
    """发布批次：冻结配方快照，此后配方改动不影响本批次。"""
    batch = batch_service.release_batch(db, batch_id)
    return ok(
        {
            "id": batch.id,
            "batch_no": batch.batch_no,
            "status": batch.status,
            "recipe_version": batch.recipe_version,
            "has_snapshot": bool(batch.recipe_snapshot),
        }
    )


@router.get("/batches/{batch_id}/dispense-plan")
def dispense_plan(batch_id: int, db: Session = Depends(get_db)):
    """应投清单：按批次冻结快照缩放，与实时配方无关。"""
    return ok(batch_service.dispense_plan(db, batch_id))