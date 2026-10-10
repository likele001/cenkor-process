# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""P2 合规服务：HACCP/CCP 监控、CIP 清洗、CoA 放行、杀菌时间-温度告警。

设计要点：
  - CCP 判定：实测值对关键限值 [limit_min, limit_max] 判定 pass/deviation；
  - 温度记录：写入时间序列，带 ccp_id 时自动判定，超限且 critical 自动生成偏差记录（异常告警）；
  - CoA 放行：pass -> 库存批置 released 并锁死；fail -> rejected 并锁死；hold -> 隔离，可再判；
    判定后 CoA 不可修改（locked），同一批次已放行则阻断二次放行（放行后批次锁死）。
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BizError
from app.models.proc import Ccp, CcpRecord, CipLog, Coa, StockLot, TempLog

VALID_DECISIONS = {"pass", "fail", "hold"}


def _eval_limits(ccp: Ccp, value: Decimal) -> tuple[str, bool]:
    """按关键限值判定，返回 (status, in_range)。"""
    if ccp.limit_min is not None and value < Decimal(ccp.limit_min):
        return "deviation", False
    if ccp.limit_max is not None and value > Decimal(ccp.limit_max):
        return "deviation", False
    return "pass", True


def _limit_text(ccp: Ccp) -> str:
    lo = ccp.limit_min if ccp.limit_min is not None else "-∞"
    hi = ccp.limit_max if ccp.limit_max is not None else "+∞"
    return f"[{lo}, {hi}]"


def create_ccp_record(db: Session, payload) -> CcpRecord:
    ccp = db.get(Ccp, payload.ccp_id)
    if not ccp:
        raise BizError(404, "关键控制点不存在")
    status, _ = _eval_limits(ccp, payload.measured_value)
    note = payload.deviation_note
    if status == "deviation" and not note:
        note = f"实测 {payload.measured_value} 超出关键限值 {_limit_text(ccp)}"
    rec = CcpRecord(
        ccp_id=ccp.id,
        batch_id=payload.batch_id,
        operation_id=payload.operation_id,
        lot_id=payload.lot_id,
        measured_value=payload.measured_value,
        uom_id=payload.uom_id or ccp.uom_id,
        measured_at=payload.measured_at or datetime.now(),
        operator_id=payload.operator_id,
        status=status,
        deviation_note=note,
        corrective_action=payload.corrective_action or (ccp.corrective_action if status == "deviation" else None),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def record_temp_log(db: Session, payload) -> dict:
    """写入一条时间-温度记录；带 ccp_id 时自动判定，超限自动生成 CCP 偏差告警。"""
    ccp = db.get(Ccp, payload.ccp_id) if payload.ccp_id else None
    if payload.ccp_id and not ccp:
        raise BizError(404, "关键控制点不存在")

    in_range = True
    if ccp is not None:
        _, in_range = _eval_limits(ccp, payload.temp_c)

    log = TempLog(
        batch_id=payload.batch_id,
        operation_id=payload.operation_id,
        ccp_id=ccp.id if ccp else None,
        station=payload.station,
        stage=payload.stage,
        recorded_at=payload.recorded_at or datetime.now(),
        temp_c=payload.temp_c,
        duration_min=payload.duration_min,
        in_range=in_range,
        note=payload.note,
    )
    db.add(log)
    db.flush()

    alert_raised = False
    if ccp is not None and not in_range and ccp.critical:
        db.add(
            CcpRecord(
                ccp_id=ccp.id,
                batch_id=payload.batch_id,
                operation_id=payload.operation_id,
                measured_value=payload.temp_c,
                uom_id=ccp.uom_id,
                measured_at=log.recorded_at,
                status="deviation",
                deviation_note=f"自动告警：温度 {payload.temp_c}℃ 超出关键限值 {_limit_text(ccp)}",
                corrective_action=ccp.corrective_action,
            )
        )
        alert_raised = True

    db.commit()
    db.refresh(log)
    return {"log": log, "in_range": in_range, "alert_raised": alert_raised}


def create_cip_log(db: Session, payload) -> CipLog:
    duration = payload.duration_min
    if duration is None and payload.end_at and payload.start_at:
        duration = int((payload.end_at - payload.start_at).total_seconds() // 60)

    # 结果判定：末次冲洗 pH 6.0~8.0 且电导率 <= 30 视为合格，否则 fail（可显式覆盖）
    result = "pass"
    if payload.final_rinse_ph is not None and not (Decimal("6.0") <= Decimal(payload.final_rinse_ph) <= Decimal("8.0")):
        result = "fail"
    if payload.rinse_conductivity is not None and Decimal(payload.rinse_conductivity) > Decimal("30"):
        result = "fail"

    log = CipLog(
        batch_id=payload.batch_id,
        station=payload.station,
        cip_type=payload.cip_type,
        start_at=payload.start_at,
        end_at=payload.end_at,
        duration_min=duration,
        caustic_conc_pct=payload.caustic_conc_pct,
        caustic_temp_c=payload.caustic_temp_c,
        acid_conc_pct=payload.acid_conc_pct,
        acid_temp_c=payload.acid_temp_c,
        rinse_conductivity=payload.rinse_conductivity,
        final_rinse_ph=payload.final_rinse_ph,
        result=result,
        operator_id=payload.operator_id,
        note=payload.note,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def next_coa_no(db: Session, when: datetime | None = None) -> str:
    when = when or datetime.now()
    prefix = f"COA{when:%Y%m%d}"
    from sqlalchemy import func

    count = db.scalar(select(func.count(Coa.id)).where(Coa.coa_no.like(f"{prefix}%"))) or 0
    return f"{prefix}{count + 1:04d}"


def create_coa(db: Session, payload) -> Coa:
    if payload.lot_id is not None:
        lot = db.get(StockLot, payload.lot_id)
        if not lot:
            raise BizError(404, "库存批次不存在")
        # 已放行的批次：不允许再建检验单（放行后批次锁死，如需复检先冻结/隔离）
        passed = db.scalar(
            select(Coa.id).where(Coa.lot_id == payload.lot_id, Coa.result == "pass").limit(1)
        )
        if passed:
            raise BizError(409, f"批次 {lot.lot_no} 已放行，锁死；如需复检请先冻结/隔离")

    coa = Coa(
        coa_no=payload.coa_no or next_coa_no(db),
        lot_id=payload.lot_id,
        material_id=payload.material_id,
        batch_id=payload.batch_id,
        direction=payload.direction,
        sample_at=payload.sample_at,
        tested_at=payload.tested_at,
        tester_id=payload.tester_id,
        result="pending",
        items=payload.items,
        note=payload.note,
    )
    db.add(coa)
    db.commit()
    db.refresh(coa)
    return coa


def decide_coa(db: Session, coa_id: int, payload) -> dict:
    """判定检验单：pass/fail 锁死并联动库存批状态；hold 隔离可再判。"""
    decision = (payload.result or "").lower()
    if decision not in VALID_DECISIONS:
        raise BizError(400, f"非法判定 {payload.result}，仅支持 {sorted(VALID_DECISIONS)}")

    coa = db.get(Coa, coa_id, with_for_update=True)
    if not coa:
        raise BizError(404, "检验单不存在")
    if coa.locked:
        raise BizError(409, f"检验单 {coa.coa_no} 已判定锁死，不可修改")

    lot = None
    if coa.lot_id is not None:
        lot = db.get(StockLot, coa.lot_id, with_for_update=True)
        if not lot:
            raise BizError(404, "库存批次不存在")
        if lot.status == "consumed":
            raise BizError(409, f"批次 {lot.lot_no} 已核销，不可再判定")
        if decision == "pass":
            other = db.scalar(
                select(Coa.id).where(Coa.lot_id == coa.lot_id, Coa.result == "pass", Coa.id != coa.id).limit(1)
            )
            if other:
                raise BizError(409, f"批次 {lot.lot_no} 已由其它检验单放行，锁死")

    coa.result = decision
    coa.released_by = payload.released_by
    coa.released_at = datetime.now()
    if payload.note:
        coa.note = payload.note

    if decision == "pass":
        coa.locked = True
        if lot is not None:
            lot.status = "released"
    elif decision == "fail":
        coa.locked = True
        if lot is not None:
            lot.status = "rejected"
    else:  # hold
        if lot is not None:
            lot.status = "quarantined"

    db.commit()
    db.refresh(coa)
    return {
        "coa_id": coa.id,
        "coa_no": coa.coa_no,
        "result": coa.result,
        "locked": coa.locked,
        "lot_id": coa.lot_id,
        "lot_status": lot.status if lot is not None else None,
    }


def alerts(db: Session) -> dict:
    """合规异常看板：CCP 偏差 / 温度越限 / CIP 不合格 / CoA 不合格。"""
    ccp_dev = db.scalars(
        select(CcpRecord).where(CcpRecord.status == "deviation").order_by(CcpRecord.id.desc()).limit(100)
    ).all()
    temp_bad = db.scalars(
        select(TempLog).where(TempLog.in_range.is_(False)).order_by(TempLog.id.desc()).limit(100)
    ).all()
    cip_bad = db.scalars(select(CipLog).where(CipLog.result == "fail").order_by(CipLog.id.desc()).limit(100)).all()
    coa_bad = db.scalars(select(Coa).where(Coa.result == "fail").order_by(Coa.id.desc()).limit(100)).all()

    ccp_deviations = [
        {
            "id": r.id,
            "ccp_id": r.ccp_id,
            "batch_id": r.batch_id,
            "measured_value": str(r.measured_value),
            "measured_at": r.measured_at,
            "note": r.deviation_note,
        }
        for r in ccp_dev
    ]
    temp_out_of_range = [
        {
            "id": r.id,
            "ccp_id": r.ccp_id,
            "batch_id": r.batch_id,
            "stage": r.stage,
            "temp_c": str(r.temp_c),
            "recorded_at": r.recorded_at,
        }
        for r in temp_bad
    ]
    cip_failed = [
        {"id": r.id, "station": r.station, "start_at": r.start_at, "ph": str(r.final_rinse_ph), "conductivity": str(r.rinse_conductivity)}
        for r in cip_bad
    ]
    coa_failed = [
        {"id": r.id, "coa_no": r.coa_no, "lot_id": r.lot_id, "material_id": r.material_id, "released_at": r.released_at}
        for r in coa_bad
    ]
    return {
        "ccp_deviations": ccp_deviations,
        "temp_out_of_range": temp_out_of_range,
        "cip_failed": cip_failed,
        "coa_failed": coa_failed,
        "total": len(ccp_deviations) + len(temp_out_of_range) + len(cip_failed) + len(coa_failed),
    }