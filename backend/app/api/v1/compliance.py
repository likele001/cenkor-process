# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""P2 合规 API：HACCP/CCP、CIP 清洗、CoA 放行、杀菌时间-温度记录、异常看板。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import BizError
from app.core.response import ok
from app.models.proc import Ccp, CcpRecord, CipLog, Coa, TempLog
from app.schemas.proc import (
    CcpIn,
    CcpOut,
    CcpRecordIn,
    CcpRecordOut,
    CipLogIn,
    CipLogOut,
    CoaDecideIn,
    CoaIn,
    CoaOut,
    TempLogIn,
    TempLogOut,
)
from app.services import compliance_service

router = APIRouter()


# ---------------- HACCP / CCP ----------------
@router.get("/ccps")
def list_ccps(active_only: bool = False, db: Session = Depends(get_db)):
    stmt = select(Ccp).where(Ccp.is_deleted.is_(False))
    if active_only:
        stmt = stmt.where(Ccp.is_active.is_(True))
    rows = db.scalars(stmt.order_by(Ccp.id.asc())).all()
    return ok([CcpOut.model_validate(r) for r in rows])


@router.post("/ccps")
def create_ccp(payload: CcpIn, db: Session = Depends(get_db)):
    exists = db.scalar(select(Ccp.id).where(Ccp.code == payload.code))
    if exists:
        raise BizError(409, f"CCP 编码 {payload.code} 已存在")
    if payload.limit_min is not None and payload.limit_max is not None and payload.limit_min > payload.limit_max:
        raise BizError(400, "关键限值下限不能大于上限")
    ccp = Ccp(**payload.model_dump())
    db.add(ccp)
    db.commit()
    db.refresh(ccp)
    return ok(CcpOut.model_validate(ccp))


@router.get("/ccps/{ccp_id}")
def get_ccp(ccp_id: int, db: Session = Depends(get_db)):
    ccp = db.get(Ccp, ccp_id)
    if not ccp or ccp.is_deleted:
        raise BizError(404, "关键控制点不存在")
    return ok(CcpOut.model_validate(ccp))


@router.post("/ccp-records")
def create_ccp_record(payload: CcpRecordIn, db: Session = Depends(get_db)):
    """记录一次 CCP 监控：自动按关键限值判定 pass/deviation。"""
    rec = compliance_service.create_ccp_record(db, payload)
    return ok(CcpRecordOut.model_validate(rec))


@router.get("/ccp-records")
def list_ccp_records(
    ccp_id: int | None = None,
    batch_id: int | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    stmt = select(CcpRecord)
    if ccp_id is not None:
        stmt = stmt.where(CcpRecord.ccp_id == ccp_id)
    if batch_id is not None:
        stmt = stmt.where(CcpRecord.batch_id == batch_id)
    if status:
        stmt = stmt.where(CcpRecord.status == status)
    rows = db.scalars(stmt.order_by(CcpRecord.id.desc())).all()
    return ok([CcpRecordOut.model_validate(r) for r in rows])


@router.get("/batches/{batch_id}/ccp-records")
def batch_ccp_records(batch_id: int, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(CcpRecord).where(CcpRecord.batch_id == batch_id).order_by(CcpRecord.id.asc())
    ).all()
    return ok([CcpRecordOut.model_validate(r) for r in rows])


# ---------------- CIP 清洗 ----------------
@router.post("/cip-logs")
def create_cip_log(payload: CipLogIn, db: Session = Depends(get_db)):
    log = compliance_service.create_cip_log(db, payload)
    return ok(CipLogOut.model_validate(log))


@router.get("/cip-logs")
def list_cip_logs(
    station: str | None = None,
    batch_id: int | None = None,
    result: str | None = None,
    db: Session = Depends(get_db),
):
    stmt = select(CipLog).where(CipLog.is_deleted.is_(False))
    if station:
        stmt = stmt.where(CipLog.station == station)
    if batch_id is not None:
        stmt = stmt.where(CipLog.batch_id == batch_id)
    if result:
        stmt = stmt.where(CipLog.result == result)
    rows = db.scalars(stmt.order_by(CipLog.id.desc())).all()
    return ok([CipLogOut.model_validate(r) for r in rows])


# ---------------- CoA 检验 / 放行 ----------------
@router.post("/coa")
def create_coa(payload: CoaIn, db: Session = Depends(get_db)):
    coa = compliance_service.create_coa(db, payload)
    return ok(CoaOut.model_validate(coa))


@router.get("/coa")
def list_coa(
    lot_id: int | None = None,
    material_id: int | None = None,
    result: str | None = None,
    db: Session = Depends(get_db),
):
    stmt = select(Coa).where(Coa.is_deleted.is_(False))
    if lot_id is not None:
        stmt = stmt.where(Coa.lot_id == lot_id)
    if material_id is not None:
        stmt = stmt.where(Coa.material_id == material_id)
    if result:
        stmt = stmt.where(Coa.result == result)
    rows = db.scalars(stmt.order_by(Coa.id.desc())).all()
    return ok([CoaOut.model_validate(r) for r in rows])


@router.get("/coa/{coa_id}")
def get_coa(coa_id: int, db: Session = Depends(get_db)):
    coa = db.get(Coa, coa_id)
    if not coa or coa.is_deleted:
        raise BizError(404, "检验单不存在")
    return ok(CoaOut.model_validate(coa))


@router.post("/coa/{coa_id}/decide")
def decide_coa(coa_id: int, payload: CoaDecideIn, db: Session = Depends(get_db)):
    """判定并放行：pass -> 批次 released 并锁死；fail -> rejected 并锁死；hold -> 隔离。"""
    return ok(compliance_service.decide_coa(db, coa_id, payload))


# ---------------- 杀菌时间-温度记录 ----------------
@router.post("/temp-logs")
def create_temp_log(payload: TempLogIn, db: Session = Depends(get_db)):
    """写入一条时间-温度记录；带 ccp_id 时自动判定并触发越限告警。"""
    res = compliance_service.record_temp_log(db, payload)
    return ok(
        {
            "log": TempLogOut.model_validate(res["log"]),
            "in_range": res["in_range"],
            "alert_raised": res["alert_raised"],
        }
    )


@router.get("/temp-logs")
def list_temp_logs(
    batch_id: int | None = None,
    ccp_id: int | None = None,
    in_range: bool | None = None,
    db: Session = Depends(get_db),
):
    stmt = select(TempLog)
    if batch_id is not None:
        stmt = stmt.where(TempLog.batch_id == batch_id)
    if ccp_id is not None:
        stmt = stmt.where(TempLog.ccp_id == ccp_id)
    if in_range is not None:
        stmt = stmt.where(TempLog.in_range.is_(in_range))
    rows = db.scalars(stmt.order_by(TempLog.id.asc())).all()
    return ok([TempLogOut.model_validate(r) for r in rows])


@router.get("/batches/{batch_id}/temp-logs")
def batch_temp_logs(batch_id: int, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(TempLog).where(TempLog.batch_id == batch_id).order_by(TempLog.recorded_at.asc(), TempLog.id.asc())
    ).all()
    return ok([TempLogOut.model_validate(r) for r in rows])


# ---------------- 合规异常看板 ----------------
@router.get("/compliance/alerts")
def compliance_alerts(db: Session = Depends(get_db)):
    """聚合 CCP 偏差 / 温度越限 / CIP 不合格 / CoA 不合格。"""
    return ok(compliance_service.alerts(db))