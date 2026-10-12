# Copyright (C) 2026 CenkorProcess Project
# SPDX-License-Identifier: AGPL-3.0
"""经营驾驶舱与数据大屏扩展（dashboard_report）后端路由。

商业纪律：
- 只建 ``ext_dsh_target`` 存 KPI 目标/警戒阈值；对核心表一律**只读**实时聚合，不建外键、不加列、不改数据。
- 跨生产/质量/物料/库存/CIP 五域把核心 KPI 聚合成一屏，配大屏快照与风险告警。
- 纯只读 + 阈值配置，无后台线程。

约定：扩展暴露 ``router``；宿主挂到 ``/api/extensions/dashboard_report``。GET 需 view，写阈值需 manage。
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import get_current_user, require_any_permissions, require_write_permission
from app.core.errors import BizError
from app.core.response import ok
from app.models.user import User

logger = logging.getLogger("dashboard_report")

router = APIRouter()

VIEW = require_any_permissions(["ext.dashboard_report.view", "ext.dashboard_report.manage"])
MANAGE = require_write_permission("ext.dashboard_report.manage")


def _jsonify(v):
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


def _rows(db: Session, sql: str, **params) -> list[dict]:
    return [{k: _jsonify(v) for k, v in dict(r).items()} for r in db.execute(text(sql), params).mappings().all()]


def _scalar(db: Session, sql: str, **params):
    return db.execute(text(sql), params).scalar()


# ---------- 指标登记：key -> {label, domain, unit, better, fmt, sql} ----------
# SQL 统一用 :cut（窗口起点 datetime）；库存类为快照，忽略窗口。value 为单值。

METRICS: dict[str, dict] = {
    "batch_completed":  {"label": "完成批次", "domain": "生产", "unit": "批", "better": "up", "fmt": "int",
                         "sql": "SELECT COUNT(*) FROM batches WHERE is_deleted=0 AND status IN('completed','closed') AND completed_at>=:cut"},
    "output_qty":       {"label": "产出量", "domain": "生产", "unit": "", "better": "up", "fmt": "num",
                         "sql": "SELECT COALESCE(SUM(produced_qty),0) FROM batches WHERE is_deleted=0 AND status IN('completed','closed') AND completed_at>=:cut"},
    "avg_yield":        {"label": "平均收率", "domain": "生产", "unit": "%", "better": "up", "fmt": "pct",
                         "sql": "SELECT ROUND(AVG(yield_pct),2) FROM batches WHERE is_deleted=0 AND yield_pct IS NOT NULL AND completed_at>=:cut"},
    "ccp_pass_rate":    {"label": "CCP 合格率", "domain": "质量", "unit": "%", "better": "up", "fmt": "pct",
                         "sql": "SELECT CASE WHEN COUNT(*)=0 THEN NULL ELSE ROUND(SUM(status='pass')/COUNT(*)*100,2) END FROM ccp_records WHERE measured_at>=:cut"},
    "ccp_deviation":    {"label": "CCP 偏差数", "domain": "质量", "unit": "条", "better": "down", "fmt": "int",
                         "sql": "SELECT COUNT(*) FROM ccp_records WHERE status='deviation' AND measured_at>=:cut"},
    "coa_pass_rate":    {"label": "CoA 合格率", "domain": "质量", "unit": "%", "better": "up", "fmt": "pct",
                         "sql": "SELECT CASE WHEN SUM(result IN('pass','fail'))=0 THEN NULL ELSE ROUND(SUM(result='pass')/SUM(result IN('pass','fail'))*100,2) END FROM coa WHERE is_deleted=0 AND tested_at>=:cut"},
    "coa_fail":         {"label": "检验不合格", "domain": "质量", "unit": "单", "better": "down", "fmt": "int",
                         "sql": "SELECT COUNT(*) FROM coa WHERE is_deleted=0 AND result='fail' AND tested_at>=:cut"},
    "dispense_dev_rate": {"label": "投料超差率", "domain": "物料", "unit": "%", "better": "down", "fmt": "pct",
                          "sql": "SELECT CASE WHEN COUNT(*)=0 THEN NULL ELSE ROUND(SUM(deviated=1)/COUNT(*)*100,2) END FROM dispense_records WHERE created_at>=:cut"},
    "cip_fail":         {"label": "CIP 清洗失败", "domain": "清洗", "unit": "次", "better": "down", "fmt": "int",
                         "sql": "SELECT COUNT(*) FROM cip_logs WHERE is_deleted=0 AND result='fail' AND start_at>=:cut"},
    "expiring_lots":    {"label": "临期批次(30天)", "domain": "库存", "unit": "批", "better": "down", "fmt": "int",
                         "sql": "SELECT COUNT(*) FROM stock_lots WHERE is_deleted=0 AND status NOT IN('consumed') AND qty>0 AND expiry_at IS NOT NULL AND expiry_at>=NOW() AND expiry_at<=DATE_ADD(NOW(),INTERVAL 30 DAY)"},
    "expired_lots":     {"label": "已过期批次", "domain": "库存", "unit": "批", "better": "down", "fmt": "int",
                         "sql": "SELECT COUNT(*) FROM stock_lots WHERE is_deleted=0 AND status NOT IN('consumed') AND qty>0 AND expiry_at IS NOT NULL AND expiry_at<NOW()"},
    "quarantine_qty":   {"label": "隔离量", "domain": "库存", "unit": "", "better": "down", "fmt": "num",
                         "sql": "SELECT COALESCE(SUM(qty),0) FROM stock_lots WHERE is_deleted=0 AND status='quarantined'"},
}


def _status(value, target, warn, better):
    """返回 good/warn/bad/neutral + 达成率（目标存在时）。"""
    if value is None:
        return "neutral", None
    v = float(value)
    reached = None
    if target is not None:
        t = float(target)
        reached = round((v / t * 100) if t else (100.0 if v == 0 else 0.0), 1)
    if better == "up":
        if target is not None and v >= float(target):
            return "good", reached
        if warn is not None and v <= float(warn):
            return "bad", reached
        return ("warn" if target is not None else "neutral"), reached
    else:  # down：越小越好
        if target is not None and v <= float(target):
            return "good", reached
        if warn is not None and v >= float(warn):
            return "bad", reached
        return ("warn" if target is not None else "neutral"), reached


# ---------- 驾驶舱 KPI 快照 ----------

@router.get("/cockpit", dependencies=[Depends(VIEW)])
def cockpit(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    from datetime import timedelta
    cut = datetime.now() - timedelta(days=days)
    targets = {r["metric_key"]: r for r in _rows(db, "SELECT metric_key,name,better,target_value,warn_value FROM ext_dsh_target WHERE is_deleted=0")}
    out = []
    for key, m in METRICS.items():
        val = _scalar(db, m["sql"], cut=cut)
        t = targets.get(key)
        better = (t or {}).get("better") or m["better"]
        status, reached = _status(val, (t or {}).get("target_value"), (t or {}).get("warn_value"), better)
        out.append({
            "key": key, "label": (t or {}).get("name") or m["label"], "domain": m["domain"],
            "unit": m["unit"], "fmt": m["fmt"], "better": better,
            "value": _jsonify(val), "target": _jsonify((t or {}).get("target_value")), "warn": _jsonify((t or {}).get("warn_value")),
            "status": status, "reached_pct": reached,
        })
    domains = {}
    for it in out:
        domains.setdefault(it["domain"], []).append(it["key"])
    return ok({"days": days, "generated_at": datetime.now().isoformat(timespec="seconds"),
               "domains": domains, "metrics": out})


# ---------- 日趋势 ----------

@router.get("/trend", dependencies=[Depends(VIEW)])
def trend(days: int = Query(30, ge=1, le=180), db: Session = Depends(get_db)):
    from datetime import timedelta
    cut = datetime.now() - timedelta(days=days)
    rows = _rows(db, """
        SELECT DATE(completed_at) d, COUNT(*) batch_cnt, COALESCE(SUM(produced_qty),0) output_qty,
               ROUND(AVG(yield_pct),2) avg_yield
        FROM batches WHERE is_deleted=0 AND status IN('completed','closed') AND completed_at>=:cut
        GROUP BY DATE(completed_at) ORDER BY d""", cut=cut)
    dev = _rows(db, """
        SELECT DATE(measured_at) d, COUNT(*) total, SUM(status='deviation') ccp_dev
        FROM ccp_records WHERE measured_at>=:cut GROUP BY DATE(measured_at) ORDER BY d""", cut=cut)
    devmap = {r["d"]: r for r in dev}
    for r in rows:
        dd = devmap.get(r["d"])
        r["ccp_total"] = (dd or {}).get("total", 0)
        r["ccp_dev"] = (dd or {}).get("ccp_dev", 0)
    return ok({"days": days, "series": rows})


# ---------- 风险告警清单（大屏滚动） ----------

@router.get("/alerts", dependencies=[Depends(VIEW)])
def alerts(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    items = []
    for r in _rows(db, """
        SELECT l.id, l.lot_no, m.name material_name, l.qty, l.expiry_at
        FROM stock_lots l JOIN materials m ON m.id=l.material_id
        WHERE l.is_deleted=0 AND l.status NOT IN('consumed') AND l.qty>0 AND l.expiry_at IS NOT NULL AND l.expiry_at<NOW()
        ORDER BY l.expiry_at LIMIT :lim""", lim=limit):
        items.append({"type": "过期批次", "level": "danger", "text": f"{r['material_name']} 批次 {r['lot_no']} 已过期（效期 {str(r['expiry_at'])[:10]}）", "at": r["expiry_at"]})
    for r in _rows(db, """
        SELECT l.id, l.lot_no, m.name material_name, l.expiry_at, DATEDIFF(l.expiry_at, NOW()) days_left
        FROM stock_lots l JOIN materials m ON m.id=l.material_id
        WHERE l.is_deleted=0 AND l.status NOT IN('consumed') AND l.qty>0 AND l.expiry_at IS NOT NULL AND l.expiry_at>=NOW() AND l.expiry_at<=DATE_ADD(NOW(),INTERVAL 30 DAY)
        ORDER BY l.expiry_at LIMIT :lim""", lim=limit):
        items.append({"type": "临期批次", "level": "warn", "text": f"{r['material_name']} 批次 {r['lot_no']} {r['days_left']} 天后到期", "at": r["expiry_at"]})
    for r in _rows(db, """
        SELECT cp.code, cp.name, cr.measured_value, cr.measured_at, cr.deviation_note
        FROM ccp_records cr JOIN ccps cp ON cp.id=cr.ccp_id WHERE cr.status='deviation'
        ORDER BY cr.measured_at DESC LIMIT :lim""", lim=limit):
        items.append({"type": "CCP 偏差", "level": "danger", "text": f"{cp_name(r)} 实测 {r['measured_value']}" + (f"｜{r['deviation_note']}" if r.get("deviation_note") else ""), "at": r["measured_at"]})
    for r in _rows(db, """
        SELECT c.coa_no, c.result, m.name material_name, c.tested_at
        FROM coa c JOIN materials m ON m.id=c.material_id WHERE c.is_deleted=0 AND c.result IN('fail','hold')
        ORDER BY c.tested_at DESC LIMIT :lim""", lim=limit):
        items.append({"type": "检验" + ("不合格" if r["result"] == "fail" else "暂扣"), "level": "danger" if r["result"] == "fail" else "warn",
                      "text": f"{r['material_name']} 单号 {r['coa_no']}", "at": r["tested_at"]})
    for r in _rows(db, """
        SELECT m.name material_name, d.actual_qty, d.planned_qty, d.created_at
        FROM dispense_records d JOIN materials m ON m.id=d.material_id WHERE d.deviated=1
        ORDER BY d.created_at DESC LIMIT :lim""", lim=limit):
        items.append({"type": "投料超差", "level": "warn", "text": f"{r['material_name']} 应投 {r['planned_qty']} / 实投 {r['actual_qty']}", "at": r["created_at"]})
    items = [i for i in items if i["at"] is not None]
    items.sort(key=lambda x: str(x["at"]), reverse=True)
    return ok(items[:limit])


def cp_name(r) -> str:
    return f"{r.get('code') or ''} {r.get('name') or ''}".strip() or "CCP"


# ---------- 大屏聚合快照（一次返回 cockpit + trend + alerts，减少往返） ----------

@router.get("/screen", dependencies=[Depends(VIEW)])
def screen(days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    return ok({"cockpit": cockpit(days=days, db=db)["data"],
               "trend": trend(days=min(days, 90), db=db)["data"],
               "alerts": alerts(limit=30, db=db)["data"]})


# ---------- KPI 目标/阈值配置 ----------

@router.get("/targets", dependencies=[Depends(VIEW)])
def list_targets(db: Session = Depends(get_db)):
    rows = _rows(db, "SELECT id,metric_key,name,better,target_value,warn_value,note FROM ext_dsh_target WHERE is_deleted=0 ORDER BY metric_key")
    builtin = [{"key": k, "label": v["label"], "domain": v["domain"], "unit": v["unit"], "better": v["better"]} for k, v in METRICS.items()]
    return ok({"configured": rows, "metrics": builtin})


@router.post("/targets", dependencies=[Depends(MANAGE)])
def upsert_target(payload: dict = Body(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    key = (payload.get("metric_key") or "").strip()
    if key not in METRICS:
        raise BizError(400, f"未知指标键：{key}")
    better = payload.get("better") or METRICS[key]["better"]
    if better not in ("up", "down"):
        better = METRICS[key]["better"]
    name = (payload.get("name") or "").strip()[:64] or None
    note = (payload.get("note") or "").strip()[:255] or None
    tv = _num_or_none(payload.get("target_value"))
    wv = _num_or_none(payload.get("warn_value"))
    exists = _scalar(db, "SELECT id FROM ext_dsh_target WHERE metric_key=:k", k=key)
    if exists:
        db.execute(text("UPDATE ext_dsh_target SET name=:n,better=:b,target_value=:t,warn_value=:w,note=:o,updated_by=:u,is_deleted=0 WHERE metric_key=:k"),
                   {"n": name, "b": better, "t": tv, "w": wv, "o": note, "u": user.id, "k": key})
    else:
        db.execute(text("INSERT INTO ext_dsh_target (metric_key,name,better,target_value,warn_value,note,updated_by) VALUES(:k,:n,:b,:t,:w,:o,:u)"),
                   {"k": key, "n": name, "b": better, "t": tv, "w": wv, "o": note, "u": user.id})
    db.commit()
    return ok({"metric_key": key, "saved": True})


@router.delete("/targets/{metric_key}", dependencies=[Depends(MANAGE)])
def delete_target(metric_key: str, db: Session = Depends(get_db)):
    n = db.execute(text("UPDATE ext_dsh_target SET is_deleted=1 WHERE metric_key=:k"), {"k": metric_key}).rowcount
    db.commit()
    return ok({"metric_key": metric_key, "deleted": n})


def _num_or_none(v):
    if v is None or v == "":
        return None
    try:
        return Decimal(str(v))
    except Exception:
        raise BizError(400, f"非法数值：{v}")
